# reusable windows 11 style tkinter widgets (canvas-drawn, rounded)

import math
import tkinter as tk

from PIL import Image, ImageDraw, ImageTk

from theme import COLORS, FONT_FAMILY

# tkinter canvas shapes have no anti-aliasing, so rounded corners and
# circles come out visibly jagged at these small sizes. ToggleSwitch and
# Checkbox render themselves as PIL images instead: draw at a higher
# resolution, then downscale with LANCZOS resampling for smooth edges.
SUPERSAMPLE = 4


def _hex_to_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _lerp_rgb(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _round_rect_points(x1, y1, x2, y2, r):
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


def draw_round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    return canvas.create_polygon(
        _round_rect_points(x1, y1, x2, y2, r), smooth=True, **kwargs
    )


class ToggleSwitch(tk.Label):
    """on/off pill switch with a sliding knob animation"""

    WIDTH = 40
    HEIGHT = 22
    STEPS = 12
    STEP_MS = 12

    def __init__(self, parent, value=True, command=None, bg=None, **kwargs):
        super().__init__(
            parent,
            bg=bg or parent["bg"],
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.value = value
        self.command = command
        self._progress = 1.0 if value else 0.0
        self._animating = False
        self._photo = None
        self.bind("<Button-1>", self._on_click)
        self._render(self._progress)

    def _on_click(self, event):
        if self._animating:
            return
        self.set(not self.value, animate=True)

    def set(self, value, animate=False):
        target = 1.0 if value else 0.0
        self.value = value

        if not animate or self._progress == target:
            self._progress = target
            self._render(target)
            if self.command:
                self.command(self.value)
            return

        self._animating = True
        start = self._progress
        steps = self.STEPS

        def step(i=0):
            t = i / steps
            eased = t * t * (3 - 2 * t)  # smoothstep
            self._progress = start + (target - start) * eased
            self._render(self._progress)
            if i < steps:
                self.after(self.STEP_MS, lambda: step(i + 1))
            else:
                self._progress = target
                self._animating = False
                if self.command:
                    self.command(self.value)

        step()

    def _render(self, progress):
        s = SUPERSAMPLE
        w, h = self.WIDTH * s, self.HEIGHT * s
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        off_rgb = _hex_to_rgb(COLORS["toggle_off"])
        on_rgb = _hex_to_rgb(COLORS["accent"])
        pill_rgb = _lerp_rgb(off_rgb, on_rgb, progress)

        pad = 2 * s
        r = h / 2 - pad
        draw.rounded_rectangle([pad, pad, w - pad, h - pad], radius=r, fill=pill_rgb)

        knob_r = r - 3 * s
        cy = h / 2
        cx = (pad + r) + (w - 2 * pad - 2 * r) * progress
        draw.ellipse([cx - knob_r, cy - knob_r, cx + knob_r, cy + knob_r], fill="white")

        img = img.resize((self.WIDTH, self.HEIGHT), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.config(image=self._photo)


class Checkbox(tk.Label):
    """clean, anti-aliased checkbox"""

    SIZE = 18

    def __init__(self, parent, value=False, command=None, bg=None, **kwargs):
        super().__init__(
            parent,
            bg=bg or parent["bg"],
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.value = value
        self.command = command
        self._photo = None
        self.bind("<Button-1>", self._on_click)
        self._render()

    def _on_click(self, event):
        self.set(not self.value)
        if self.command:
            self.command(self.value)

    def set(self, value):
        self.value = value
        self._render()

    def _render(self):
        s = SUPERSAMPLE
        size = self.SIZE * s
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        r = size * 0.22

        if self.value:
            draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=COLORS["accent"])
            lw = max(2, round(size * 0.09))
            p1 = (size * 0.23, size * 0.52)
            p2 = (size * 0.42, size * 0.72)
            p3 = (size * 0.80, size * 0.28)
            draw.line([p1, p2, p3], fill="white", width=lw, joint="curve")
            for p in (p1, p3):
                draw.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill="white")
        else:
            border = max(2, round(size * 0.085))
            draw.rounded_rectangle(
                [border / 2, border / 2, size - 1 - border / 2, size - 1 - border / 2],
                radius=r, outline=COLORS["border"], width=border,
            )

        img = img.resize((self.SIZE, self.SIZE), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self.config(image=self._photo)


class RoundButton(tk.Canvas):
    """win11 style rounded button, style is 'default', 'accent' or 'danger'"""

    def __init__(
        self, parent, text, command=None, style="default",
        width=None, height=32, font=None, bg=None, **kwargs
    ):
        self.text = text
        self.command = command
        self.style = style
        self.height = height
        self._font = font or (FONT_FAMILY, 10)

        probe = tk.Label(parent, text=text, font=self._font)
        probe.update_idletasks()
        text_w = probe.winfo_reqwidth()
        probe.destroy()
        self.width = width or (text_w + 28)

        super().__init__(
            parent,
            width=self.width,
            height=self.height,
            bg=bg or parent["bg"],
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self._pressed = False
        self._hover = False
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self._draw()

    def _colors(self):
        if self.style == "accent":
            return COLORS["accent"], COLORS["accent_hover"], COLORS["accent_pressed"], "white"
        if self.style == "danger":
            return COLORS["danger"], COLORS["danger_hover"], COLORS["danger_hover"], "white"
        return COLORS["card_bg"], COLORS["row_hover"], COLORS["border"], COLORS["text"]

    def _draw(self):
        self.delete("all")
        base, hover, press, fg = self._colors()
        if self._pressed:
            fill = press
        elif self._hover:
            fill = hover
        else:
            fill = base
        outline = fill if self.style != "default" else COLORS["border"]
        draw_round_rect(self, 1, 1, self.width - 1, self.height - 1, 6, fill=fill, outline=outline)
        self.create_text(self.width / 2, self.height / 2, text=self.text, font=self._font, fill=fg)

    def _on_enter(self, event):
        self._hover = True
        self._draw()

    def _on_leave(self, event):
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, event):
        self._pressed = True
        self._draw()

    def _on_release(self, event):
        self._pressed = False
        self._draw()
        if self.command and 0 <= event.x <= self.width and 0 <= event.y <= self.height:
            self.command()


def _lerp_color(c1, c2, t):
    r = int(c1[0] + (c2[0] - c1[0]) * t)
    g = int(c1[1] + (c2[1] - c1[1]) * t)
    b = int(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


class ThemeToggle(tk.Canvas):
    """round button that flips between a sun and a moon icon, animated"""

    SIZE = 32
    STEPS = 16
    STEP_MS = 12

    SUN_BG = (0xFD, 0xB8, 0x13)
    MOON_BG = (0x2B, 0x3A, 0x67)
    SUN_ICON = "#fff4d6"
    MOON_ICON = "#f4f1e8"

    def __init__(self, parent, is_dark, command=None, bg=None, **kwargs):
        super().__init__(
            parent,
            width=self.SIZE,
            height=self.SIZE,
            bg=bg or parent["bg"],
            highlightthickness=0,
            cursor="hand2",
            **kwargs,
        )
        self.is_dark = is_dark
        self.command = command
        self._animating = False
        self._scale = 1.0
        start = self.MOON_BG if is_dark else self.SUN_BG
        self._bg_color = _lerp_color(start, start, 0)
        self.bind("<Button-1>", self._on_click)
        self._render()

    def _on_click(self, event):
        if self._animating:
            return
        target_dark = not self.is_dark
        start_bg = self.MOON_BG if self.is_dark else self.SUN_BG
        end_bg = self.MOON_BG if target_dark else self.SUN_BG
        showing_dark = self.is_dark
        self._animating = True
        steps = self.STEPS

        def step(i=0):
            t = i / steps
            self._scale = abs(math.cos(t * math.pi))
            self._bg_color = _lerp_color(start_bg, end_bg, t)
            nonlocal showing_dark
            if t >= 0.5 and showing_dark != target_dark:
                showing_dark = target_dark
            self.is_dark = showing_dark
            self._render()
            if i < steps:
                self.after(self.STEP_MS, lambda: step(i + 1))
            else:
                self.is_dark = target_dark
                self._scale = 1.0
                self._animating = False
                if self.command:
                    self.command(self.is_dark)

        step()

    def _render(self):
        self.delete("all")
        s = self.SIZE
        cx = cy = s / 2
        r = s / 2 - 2
        scale = self._scale
        icon_color = self.MOON_ICON if self.is_dark else self.SUN_ICON

        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=self._bg_color, outline=self._bg_color)

        icon_r = r * 0.42
        if self.is_dark:
            outer = icon_r * 1.3
            offset = outer * 0.6 * scale
            self.create_oval(
                cx - outer * scale, cy - outer, cx + outer * scale, cy + outer,
                fill=icon_color, outline=icon_color,
            )
            self.create_oval(
                cx - outer * scale + offset, cy - outer * 0.95,
                cx + outer * scale + offset, cy + outer * 0.95,
                fill=self._bg_color, outline=self._bg_color,
            )
        else:
            self.create_oval(
                cx - icon_r * scale, cy - icon_r, cx + icon_r * scale, cy + icon_r,
                fill=icon_color, outline=icon_color,
            )
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                x1 = cx + math.cos(rad) * icon_r * 1.5 * scale
                y1 = cy + math.sin(rad) * icon_r * 1.5
                x2 = cx + math.cos(rad) * icon_r * 2.1 * scale
                y2 = cy + math.sin(rad) * icon_r * 2.1
                self.create_line(x1, y1, x2, y2, fill=icon_color, width=2, capstyle=tk.ROUND)
