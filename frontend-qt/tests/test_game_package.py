"""Package wire format, source integrity and atomic publication, without Qt."""
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nspb_qt.win.game_package import write_package, export_game_package, MAGIC
from nspb_qt.win.hot_install import HotInstallError, HostIdentity


class GamePackageTests(unittest.TestCase):
    def test_stream_round_trip_and_unicode_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'data'
            payload = b'large-file-chunk' * 100000
            source.write_bytes(payload)
            package = root / 'game.sppgame'
            write_package(package, title_id='0100000000010000', bundle_id='app', team_id='team',
                          files=[('data/romfs.img', source, len(payload)), ('framework/封面.jpg', source, 8)])
            with package.open('rb') as stream:
                self.assertEqual(stream.read(8), MAGIC)
                manifest = json.loads(stream.read(struct.unpack('<Q', stream.read(8))[0]))
                self.assertEqual(manifest['bundleID'], 'app')
                for entry in manifest['files']:
                    data = stream.read(entry['size'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
                self.assertEqual(stream.read(), b'')
            self.assertFalse(list(root.glob('.sppgame-*.part')))

    def test_rejects_paths_that_could_touch_saves_or_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.write_bytes(b'data')
            for name in ['data/save/main.dat', '../save', 'framework/../save', 'framework/C:x',
                         'framework/dir\\x', 'data/msl//x', '/data/romfs.img']:
                with self.subTest(name=name), self.assertRaises(HotInstallError):
                    write_package(root / 'bad.sppgame', title_id='0100000000010000', bundle_id='app', team_id='team',
                                  files=[(name, source, 4)])

    def test_rejects_case_collisions(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'; source.write_bytes(b'x')
            with self.assertRaises(HotInstallError):
                write_package(Path(temp) / 'bad', title_id='0100000000010000', bundle_id='app', team_id='team',
                              files=[('framework/A', source, 1), ('framework/a', source, 1)])

    def test_changed_source_does_not_replace_existing_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source'; package = root / 'old.sppgame'
            source.write_bytes(b'data'); package.write_bytes(b'old good package')
            with patch('nspb_qt.win.game_package._digest', return_value='0' * 64), self.assertRaises(HotInstallError):
                write_package(package, title_id='0100000000010000', bundle_id='app', team_id='team',
                              files=[('data/romfs.img', source, 4)])
            self.assertEqual(package.read_bytes(), b'old good package')
            self.assertFalse(list(root.glob('.sppgame-*.part')))

    def test_shared_python_fixture_has_valid_file_hashes(self):
        fixture = Path(__file__).resolve().parents[2] / 'frontend-ios/Tests/ShellHostTests/Fixtures/GamePackage/synthetic.sppgame'
        with fixture.open('rb') as source:
            self.assertEqual(source.read(8), MAGIC)
            header = json.loads(source.read(struct.unpack('<Q', source.read(8))[0]))
            self.assertEqual(header['schema'], 1)
            for entry in header['files']:
                self.assertEqual(hashlib.sha256(source.read(entry['size'])).hexdigest(), entry['sha256'])
            self.assertEqual(source.read(), b'')

    def test_complete_export_includes_framework_shaders_and_dlc_but_never_saves(self):
        fixture = Path(__file__).resolve().parents[2] / 'frontend-ios/Tests/ShellHostTests/Fixtures/GamePackage/synthetic.sppgame'
        with tempfile.TemporaryDirectory() as temp, fixture.open('rb') as source:
            root = Path(temp)
            source.read(8)
            header = json.loads(source.read(struct.unpack('<Q', source.read(8))[0]))
            fw = root / f"DmGame{header['titleID']}.framework"
            for entry in header['files']:
                name = entry['path']
                output = fw / name.removeprefix('framework/') if name.startswith('framework/') else root / name
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(source.read(entry['size']))
            (root / 'data/aoc').mkdir()
            (root / 'data/aoc/1000.img').write_bytes(b'synthetic DLC')
            (root / 'data/save').mkdir()
            (root / 'data/save/main.dat').write_bytes(b'private save must stay here')
            target = export_game_package(fw, root / 'data/romfs.img', root / 'export.sppgame',
                                         HostIdentity(header['bundleID'], header['teamID'], 'b-3f9a2c', None))
            with target.open('rb') as package:
                package.read(8)
                manifest = json.loads(package.read(struct.unpack('<Q', package.read(8))[0]))
            names = {e['path'] for e in manifest['files']}
            self.assertIn('data/aoc/1000.img', names)
            self.assertIn('framework/banner.jpg', names)
            self.assertTrue(any(n.startswith('data/msl/') for n in names))
            self.assertFalse(any('save' in n for n in names))
            self.assertEqual((root / 'data/save/main.dat').read_bytes(), b'private save must stay here')
            # An inline shader tree is already part of the signed framework copy.
            # Keep it intact and do not also add a second copy beside the image.
            inline = fw / 'msl/b-3f9a2c/synthetic.metallib'
            inline.parent.mkdir(parents=True)
            inline.write_bytes(b'inline shader')
            target = export_game_package(fw, root / 'data/romfs.img', root / 'inline.sppgame',
                                         HostIdentity(header['bundleID'], header['teamID'], 'b-3f9a2c', None))
            with target.open('rb') as package:
                package.read(8)
                manifest = json.loads(package.read(struct.unpack('<Q', package.read(8))[0]))
            names = {e['path'] for e in manifest['files']}
            self.assertIn('framework/msl/b-3f9a2c/synthetic.metallib', names)
            self.assertFalse(any(n.startswith('data/msl/') for n in names))


if __name__ == '__main__':
    unittest.main()
