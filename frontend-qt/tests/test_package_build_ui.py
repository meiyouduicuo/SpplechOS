"""The simplified build flow keeps global keys out of the collapsed game inputs."""
import os
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEvent, QSettings
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 is not installed')
class PackageBuildUITests(unittest.TestCase):
    def test_collapsed_inputs_and_global_keys(self):
        from nspb_qt.model import Model
        from nspb_qt.ui import MainWindow
        from nspb_qt import platform_util as pu
        app = QApplication.instance() or QApplication([])
        settings_dir = tempfile.TemporaryDirectory()
        self.addCleanup(settings_dir.cleanup)
        settings = QSettings(str(Path(settings_dir.name) / 'settings.ini'), QSettings.IniFormat)
        with patch('nspb_qt.model.QSettings', return_value=settings):
            model = Model()
        model.repo_path = ''
        window = MainWindow(model)
        try:
            window.show()
            window._switch_page('builds')
            app.processEvents()
            self.assertFalse(window.file_details.isVisible())
            self.assertTrue(window.pick_folder_btn.isVisible())
            self.assertTrue(window.tools_group.isAncestorOf(window.input_rows['keys']['choose']))
            self.assertFalse(window.files_group.isAncestorOf(window.input_rows['keys']['choose']))
            window.files_toggle_btn.click()
            self.assertTrue(window.file_details.isVisible())
            self.assertTrue(window.input_rows['base']['choose'].isVisible())
            window.files_toggle_btn.click()
            self.assertFalse(window.file_details.isVisible())
            if pu.IS_WIN:
                self.assertFalse(window.install_group.isVisible())
                self.assertTrue(window.package_group.isVisible())
        finally:
            window.close()
            window.deleteLater()
            model.deleteLater()
            app.sendPostedEvents(None, QEvent.DeferredDelete)
            app.processEvents()
