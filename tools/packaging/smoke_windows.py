"""Start only the supplied build, check its hidden main window, then close it."""
import argparse
import ctypes
import subprocess
import time
from ctypes import wintypes
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path)
    args = parser.parse_args()
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.EnumWindows.argtypes = [callback, wintypes.LPARAM]
    info = subprocess.STARTUPINFO()
    info.dwFlags = subprocess.STARTF_USESHOWWINDOW
    info.wShowWindow = 0
    process = subprocess.Popen([str(args.executable.resolve())], startupinfo=info)
    titles = []

    @callback
    def window(hwnd, _):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == process.pid:
            buffer = ctypes.create_unicode_buffer(user.GetWindowTextLengthW(hwnd) + 1)
            user.GetWindowTextW(hwnd, buffer, len(buffer))
            if buffer.value:
                titles.append(buffer.value)
        return True

    try:
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise SystemExit(f'Startup exited with {process.returncode}')
            titles.clear()
            user.EnumWindows(window, 0)
            if any('Unhandled exception' in title for title in titles):
                raise SystemExit('The packaged app opened a PyInstaller exception dialog')
            if any(title.startswith('SpplechOS') for title in titles):
                print('Startup passed: SpplechOS main window created without an exception dialog')
                return
            time.sleep(0.25)
        raise SystemExit('No SpplechOS main window appeared within 25 seconds')
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
