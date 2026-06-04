"""
Crisp monochrome line icons, drawn at runtime with Pillow.

Replaces the emoji icons (🏠📊🤖🎧⚙️) that rendered inconsistently across
machines and looked toy-like. Icons are drawn as 1.5px-stroke glyphs,
supersampled 4× and downsampled with LANCZOS for clean anti-aliased edges,
then cached by (name, size, color).

Usage:
    from .icons import get_icon
    label = ctk.CTkLabel(parent, text="", image=get_icon("home", 22, PRIMARY))
    button.configure(image=get_icon("settings", 20, "#FFFFFF"))

No new dependencies (Pillow + customtkinter are already required). If an icon
name is unknown it falls back to a small filled dot, so callers never crash.
"""

from __future__ import annotations

import customtkinter as ctk
from PIL import Image, ImageColor, ImageDraw

try:
    from .theme import PRIMARY
except ImportError:  # pragma: no cover - flat import fallback
    PRIMARY = "#1F5563"

_SS = 4  # supersample factor
_CACHE: dict[tuple, ctk.CTkImage] = {}


# ── individual drawings (coords in 0..1, scaled to G) ──────────────────
def _line(d, pts, G, w, color, joint="curve"):
    d.line([(x * G, y * G) for x, y in pts], fill=color, width=w, joint=joint)


def _ellipse(d, box, G, w, color, fill=None):
    d.ellipse([box[0] * G, box[1] * G, box[2] * G, box[3] * G],
              outline=color, width=w, fill=fill)


def _rrect(d, box, G, w, color, radius=0.12, fill=None):
    d.rounded_rectangle(
        [box[0] * G, box[1] * G, box[2] * G, box[3] * G],
        radius=radius * G, outline=color, width=w, fill=fill)


def _dot(d, cx, cy, r, G, color):
    d.ellipse([(cx - r) * G, (cy - r) * G, (cx + r) * G, (cy + r) * G],
              fill=color)


def _home(d, G, w, c):
    _line(d, [(0.5, 0.12), (0.12, 0.45)], G, w, c)
    _line(d, [(0.5, 0.12), (0.88, 0.45)], G, w, c)
    _line(d, [(0.2, 0.4), (0.2, 0.85), (0.8, 0.85), (0.8, 0.4)], G, w, c)
    _line(d, [(0.42, 0.85), (0.42, 0.6), (0.58, 0.6), (0.58, 0.85)], G, w, c)


def _analytics(d, G, w, c):
    _line(d, [(0.15, 0.85), (0.85, 0.85)], G, w, c)        # baseline
    _rrect(d, (0.20, 0.55, 0.36, 0.83), G, w, c, radius=0.03)
    _rrect(d, (0.42, 0.35, 0.58, 0.83), G, w, c, radius=0.03)
    _rrect(d, (0.64, 0.20, 0.80, 0.83), G, w, c, radius=0.03)


def _star(d, G, w, c, cx, cy, R, r):
    import math
    pts = []
    for i in range(8):
        ang = -math.pi / 2 + i * math.pi / 4
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    d.polygon([(x * G, y * G) for x, y in pts], fill=c)


def _autofill(d, G, w, c):
    # sparkles — automation / "auto" fill
    _star(d, G, w, c, 0.42, 0.42, 0.30, 0.11)
    _star(d, G, w, c, 0.74, 0.72, 0.16, 0.06)


def _support(d, G, w, c):
    # headset
    d.arc([0.16 * G, 0.18 * G, 0.84 * G, 0.86 * G], 180, 360, fill=c, width=w)
    _rrect(d, (0.14, 0.5, 0.27, 0.74), G, w, c, radius=0.04, fill=c)
    _rrect(d, (0.73, 0.5, 0.86, 0.74), G, w, c, radius=0.04, fill=c)
    _line(d, [(0.8, 0.72), (0.8, 0.82), (0.55, 0.82)], G, w, c)
    _dot(d, 0.5, 0.82, 0.045, G, c)


def _settings(d, G, w, c):
    # sliders — three tracks, each with a knob
    for y, kx in ((0.3, 0.66), (0.5, 0.38), (0.7, 0.58)):
        _line(d, [(0.16, y), (0.84, y)], G, w, c)
        _dot(d, kx, y, 0.08, G, c)


def _tasks(d, G, w, c):
    _rrect(d, (0.2, 0.15, 0.8, 0.88), G, w, c, radius=0.08)
    _rrect(d, (0.38, 0.08, 0.62, 0.2), G, w, c, radius=0.04)
    for y in (0.4, 0.55, 0.7):
        _line(d, [(0.32, y), (0.68, y)], G, w, c)


def _printer(d, G, w, c):
    _line(d, [(0.28, 0.32), (0.28, 0.14), (0.72, 0.14), (0.72, 0.32)], G, w, c)
    _rrect(d, (0.14, 0.32, 0.86, 0.66), G, w, c, radius=0.06)
    _rrect(d, (0.28, 0.6, 0.72, 0.88), G, w, c, radius=0.04)
    _dot(d, 0.72, 0.45, 0.04, G, c)


def _clock(d, G, w, c):
    _ellipse(d, (0.15, 0.15, 0.85, 0.85), G, w, c)
    _line(d, [(0.5, 0.5), (0.5, 0.28)], G, w, c)
    _line(d, [(0.5, 0.5), (0.66, 0.58)], G, w, c)


def _calendar(d, G, w, c):
    _rrect(d, (0.15, 0.2, 0.85, 0.85), G, w, c, radius=0.07)
    _line(d, [(0.15, 0.36), (0.85, 0.36)], G, w, c)
    _line(d, [(0.32, 0.12), (0.32, 0.26)], G, w, c)
    _line(d, [(0.68, 0.12), (0.68, 0.26)], G, w, c)


def _search(d, G, w, c):
    _ellipse(d, (0.2, 0.2, 0.64, 0.64), G, w, c)
    _line(d, [(0.6, 0.6), (0.84, 0.84)], G, w, c)


def _chevron(d, G, w, c):
    _line(d, [(0.36, 0.3), (0.62, 0.5), (0.36, 0.7)], G, w, c)


def _refresh(d, G, w, c):
    d.arc([0.18 * G, 0.18 * G, 0.82 * G, 0.82 * G], 60, 330, fill=c, width=w)
    _line(d, [(0.78, 0.18), (0.82, 0.36), (0.64, 0.34)], G, w, c)


def _plus(d, G, w, c):
    _line(d, [(0.5, 0.2), (0.5, 0.8)], G, w, c)
    _line(d, [(0.2, 0.5), (0.8, 0.5)], G, w, c)


def _revenue(d, G, w, c):
    # coin with a simple "$" stroke
    _ellipse(d, (0.18, 0.18, 0.82, 0.82), G, w, c)
    _line(d, [(0.5, 0.28), (0.5, 0.72)], G, w, c)
    d.arc([0.36 * G, 0.3 * G, 0.64 * G, 0.5 * G], 20, 250, fill=c, width=w)
    d.arc([0.36 * G, 0.5 * G, 0.64 * G, 0.7 * G], 200, 70, fill=c, width=w)


def _target(d, G, w, c):
    _ellipse(d, (0.15, 0.15, 0.85, 0.85), G, w, c)
    _ellipse(d, (0.32, 0.32, 0.68, 0.68), G, w, c)
    _dot(d, 0.5, 0.5, 0.07, G, c)


def _scale(d, G, w, c):
    _line(d, [(0.5, 0.16), (0.5, 0.78)], G, w, c)
    _line(d, [(0.2, 0.3), (0.8, 0.3)], G, w, c)
    d.arc([0.1 * G, 0.3 * G, 0.4 * G, 0.6 * G], 0, 180, fill=c, width=w)
    d.arc([0.6 * G, 0.3 * G, 0.9 * G, 0.6 * G], 0, 180, fill=c, width=w)
    _line(d, [(0.32, 0.82), (0.68, 0.82)], G, w, c)


def _trophy(d, G, w, c):
    _line(d, [(0.32, 0.16), (0.68, 0.16)], G, w, c)
    _line(d, [(0.34, 0.16), (0.36, 0.48), (0.64, 0.48), (0.66, 0.16)], G, w, c)
    d.arc([0.62 * G, 0.16 * G, 0.86 * G, 0.42 * G], 270, 90, fill=c, width=w)
    d.arc([0.14 * G, 0.16 * G, 0.38 * G, 0.42 * G], 90, 270, fill=c, width=w)
    _line(d, [(0.5, 0.48), (0.5, 0.66)], G, w, c)
    _line(d, [(0.36, 0.84), (0.64, 0.84)], G, w, c)
    _line(d, [(0.42, 0.66), (0.58, 0.66)], G, w, c)


def _meals(d, G, w, c):
    # fork + knife
    _line(d, [(0.32, 0.16), (0.32, 0.84)], G, w, c)
    _line(d, [(0.24, 0.16), (0.24, 0.38)], G, w, c)
    _line(d, [(0.4, 0.16), (0.4, 0.38)], G, w, c)
    _line(d, [(0.24, 0.38), (0.4, 0.38)], G, w, c)
    _line(d, [(0.66, 0.16), (0.66, 0.84)], G, w, c)
    d.arc([0.6 * G, 0.16 * G, 0.78 * G, 0.56 * G], 180, 360, fill=c, width=w)


def _trash(d, G, w, c):
    _line(d, [(0.22, 0.26), (0.78, 0.26)], G, w, c)
    _line(d, [(0.4, 0.26), (0.43, 0.16), (0.57, 0.16), (0.6, 0.26)], G, w, c)
    _line(d, [(0.28, 0.26), (0.32, 0.84), (0.68, 0.84), (0.72, 0.26)], G, w, c)
    _line(d, [(0.42, 0.4), (0.44, 0.72)], G, w, c)
    _line(d, [(0.58, 0.4), (0.56, 0.72)], G, w, c)


def _check(d, G, w, c):
    _line(d, [(0.22, 0.52), (0.42, 0.72), (0.78, 0.3)], G, w, c)


_DRAWERS = {
    "home": _home,
    "trash": _trash,
    "check": _check,
    "analytics": _analytics,
    "autofill": _autofill,
    "support": _support,
    "settings": _settings,
    "tasks": _tasks,
    "printer": _printer,
    "clock": _clock,
    "calendar": _calendar,
    "search": _search,
    "chevron": _chevron,
    "refresh": _refresh,
    "plus": _plus,
    "revenue": _revenue,
    "target": _target,
    "scale": _scale,
    "trophy": _trophy,
    "meals": _meals,
}


def get_icon(name: str, size: int = 20, color: str = PRIMARY) -> ctk.CTkImage:
    """Return a cached CTkImage of the named line icon, tinted ``color``."""
    key = (name, size, color)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    G = size * _SS
    w = max(2, round(size * 0.085) * _SS)
    rgb = ImageColor.getrgb(color)
    stroke = rgb + (255,)

    img = Image.new("RGBA", (G, G), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    drawer = _DRAWERS.get(name)
    if drawer is None:
        _dot(d, 0.5, 0.5, 0.18, G, stroke)
    else:
        drawer(d, G, w, stroke)

    img = img.resize((size, size), Image.LANCZOS)
    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    _CACHE[key] = ctk_img
    return ctk_img
