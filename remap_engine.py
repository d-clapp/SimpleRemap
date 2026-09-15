# loads/saves remaps and turns them into real key/mouse hooks

import json
import sys
import threading
from pathlib import Path

import keyboard
import mouse

import mouse_hook

if getattr(sys, "frozen", False):
    # running as a PyInstaller exe, keep remaps.json next to the exe
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).parent

REMAPS_FILE = APP_DIR / "remaps.json"


def load_remaps():
    if not REMAPS_FILE.exists():
        return []
    try:
        with open(REMAPS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_remaps(remaps):
    with open(REMAPS_FILE, "w") as f:
        json.dump(remaps, f, indent=2)


def _make_key_to_mouse_handler(dest_button):
    # fires when a remapped key (that targets a mouse button) goes up/down
    def handler(event):
        if event.event_type == keyboard.KEY_DOWN:
            mouse.press(button=dest_button)
        else:
            mouse.release(button=dest_button)
        return False

    return handler


def apply_remaps(remaps):
    # wipes old hooks and rebuilds everything from the current remap list
    keyboard.unhook_all()

    mouse_map = {}

    for remap in remaps:
        if not remap.get("enabled", True):
            continue

        from_type = remap["from_type"]
        from_value = remap["from"]
        to_type = remap["to_type"]
        to_value = remap["to"]

        if from_type == "key":
            if to_type == "key":
                keyboard.remap_key(from_value, to_value)
            else:
                keyboard.hook_key(
                    from_value,
                    _make_key_to_mouse_handler(to_value),
                    suppress=True,
                )
        elif from_type == "mouse" and from_value != "left":
            mouse_map[from_value] = (to_type, to_value)

    mouse_hook.set_active_map(mouse_map)
    mouse_hook.start()


def validate_remap(remaps, from_type, from_value, to_type, to_value, editing=None):
    # returns an error message string, or None if the remap is allowed.
    # pass the remap being changed as `editing` to exclude it from the
    # duplicate check (so editing a remap without changing its source works)
    if from_type == "mouse" and from_value == "left":
        return "Left click cannot be remapped."

    if from_type == to_type and from_value == to_value:
        return "Can't remap a key/button to itself."

    for remap in remaps:
        if remap is editing:
            continue
        if remap["from_type"] == from_type and remap["from"] == from_value:
            return "That key/button is already remapped. Delete it first if you want to change it."

    return None


def capture_input(exclude_left, cancel_event):
    # blocks (on a background thread) until the user presses a key or button
    # returns {"type": "key"/"mouse", "value": name}, or None if cancelled
    result = {}
    done = threading.Event()

    def on_key(event):
        if event.event_type == keyboard.KEY_DOWN and not done.is_set():
            result["type"] = "key"
            result["value"] = event.name
            done.set()

    def on_mouse(event):
        if not isinstance(event, mouse.ButtonEvent):
            return
        if event.event_type != mouse.DOWN or done.is_set():
            return
        if exclude_left and event.button == mouse.LEFT:
            return  # not allowed, keep waiting
        result["type"] = "mouse"
        result["value"] = event.button
        done.set()

    keyboard.hook(on_key)
    mouse.hook(on_mouse)

    while not done.is_set() and not cancel_event.is_set():
        done.wait(0.1)

    keyboard.unhook(on_key)
    mouse.unhook(on_mouse)

    return result if result else None
