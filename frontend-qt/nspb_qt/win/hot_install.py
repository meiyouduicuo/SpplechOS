"""Preflight for delivering game frameworks to a compatible installed shell.

This module deliberately does not sign or write to a device. Those operations require
the exact signing identity used by the installed app and a tested AFC transport.
"""
from __future__ import annotations

import json
import importlib.util
import os
import re
import stat
import struct
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


class HotInstallError(ValueError):
    """The device or framework is not ready for an incremental installation."""


@dataclass(frozen=True)
class HostIdentity:
    bundle_id: str
    team_id: str
    chain: str
    expires_at: int | None


def check_host(data: bytes, *, expected_bundle_id: str, expected_team_id: str,
               now: int | None = None) -> HostIdentity:
    """Validate the installed shell's beacon, matching the macOS hot-install gate."""
    try:
        beacon = json.loads(data)
        if not isinstance(beacon, dict):
            raise ValueError('not an object')
        if beacon.get('schema') != 1 or beacon.get('glueVersion') != 1:
            raise HotInstallError('Unsupported shell protocol; install a compatible shell first')
        bundle = beacon.get('bundleID')
        team = beacon.get('teamID')
        if not expected_bundle_id or bundle != expected_bundle_id:
            raise HotInstallError('Installed app identifier does not match')
        if not expected_team_id or team != expected_team_id:
            raise HotInstallError('Signing team does not match the installed app')
        expiry = beacon.get('expiresAtEpoch')
        if expiry is not None:
            if isinstance(expiry, bool) or not isinstance(expiry, int):
                raise ValueError('invalid expiry')
            if expiry - (int(time.time()) if now is None else now) < 86400:
                raise HotInstallError('Installed app signature expires in less than 24 hours')
        chain = beacon.get('chain', '')
        if not isinstance(chain, str):
            raise ValueError('invalid chain')
        return HostIdentity(bundle, team, chain, expiry)
    except HotInstallError:
        raise
    except (ValueError, TypeError, UnicodeDecodeError) as exc:
        raise HotInstallError('Installed app has no valid hot-install beacon') from exc


def inspect_framework(path: Path, title_id: str) -> dict:
    """Validate a self-contained game framework before requesting a signature."""
    title_id = title_id.upper()
    if not re.fullmatch(r'[0-9A-F]{16}', title_id):
        raise HotInstallError('Invalid game identifier')
    path = Path(path)
    if path.name != f'DmGame{title_id}.framework' or not path.is_dir():
        raise HotInstallError('Game framework name or path does not match')
    try:
        manifest = json.loads((path / 'game.manifest.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('loader') != 'FH':
            raise HotInstallError('Game framework does not contain its own host')
        if str(manifest.get('title_id', '')).upper() != title_id:
            raise HotInstallError('Framework belongs to a different game')
        executable = manifest.get('framework_executable', f'DmGame{title_id}')
        if not isinstance(executable, str) or Path(executable).name != executable:
            raise HotInstallError('Invalid framework executable name')
        binary = path / executable
        if not binary.is_file() or binary.stat().st_size == 0:
            raise HotInstallError('Game framework executable is missing')
        return manifest
    except HotInstallError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise HotInstallError('Cannot read game framework manifest') from exc


def ready_payload(path: Path, title_id: str) -> bytes:
    """Create the shell's transfer-complete marker without modifying the framework.

    This only checks the transfer footprint. It does not verify the code signature
    and must not be used as authorization to send or load a framework.
    """
    inspect_framework(path, title_id)
    total = count = 0
    try:
        for directory, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [name for name in dirs if name != '.DS_Store' and not name.startswith('._')]
            for name in dirs + files:
                if name == '.DS_Store' or name.startswith('._'):
                    continue
                item = Path(directory) / name
                info = item.lstat()
                if stat.S_ISDIR(info.st_mode):
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise HotInstallError('Framework contains a link or unsupported file')
                count += 1
                total += info.st_size
        return json.dumps({'schema': 1, 'titleID': title_id.upper(),
                           'files': count, 'bytes': total}, separators=(',', ':')).encode('utf-8')
    except OSError as exc:
        raise HotInstallError('Cannot inspect game framework files') from exc


async def upload_signed_framework(afc, path: Path, title_id: str, progress=None) -> str:
    """Stage a *previously signed and verified* framework; publish the marker last.

    The caller must independently verify the signing identity against the installed
    host. The marker checks transfer completeness, not code-signing authenticity.
    An interrupted transfer stays in its unique staging folder and is never promoted.
    """
    path = Path(path)
    marker = ready_payload(path, title_id)
    expected = json.loads(marker)
    root = '/Documents/Frameworks'
    stage = f'{root}/.staging-{title_id.upper()}-{uuid.uuid4().hex}'
    await afc.makedirs(root)
    await afc.makedirs(stage)
    done = 0
    for item in sorted(path.rglob('*')):
        rel = item.relative_to(path)
        if any(part == '.DS_Store' or part.startswith('._') for part in rel.parts):
            continue
        if item.is_symlink():
            raise HotInstallError('Framework contains a link')
        remote = f'{stage}/{path.name}/{rel.as_posix()}'
        if item.is_dir():
            await afc.makedirs(remote)
        elif item.is_file():
            await afc.makedirs(remote.rsplit('/', 1)[0])
            handle = await afc.fopen(remote, 'w')
            try:
                with item.open('rb') as source:
                    while chunk := source.read(1024 * 1024):
                        await afc.fwrite(handle, chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, expected['bytes'])
            finally:
                await afc.fclose(handle)
            info = await afc.stat(remote)
            if int(info['st_size']) != item.stat().st_size:
                raise HotInstallError('Device copy has an incorrect file size')
        else:
            raise HotInstallError('Framework contains an unsupported file')
    if done != expected['bytes'] or ready_payload(path, title_id) != marker:
        raise HotInstallError('Framework changed during transfer')
    await afc.set_file_contents(stage + '/.ready', marker)
    return stage


async def upload_romfs(afc, image: Path, title_id: str, expected_identity: str, progress=None,
                       *, romfs_tool: Path | None = None, expected_chain: str = '', stage_progress=None,
                       shader_image: Path | None = None) -> str:
    """Copy verified data into an unused game directory without overwriting saves."""
    from ..refresh_flow import matches_romfs_identity

    title_id = title_id.upper()
    if not re.fullmatch(r'[0-9A-F]{16}', title_id):
        raise HotInstallError('Invalid game identifier')
    image = Path(image)
    if not expected_identity or not matches_romfs_identity(image, expected_identity):
        raise HotInstallError('Game data does not match the built framework')
    with image.open('rb') as source:
        header = source.read(32)
    if len(header) != 32:
        raise HotInstallError('Game image header is incomplete')
    magic, index_offset, index_size, _ = struct.unpack('<8sQQQ', header)
    full_size = image.stat().st_size
    size = index_offset + index_size
    if magic != b'DMROMFS1' or size > full_size or size < 32:
        raise HotInstallError('Game image is invalid')
    trailer = full_size != size
    info = await afc.get_device_info()
    if int(info.get('FSFreeBytes', 0)) < size + 256 * 1024 * 1024:
        raise HotInstallError('Not enough free space for game data')
    await afc.makedirs('/Documents/games')
    folder = '/Documents/games/' + title_id
    await afc.makedirs(folder)
    if any(name.lower() == 'romfs.img' for name in await afc.listdir(folder)):
        raise HotInstallError('Game data already exists; refusing to overwrite it')
    if trailer:
        if not romfs_tool or not Path(romfs_tool).is_file():
            raise HotInstallError('Shader extraction tool is unavailable')
        try:
            spec = importlib.util.spec_from_file_location('_spple_romfs_image', romfs_tool)
            if spec is None or spec.loader is None:
                raise ValueError('No loader')
            tool = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tool)
            details = tool.inspect_msl(str(image))
            if not details.get('has_trailer') or (expected_chain and details.get('chain') != expected_chain):
                raise HotInstallError('Shader data does not match the game framework')
            if 'msl' in await afc.listdir(folder):
                raise HotInstallError('Shader data already exists; refusing to overwrite it')
            with tempfile.TemporaryDirectory(prefix='spple-shaders-') as temp:
                if stage_progress:
                    stage_progress('extract', 0, 0)
                root = Path(temp)
                stage = folder + '/.msl-' + uuid.uuid4().hex
                await afc.makedirs(stage)
                packed = Path(shader_image) if shader_image else None
                if (packed and packed.is_file() and details.get('gfx_api') == 'nvn'
                        and not details.get('multi_program') and expected_chain
                        and re.fullmatch(r'b-[A-Za-z0-9._-]+', expected_chain)
                        and _same_shader_image(tool, image, details, packed)):
                    remote = stage + '/' + expected_chain + '.img'
                    initial = packed.stat()
                    total = initial.st_size
                    done = 0
                    handle = await afc.fopen(remote, 'w')
                    try:
                        with packed.open('rb') as source:
                            while chunk := source.read(4 * 1024 * 1024):
                                await afc.fwrite(handle, chunk)
                                done += len(chunk)
                                if stage_progress:
                                    stage_progress('shader', done, total)
                    finally:
                        await afc.fclose(handle)
                    final = packed.stat()
                    if (done != total or final.st_size != total or final.st_mtime_ns != initial.st_mtime_ns
                            or int((await afc.stat(remote))['st_size']) != total):
                        raise HotInstallError('Shader copy is incomplete')
                    items = []
                else:
                    tool.extract_msl(str(image), temp)
                    items = sorted(root.rglob('*'))
                total_files = sum(1 for item in items if item.is_file())
                copied_files = 0
                for item in items:
                    if item.is_symlink():
                        raise HotInstallError('Shader data contains a link')
                    remote = stage + '/' + item.relative_to(root).as_posix()
                    if item.is_dir():
                        await afc.makedirs(remote)
                    elif item.is_file():
                        await afc.makedirs(remote.rsplit('/', 1)[0])
                        await afc.set_file_contents(remote, item.read_bytes())
                        if int((await afc.stat(remote))['st_size']) != item.stat().st_size:
                            raise HotInstallError('Shader copy is incomplete')
                        copied_files += 1
                        if stage_progress:
                            stage_progress('shader', copied_files, total_files)
                if 'msl' in await afc.listdir(folder):
                    raise HotInstallError('Shader data appeared during transfer')
                await afc.rename(stage, folder + '/msl')
        except HotInstallError:
            raise
        except (OSError, ValueError, AttributeError) as exc:
            raise HotInstallError('Cannot safely extract shader data') from exc
    partial = folder + '/.romfs-' + uuid.uuid4().hex + '.part'
    handle = await afc.fopen(partial, 'w')
    done = 0
    try:
        with image.open('rb') as source:
            while done < size and (chunk := source.read(min(4 * 1024 * 1024, size - done))):
                await afc.fwrite(handle, chunk)
                done += len(chunk)
                if progress:
                    progress(done, size)
    finally:
        await afc.fclose(handle)
    if done != size or int((await afc.stat(partial))['st_size']) != size:
        raise HotInstallError('Device game data copy is incomplete')
    if not matches_romfs_identity(image, expected_identity):
        raise HotInstallError('Game data changed during transfer')
    if any(name.lower() == 'romfs.img' for name in await afc.listdir(folder)):
        raise HotInstallError('Game data appeared during transfer; refusing to overwrite it')
    target = folder + '/romfs.img'
    await afc.rename(partial, target)
    return target


def _same_shader_image(tool, image: Path, details: dict, packed: Path) -> bool:
    """Verify a cached shader image is byte-for-byte equivalent to the trailer files."""
    try:
        offset = details['msl_offset']
        with image.open('rb') as trailer, packed.open('rb') as cache:
            embedded = tool._validate_and_list_slice(trailer, offset, details['msl_size'], str(image))
            cached = tool._validate_and_list_slice(cache, 0, packed.stat().st_size, str(packed))
            prefix = details['chain'] + '/'
            files = {name[len(prefix):]: (entry[1], entry[2]) for name, entry in embedded.items()
                     if not entry[0] and name.startswith(prefix)}
            other = {name: (entry[1], entry[2]) for name, entry in cached.items()
                     if not entry[0] and tool._keep_msl_file(name)}
            if not files or files != other or len(files) != sum(not e[0] for e in embedded.values()):
                return False
            trailer.seek(offset); th = trailer.read(32)
            cache.seek(0); ch = cache.read(32)
            _, ti, _, _ = struct.unpack('<8sQQQ', th)
            _, ci, _, _ = struct.unpack('<8sQQQ', ch)
            if ti != ci or ti < 32:
                return False
            trailer.seek(offset + 32); cache.seek(32)
            left = ti - 32
            while left:
                n = min(left, 4 * 1024 * 1024)
                a, b = trailer.read(n), cache.read(n)
                if len(a) != n or a != b:
                    return False
                left -= n
            return True
    except (OSError, ValueError, KeyError, TypeError, AttributeError, struct.error):
        return False


async def upload_aoc(afc, folder: Path, title_id: str, progress=None) -> str | None:
    """Stage add-on data separately without replacing existing phone data."""
    folder = Path(folder)
    if not folder.exists():
        return None
    if folder.is_symlink() or not folder.is_dir():
        raise HotInstallError('Invalid DLC directory')
    if not re.fullmatch(r'[0-9A-F]{16}', title_id.upper()):
        raise HotInstallError('Invalid game identifier')
    items = sorted(folder.rglob('*'))
    if any(item.is_symlink() or not (item.is_file() or item.is_dir()) for item in items):
        raise HotInstallError('DLC contains a link or unsupported file')
    files = [item for item in items if item.is_file()]
    if not files:
        return None
    parent = '/Documents/games/' + title_id.upper()
    if 'aoc' in await afc.listdir(parent):
        raise HotInstallError('DLC already exists; refusing to overwrite it')
    size = sum(item.stat().st_size for item in files)
    if int((await afc.get_device_info()).get('FSFreeBytes', 0)) < size + 256 * 1024 * 1024:
        raise HotInstallError('Not enough free space for DLC data')
    stage = parent + '/.aoc-' + uuid.uuid4().hex
    await afc.makedirs(stage)
    done = 0
    for item in items:
        remote = stage + '/' + item.relative_to(folder).as_posix()
        if item.is_dir():
            await afc.makedirs(remote)
            continue
        initial = item.stat()
        await afc.makedirs(remote.rsplit('/', 1)[0])
        handle = await afc.fopen(remote, 'w')
        try:
            with item.open('rb') as source:
                while chunk := source.read(4 * 1024 * 1024):
                    await afc.fwrite(handle, chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, size)
        finally:
            await afc.fclose(handle)
        final = item.stat()
        if (final.st_size != initial.st_size or final.st_mtime_ns != initial.st_mtime_ns
                or int((await afc.stat(remote))['st_size']) != initial.st_size):
            raise HotInstallError('DLC changed or its transfer is incomplete')
    if 'aoc' in await afc.listdir(parent):
        raise HotInstallError('DLC appeared during transfer; refusing to overwrite it')
    target = parent + '/aoc'
    await afc.rename(stage, target)
    return target
