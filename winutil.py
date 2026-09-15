# small windows-specific helpers: admin check, dpi awareness,
# single-instance lock, and the "start with windows" registry entry

import ctypes
import sys
import winreg
from pathlib import Path

_MUTEX_NAME = "Local\\SimpleRemapSingleInstance"
_ERROR_ALREADY_EXISTS = 183

_mutex_handle = None  # kept alive for the process lifetime

# a plain ctypes.windll call can have its Win32 last-error state clobbered
# by other calls ctypes makes internally before we get to read it; a
# WinDLL loaded with use_last_error=True keeps its own reliable copy
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = "SimpleRemap"


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def enable_dpi_awareness():
    # without this windows upscales the whole window on a scaled display,
    # which blurs tkinter's own (already crisp) rendering
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system dpi aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def acquire_single_instance_lock():
    # returns False if another copy of the app already holds the mutex
    global _mutex_handle
    _mutex_handle = _kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS


def _autostart_command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    # running from source: launch with pythonw so no console window pops up
    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    script = Path(__file__).parent / "main.py"
    return f'"{interpreter}" "{script}"'


def autostart_is_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _RUN_VALUE_NAME)
            return True
    except FileNotFoundError:
        return False


def set_autostart_enabled(enabled):
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
        if enabled:
            winreg.SetValueEx(key, _RUN_VALUE_NAME, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, _RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
