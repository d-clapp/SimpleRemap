# color palettes for light/dark mode
# COLORS gets mutated in place on switch, not reassigned, so modules that
# did "from theme import COLORS" keep seeing live values

THEMES = {
    "dark": {
        "bg": "#202020",
        "card_bg": "#2b2b2b",
        "border": "#3a3a3a",
        "row_hover": "#343434",
        "text": "#f2f2f2",
        "text_secondary": "#a6a6a6",
        "accent": "#4cc2ff",
        "accent_hover": "#6ecfff",
        "accent_pressed": "#3aa8e0",
        "toggle_off": "#5a5a5a",
        "danger": "#ff6961",
        "danger_hover": "#ff8078",
    },
    "light": {
        "bg": "#f3f3f3",
        "card_bg": "#fbfbfb",
        "border": "#e5e5e5",
        "row_hover": "#f5f5f5",
        "text": "#1a1a1a",
        "text_secondary": "#5f5f5f",
        "accent": "#0067c0",
        "accent_hover": "#1975c8",
        "accent_pressed": "#005ba1",
        "toggle_off": "#8a8a8a",
        "danger": "#c42b1c",
        "danger_hover": "#d13438",
    },
}

FONT_FAMILY = "Segoe UI"
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_TITLE = (FONT_FAMILY, 15, "bold")

_mode = "dark"
COLORS = dict(THEMES[_mode])


def is_dark():
    return _mode == "dark"


def set_theme(mode):
    global _mode
    _mode = mode
    COLORS.clear()
    COLORS.update(THEMES[mode])
