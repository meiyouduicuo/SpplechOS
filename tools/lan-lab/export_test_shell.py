"""Package an unsigned Monster Hunter Rise LAN build.

The target directory must be empty. This does not touch installed apps, their
sandboxes, or the production shell library. Use a sideloader to sign it.
"""
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'frontend-qt'))
from nspb_qt.win import shell_export as shell  # noqa: E402

BUNDLE_ID = 'org.spplechos.lantest'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--framework', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--version', default='1.1', help='visible and bundle version for identifying this test build')
    parser.add_argument('--build-number', default='2', help='CFBundleVersion for identifying this test build')
    parser.add_argument('--release', action='store_true',
                        help='use SpplechOS branding and disable LAN tracing for an in-place upgrade')
    args = parser.parse_args()
    target = args.root.resolve()
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f'Test shell directory is not empty: {target}')
    if not args.framework.is_dir() or not (args.template / 'Info.plist').is_file():
        raise SystemExit('Missing completed game framework or shell template')
    target.mkdir(parents=True, exist_ok=True)
    os.environ['NSPB_SHELL_TEMPLATE'] = str(args.template.resolve())
    shell.ShellLibrary(bundle_id=BUNDLE_ID).save(target)
    update_plist = shell._update_shell_plist
    def update_test_plist(app, bundle_id, repo):
        update_plist(app, bundle_id, repo)
        path = app / 'Info.plist'
        with path.open('rb') as f:
            info = plistlib.load(f)
        info['CFBundleDisplayName'] = 'SpplechOS' if args.release else f'Spple LAN {args.version}'
        info['CFBundleName'] = 'SpplechOS' if args.release else 'Spple LAN'
        info['CFBundleShortVersionString'] = args.version
        info['CFBundleVersion'] = args.build_number
        with path.open('wb') as f:
            plistlib.dump(info, f)
    shell._update_shell_plist = update_test_plist
    def export(framework):
        return shell.export_shell(
            root=target, repo=ROOT / 'engine', framework=framework,
            title_id='0100559011740000', name='MONSTER HUNTER RISE',
            python_exe=sys.executable, log=lambda line: print(line, end='', flush=True))

    framework = args.framework.resolve()
    if args.release:
        with tempfile.TemporaryDirectory(prefix='spple-release-', dir=target.parent) as staging:
            prepared = Path(staging) / framework.name
            shutil.copytree(framework, prepared)
            env_file = prepared / 'dm/env.txt'
            env_lines = env_file.read_text(encoding='utf-8').splitlines()
            env_lines = [line for line in env_lines if line.partition('=')[0].strip() != 'DM_LDN_TRACE']
            env_file.write_text('\n'.join(env_lines) + '\n', encoding='utf-8')
            ok, ipa, message, notes = export(prepared)
    else:
        ok, ipa, message, notes = export(framework)
    if not ok:
        raise SystemExit(message)
    with zipfile.ZipFile(ipa) as archive:
        files = archive.namelist()
        info_path = next((n for n in files if n.startswith('Payload/') and n.count('/') == 2 and n.endswith('.app/Info.plist')), None)
        if not info_path:
            raise SystemExit('No application Info.plist in test IPA')
        info = plistlib.loads(archive.read(info_path))
        if info.get('CFBundleIdentifier') != BUNDLE_ID or '_spplechos-ldn._tcp' not in info.get('NSBonjourServices', []):
            raise SystemExit('IPA identity or Bonjour metadata is incorrect')
        if any(n.lower().endswith('/romfs.img') for n in files):
            raise SystemExit('Test IPA unexpectedly contains game data')
        env_paths = [n for n in files if n.endswith('.framework/dm/env.txt')]
        if not env_paths or b'DM_LAN=1' not in archive.read(env_paths[0]):
            raise SystemExit('The embedded framework did not enable the LAN backend')
        if args.release and b'DM_LDN_TRACE' in archive.read(env_paths[0]):
            raise SystemExit('Release framework still enables LAN tracing')
        nacp_paths = [n for n in files if n.endswith('.framework/dm/control.nacp')]
        if not nacp_paths:
            raise SystemExit('The embedded framework is missing control.nacp')
        nacp = archive.read(nacp_paths[0])
        if len(nacp) < 0x30b8 or not any(nacp[0x30b0:0x30b8]):
            raise SystemExit('The game has no local communication ID')
    print('\nUnsigned release IPA:' if args.release else '\nUnsigned isolated test IPA:', ipa)
    print('Bundle identifier:', info['CFBundleIdentifier'])
    print('Game data and saves are not bundled.')
    if notes:
        print('\n'.join(notes))


if __name__ == '__main__':
    main()
