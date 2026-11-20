"""Background USB package import, with no signing dependency."""
import asyncio
from PySide6.QtCore import QThread, Signal


class USBPackageWorker(QThread):
    progress = Signal(str, int)
    result = Signal(bool, str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path

    def run(self):
        from .usb_package import import_package
        from .hot_install import HotInstallError
        last = None
        def report(stage, percent):
            nonlocal last
            if (stage, percent) != last:
                last = (stage, percent)
                self.progress.emit(stage, percent)
        try:
            title_id = asyncio.run(import_package(self.path, report))
            self.result.emit(True, title_id)
        except Exception as exc:
            self.result.emit(False, str(exc) if isinstance(exc, HotInstallError) else 'usb.connectionFailed')
