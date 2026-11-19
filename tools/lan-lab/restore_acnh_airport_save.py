"""Restore a verified Animal Crossing snapshot into the airport test app."""
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
from uuid import uuid4
import zipfile

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.house_arrest import HouseArrestService
from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.usbmux import list_devices

TITLE_ID = '01006F8002326000'
BUNDLE_ID = 'org.spplechos.acnh.airporttest'
SAVE_ROOTS = {'save', 'save_device'}
REMOTE_GAME = f'/Documents/games/{TITLE_ID}'


def read_snapshot(path):
    with zipfile.ZipFile(path) as archive:
        snapshot = json.loads(archive.read('snapshot.json'))
        entries = snapshot['files']
        names = archive.namelist()
        if (snapshot['title_id'] != TITLE_ID or not entries
                or len(names) != len(entries) + 1
                or set(names) != {*entries, 'snapshot.json'}
                or sum(info.file_size for info in archive.infolist()) > 513 * 1024**2):
            raise ValueError('Unexpected contents in the save snapshot')
        files = {}
        for name, expected in entries.items():
            parts = name.split('/')
            if (len(parts) < 2 or parts[0] not in SAVE_ROOTS
                    or any(part in ('', '.', '..') for part in parts)
                    or re.search(r'[\\\x00-\x1f]', name)):
                raise ValueError('Invalid path in the save snapshot')
            data = archive.read(name)
            if len(data) != expected['bytes'] or sha256(data).hexdigest() != expected['sha256']:
                raise ValueError('A save file failed its integrity check')
            files[PurePosixPath(name)] = data
        return files


async def restore(files):
    devices = [device for device in await list_devices() if device.connection_type == 'USB']
    if len(devices) != 1:
        raise RuntimeError('Connect exactly one iPhone by USB')
    async with await create_using_usbmux(serial=devices[0].serial) as device:
        apps = await InstallationProxyService(lockdown=device).get_apps(application_type='User')
        targets = [
            bundle for bundle, app in apps.items()
            if (bundle == BUNDLE_ID or bundle.startswith(BUNDLE_ID + '.'))
            and app.get('ALTBundleIdentifier', BUNDLE_ID) == BUNDLE_ID
        ]
        if len(targets) != 1:
            raise RuntimeError('Install and open the separate airport test app first')
        async with await HouseArrestService.create(device, targets[0], documents_only=False) as afc:
            folders = sorted({path.parts[0] for path in files})
            for folder in SAVE_ROOTS:
                if await afc.exists(f'{REMOTE_GAME}/{folder}'):
                    raise RuntimeError('The test app already has save folders. No files were replaced.')
            for directory in ('/Documents/games', REMOTE_GAME):
                if not await afc.exists(directory):
                    await afc.makedirs(directory)
            staging = f'{REMOTE_GAME}/.airport-restore-{uuid4().hex}'
            await afc.makedirs(staging)
            created = {PurePosixPath('.')}
            for path, data in files.items():
                for parent in reversed(path.parents):
                    if parent not in created:
                        await afc.makedirs(f'{staging}/{parent.as_posix()}')
                        created.add(parent)
                remote = f'{staging}/{path.as_posix()}'
                await afc.set_file_contents(remote, data)
                if sha256(await afc.get_file_contents(remote)).digest() != sha256(data).digest():
                    raise RuntimeError(f'The restored copy did not match its backup: {path.name}')
            for folder in folders:
                destination = f'{REMOTE_GAME}/{folder}'
                if await afc.exists(destination):
                    raise RuntimeError('The test game created a save while the copy was in progress')
                await afc.rename(f'{staging}/{folder}', destination)
            await afc.rm_single(staging)
    print(f'Restored and verified {len(files)} save files in the airport test app.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    args = parser.parse_args()
    asyncio.run(asyncio.wait_for(restore(read_snapshot(args.snapshot)), 120))
