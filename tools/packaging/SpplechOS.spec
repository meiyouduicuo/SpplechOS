# Build with the device-capable Python environment and these two input folders:
# SPPLECHOS_SHELL_TEMPLATE: contains the compiled DmShell.app
# SPPLECHOS_ZSIGN_DIR: contains the patched zsign.exe, never signing credentials
import os
import sys
from pathlib import Path
import pefile
from PyInstaller.utils.hooks import collect_all, collect_submodules

packaging = Path(SPECPATH)
repo = packaging.parent.parent
frontend = repo / 'frontend-qt'
sys.path.insert(0, str(frontend))
template = Path(os.environ['SPPLECHOS_SHELL_TEMPLATE'])
zsign = Path(os.environ['SPPLECHOS_ZSIGN_DIR'])
if not (template / 'DmShell.app' / 'DmShell').is_file() or not (zsign / 'zsign.exe').is_file():
    raise RuntimeError('A compiled shell template and patched zsign.exe are required')
datas = [(str(repo / 'frontend/fonts/Manrope.ttf'), 'fonts'),
         (str(repo / 'frontend/fonts/Manrope-OFL.txt'), 'fonts'),
         (str(repo / 'frontend/l10n'), 'l10n'), (str(template), 'shell_template'),
         (str(frontend / 'nspb_qt'), 'nspb_qt')]
for name in ('zsign.exe', 'libcrypto-3-x64.dll', 'libssl-3-x64.dll', 'LICENSE-zsign.txt', 'LICENSE-OpenSSL.txt'):
    if (zsign / name).is_file():
        datas.append((str(zsign / name), 'tools'))
binaries = []
imports = collect_submodules('nspb_qt')
for package in ('pymobiledevice3', 'cryptography'):
    data, binary, hidden = collect_all(package)
    datas += data
    binaries += binary
    imports += hidden
a = Analysis([str(frontend / 'run_gui.py')], pathex=[str(frontend)],
             binaries=binaries, datas=datas, hiddenimports=imports,
             hookspath=[], hooksconfig={}, runtime_hooks=[str(packaging / 'qt_runtime.py')],
             excludes=[], noarchive=False, optimize=0)

# Qt on Windows uses the operating system's ICU with unversioned exports.
# An MSYS2 toolchain on PATH can make PyInstaller pick up its incompatible ICU
# instead. That produces "procedure not found" while importing QtCore even
# though every Qt DLL is present. Never ship that substitute in the app root.
bad_icu = False
for destination, source, kind in a.binaries:
    if Path(destination).name.lower() == 'icuuc.dll':
        pe = pefile.PE(source, fast_load=True)
        try:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
            names = {entry.name for entry in pe.DIRECTORY_ENTRY_EXPORT.symbols}
            bad_icu = b'ucnv_open' not in names
        finally:
            pe.close()
if bad_icu:
    a.binaries = [entry for entry in a.binaries
                  if Path(entry[0]).name.lower() != 'icuuc.dll'
                  and not (Path(entry[0]).name.lower().startswith('icudt') and entry[0].lower().endswith('.dll'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SpplechOS', debug=False,
          bootloader_ignore_signals=False, strip=False, upx=True, console=False,
          disable_windowed_traceback=False, argv_emulation=False, target_arch=None,
          codesign_identity=None, entitlements_file=None,
          icon=[str(frontend / 'nspb_qt/assets/app_icon.ico')],
          manifest=str(frontend / 'spplechos.manifest'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[], name='SpplechOS')
