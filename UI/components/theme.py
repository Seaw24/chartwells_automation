"""
Chartwells Automation — Unified Design System
=============================================
Single source of truth for the whole app's look & feel.

Every screen used to define its own colors (sidebar purple, autofill teal,
analytics navy, tasks purple) which made the product feel like four different
apps. This module fixes that: one Deep-Teal "Chartwells" identity, shared
fonts, and small formatting/styling helpers.

Other modules should import from here rather than hard-coding hex values.
"""

from __future__ import annotations

# ══════════════════════════════════════════════════════════════════════
#  PALETTE — Deep Teal (Chartwells brand)
# ══════════════════════════════════════════════════════════════════════
PRIMARY        = "#1F5563"   # deep teal — sidebar, primary buttons, active tab
PRIMARY_DARK   = "#15414D"   # hover / pressed
PRIMARY_LIGHT  = "#DCEFF3"   # tint fills (icon chips, active pill)
PRIMARY_SUBTLE = "#EFF7F9"   # hover tint on transparent controls
ACCENT         = "#2E7D8F"   # secondary teal — links, highlights
ACCENT_LIGHT   = "#D6EAEF"
ACCENT_HOVER   = "#256777"

# Neutrals
BG          = "#F4F7F9"   # app background
BG_SUBTLE   = "#EDF1F4"   # alt rows / muted fills
CARD        = "#FFFFFF"
BORDER      = "#E2E8EC"
TEXT        = "#16232B"
TEXT_SEC    = "#5A6873"
TEXT_MUTED  = "#8B98A3"

# Semantic — finance up/down + status
GREEN       = "#1F8A5B"
GREEN_BG    = "#E6F6EE"
GREEN_LIGHT = "#C8ECD7"
RED         = "#C0392B"
RED_BG      = "#FBE9E7"
RED_LIGHT   = "#F6D2CC"
AMBER       = "#B7791F"
AMBER_BG    = "#FBF1DE"
BLUE        = "#2E7D8F"   # alias to accent (kept for analytics references)
BLUE_BG     = "#D6EAEF"
BLUE_LIGHT  = "#C2DFE6"

# Scrollbar
SCROLL       = "#C3CDD4"
SCROLL_HOVER = "#9AAAB4"

# Typography — resolve to a font that actually exists on this OS so we get a
# native look everywhere and matplotlib stops spamming "findfont" warnings.
def _resolve_font(candidates, default):
    try:
        from matplotlib import font_manager
        installed = {f.name for f in font_manager.fontManager.ttflist}
    except Exception:
        installed = set()
    for name in candidates:
        if name in installed:
            return name
    return default


FONT = _resolve_font(
    ["Segoe UI", "Helvetica Neue", "Helvetica", "Arial", "Roboto"],
    "DejaVu Sans")
FONT_MONO = _resolve_font(
    ["Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", "Courier New"],
    "monospace")

# Categorical chart palette — distinguishable, on-brand, no neon
CHART_PALETTE = [
    PRIMARY,    # deep teal
    "#3E92A3",  # mid teal
    "#C0392B",  # red
    "#B7791F",  # amber
    "#6B5B95",  # muted violet
    "#1F8A5B",  # green
    "#9AAAB4",  # slate
    "#D98C5F",  # terracotta
]


# ══════════════════════════════════════════════════════════════════════
#  FORMATTING HELPERS
# ══════════════════════════════════════════════════════════════════════
def money(value, compact: bool = True) -> str:
    """Format a currency value.

    compact=True  → "$0", "$945", "$1.2k", "$3.4M"  (for axes / chips)
    compact=False → "$1,234.56"                      (for tables / details)
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "$0"

    if not compact:
        return f"${v:,.2f}"

    neg = v < 0
    v = abs(v)
    if v >= 1_000_000:
        s = f"${v / 1_000_000:.1f}M".replace(".0M", "M")
    elif v >= 1_000:
        s = f"${v / 1_000:.1f}k".replace(".0k", "k")
    else:
        s = f"${v:,.0f}"
    return f"-{s}" if neg else s


def money_axis_formatter():
    """A matplotlib FuncFormatter that renders compact dollars on an axis."""
    import matplotlib.ticker as mticker
    return mticker.FuncFormatter(lambda x, _: money(x, compact=True))


# ══════════════════════════════════════════════════════════════════════
#  MATPLOTLIB STYLING
# ══════════════════════════════════════════════════════════════════════
_CHART_STYLE_APPLIED = False


def apply_chart_style() -> None:
    """Apply consistent matplotlib rcParams once for the whole app."""
    global _CHART_STYLE_APPLIED
    if _CHART_STYLE_APPLIED:
        return
    import matplotlib as mpl

    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [FONT, "DejaVu Sans", "Arial", "sans-serif"],
        "font.size": 9.5,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlecolor": TEXT,
        "axes.labelcolor": TEXT_SEC,
        "axes.edgecolor": BORDER,
        "axes.linewidth": 1.0,
        "axes.facecolor": CARD,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "grid.color": BORDER,
        "grid.linewidth": 0.7,
        "grid.alpha": 0.6,
        "xtick.color": TEXT_SEC,
        "ytick.color": TEXT_SEC,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "text.color": TEXT,
        "figure.facecolor": CARD,
        "figure.dpi": 100,
        "legend.frameon": False,
        "legend.fontsize": 9.5,
    })
    _CHART_STYLE_APPLIED = True
