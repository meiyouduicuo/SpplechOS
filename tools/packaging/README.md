# Windows SpplechOS package

Use Python 3.12 with PySide6 Essentials, PyInstaller, pymobiledevice3 and cryptography.
Set `SPPLECHOS_SHELL_TEMPLATE` to a folder containing the tested `DmShell.app` template,
and `SPPLECHOS_ZSIGN_DIR` to the folder holding the patched `zsign.exe`.

Run `python -m PyInstaller --noconfirm --distpath <output> --workpath <work> tools/packaging/SpplechOS.spec`.
The spec uses repository-relative sources and never copies a signing key, profile,
game image or saved game. Its ICU filter prevents an MSYS2 installation on PATH from
substituting a DLL with incompatible exports for the Windows ICU used by Qt.

Before distributing the output, start the frozen executable and verify that the main
SpplechOS window opens. A running process alone is insufficient, because a PyInstaller
exception dialog also leaves a process alive. Package the directory with Inno Setup
using the existing application ID to update the desktop installation in place.
