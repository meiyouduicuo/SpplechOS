"""Keep the DLL search directories alive for the packaged Windows application."""
import os
import sys
from pathlib import Path

root = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
sys._spplechos_dll_directories = [
    os.add_dll_directory(str(folder))
    for folder in (root, root / 'PySide6', root / 'shiboken6') if folder.is_dir()
]
