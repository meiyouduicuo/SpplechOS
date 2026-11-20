"""Deliver an already signed package over USB and await the phone's import receipt.

Only unique inbox files are written. This module never signs code or accesses keys.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import struct
import time
import uuid
from pathlib import Path

from .game_package import MAGIC, MAX_HEADER, MAX_BYTES, CHUNK
from .hot_install import HotInstallError

INBOX = '/Documents/.usb-game-import'


def package_identity(path: Path) -> dict:
    with path.open('rb') as source:
        prefix = source.read(16)
        if len(prefix) != 16 or prefix[:8] != MAGIC:
            raise HotInstallError('usb.invalidPackage')
        size = struct.unpack('<Q', prefix[8:])[0]
        if not 0 < size <= MAX_HEADER:
            raise HotInstallError('usb.invalidPackage')
        header = source.read(size)
    try:
        manifest = json.loads(header)
        files = manifest['files']
        if manifest['schema'] != 1 or not isinstance(files, list) or len(files) > 200_000:
            raise ValueError()
        sizes = [item['size'] for item in files]
        if any(type(n) is not int or n < 0 for n in sizes):
            raise ValueError()
        total = sum(sizes)
        if total > MAX_BYTES or 16 + size + total != path.stat().st_size:
            raise ValueError()
        if not all(isinstance(manifest.get(key), str) and manifest[key]
                   for key in ('bundleID', 'teamID', 'titleID')):
            raise ValueError()
    except (ValueError, KeyError, TypeError) as exc:
        raise HotInstallError('usb.invalidPackage') from exc
    return manifest


async def send_package(service, path: Path, manifest: dict, report, *, timeout=300) -> str:
    """AFC seam, independently tested without a phone or signing credentials."""
    snapshot = path.stat()
    info = await service.get_device_info()
    if int(info.get('FSFreeBytes', 0)) < snapshot.st_size * 2 + 256 * 1024**2:
        raise HotInstallError('usb.space')
    request_id = str(uuid.uuid4())
    base = INBOX + '/' + request_id
    partial, package = base + '.part', base + '.sppgame'
    await service.makedirs(INBOX)
    report('usb.upload', 0)
    digest = hashlib.sha1()
    handle = await service.fopen(partial, 'w')
    try:
        done = 0
        with path.open('rb') as source:
            while chunk := source.read(CHUNK):
                await service.fwrite(handle, chunk)
                digest.update(chunk)
                done += len(chunk)
                report('usb.upload', int(done * 100 / snapshot.st_size))
    finally:
        await service.fclose(handle)
    current = path.stat()
    if current.st_size != snapshot.st_size or current.st_mtime_ns != snapshot.st_mtime_ns:
        raise HotInstallError('usb.changed')
    report('usb.verify', 0)
    if int((await service.stat(partial))['st_size']) != snapshot.st_size:
        raise HotInstallError('usb.verifyFailed')
    if await service.get_file_hash(partial) != digest.digest():
        raise HotInstallError('usb.verifyFailed')
    await service.rename(partial, package)
    request = json.dumps({'schema': 1, 'id': request_id, 'file': request_id + '.sppgame'}).encode()
    await service.set_file_contents(base + '.request.part', request)
    await service.rename(base + '.request.part', base + '.request.json')
    report('usb.wait', 0)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_path = base + '.status.json'
        if await service.exists(status_path):
            status = json.loads(await service.get_file_contents(status_path))
            if status.get('schema') != 1 or status.get('id') != request_id:
                raise HotInstallError('usb.invalidReceipt')
            if status.get('state') == 'complete':
                if status.get('titleID') != manifest['titleID']:
                    raise HotInstallError('usb.invalidReceipt')
                await service.rm(status_path)
                report('usb.complete', 100)
                return manifest['titleID']
            if status.get('state') == 'failed':
                raise HotInstallError(str(status.get('message') or 'usb.importFailed'))
            report('usb.import', int(max(0, min(1, status.get('progress', 0))) * 100))
        await asyncio.sleep(1)
    raise HotInstallError('usb.waitTimeout')


async def import_package(path: Path, report=lambda stage, percent: None) -> str:
    manifest = package_identity(path)
    from pymobiledevice3.usbmux import list_devices
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService
    from .device_probe import probe_shell

    devices = [d for d in await list_devices() if d.connection_type == 'USB']
    if len(devices) != 1:
        raise HotInstallError('usb.oneDevice')
    report('usb.check', 0)
    device = await create_using_usbmux(serial=devices[0].serial, connection_type='USB')
    try:
        host = await probe_shell(device)
        if (manifest['bundleID'], manifest['teamID']) != (host.identity.bundle_id, host.identity.team_id):
            raise HotInstallError('usb.identity')
        async with await HouseArrestService.create(device, host.bundle_id, documents_only=True) as service:
            beacon = json.loads(await service.get_file_contents('/Documents/.shell-host.json'))
            if beacon.get('usbPackageImport') != 1:
                raise HotInstallError('usb.updateApp')
            return await send_package(service, path, manifest, report)
    finally:
        await device.close()
