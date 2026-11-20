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
from nspb_qt.win.game_package import write_package, MAGIC, _tree
from nspb_qt.win.hot_install import HotInstallError


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


if __name__ == '__main__':
    unittest.main()
