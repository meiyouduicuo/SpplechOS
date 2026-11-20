"""Package the Animal Crossing airport check in a separate iOS app."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'frontend-qt'))
from nspb_qt.win import shell_export as shell  # noqa: E402
from nspb_qt.refresh_flow import matches_romfs_identity  # noqa: E402
from verify_framework_hle import verify_forced_hle  # noqa: E402
from airport_test_env import with_lan_defaults  # noqa: E402

TITLE_ID = '01006F8002326000'
BUNDLE_ID = 'org.spplechos.acnh.airporttest'
DISPLAY_NAME = 'SpplechOS 动森机场测试'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--framework', type=Path, required=True)
    parser.add_argument('--shader-meta', type=Path, required=True)
    parser.add_argument('--romfs-image', type=Path, required=True,
                        help='validate the existing image without copying it into the IPA')
    parser.add_argument('--template', type=Path, required=True)
    args = parser.parse_args()
    target = args.root.resolve()
    framework = args.framework.resolve()
    expected_env = 'DM_ACNH_AIRPORT_TEST=1'
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f'Test shell directory is not empty: {target}')
    env = framework / 'dm/env.txt'
    if framework.name != f'DmGame{TITLE_ID}.framework' or not env.is_file():
        raise SystemExit('Expected an Animal Crossing test framework')
    if expected_env not in env.read_text(encoding='utf-8').splitlines():
        raise SystemExit('The framework did not enable the airport test')
    verify_forced_hle(framework / framework.stem)

    manifest = json.loads((framework / 'game.manifest.json').read_text(encoding='utf-8'))
    if not matches_romfs_identity(args.romfs_image, manifest['romfs_identity']):
        raise SystemExit('The existing game image does not match this framework')
    shaders = json.loads(args.shader_meta.read_text(encoding='utf-8'))
    shader_image = Path(shaders['lib_path'])
    if (shaders['title_id'].upper() != TITLE_ID or shaders['chain'] != manifest['chain']
            or shaders['multi_program'] or not shader_image.is_file()
            or shader_image.name != f'{manifest["chain"]}.img'):
        raise SystemExit('Expected a packed shader library matching this framework')

    target.mkdir(parents=True, exist_ok=True)
    os.environ['NSPB_SHELL_TEMPLATE'] = str(args.template.resolve())
    shell.ShellLibrary(bundle_id=BUNDLE_ID).save(target)
    framework = shell.mirror_framework(framework, target, TITLE_ID)
    test_env = framework / 'dm/env.txt'
    test_env.write_text(with_lan_defaults(test_env.read_text(encoding='utf-8')), encoding='utf-8')
    bundled_msl = framework / 'msl'
    bundled_msl.mkdir(exist_ok=True)
    shutil.copy2(shader_image, bundled_msl / shader_image.name)
    update_plist = shell._update_shell_plist

    def update_test_plist(app, bundle_id, repo):
        update_plist(app, bundle_id, repo)
        path = app / 'Info.plist'
        info = plistlib.loads(path.read_bytes())
        info['CFBundleDisplayName'] = DISPLAY_NAME
        info['CFBundleName'] = 'SpplechOS ACNH Airport Test'
        path.write_bytes(plistlib.dumps(info))

    shell._update_shell_plist = update_test_plist
    ok, ipa, message, notes = shell.export_shell(
        root=target, repo=ROOT / 'engine', framework=framework,
        title_id=TITLE_ID, name='Animal Crossing: New Horizons',
        python_exe=sys.executable, log=lambda line: print(line, end='', flush=True))
    if not ok:
        raise SystemExit(message)

    app = 'Payload/DmShell.app'
    with zipfile.ZipFile(ipa) as archive:
        info = plistlib.loads(archive.read(f'{app}/Info.plist'))
        if info['CFBundleIdentifier'] != BUNDLE_ID:
            raise SystemExit('The test app was packaged with an unexpected identifier')
        if any(name.lower().endswith('/romfs.img') for name in archive.namelist()):
            raise SystemExit('The test package unexpectedly contains a game image')
        packaged = archive.read(f'{app}/Frameworks/{framework.name}/dm/env.txt')
        if expected_env.encode() not in packaged.splitlines():
            raise SystemExit('The packaged framework did not enable the airport test')
        packaged_keys = {line.partition(b'=')[0].strip() for line in packaged.splitlines() if b'=' in line}
        for key in (b'DM_LAN', b'DM_LDN_TRACE'):
            if key not in packaged_keys:
                raise SystemExit('The airport test package is missing its LAN defaults')
        if f'{app}/Frameworks/{framework.name}/msl/{shader_image.name}' not in archive.namelist():
            raise SystemExit('The packaged framework is missing its shader library')
    print(ipa)
    if notes:
        print('\n'.join(notes))


if __name__ == '__main__':
    main()
