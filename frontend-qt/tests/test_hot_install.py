import json
import struct
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path

from nspb_qt.win.hot_install import HotInstallError, check_host, inspect_framework, ready_payload, upload_aoc, upload_signed_framework, upload_romfs, _same_shader_image


class HotInstallPreflightTests(unittest.TestCase):
    def test_packed_shader_must_match_trailer_contents(self):
        class Tool:
            @staticmethod
            def _validate_and_list_slice(f, offset, size, label):
                return {'b-test/shader.metallib' if offset else 'shader.metallib': (False, 32, 4)}
            @staticmethod
            def _keep_msl_file(name): return True
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            header = struct.pack('<8sQQQ', b'DMROMFS1', 36, 0, 1)
            image = root / 'game.img'
            image.write_bytes(b'prefix' + header + b'abcd')
            cache = root / 'cache.img'
            cache.write_bytes(header + b'abcd')
            details = {'msl_offset': 6, 'msl_size': 36, 'chain': 'b-test'}
            self.assertTrue(_same_shader_image(Tool(), image, details, cache))
            cache.write_bytes(header + b'abce')
            self.assertFalse(_same_shader_image(Tool(), image, details, cache))

    def test_valid_host_and_expiry(self):
        beacon = json.dumps({'schema': 1, 'glueVersion': 1, 'bundleID': 'org.spplechos.shell',
                             'teamID': 'TEAM', 'chain': 'b-chain', 'expiresAtEpoch': 200000}).encode()
        self.assertEqual(check_host(beacon, expected_bundle_id='org.spplechos.shell',
                                    expected_team_id='TEAM', now=100000).chain, 'b-chain')
        with self.assertRaises(HotInstallError):
            check_host(beacon, expected_bundle_id='org.spplechos.shell', expected_team_id='OTHER', now=100000)
        with self.assertRaises(HotInstallError):
            check_host(beacon, expected_bundle_id='org.spplechos.shell', expected_team_id='TEAM', now=150000)

    def test_missing_and_malformed_beacon_fails_closed(self):
        for data in (b'', b'[]', b'{}', b'null'):
            with self.subTest(data=data), self.assertRaises(HotInstallError):
                check_host(data, expected_bundle_id='org.spplechos.shell', expected_team_id='TEAM')

    def test_validates_game_framework(self):
        tid = '0100559011740000'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / f'DmGame{tid}.framework'
            root.mkdir()
            (root / f'DmGame{tid}').write_bytes(b'example')
            path = root / 'game.manifest.json'
            path.write_text(json.dumps({'title_id': tid, 'loader': 'FH'}), encoding='utf-8')
            self.assertEqual(inspect_framework(root, tid)['loader'], 'FH')
            ready = json.loads(ready_payload(root, tid))
            self.assertEqual(ready['titleID'], tid)
            self.assertEqual(ready['files'], 2)
            self.assertEqual(ready['bytes'], sum(p.stat().st_size for p in root.iterdir()))
            path.write_text(json.dumps({'title_id': tid, 'loader': 'FR'}), encoding='utf-8')
            with self.assertRaises(HotInstallError):
                inspect_framework(root, tid)


class TransferTests(unittest.IsolatedAsyncioTestCase):
    async def test_dlc_is_staged_and_existing_dlc_is_not_replaced(self):
        class AFC:
            def __init__(self): self.files = {}; self.dirs = set(); self.exists = False
            async def listdir(self, path): return ['aoc'] if self.exists else []
            async def get_device_info(self): return {'FSFreeBytes': 1024 * 1024 * 1024}
            async def makedirs(self, path): self.dirs.add(path)
            async def fopen(self, path, mode): self.files[path] = bytearray(); return path
            async def fwrite(self, handle, data): self.files[handle].extend(data)
            async def fclose(self, handle): pass
            async def stat(self, path): return {'st_size': len(self.files[path])}
            async def rename(self, source, target):
                for key in list(self.files):
                    if key.startswith(source + '/'): self.files[target + key[len(source):]] = self.files.pop(key)
                self.exists = True
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'aoc'
            root.mkdir()
            (root / '1000.img').write_bytes(b'dlc')
            afc = AFC()
            target = await upload_aoc(afc, root, '0100559011740000')
            self.assertEqual(afc.files[target + '/1000.img'], b'dlc')
            with self.assertRaises(HotInstallError):
                await upload_aoc(afc, root, '0100559011740000')
            self.assertEqual(afc.files[target + '/1000.img'], b'dlc')

    async def test_disconnected_device_reports_useful_error(self):
        from nspb_qt.win.hot_pipeline import deliver_game
        from pymobiledevice3.exceptions import NoDeviceConnectedError
        tid = '0100559011740000'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / f'DmGame{tid}.framework'
            root.mkdir()
            (root / f'DmGame{tid}').write_bytes(b'game')
            (root / 'game.manifest.json').write_text(json.dumps({'title_id': tid, 'loader': 'FH'}))
            statuses = []
            with patch('nspb_qt.win.hot_pipeline.probe_shell', new=AsyncMock(side_effect=NoDeviceConnectedError())):
                with self.assertRaisesRegex(HotInstallError, '未检测到'):
                    await deliver_game(root, tid, None, root / 'zsign.exe', root,
                                       lambda stage, done, total: statuses.append(stage))
            self.assertEqual(statuses, ['device'])

    async def test_romfs_does_not_overwrite_existing_image(self):
        class AFC:
            async def get_device_info(self): return {'FSFreeBytes': 1024 * 1024 * 1024}
            async def makedirs(self, path): pass
            async def listdir(self, path): return ['romfs.img', 'save']
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / 'romfs.img'
            image.write_bytes(struct.pack('<8sQQQ', b'DMROMFS1', 32, 0, 0))
            with patch('nspb_qt.refresh_flow.matches_romfs_identity', return_value=True):
                with self.assertRaises(HotInstallError):
                    await upload_romfs(AFC(), image, '0100559011740000', 'valid')

    async def test_trailer_is_separated_for_older_game_framework(self):
        class AFC:
            def __init__(self): self.files = {}; self.dirs = set()
            async def get_device_info(self): return {'FSFreeBytes': 1024 * 1024 * 1024}
            async def makedirs(self, path): self.dirs.add(path)
            async def listdir(self, path):
                return [p[len(path)+1:] for p in self.dirs | set(self.files)
                        if p.startswith(path + '/') and '/' not in p[len(path)+1:]]
            async def fopen(self, path, mode): self.files[path] = bytearray(); return path
            async def fwrite(self, handle, data): self.files[handle].extend(data)
            async def fclose(self, handle): pass
            async def stat(self, path): return {'st_size': len(self.files[path])}
            async def set_file_contents(self, path, data): self.files[path] = data
            async def rename(self, source, target):
                if source in self.files: self.files[target] = self.files.pop(source)
                else:
                    self.dirs.add(target)
                    for key in list(self.files):
                        if key.startswith(source + '/'): self.files[target + key[len(source):]] = self.files.pop(key)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / 'game.img'
            base = struct.pack('<8sQQQ', b'DMROMFS1', 32, 0, 0)
            image.write_bytes(base + b'trailer')
            tool = root / 'tool.py'
            tool.write_text("def inspect_msl(p): return {'has_trailer': True, 'chain': 'b-test'}\n"
                            "def extract_msl(p, d):\n from pathlib import Path\n (Path(d)/'shader.metallib').write_bytes(b'shader')\n")
            afc = AFC()
            with patch('nspb_qt.refresh_flow.matches_romfs_identity', return_value=True):
                target = await upload_romfs(afc, image, '0100559011740000', 'valid',
                                            romfs_tool=tool, expected_chain='b-test')
            self.assertEqual(afc.files[target], base)
            self.assertEqual(afc.files[target.rsplit('/', 1)[0] + '/msl/shader.metallib'], b'shader')
            self.assertEqual(image.read_bytes(), base + b'trailer')

    async def test_marker_is_published_only_after_verified_transfer(self):
        class AFC:
            def __init__(self, bad_size=False):
                self.files = {}
                self.bad_size = bad_size
            async def makedirs(self, path): pass
            async def fopen(self, path, mode):
                self.files[path] = bytearray()
                return path
            async def fwrite(self, handle, data): self.files[handle].extend(data)
            async def fclose(self, handle): pass
            async def stat(self, path): return {'st_size': len(self.files[path]) + self.bad_size}
            async def set_file_contents(self, path, data): self.files[path] = data
        tid = '0100559011740000'
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / f'DmGame{tid}.framework'
            root.mkdir()
            (root / f'DmGame{tid}').write_bytes(b'game')
            (root / 'game.manifest.json').write_text(json.dumps({'title_id': tid, 'loader': 'FH'}))
            afc = AFC()
            stage = await upload_signed_framework(afc, root, tid)
            self.assertEqual(afc.files[stage + '/.ready'], ready_payload(root, tid))
            broken = AFC(bad_size=True)
            with self.assertRaises(HotInstallError):
                await upload_signed_framework(broken, root, tid)
            self.assertFalse(any(path.endswith('/.ready') for path in broken.files))


if __name__ == '__main__':
    unittest.main()
