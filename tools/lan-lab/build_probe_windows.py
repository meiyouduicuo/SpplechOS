"""Cross-build an unsigned iOS LAN diagnostic IPA on Windows.

This standalone probe does not contain or launch games. It must be signed by the
user's existing sideloading tool; the script does not read signing credentials.
"""
from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--clang', required=True, type=Path)
    ap.add_argument('--sdk', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    project = root.parents[1]
    icons = project / 'frontend-qt' / 'nspb_qt' / 'assets' / 'spplechos_icons'
    if not args.clang.is_file() or not (args.sdk / 'System/Library/Frameworks/UIKit.framework/UIKit.tbd').is_file():
        raise SystemExit('Missing clang or iPhoneOS SDK')
    env = dict(os.environ)
    env['PATH'] = str(args.clang.parent) + os.pathsep + env.get('PATH', '')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='spple-lan-probe-') as temp:
        work = Path(temp)
        app = work / 'Payload' / 'SppleLANProbe.app'
        app.mkdir(parents=True)
        executable = app / 'SppleLANProbe'
        common = [str(args.clang), '-target', 'arm64-apple-ios26.0', '-isysroot', str(args.sdk),
                  '-I' + str(root / 'src'), '-Wall', '-Wextra', '-Werror']
        sources = [root / 'ios/LanProbe.m'] + [root / 'src' / (name + '.c') for name in
                                               ('lan_frame', 'lan_protocol', 'lan_handshake', 'lan_discovery', 'lan_retry')]
        objects = []
        for source in sources:
            obj = work / (source.stem + '.o')
            flags = ['-std=gnu11', '-fobjc-arc', '-fblocks'] if source.suffix == '.m' else ['-std=c11']
            subprocess.run(common + flags + ['-c', str(source), '-o', str(obj)], check=True, env=env)
            objects.append(obj)
        subprocess.run([str(args.clang), '-target', 'arm64-apple-ios26.0', '-isysroot', str(args.sdk),
                        '-fuse-ld=lld', '-fobjc-arc', '-o', str(executable), *map(str, objects),
                        '-Wl,-adhoc_codesign', '-lobjc', '-lSystem', '-framework', 'UIKit',
                        '-framework', 'Foundation'], check=True, env=env)
        info = {
            'CFBundleIdentifier': 'org.spplechos.lanprobe', 'CFBundleExecutable': 'SppleLANProbe',
            'CFBundleName': 'SppleLANProbe', 'CFBundleDisplayName': '局域网诊断',
            'CFBundlePackageType': 'APPL', 'CFBundleInfoDictionaryVersion': '6.0',
            'CFBundleShortVersionString': '0.1', 'CFBundleVersion': '1', 'LSRequiresIPhoneOS': True,
            'MinimumOSVersion': '26.0', 'CFBundleSupportedPlatforms': ['iPhoneOS'],
            'UIDeviceFamily': [1, 2], 'UILaunchScreen': {},
            'NSLocalNetworkUsageDescription': '用于发现同一局域网内的另一台设备并测试连接。',
            'NSBonjourServices': ['_spplechos-ldn._tcp'],
            'UIApplicationSceneManifest': {'UIApplicationSupportsMultipleScenes': False,
                'UISceneConfigurations': {'UIWindowSceneSessionRoleApplication': [
                    {'UISceneConfigurationName': 'Default', 'UISceneDelegateClassName': 'ProbeScene'}]}},
            'UISupportedInterfaceOrientations': ['UIInterfaceOrientationPortrait',
                'UIInterfaceOrientationLandscapeLeft', 'UIInterfaceOrientationLandscapeRight'],
        }
        names = ['SpplechIcon60x60@2x.png', 'SpplechIcon60x60@3x.png',
                 'SpplechIcon76x76@2x~ipad.png', 'SpplechIcon83.5x83.5@2x~ipad.png']
        for name in names:
            shutil.copy2(icons / name, app / name)
        info['CFBundleIcons'] = {'CFBundlePrimaryIcon': {'CFBundleIconFiles': ['SpplechIcon60x60']}}
        info['CFBundleIcons~ipad'] = {'CFBundlePrimaryIcon': {'CFBundleIconFiles': [
            'SpplechIcon60x60', 'SpplechIcon76x76', 'SpplechIcon83.5x83.5']}}
        with (app / 'Info.plist').open('wb') as f:
            plistlib.dump(info, f)
        with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path in sorted(app.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(work).as_posix())
        print('Built unsigned diagnostic IPA:', args.output)


if __name__ == '__main__':
    main()
