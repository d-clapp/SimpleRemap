# low level mouse hook for windows
# used to block a specific mouse button and remap it to something else
# needed because the "mouse" library can detect clicks but cannot block them

import ctypes
import threading
from ctypes import wintypes

import keyboard
import mouse

user32 = ctypes.WinDLL("user32", use_last_error=True)

WH_MOUSE_LL = 14

# windows message codes for mouse buttons
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_XBUTTONDOWN = 0x020B
WM_XBUTTONUP = 0x020C

BUTTON_DOWN_CODES = {
    WM_LBUTTONDOWN: "left",
    WM_RBUTTONDOWN: "right",
    WM_MBUTTONDOWN: "middle",
    WM_XBUTTONDOWN: "x",  # could be x or x2, checked later
}
BUTTON_UP_CODES = {
    WM_LBUTTONUP: "left",
    WM_RBUTTONUP: "right",
    WM_MBUTTONUP: "middle",
    WM_XBUTTONUP: "x",
}


# struct windows fills in for low level mouse events
class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
        ("data", ctypes.c_int32),
        ("reserved", ctypes.c_int32),
        ("flags", wintypes.DWORD),
        ("time", ctypes.c_int),
    ]


LowLevelMouseProc = ctypes.CFUNCTYPE(
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
    ctypes.POINTER(MSLLHOOKSTRUCT),
)

SetWindowsHookEx = user32.SetWindowsHookExA
SetWindowsHookEx.restype = wintypes.HHOOK

CallNextHookEx = user32.CallNextHookEx
CallNextHookEx.restype = ctypes.c_int

UnhookWindowsHookEx = user32.UnhookWindowsHookEx
UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
UnhookWindowsHookEx.restype = wintypes.BOOL

GetMessage = user32.GetMessageW
GetMessage.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    ctypes.c_uint,
    ctypes.c_uint,
]
GetMessage.restype = wintypes.BOOL

TranslateMessage = user32.TranslateMessage
DispatchMessage = user32.DispatchMessageW

# current active remaps, example: {"right": ("key", "a"), "x": ("mouse", "middle")}
active_map = {}
_lock = threading.Lock()
_hook_started = False


def set_active_map(new_map):
    # replaces the whole active remap table
    global active_map
    with _lock:
        active_map = dict(new_map)


def _press_destination(dest_type, dest_value):
    if dest_type == "key":
        keyboard.press(dest_value)
    else:
        mouse.press(button=dest_value)


def _release_destination(dest_type, dest_value):
    if dest_type == "key":
        keyboard.release(dest_value)
    else:
        mouse.release(button=dest_value)


def _mouse_proc(n_code, w_param, l_param):
    # called by windows for every mouse event, must return fast
    try:
        if n_code >= 0:
            button = BUTTON_DOWN_CODES.get(w_param)
            is_down = button is not None
            if button is None:
                button = BUTTON_UP_CODES.get(w_param)

            if button == "x":
                struct = l_param.contents
                button = "x" if struct.data == 0x10000 else "x2"

            if button is not None and button != "left":
                with _lock:
                    dest = active_map.get(button)
                if dest is not None:
                    dest_type, dest_value = dest
                    if is_down:
                        _press_destination(dest_type, dest_value)
                    else:
                        _release_destination(dest_type, dest_value)
                    return 1  # block the original click
    except Exception:
        pass

    return CallNextHookEx(None, n_code, w_param, l_param)


def _run_hook_thread():
    callback = LowLevelMouseProc(_mouse_proc)
    hook_id = SetWindowsHookEx(WH_MOUSE_LL, callback, None, 0)

    msg = wintypes.MSG()
    while GetMessage(ctypes.byref(msg), None, 0, 0) != 0:
        TranslateMessage(ctypes.byref(msg))
        DispatchMessage(ctypes.byref(msg))

    UnhookWindowsHookEx(hook_id)


def start():
    # starts the background hook thread, safe to call more than once
    global _hook_started
    if _hook_started:
        return
    _hook_started = True
    thread = threading.Thread(target=_run_hook_thread, daemon=True)
    thread.start()
