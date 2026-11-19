"""Qt worker for experimental incremental game delivery."""
from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QThread, Signal


class HotInstallWorker(QThread):
    progress = Signal(str, int)
    result = Signal(bool, str)

    def __init__(self, framework: Path, title_id: str, image: Path | None,
                 zsign: Path, credential_dir: Path, parent=None, *, romfs_tool: Path | None = None,
                 shader_dir: Path | None = None):
        super().__init__(parent)
        self.framework, self.title_id, self.image = framework, title_id, image
        self.zsign, self.credential_dir = zsign, credential_dir
        self.romfs_tool = romfs_tool
        self.shader_dir = shader_dir

    def run(self):
        try:
            from .hot_pipeline import deliver_game
            last = [None]
            def report(stage, done, total):
                current = (stage, int(done * 100 / total) if total else 0)
                if current != last[0]:
                    last[0] = current
                    self.progress.emit(*current)
            asyncio.run(deliver_game(self.framework, self.title_id, self.image,
                                     self.zsign, self.credential_dir, report, romfs_tool=self.romfs_tool,
                                     shader_dir=self.shader_dir))
            self.result.emit(True, '')
        except BaseException as exc:
            from .hot_install import HotInstallError
            message = str(exc) if isinstance(exc, HotInstallError) else '连接、签名或传输失败，请检查设备连接与签名环境。'
            self.result.emit(False, message)
