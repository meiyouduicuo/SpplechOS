"""Send the independently built Monster Hunter test assets to the LAN test app.

Only the test bundle ID is accepted. Existing game files or shaders are never
replaced. Run with one unlocked, trusted device connected at a time.
"""
import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'frontend-qt'))
from nspb_qt.refresh_flow import matches_romfs_identity  # noqa: E402
from nspb_qt.win.hot_install import check_host, upload_aoc, upload_romfs  # noqa: E402

BUNDLE = 'org.spplechos.lantest'
TITLE = '0100559011740000'


def progress(label):
    last = [-5, 0.0]
    def report(done, total):
        percent = int(done * 100 / total) if total else 0
        if percent >= last[0] + 5 or done == total or time.monotonic() - last[1] >= 60:
            print(f'{label}: {percent}% ({done}/{total} bytes)', flush=True)
            last[:] = [percent, time.monotonic()]
    return report


async def main(args):
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.house_arrest import HouseArrestService
    from pymobiledevice3.services.installation_proxy import InstallationProxyService

    manifest = json.loads((args.framework / 'game.manifest.json').read_text(encoding='utf-8'))
    cache = json.loads(args.shader_meta.read_text(encoding='utf-8'))
    chain = manifest.get('chain', '')
    shader = Path(cache.get('lib_path', ''))
    if (manifest.get('title_id') != TITLE or cache.get('title_id') != TITLE or
            cache.get('chain') != chain or cache.get('multi_program') or
            not re.fullmatch(r'b-[a-zA-Z0-9._-]+', chain) or not shader.is_file() or
            not args.image.is_file() or not matches_romfs_identity(args.image, manifest.get('romfs_identity', ''))):
        raise RuntimeError('Game image, shader cache, or framework identity does not match')
    aoc = args.image.parent / 'aoc'
    dlc_files = list(aoc.rglob('*')) if aoc.is_dir() else []
    if any(p.is_symlink() for p in dlc_files):
        raise RuntimeError('DLC directory contains a link')
    size = args.image.stat().st_size + shader.stat().st_size + sum(p.stat().st_size for p in dlc_files if p.is_file())
    device = await asyncio.wait_for(create_using_usbmux(), 20)
    try:
        apps = await asyncio.wait_for(InstallationProxyService(lockdown=device).get_apps(application_type='User'), 30)
        matches = [(key, app) for key, app in apps.items()
                   if key == BUNDLE or key.startswith(BUNDLE + '.') or app.get('ALTBundleIdentifier') == BUNDLE]
        if len(matches) != 1:
            raise RuntimeError('Expected exactly one installed LAN test app; open it once and connect one device')
        bundle, app = matches[0]
        team = (app.get('Entitlements') or {}).get('com.apple.developer.team-identifier', '')
        if not team:
            raise RuntimeError('The installed test app does not report its signing team')
        async with await HouseArrestService.create(device, bundle, documents_only=False) as afc:
            documents = await afc.listdir('/Documents')
            if '.shell-host.json' in documents:
                check_host(await afc.get_file_contents('/Documents/.shell-host.json'), expected_bundle_id=bundle, expected_team_id=team)
            else:
                # Older shell templates do not emit a beacon. Only accept an exact
                # original ID and a launch log identifying this bundle and game.
                if app.get('ALTBundleIdentifier') != BUNDLE or 'shell-log.txt' not in documents:
                    raise RuntimeError('Cannot verify the isolated test shell')
                log = (await afc.get_file_contents('/Documents/shell-log.txt')).decode('utf-8', 'replace')
                if ('shell: ' + bundle + ' ') not in log or ('framework DmGame' + TITLE + '.framework') not in log or ('shader chain ' + chain.removeprefix('b-')) not in log:
                    raise RuntimeError('Test shell log does not match the expected bundle, game, or shader chain')
            if int((await afc.get_device_info()).get('FSFreeBytes', 0)) < size + 256 * 1024 * 1024:
                raise RuntimeError('Insufficient device free space for game, shader and DLC data')
            folder = '/Documents/games/' + TITLE
            await afc.makedirs(folder)
            names = await afc.listdir(folder)
            if any(name.lower() in ('romfs.img', 'msl', 'aoc') for name in names):
                raise RuntimeError('Test game data already exists; refusing to replace any file')
            print('Sending game data to the isolated LAN test app:', bundle, flush=True)
            await upload_romfs(afc, args.image, TITLE, manifest['romfs_identity'], progress('游戏数据'))
            stage = folder + '/.msl-' + uuid.uuid4().hex
            await afc.makedirs(stage)
            remote = stage + '/' + chain + '.img'
            before = shader.stat()
            handle = await afc.fopen(remote, 'w')
            done = 0
            report = progress('着色器')
            try:
                with shader.open('rb') as f:
                    while chunk := f.read(4 * 1024 * 1024):
                        await afc.fwrite(handle, chunk)
                        done += len(chunk)
                        report(done, before.st_size)
            finally:
                await afc.fclose(handle)
            after = shader.stat()
            if (done != before.st_size or after.st_size != before.st_size or after.st_mtime_ns != before.st_mtime_ns or
                    int((await afc.stat(remote))['st_size']) != before.st_size):
                raise RuntimeError('Shader transfer did not complete')
            if 'msl' in await afc.listdir(folder):
                raise RuntimeError('Shader directory appeared during transfer; refusing to replace it')
            await afc.rename(stage, folder + '/msl')
            await upload_aoc(afc, aoc, TITLE, progress('DLC'))
            print('Game, matching shaders and available DLC transferred.', flush=True)
    finally:
        await device.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--framework', type=Path, required=True)
    parser.add_argument('--shader-meta', type=Path, required=True)
    parser.add_argument('--image', type=Path, required=True)
    asyncio.run(main(parser.parse_args()))
