# simple remap - main window
# lets you remap keys/mouse buttons 1:1 and turn remaps on/off

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pystray
from PIL import Image

import remap_engine
import theme
import winutil
from theme import COLORS, FONT_FAMILY, FONT_NORMAL, FONT_SMALL, FONT_TITLE
from widgets import Checkbox, RoundButton, ThemeToggle, ToggleSwitch

MOUSE_DISPLAY_NAMES = {
    "left": "Left Click",
    "right": "Right Click",
    "middle": "Middle Click",
    "x": "Mouse Button 4",
    "x2": "Mouse Button 5",
}


def display_name(kind, value):
    if kind == "mouse":
        return MOUSE_DISPLAY_NAMES.get(value, value)
    return value.title()


def resource_path(name):
    # bundled read-only assets: next to the script, or inside the
    # pyinstaller temp extraction dir when running as a frozen exe
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent
    return str(base / name)


def load_icon_image(size=64):
    img = Image.open(resource_path("icon.ico")).convert("RGBA")
    if img.size != (size, size):
        img = img.resize((size, size), Image.LANCZOS)
    return img


class AddRemapDialog(tk.Toplevel):
    def __init__(self, parent, dialog_title, on_done):
        super().__init__(parent)
        self.title(dialog_title)
        self.geometry("360x160")
        self.resizable(False, False)
        self.configure(bg=COLORS["bg"])
        self.on_done = on_done
        self.cancel_event = threading.Event()
        self.result_queue = queue.Queue()

        self.from_result = None
        self.step = "from"  # "from" then "to"

        self.label = tk.Label(
            self,
            text="Press the key or mouse button you want to remap.\n(left click cannot be used)",
            wraplength=310,
            justify="center",
            font=FONT_NORMAL,
            bg=COLORS["bg"],
            fg=COLORS["text"],
        )
        self.label.pack(pady=24)

        RoundButton(self, "Cancel", command=self.cancel, bg=COLORS["bg"]).pack(pady=5)

        self.protocol("WM_DELETE_WINDOW", self.cancel)

        self.start_capture(exclude_left=True)

    def start_capture(self, exclude_left):
        thread = threading.Thread(
            target=self._capture_worker,
            args=(exclude_left,),
            daemon=True,
        )
        thread.start()
        self.after(100, self.poll_queue)

    def _capture_worker(self, exclude_left):
        result = remap_engine.capture_input(exclude_left, self.cancel_event)
        self.result_queue.put(result)

    def poll_queue(self):
        if not self.winfo_exists():
            return  # dialog was closed already

        try:
            result = self.result_queue.get_nowait()
        except queue.Empty:
            if not self.cancel_event.is_set():
                self.after(100, self.poll_queue)
            return

        if result is None:
            return  # cancelled

        if self.step == "from":
            self.from_result = result
            self.step = "to"
            name = display_name(result["type"], result["value"])
            self.label.config(
                text=f"Remapping: {name}\n\nNow press the key or mouse button\nyou want it remapped TO."
            )
            self.start_capture(exclude_left=False)
        else:
            self.finish(result)

    def finish(self, to_result):
        self.on_done(self.from_result, to_result)
        self.destroy()

    def cancel(self):
        self.cancel_event.set()
        self.destroy()


class RemapRow(tk.Frame):
    """one row in the remap list: select checkbox, name, on/off toggle, delete"""

    def __init__(self, parent, remap, on_select, on_toggle, on_edit, on_delete):
        super().__init__(parent, bg=COLORS["card_bg"])
        self.remap = remap
        self.selected = False
        self._on_select = on_select
        self._on_toggle = on_toggle

        self.checkbox = Checkbox(
            self, value=False, command=self._select_changed, bg=COLORS["card_bg"]
        )
        self.checkbox.pack(side="left", padx=(12, 10), pady=10)

        from_name = display_name(remap["from_type"], remap["from"])
        to_name = display_name(remap["to_type"], remap["to"])
        self.label = tk.Label(
            self,
            text=f"{from_name}   →   {to_name}",
            font=FONT_NORMAL,
            bg=COLORS["card_bg"],
            fg=COLORS["text"],
            anchor="w",
        )
        self.label.pack(side="left", fill="x", expand=True, pady=10)

        self.delete_button = RoundButton(
            self, "Delete", command=lambda: on_delete(self),
            style="default", height=26, font=FONT_SMALL, bg=COLORS["card_bg"],
        )
        self.delete_button.pack(side="right", padx=(10, 12), pady=8)

        self.edit_button = RoundButton(
            self, "Edit", command=lambda: on_edit(self),
            style="default", height=26, font=FONT_SMALL, bg=COLORS["card_bg"],
        )
        self.edit_button.pack(side="right", padx=(10, 6), pady=8)

        self.toggle = ToggleSwitch(
            self, value=remap.get("enabled", True),
            command=self._toggle_changed, bg=COLORS["card_bg"],
        )
        self.toggle.pack(side="right", padx=(10, 0), pady=8)

        for widget in (self, self.label):
            widget.configure(cursor="hand2")
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<Button-1>", self._on_row_click)

    def _on_row_click(self, event):
        self.checkbox.set(not self.checkbox.value)
        self._select_changed(self.checkbox.value)

    def _on_enter(self, event):
        self._set_bg(COLORS["row_hover"])

    def _on_leave(self, event):
        self._set_bg(COLORS["card_bg"])

    def _set_bg(self, color):
        self.configure(bg=color)
        self.label.configure(bg=color)
        self.checkbox.configure(bg=color)
        self.toggle.configure(bg=color)
        self.edit_button.configure(bg=color)
        self.delete_button.configure(bg=color)

    def _select_changed(self, value):
        self.selected = value
        self._on_select()

    def _toggle_changed(self, value):
        self.remap["enabled"] = value
        self._on_toggle()

    def set_selected(self, value):
        self.selected = value
        self.checkbox.set(value)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Remap")
        self.geometry("560x480")
        self.minsize(520, 360)
        self.configure(bg=COLORS["bg"])

        try:
            self.iconbitmap(resource_path("icon.ico"))
        except tk.TclError:
            pass

        self.remaps = remap_engine.load_remaps()
        remap_engine.apply_remaps(self.remaps)
        self.rows = []
        self.tray_icon = None
        self.admin_banner = None
        self._admin_banner_dismissed = False

        self._build_ui()
        self.refresh_list()

    def _on_theme_toggle(self, is_dark_now):
        theme.set_theme("dark" if is_dark_now else "light")
        self._rebuild_ui()

    def _rebuild_ui(self):
        selected_ids = {id(row.remap) for row in self.rows if row.selected}
        scroll_pos = self.list_canvas.yview()[0]

        self.container.destroy()
        self.configure(bg=COLORS["bg"])
        self._build_ui()
        self.refresh_list()

        for row in self.rows:
            if id(row.remap) in selected_ids:
                row.set_selected(True)
        self.update_select_all_state()
        self.list_canvas.yview_moveto(scroll_pos)

    def _style_scrollbar(self):
        # ttk's default windows theme ignores custom colors, so use "clam"
        # to get a flat scrollbar that matches the current light/dark theme
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Remap.Vertical.TScrollbar",
            background=COLORS["border"],
            troughcolor=COLORS["card_bg"],
            bordercolor=COLORS["card_bg"],
            arrowcolor=COLORS["text_secondary"],
            relief="flat",
            arrowsize=12,
        )
        style.map(
            "Remap.Vertical.TScrollbar",
            background=[("active", COLORS["accent"])],
        )

    def _labeled_checkbox(self, parent, text, value, command):
        box = Checkbox(parent, value=value, command=command, bg=parent["bg"])
        label = tk.Label(
            parent, text=text, font=FONT_SMALL,
            bg=parent["bg"], fg=COLORS["text_secondary"], cursor="hand2",
        )

        def on_label_click(event):
            new_value = not box.value
            box.set(new_value)
            command(new_value)

        label.bind("<Button-1>", on_label_click)
        return box, label

    def _build_admin_banner(self):
        bg = COLORS["accent"]
        self.admin_banner = tk.Frame(self.container, bg=bg)
        self.admin_banner.pack(fill="x", pady=(0, 10))
        tk.Label(
            self.admin_banner,
            text="⚠ Not running as administrator — some apps/games may ignore remaps.",
            font=FONT_SMALL, bg=bg, fg="white", anchor="w",
        ).pack(side="left", padx=12, pady=7, fill="x", expand=True)
        dismiss = tk.Label(
            self.admin_banner, text="Dismiss", font=(FONT_FAMILY, 9, "underline"),
            bg=bg, fg="white", cursor="hand2",
        )
        dismiss.pack(side="right", padx=12, pady=7)
        dismiss.bind("<Button-1>", lambda e: self._dismiss_admin_banner())

    def _dismiss_admin_banner(self):
        self._admin_banner_dismissed = True
        if self.admin_banner is not None:
            self.admin_banner.destroy()
            self.admin_banner = None

    def _build_ui(self):
        self.container = tk.Frame(self, bg=COLORS["bg"], padx=18, pady=16)
        self.container.pack(fill="both", expand=True)

        header = tk.Frame(self.container, bg=COLORS["bg"])
        header.pack(fill="x", pady=(0, 12))
        tk.Label(
            header, text="Simple Remap", font=FONT_TITLE,
            bg=COLORS["bg"], fg=COLORS["text"],
        ).pack(side="left")
        ThemeToggle(
            header, is_dark=theme.is_dark(), command=self._on_theme_toggle,
        ).pack(side="right")

        toolbar = tk.Frame(self.container, bg=COLORS["bg"])
        toolbar.pack(fill="x", pady=(0, 10))
        RoundButton(
            toolbar, "+  Add Remap", command=self.add_remap, style="accent",
        ).pack(side="left")
        RoundButton(
            toolbar, "Toggle On/Off", command=self.toggle_selected,
        ).pack(side="left", padx=(8, 0))
        RoundButton(
            toolbar, "Delete", command=self.delete_selected, style="danger",
        ).pack(side="left", padx=(8, 0))
        RoundButton(
            toolbar, "Minimize to Tray", command=self.minimize_to_tray,
        ).pack(side="right")

        if not winutil.is_admin() and not self._admin_banner_dismissed:
            self._build_admin_banner()

        select_row = tk.Frame(self.container, bg=COLORS["bg"])
        select_row.pack(fill="x", pady=(0, 6))

        self.select_all_box, select_all_label = self._labeled_checkbox(
            select_row, "Select All", False, self.toggle_select_all,
        )
        self.select_all_box.pack(side="left", padx=(2, 8))
        select_all_label.pack(side="left")

        self.autostart_box, autostart_label = self._labeled_checkbox(
            select_row, "Start with Windows", winutil.autostart_is_enabled(), self._on_autostart_toggle,
        )
        autostart_label.pack(side="right")
        self.autostart_box.pack(side="right", padx=(0, 8))

        list_frame = tk.Frame(
            self.container, bg=COLORS["card_bg"],
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        list_frame.pack(fill="both", expand=True)

        self._style_scrollbar()
        self.list_canvas = tk.Canvas(
            list_frame, bg=COLORS["card_bg"], highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", style="Remap.Vertical.TScrollbar",
            command=self.list_canvas.yview,
        )
        self.list_canvas.configure(yscrollcommand=scrollbar.set)
        self.list_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.list_body = tk.Frame(self.list_canvas, bg=COLORS["card_bg"])
        self._list_window = self.list_canvas.create_window(
            (0, 0), window=self.list_body, anchor="nw"
        )
        self.list_body.bind(
            "<Configure>",
            lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")),
        )
        self.list_canvas.bind(
            "<Configure>",
            lambda e: self.list_canvas.itemconfig(self._list_window, width=e.width),
        )
        self.list_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.empty_label = tk.Label(
            self.list_body, text="No remaps yet. Click “+ Add Remap” to create one.",
            font=FONT_NORMAL, bg=COLORS["card_bg"], fg=COLORS["text_secondary"],
        )

    def _on_mousewheel(self, event):
        # only scroll the remap list when the cursor is actually over it,
        # and never past the top/bottom of the content
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget is not self.list_canvas:
            widget = widget.master
        if widget is None:
            return

        top, bottom = self.list_canvas.yview()
        delta = int(-1 * (event.delta / 120))
        if delta < 0 and top <= 0.0:
            return
        if delta > 0 and bottom >= 1.0:
            return
        self.list_canvas.yview_scroll(delta, "units")

    def refresh_list(self):
        for row in self.rows:
            row.destroy()
        self.rows = []
        self.empty_label.pack_forget()
        self.list_canvas.yview_moveto(0)

        if not self.remaps:
            self.empty_label.pack(pady=30)
            self.select_all_box.set(False)
            return

        for i, remap in enumerate(self.remaps):
            row = RemapRow(
                self.list_body, remap,
                on_select=self.update_select_all_state,
                on_toggle=self._on_row_toggled,
                on_edit=self.edit_remap,
                on_delete=self._delete_row,
            )
            row.pack(fill="x")
            if i < len(self.remaps) - 1:
                tk.Frame(self.list_body, bg=COLORS["border"], height=1).pack(fill="x")
            self.rows.append(row)

        self.select_all_box.set(False)

    def update_select_all_state(self):
        all_selected = bool(self.rows) and all(r.selected for r in self.rows)
        self.select_all_box.set(all_selected)

    def toggle_select_all(self, value):
        for row in self.rows:
            row.set_selected(value)

    def _on_autostart_toggle(self, enabled):
        try:
            winutil.set_autostart_enabled(enabled)
        except OSError:
            messagebox.showerror(
                "Start with Windows",
                "Couldn't update the Windows startup setting.",
            )
            self.autostart_box.set(not enabled)

    def _on_row_toggled(self):
        remap_engine.save_remaps(self.remaps)
        remap_engine.apply_remaps(self.remaps)

    def _delete_row(self, row):
        if not messagebox.askyesno("Delete remap", "Delete this remap?"):
            return
        self.remaps.remove(row.remap)
        remap_engine.save_remaps(self.remaps)
        remap_engine.apply_remaps(self.remaps)
        self.refresh_list()

    def add_remap(self):
        AddRemapDialog(self, "Add Remap", self.save_new_remap)

    def save_new_remap(self, from_result, to_result):
        error = remap_engine.validate_remap(
            self.remaps,
            from_result["type"], from_result["value"],
            to_result["type"], to_result["value"],
        )
        if error:
            messagebox.showerror("Can't add remap", error)
            return

        self.remaps.append(
            {
                "from_type": from_result["type"],
                "from": from_result["value"],
                "to_type": to_result["type"],
                "to": to_result["value"],
                "enabled": True,
            }
        )
        remap_engine.save_remaps(self.remaps)
        remap_engine.apply_remaps(self.remaps)
        self.refresh_list()

    def edit_remap(self, row):
        AddRemapDialog(
            self, "Edit Remap",
            lambda from_result, to_result: self.save_edited_remap(row.remap, from_result, to_result),
        )

    def save_edited_remap(self, remap, from_result, to_result):
        error = remap_engine.validate_remap(
            self.remaps,
            from_result["type"], from_result["value"],
            to_result["type"], to_result["value"],
            editing=remap,
        )
        if error:
            messagebox.showerror("Can't save remap", error)
            return

        remap["from_type"] = from_result["type"]
        remap["from"] = from_result["value"]
        remap["to_type"] = to_result["type"]
        remap["to"] = to_result["value"]
        remap_engine.save_remaps(self.remaps)
        remap_engine.apply_remaps(self.remaps)
        self.refresh_list()

    def get_selected_rows(self):
        return [row for row in self.rows if row.selected]

    def toggle_selected(self):
        selected = self.get_selected_rows()
        if not selected:
            messagebox.showinfo("No selection", "Select at least one remap first.")
            return
        for row in selected:
            new_value = not row.remap.get("enabled", True)
            row.remap["enabled"] = new_value
            row.toggle.set(new_value)
        remap_engine.save_remaps(self.remaps)
        remap_engine.apply_remaps(self.remaps)

    def delete_selected(self):
        selected = self.get_selected_rows()
        if not selected:
            messagebox.showinfo("No selection", "Select at least one remap first.")
            return
        count = len(selected)
        label = "this remap" if count == 1 else f"these {count} remaps"
        if not messagebox.askyesno("Delete remap", f"Delete {label}?"):
            return
        for row in selected:
            self.remaps.remove(row.remap)
        remap_engine.save_remaps(self.remaps)
        remap_engine.apply_remaps(self.remaps)
        self.refresh_list()

    def minimize_to_tray(self):
        self.withdraw()
        image = load_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Show", self.show_from_tray, default=True),
            pystray.MenuItem("Exit", self.exit_from_tray),
        )
        icon = pystray.Icon("simple_remap", image, "Simple Remap", menu)
        self.tray_icon = icon
        icon.run()  # blocks here until icon.stop() is called

    def show_from_tray(self, icon):
        icon.stop()
        self.after(0, self.deiconify)

    def exit_from_tray(self, icon):
        icon.stop()
        self.after(0, self.destroy)


if __name__ == "__main__":
    winutil.enable_dpi_awareness()

    if not winutil.acquire_single_instance_lock():
        messagebox.showinfo("Simple Remap", "Simple Remap is already running.")
        sys.exit(0)

    app = App()
    app.mainloop()
