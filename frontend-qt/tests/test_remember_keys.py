import tempfile
import unittest
from pathlib import Path

try:
    from PySide6.QtCore import QSettings
    from nspb_qt.model import Model
except ImportError:
    QSettings = None
    Model = None


@unittest.skipIf(QSettings is None, 'PySide6 is not installed')
class RememberKeysTests(unittest.TestCase):
    def test_restores_only_existing_path_and_clear_forgets_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = QSettings(str(root / 'settings.ini'), QSettings.IniFormat)
            key = root / 'prod.keys'
            key.write_bytes(b'fixture')
            class Holder:
                pass
            obj = Holder()
            obj.settings = settings
            Model.keys_path.fset(obj, str(key))
            settings.sync()
            self.assertEqual(Model._restore_keys_path(settings), str(key))
            self.assertNotIn('fixture', (root / 'settings.ini').read_text())
            key.unlink()
            self.assertEqual(Model._restore_keys_path(settings), '')
            Model.keys_path.fset(obj, '')
            self.assertFalse(settings.contains('lastKeysPath'))


if __name__ == '__main__':
    unittest.main()
