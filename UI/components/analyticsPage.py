"""
Analytics Page v3 – Executive Finance Dashboard
------------------------------------------------
Designed from the perspective of a finance director who needs:
• Instant read on revenue direction (up/down vs prior period)
• Location performance ranked with context
• Payment mix grouped by CATEGORY not 12 individual tenders
• Trends you can actually read (lines, not stacked rainbow)
• A table that tells a story, not just dumps numbers

Tabs: Overview | Locations | Payment Mix | Trends | Detail Table
"""

from __future__ import annotations

import calendar as cal_mod
from importlib import import_module
import queue
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from weakref import ref

import customtkinter as ctk
import matplotlib
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np

# ── ensure imports resolve ────────────────────────────────────────────
_UI_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _UI_DIR.parent
for _p in (_UI_DIR, _ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _load_tenders_db_manager_class():
    for module_name in ("BE.src.db.tendersdb_manager", "src.db.tendersdb_manager"):
        try:
            return import_module(module_name).TendersDBManager
        except ImportError:
            continue
    raise ImportError("Unable to import TendersDBManager")


TendersDBManager = _load_tenders_db_manager_class()
matplotlib.use("Agg")


# ══════════════════════════════════════════════════════════════════════
#  PALETTE  — clean, professional, not "startup purple"
# ══════════════════════════════════════════════════════════════════════
NAVY = "#1B2A4A"
NAVY_LIGHT = "#2D4A7A"
SLATE = "#475569"
BG = "#F8FAFC"
TEXT_PRIMARY = "#0F172A"
TEXT_SEC = "#64748B"
TEXT_MUTED = "#94A3B8"
CARD_BG = "#FFFFFF"
BORDER = "#E2E8F0"
GREEN = "#059669"
GREEN_BG = "#ECFDF5"
GREEN_LIGHT = "#D1FAE5"
RED = "#DC2626"
RED_BG = "#FEF2F2"
RED_LIGHT = "#FECACA"
AMBER = "#D97706"
AMBER_BG = "#FFFBEB"
BLUE = "#2563EB"
BLUE_BG = "#EFF6FF"
BLUE_LIGHT = "#DBEAFE"
ACCENT = "#1E40AF"
ACCENT_LIGHT = "#DBEAFE"
ACCENT_HOVER = "#1E3A8A"
FONT = "Segoe UI"

# ── Chart palette: muted, professional, distinguishable ───────────
CHART_PALETTE = [
    "#2563EB",  # blue — meal plans
    "#059669",  # green — campus currency
    "#DC2626",  # red — credit cards
    "#D97706",  # amber — other
    "#7C3AED",  # purple
    "#0891B2",  # cyan
    "#BE185D",  # pink
    "#475569",  # slate
]

# ══════════════════════════════════════════════════════════════════════
#  TENDER CATEGORY GROUPING
#  Rich doesn't care about 12 individual tenders.
#  He thinks in categories: meal plans, campus, cards, other.
# ══════════════════════════════════════════════════════════════════════
TENDER_CATEGORIES: dict[str, dict] = {
    "Meal Plans": {
        "keys": ["contract_card", "flex", "transfer", "dining_dollars"],
        "color": "#2563EB",
        "bg": "#DBEAFE",
        "icon": "🍽️",
    },
    "Campus Currency": {
        "keys": ["ucash", "ushop", "chartwellsDCB"],
        "color": "#059669",
        "bg": "#D1FAE5",
        "icon": "🏫",
    },
    "Credit Cards": {
        "keys": ["visa", "mc", "amex", "discover"],
        "color": "#DC2626",
        "bg": "#FEE2E2",
        "icon": "💳",
    },
    "Other": {
        "keys": ["coupons"],
        "color": "#D97706",
        "bg": "#FEF3C7",
        "icon": "🎟️",
    },
}

TENDER_LABELS: dict[str, str] = {
    "contract_card": "Contract Card",
    "flex": "Flex",
    "transfer": "Transfer",
    "coupons": "Coupons",
    "ucash": "UCash",
    "ushop": "UShop",
    "chartwellsDCB": "Chartwells DCB",
    "dining_dollars": "Dining Dollars",
    "amex": "Amex",
    "discover": "Discover",
    "mc": "Mastercard",
    "visa": "Visa",
}

# Tab labels
TAB_OVERVIEW = "  Overview"
TAB_LOCATION = "  Locations"
TAB_MIX = "  Payment Mix"
TAB_TRENDS = "  Trends"
TAB_TABLE = "  Detail Table"
ALL_TABS = [TAB_OVERVIEW, TAB_LOCATION, TAB_MIX, TAB_TRENDS, TAB_TABLE]


def _sum_category(data: dict, keys: list[str]) -> float:
    """Sum tender values for a category from a data dict."""
    return sum(float(data.get(k, 0.0)) for k in keys)


def _pct_change(current: float, previous: float) -> float | None:
    """Calculate % change. Returns None if previous is 0."""
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100


def _to_plot_datetime(value) -> datetime | None:
    """Normalize report dates for chart axes."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None
    return None


# ══════════════════════════════════════════════════════════════════════
#  CUSTOM CALENDAR POPUP  (unchanged logic, refreshed style)
# ══════════════════════════════════════════════════════════════════════
class _CalendarPopup(ctk.CTkToplevel):
    W, H = 296, 340

    def __init__(self, anchor, on_select, initial=None):
        super().__init__(anchor)
        self.overrideredirect(True)
        self.configure(fg_color=CARD_BG)
        self.attributes("-topmost", True)
        self._on_select = on_select
        self._selected = initial
        ref = initial or date.today()
        self._year, self._month = ref.year, ref.month
        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")
        self._build()
        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _: self.destroy())

    def _build(self):
        outer = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                             border_width=1, border_color=BORDER)
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        hdr = ctk.CTkFrame(outer, fg_color="transparent", height=42)
        hdr.pack(fill="x", padx=10, pady=(10, 2))
        hdr.pack_propagate(False)

        ctk.CTkButton(hdr, text="◀", width=30, height=30, corner_radius=8,
                      fg_color="transparent", text_color=TEXT_PRIMARY,
                      hover_color=ACCENT_LIGHT, font=ctk.CTkFont(size=14),
                      command=self._prev).pack(side="left")
        self._title = ctk.CTkLabel(hdr, text="",
                                   font=ctk.CTkFont(
                                       family=FONT, size=14, weight="bold"),
                                   text_color=TEXT_PRIMARY)
        self._title.pack(side="left", expand=True)
        ctk.CTkButton(hdr, text="▶", width=30, height=30, corner_radius=8,
                      fg_color="transparent", text_color=TEXT_PRIMARY,
                      hover_color=ACCENT_LIGHT, font=ctk.CTkFont(size=14),
                      command=self._next).pack(side="right")

        wd = ctk.CTkFrame(outer, fg_color="transparent", height=22)
        wd.pack(fill="x", padx=12, pady=(6, 0))
        wd.pack_propagate(False)
        for i, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            ctk.CTkLabel(wd, text=name, width=36,
                         font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(row=0, column=i)
            wd.grid_columnconfigure(i, weight=1)

        self._grid = ctk.CTkFrame(outer, fg_color="transparent")
        self._grid.pack(fill="both", expand=True, padx=8, pady=(2, 2))
        for i in range(7):
            self._grid.grid_columnconfigure(i, weight=1)

        bot = ctk.CTkFrame(outer, fg_color="transparent", height=38)
        bot.pack(fill="x", padx=10, pady=(0, 10))
        bot.pack_propagate(False)
        ctk.CTkButton(bot, text="Today", width=60, height=28, corner_radius=6,
                      fg_color=ACCENT_LIGHT, text_color=ACCENT,
                      hover_color=BLUE_LIGHT,
                      font=ctk.CTkFont(family=FONT, size=11),
                      command=self._go_today).pack(side="left", padx=4)
        ctk.CTkButton(bot, text="Clear", width=52, height=28, corner_radius=6,
                      fg_color=RED_BG, text_color=RED, hover_color=RED_LIGHT,
                      font=ctk.CTkFont(family=FONT, size=11),
                      command=self._clear).pack(side="right", padx=4)
        self._render_days()

    def _render_days(self):
        for w in self._grid.winfo_children():
            w.destroy()
        self._title.configure(
            text=f"{cal_mod.month_name[self._month]}  {self._year}")
        first_wd, n_days = cal_mod.monthrange(self._year, self._month)
        today = date.today()
        row, col = 0, first_wd
        for day in range(1, n_days + 1):
            d = date(self._year, self._month, day)
            is_sel = self._selected is not None and d == self._selected
            is_today = d == today
            if is_sel:
                fg, tc, hov = ACCENT, "white", ACCENT_HOVER
            elif is_today:
                fg, tc, hov = ACCENT_LIGHT, ACCENT, BLUE_LIGHT
            else:
                fg, tc, hov = "transparent", TEXT_PRIMARY, ACCENT_LIGHT
            ctk.CTkButton(self._grid, text=str(day), width=34, height=30,
                          corner_radius=8, fg_color=fg, text_color=tc,
                          hover_color=hov,
                          font=ctk.CTkFont(family=FONT, size=12),
                          command=lambda d=d: self._pick(d)
                          ).grid(row=row, column=col, padx=1, pady=1)
            col += 1
            if col > 6:
                col, row = 0, row + 1

    def _pick(self, d):
        self._on_select(d)
        self.destroy()

    def _go_today(self):
        self._pick(date.today())

    def _clear(self):
        self._on_select(None)
        self.destroy()

    def _prev(self):
        self._month -= 1
        if self._month < 1:
            self._month, self._year = 12, self._year - 1
        self._render_days()

    def _next(self):
        self._month += 1
        if self._month > 12:
            self._month, self._year = 1, self._year + 1
        self._render_days()


class _DatePickerBtn(ctk.CTkFrame):
    def __init__(self, parent, placeholder="Pick date", initial=None, on_change=None, **kw):
        super().__init__(parent, fg_color="transparent", **kw)
        self._date = initial
        self._on_change = on_change
        self._ph = placeholder
        self._btn = ctk.CTkButton(
            self, width=160, height=34, corner_radius=8,
            fg_color=CARD_BG, text_color=TEXT_PRIMARY,
            hover_color=ACCENT_LIGHT, border_width=1, border_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=12),
            anchor="w", command=self._open, cursor="hand2")
        self._btn.pack()
        self._refresh()

    def _refresh(self):
        if self._date:
            self._btn.configure(
                text=f"  📅  {self._date.strftime('%b %d, %Y')}")
        else:
            self._btn.configure(text=f"  📅  {self._ph}")

    def _open(self):
        _CalendarPopup(self._btn, self._on_picked, self._date)

    def _on_picked(self, d):
        self._date = d
        self._refresh()
        if self._on_change:
            self._on_change(d)

    @property
    def value(self):
        return self._date

    @value.setter
    def value(self, d):
        self._date = d
        self._refresh()


# ══════════════════════════════════════════════════════════════════════
#  MAIN ANALYTICS PAGE
# ══════════════════════════════════════════════════════════════════════
class AnalyticsPage(ctk.CTkFrame):
    """Executive finance dashboard — designed for Rich."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=BG)
        self.db = TendersDBManager()
        self._chart_canvases: list[FigureCanvasTkAgg] = []
        self._selected_locations: list[str] = []
        self._active_preset: str = "all"

        # flex total 
        self._flex_total: float = 0.0


        # cached query results
        self._summary: dict = {}
        self._daily: list[dict] = []
        self._by_location: list[dict] = []
        # previous period for comparison
        self._prev_summary: dict = {}
        self._prev_daily: list[dict] = []
        self._current_range: tuple[date | None, date | None] = (None, None)
        self._query_generation = 0
        self._is_loading = False
        self._query_results: queue.Queue = queue.Queue()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._build_header()       # row 0
        self._build_date_bar()     # row 1
        self._build_kpi_row()      # row 2
        self._load_flex_total()
        self._build_chart_area()   # rows 3 + 4

        self.after(75, self._drain_query_results)
        self.after(250, self._auto_load)

    # ══════════════════════════════════════════════════════════════
    #  HEADER
    # ══════════════════════════════════════════════════════════════
    def _build_header(self):
        bar = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=12,
                           border_width=1, border_color=BORDER, height=56)
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            bar, text="  📊  Financial Overview",
            font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=(14, 0), pady=11)

        self._rec_badge = ctk.CTkLabel(
            bar, text="",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_SEC)
        self._rec_badge.grid(row=0, column=1, sticky="e", padx=(0, 6), pady=11)

        self._status_badge = ctk.CTkLabel(
            bar, text="",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=TEXT_SEC, fg_color="transparent", corner_radius=8,
            padx=10, pady=4,
        )
        self._status_badge.grid(
            row=0, column=2, sticky="e", padx=(0, 8), pady=11)

        self._loc_btn = ctk.CTkButton(
            bar, text="All Locations ▾", width=160, height=32,
            corner_radius=8, fg_color=ACCENT_LIGHT, text_color=ACCENT,
            hover_color=BLUE_LIGHT,
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=self._show_location_picker, cursor="hand2")
        self._loc_btn.grid(row=0, column=3, padx=(0, 14), pady=11, sticky="e")

    # ══════════════════════════════════════════════════════════════
    #  DATE BAR
    # ══════════════════════════════════════════════════════════════
    def _build_date_bar(self):
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 2))
        wrapper.grid_columnconfigure(0, weight=1)

        chip_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        chip_row.grid(row=0, column=0, sticky="w")

        self._preset_btns: dict[str, ctk.CTkButton] = {}
        presets = [
            ("7d", "Last 7 Days"), ("30d", "Last 30 Days"),
            ("month", "This Month"), ("all", "All Time"),
            ("custom", "Custom Range"),
        ]
        for key, label in presets:
            btn = ctk.CTkButton(
                chip_row, text=label, height=30, corner_radius=8,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                cursor="hand2", command=lambda k=key: self._select_preset(k))
            btn.pack(side="left", padx=(0, 6))
            self._preset_btns[key] = btn

        self._custom_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        ctk.CTkLabel(self._custom_row, text="From",
                     font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TEXT_SEC).pack(side="left", padx=(0, 4))
        self._dp_from = _DatePickerBtn(
            self._custom_row, placeholder="Start date")
        self._dp_from.pack(side="left", padx=(0, 12))
        ctk.CTkLabel(self._custom_row, text="To",
                     font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TEXT_SEC).pack(side="left", padx=(0, 4))
        self._dp_to = _DatePickerBtn(self._custom_row, placeholder="End date")
        self._dp_to.pack(side="left", padx=(0, 14))
        self._custom_apply_btn = ctk.CTkButton(
            self._custom_row, text="Apply", width=80, height=32,
            corner_radius=8, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="white",
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=self._on_custom_apply, cursor="hand2")
        self._custom_apply_btn.pack(side="left")

        self._style_presets("all")

    def _style_presets(self, active):
        for key, btn in self._preset_btns.items():
            if key == active:
                btn.configure(fg_color=ACCENT, text_color="white",
                              hover_color=ACCENT_HOVER)
            else:
                btn.configure(fg_color=ACCENT_LIGHT, text_color=ACCENT,
                              hover_color=BLUE_LIGHT)

    def _select_preset(self, key):
        self._active_preset = key
        self._style_presets(key)
        if key == "custom":
            self._custom_row.grid(row=1, column=0, sticky="w", pady=(6, 0))
            return
        self._custom_row.grid_forget()
        today = date.today()
        if key == "7d":
            d_from, d_to = today - timedelta(days=6), today
        elif key == "30d":
            d_from, d_to = today - timedelta(days=29), today
        elif key == "month":
            d_from, d_to = today.replace(day=1), today
        else:
            d_from, d_to = None, None
        self._query(d_from, d_to)

    def _on_custom_apply(self):
        if self._dp_from.value and self._dp_to.value and self._dp_from.value > self._dp_to.value:
            self._set_status(
                "Start date must be before end date.", kind="error")
            self._show_empty_state(
                "Invalid custom range. Choose a start date before the end date.")
            return
        self._query(self._dp_from.value, self._dp_to.value)

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for btn in self._preset_btns.values():
            btn.configure(state=state)
        for btn in self._tab_btns.values():
            btn.configure(state=state)
        self._loc_btn.configure(state=state)
        self._custom_apply_btn.configure(state=state)

    def _set_status(self, text: str, kind: str = "info"):
        if not text:
            self._status_badge.configure(text="", fg_color="transparent")
            return

        styles = {
            "info": (TEXT_SEC, "#E2E8F0"),
            "loading": (ACCENT, ACCENT_LIGHT),
            "success": (GREEN, GREEN_BG),
            "error": (RED, RED_BG),
        }
        text_color, fg_color = styles.get(kind, styles["info"])
        self._status_badge.configure(
            text=text, text_color=text_color, fg_color=fg_color)

    def _show_empty_state(self, message: str):
        self._destroy_charts()
        for w in self._chart_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._chart_scroll,
            text=message,
            font=ctk.CTkFont(family=FONT, size=14),
            text_color=TEXT_MUTED,
            justify="center",
        ).pack(pady=60)

    # ══════════════════════════════════════════════════════════════
    #  KPI CARDS — with period-over-period comparison
    # ══════════════════════════════════════════════════════════════
    def _build_kpi_row(self):
        self._kpi_container = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_container.grid(
            row=2, column=0, sticky="ew", padx=16, pady=(6, 2))
        for i in range(3):
            self._kpi_container.grid_columnconfigure(i, weight=1)

        self._kpi_refs: list[dict] = []

        # Row 0: Revenue + Flex tracking
        row0 = [
            ("💰", "Total Revenue",  "$0", ACCENT, BLUE_BG,   "label"),
            ("🎯", "Flex Total",     "$0", SLATE,  "#F1F5F9", "input"),
            ("⚖️", "Flex Balance",   "$0", GREEN,  GREEN_BG,  "computed"),
        ]
        # Row 1: Operations
        row1 = [
            ("📊", "Daily Average",  "$0", GREEN, GREEN_BG,   "label"),
            ("🍱", "Meals Served",   "0",  AMBER, AMBER_BG,   "label"),
            ("🏆", "Top Location",   "—",  SLATE, "#F1F5F9",  "label"),
        ]

        for r, row_meta in enumerate([row0, row1]):
            for c, (icon, label, default, accent, bg, kind) in enumerate(row_meta):
                refs = self._make_kpi_card(
                    self._kpi_container, r, c,  
                    icon, label, default, accent, bg, kind)
                self._kpi_refs.append(refs)

        # Bind focus-out on the Flex Total entry (index 1)
        flex_entry = self._kpi_refs[1]["value"]
        self.winfo_toplevel().bind("<Button-1>", self._maybe_release_flex, add="+")

        # Static sub-message for the input card (managed only by save handler after this)
        self._kpi_refs[1]["change"].configure(
            text="Editable · saves on click-away", text_color=TEXT_MUTED)

    def _make_kpi_card(self, parent, row, col, icon, label, value,
                   accent, icon_bg, kind="label"):
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")
        badge = ctk.CTkFrame(top, width=32, height=32,
                            corner_radius=8, fg_color=icon_bg)
        badge.pack(side="left")
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=icon, font=ctk.CTkFont(size=14)).place(
            relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(top, text=label,
                    font=ctk.CTkFont(family=FONT, size=11),
                    text_color=TEXT_SEC).pack(side="left", padx=(8, 0))

        if kind == "input":
            # $ prefix as a locked label + editable number entry, side-by-side
            val_frame = ctk.CTkFrame(inner, fg_color="transparent")
            val_frame.pack(anchor="w", pady=(6, 0), fill="x")

            ctk.CTkLabel(
                val_frame, text="$",
                font=ctk.CTkFont(family=FONT, size=22, weight="bold"),
                text_color=accent
            ).pack(side="left", padx=(0, 2))

            val_widget = ctk.CTkEntry(
                val_frame,
                font=ctk.CTkFont(family=FONT, size=22, weight="bold"),
                text_color=accent,
                fg_color="transparent",
                border_width=0,
                justify="left",
            )
            val_widget.insert(0, str(value).replace("$", ""))
            val_widget.pack(side="left", fill="x", expand=True)
        else:
            val_widget = ctk.CTkLabel(
                inner, text=value,
                font=ctk.CTkFont(family=FONT, size=22, weight="bold"),
                text_color=accent)
            val_widget.pack(anchor="w", pady=(6, 0))

        change_lbl = ctk.CTkLabel(inner, text="",
                                font=ctk.CTkFont(family=FONT, size=11),
                                text_color=TEXT_MUTED)
        change_lbl.pack(anchor="w")

        return {"value": val_widget, "change": change_lbl,
                "kind": kind, "default_color": accent}

    def _update_kpis(self):
        s = self._summary
        ps = self._prev_summary
        rc = s.get("record_count", 0)
        total = float(s.get("total_sales", 0))
        meals = int(s.get("meal_count", 0))

        n_days = len(self._daily) if self._daily else 1
        daily_avg = total / n_days if n_days else 0

        prev_total = float(ps.get("total_sales", 0))
        prev_meals = int(ps.get("meal_count", 0))
        prev_days = len(self._prev_daily) if self._prev_daily else 1
        prev_daily_avg = prev_total / prev_days if prev_days else 0

        # Flex tracking
        flex_used = float(s.get("flex", 0))
        flex_total = float(self._flex_total)
        flex_balance = flex_total - flex_used

        top_loc, top_loc_amt = "—", ""
        if self._by_location:
            top = self._by_location[0]
            top_loc = top["location"]
            top_loc_amt = f"${float(top['total_sales']):,.2f}"

        def _pp_change(ref, val_text, val, prev):
            ref["value"].configure(text=val_text)
            change = _pct_change(val, prev)
            if change is None:
                ref["change"].configure(text="", text_color=TEXT_MUTED)
                return
            arrow = "▲" if change >= 0 else "▼"
            color = GREEN if change >= 0 else RED
            ref["change"].configure(
                text=f"{arrow} {abs(change):.1f}% vs prior period",
                text_color=color)
        # 0: Total Revenue
        _pp_change(self._kpi_refs[0], f"${total:,.2f}", total, prev_total)

        # 1: Flex Total — DO NOT TOUCH (user-controlled input)

        # 2: Flex Balance
        bal_ref = self._kpi_refs[2]
        if flex_balance >= 0:
            bal_ref["value"].configure(text=f"${flex_balance:,.2f}", text_color=GREEN)
            bal_ref["change"].configure(
                text=f"${flex_used:,.2f} used of ${flex_total:,.2f}",
                text_color=TEXT_SEC)
        else:
            bal_ref["value"].configure(
                text=f"-${abs(flex_balance):,.2f}", text_color=RED)
            bal_ref["change"].configure(
                text=f"Over budget by ${abs(flex_balance):,.2f}",
                text_color=RED)

        # 3: Daily Average
        _pp_change(self._kpi_refs[3], f"${daily_avg:,.2f}", daily_avg, prev_daily_avg)

        # 4: Meals Served
        _pp_change(self._kpi_refs[4], f"{meals:,}", meals, prev_meals)

        # 5: Top Location
        loc_ref = self._kpi_refs[5]
        loc_ref["value"].configure(text=top_loc)
        loc_ref["change"].configure(
            text=top_loc_amt, text_color=TEXT_SEC) if top_loc_amt else \
            loc_ref["change"].configure(text="")

        self._rec_badge.configure(
            text=f"{rc} records  •  {n_days} days" if rc else "")
    def _load_flex_total(self):
        """Pull flex_total from app_settings into widget + state."""
        from BE.src.db.tendersdb_manager import TendersDBManager  # adjust import to match your style
        db = TendersDBManager()
        raw = db.get_setting("flex_total", default=0)
        try:
            self._flex_total = float(raw)
        except (TypeError, ValueError):
            self._flex_total = 0.0

        entry = self._kpi_refs[1]["value"]
        entry.delete(0, "end")
        entry.insert(0, f"{self._flex_total:,.2f}")

    def _on_flex_total_focus_out(self, event=None):
        entry = self._kpi_refs[1]["value"]
        sub_lbl = self._kpi_refs[1]["change"]
        raw = entry.get().strip().replace(",", "")

        def _show_error(message):
            entry.delete(0, "end")
            entry.insert(0, f"{self._flex_total:,.2f}")
            sub_lbl.configure(text=message, text_color=RED)
            entry.configure(border_width=2, border_color=RED)
            self.after(2500, lambda: entry.configure(border_width=0))
            self.after(2500, lambda: sub_lbl.configure(
                text="Editable · saves on click-away", text_color=TEXT_MUTED))

        try:
            new_val = float(raw) if raw else 0.0
        except ValueError:
            shown = raw[:20] + ("…" if len(raw) > 20 else "")
            _show_error(f"✗ '{shown}' isn't a valid number — reverted")
            return

        if new_val < 0:
            _show_error("✗ Flex total must be ≥ 0 — reverted")
            return

        if abs(new_val - self._flex_total) < 0.005:
            entry.delete(0, "end")
            entry.insert(0, f"{new_val:,.2f}")
            return

        from BE.src.db.tendersdb_manager import TendersDBManager
        db = TendersDBManager()
        if db.set_setting("flex_total", new_val):
            self._flex_total = new_val
            entry.delete(0, "end")
            entry.insert(0, f"{new_val:,.2f}")
            sub_lbl.configure(text="✓ Saved", text_color=GREEN)
            self._update_kpis()
            self.after(2000, lambda: sub_lbl.configure(
                text="Editable · saves on click-away", text_color=TEXT_MUTED))
        else:
            _show_error("✗ Save failed — check connection")     

    # ══════════════════════════════════════════════════════════════
    #  CHART AREA
    # ══════════════════════════════════════════════════════════════
    def _build_chart_area(self):
        tab_container = ctk.CTkFrame(self, fg_color="transparent")
        tab_container.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 0))

        self._tab_bar = ctk.CTkFrame(tab_container, fg_color=CARD_BG,
                                     corner_radius=10, border_width=1,
                                     border_color=BORDER, height=42)
        self._tab_bar.pack(fill="x")
        self._tab_bar.pack_propagate(False)

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for tab in ALL_TABS:
            btn = ctk.CTkButton(
                self._tab_bar, text=tab, height=32, corner_radius=8,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                cursor="hand2", command=lambda t=tab: self._switch_tab(t))
            btn.pack(side="left", padx=3, pady=5)
            self._tab_btns[tab] = btn

        self._active_tab = TAB_OVERVIEW
        self._style_tabs()

        self._chart_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color="#CBD5E1",
            scrollbar_button_hover_color="#94A3B8")
        self._chart_scroll.grid(
            row=4, column=0, sticky="nsew", padx=16, pady=(4, 14))
        self._chart_scroll.grid_columnconfigure(0, weight=1)

    def _style_tabs(self):
        for tab, btn in self._tab_btns.items():
            if tab == self._active_tab:
                btn.configure(fg_color=ACCENT, text_color="white",
                              hover_color=ACCENT_HOVER)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SEC,
                              hover_color=ACCENT_LIGHT)

    def _switch_tab(self, tab):
        if tab == self._active_tab:
            return
        self._active_tab = tab
        self._style_tabs()
        self._render_active_chart()

    # ══════════════════════════════════════════════════════════════
    #  QUERY + PRIOR PERIOD COMPARISON
    # ══════════════════════════════════════════════════════════════
    def _query(self, d_from: date | None, d_to: date | None):
        locs = self._selected_locations or None
        self._current_range = (d_from, d_to)
        self._query_generation += 1
        query_id = self._query_generation
        self._is_loading = True
        self._set_controls_enabled(False)
        self._set_status("Loading data...", kind="loading")
        self._show_empty_state("Loading analytics...")

        def _worker():
            try:
                sf = d_from.isoformat() if d_from else None
                st = d_to.isoformat() if d_to else None
                result = {
                    "summary": self.db.get_summary(locs, sf, st),
                    "daily": self.db.get_daily_totals(locs, sf, st),
                    "by_location": self.db.get_location_totals(locs, sf, st),
                    "prev_summary": {},
                    "prev_daily": [],
                }

                if d_from and d_to:
                    span = (d_to - d_from).days + 1
                    prev_to = d_from - timedelta(days=1)
                    prev_from = prev_to - timedelta(days=span - 1)
                    pf = prev_from.isoformat()
                    pt = prev_to.isoformat()
                    result["prev_summary"] = self.db.get_summary(locs, pf, pt)
                    result["prev_daily"] = self.db.get_daily_totals(
                        locs, pf, pt)

                self._query_results.put((query_id, result, None))
            except Exception as exc:
                self._query_results.put((query_id, None, exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _drain_query_results(self):
        try:
            while True:
                query_id, result, error = self._query_results.get_nowait()
                self._apply_query_result(query_id, result, error)
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(75, self._drain_query_results)

    def _apply_query_result(self, query_id: int, result: dict | None, error: Exception | None):
        if query_id != self._query_generation:
            return

        self._is_loading = False
        self._set_controls_enabled(True)

        if error is not None:
            self._set_status("Unable to load analytics", kind="error")
            self._show_empty_state(
                "The analytics view could not load data. Check the database connection and try again.")
            return

        self._summary = result.get("summary", {}) if result else {}
        self._daily = result.get("daily", []) if result else []
        self._by_location = result.get("by_location", []) if result else []
        self._prev_summary = result.get("prev_summary", {}) if result else {}
        self._prev_daily = result.get("prev_daily", []) if result else []

        self._update_kpis()
        self._render_active_chart()

        if self._summary.get("record_count", 0):
            self._set_status("Live data", kind="success")
        else:
            self._set_status("No records for this view", kind="info")

    def _auto_load(self):
        self._refresh_dates_and_query()

    def on_show(self):
        self._refresh_dates_and_query()

    def _refresh_dates_and_query(self):
        min_d, max_d = self.db.get_date_range()
        if min_d:
            try:
                self._dp_from.value = datetime.strptime(
                    min_d, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        if max_d:
            try:
                self._dp_to.value = datetime.strptime(max_d, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        self._select_preset(self._active_preset)

    # ══════════════════════════════════════════════════════════════
    #  RENDER DISPATCHER
    # ══════════════════════════════════════════════════════════════
    def _render_active_chart(self):
        self._destroy_charts()
        for w in self._chart_scroll.winfo_children():
            w.destroy()

        if self._is_loading:
            self._show_empty_state("Loading analytics...")
            return

        if not self._summary or self._summary.get("record_count", 0) == 0:
            self._show_empty_state(
                "No data for this period. Try a different date range or location filter.")
            return

        dispatch = {
            TAB_OVERVIEW: self._chart_overview,
            TAB_LOCATION: self._chart_locations,
            TAB_MIX: self._chart_payment_mix,
            TAB_TRENDS: self._chart_trends,
            TAB_TABLE: self._render_table,
        }
        dispatch.get(self._active_tab, lambda: None)()

    def _embed(self, fig: Figure):
        card = ctk.CTkFrame(self._chart_scroll, fg_color=CARD_BG,
                            corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, pady=4)
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        w = canvas.get_tk_widget()
        w.configure(highlightthickness=0, bd=0)
        w.pack(fill="both", expand=True, padx=8, pady=8)
        self._chart_canvases.append(canvas)

    def _style_ax(self, ax, dollar_y=False):
        ax.set_facecolor("#FAFBFC")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(BORDER)
        ax.tick_params(colors=TEXT_SEC, labelsize=9)
        if dollar_y:
            ax.yaxis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda x, _: f"${x:,.2f}" if x >= 1 else f"${x:,.2f}"))

    # ══════════════════════════════════════════════════════════════
    #  TAB 1 — OVERVIEW: daily revenue bars + category breakdown
    # ══════════════════════════════════════════════════════════════
    def _chart_overview(self):
        daily = self._daily
        if not daily:
            return

        # ── Daily revenue bar chart ──────────────────────────────
        fig = Figure(figsize=(10.5, 4.0), dpi=100, facecolor=CARD_BG)
        ax = fig.add_subplot(111)
        self._style_ax(ax, dollar_y=True)

        dates = [d["report_date"] for d in daily]
        sales = [float(d["total_sales"]) for d in daily]
        short = []
        for d in dates:
            try:
                short.append(datetime.strptime(
                    d, "%Y-%m-%d").strftime("%m/%d"))
            except (ValueError, TypeError):
                short.append(str(d))

        x_pos = list(range(len(short)))

        # Color bars: green if above average, muted if below
        avg_val = sum(sales) / len(sales) if sales else 0
        colors = [ACCENT if v >= avg_val else "#CBD5E1" for v in sales]

        ax.bar(x_pos, sales, color=colors, edgecolor="white",
               linewidth=0.5, width=0.6, zorder=3)

        # Average line
        ax.axhline(y=avg_val, color=AMBER, linewidth=1.5, linestyle="--",
                   alpha=0.7, zorder=4)
        ax.text(len(x_pos) - 0.5, avg_val + max(sales) * 0.02,
                f"Avg ${avg_val:,.2f}", fontsize=9, color=AMBER,
                fontweight="bold", ha="right")

        # Value labels on bars (only if <= 14 bars)
        if len(sales) <= 14:
            max_sale = max(sales) if sales else 1
            for xi, val in zip(x_pos, sales):
                ax.text(xi, val + max_sale * 0.02, f"${val:,.2f}",
                        ha="center", va="bottom", fontsize=8,
                        color=TEXT_SEC, fontweight="bold")

        ax.set_xticks(x_pos)
        ax.set_xticklabels(short)
        ax.set_title("Daily Revenue", fontsize=13, fontweight="bold",
                     color=TEXT_PRIMARY, pad=12, loc="left")
        ax.grid(axis="y", color=BORDER, linewidth=0.5, alpha=0.5)
        if sales:
            ax.set_ylim(top=max(sales) * 1.15)
        if len(short) > 10:
            ax.tick_params(axis="x", rotation=45)
        fig.tight_layout()
        self._embed(fig)

        # ── Category breakdown mini-bars ─────────────────────────
        self._render_category_summary_card()

    def _render_category_summary_card(self):
        """Compact horizontal bars showing revenue by tender category."""
        s = self._summary
        card = ctk.CTkFrame(self._chart_scroll, fg_color=CARD_BG,
                            corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=4)

        ctk.CTkLabel(card, text="  Revenue by Payment Category",
                     font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TEXT_PRIMARY, anchor="w"
                     ).pack(fill="x", padx=16, pady=(14, 8))

        grand = sum(
            _sum_category(s, cat["keys"])
            for cat in TENDER_CATEGORIES.values()
        )

        for cat_name, cat_info in TENDER_CATEGORIES.items():
            val = _sum_category(s, cat_info["keys"])
            pct = (val / grand * 100) if grand else 0
            if val == 0:
                continue

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            row.grid_columnconfigure(1, weight=1)

            # Label
            ctk.CTkLabel(
                row, text=f"{cat_info['icon']}  {cat_name}",
                font=ctk.CTkFont(family=FONT, size=12),
                text_color=TEXT_PRIMARY, width=160, anchor="w"
            ).grid(row=0, column=0, sticky="w")

            # Progress bar background
            bar_frame = ctk.CTkFrame(
                row, fg_color="#F1F5F9", corner_radius=4, height=20)
            bar_frame.grid(row=0, column=1, sticky="ew", padx=(8, 8))
            bar_frame.grid_propagate(False)

            # Filled portion
            fill_width = max(pct, 2)  # minimum 2% visible
            fill = ctk.CTkFrame(bar_frame, fg_color=cat_info["color"],
                                corner_radius=4, height=20)
            fill.place(relx=0, rely=0, relwidth=fill_width /
                       100, relheight=1.0)

            # Value
            ctk.CTkLabel(
                row, text=f"${val:,.2f}  ({pct:.1f}%)",
                font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                text_color=TEXT_SEC, width=140, anchor="e"
            ).grid(row=0, column=2, sticky="e")

        # Bottom padding
        ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

    # ══════════════════════════════════════════════════════════════
    #  TAB 2 — LOCATIONS: ranked horizontal bars with meal overlay
    # ══════════════════════════════════════════════════════════════
    def _chart_locations(self):
        by_loc = self._by_location
        if not by_loc:
            ctk.CTkLabel(self._chart_scroll,
                         text="Not enough location data.",
                         font=ctk.CTkFont(family=FONT, size=13),
                         text_color=TEXT_MUTED).pack(pady=60)
            return

        n = len(by_loc)
        fig_h = max(4.0, n * 0.7 + 1.5)
        fig = Figure(figsize=(10.5, min(fig_h, 9)), dpi=100, facecolor=CARD_BG)
        ax = fig.add_subplot(111)
        self._style_ax(ax)

        locs = [d["location"] for d in by_loc]
        sales = [float(d["total_sales"]) for d in by_loc]
        meals = [int(d.get("meal_count", 0)) for d in by_loc]

        # Gradient color: top = darkest, bottom = lightest
        clrs = []
        for i in range(n):
            ratio = i / max(n - 1, 1)
            r = int(37 + ratio * 150)
            g = int(99 + ratio * 120)
            b = int(235 - ratio * 50)
            clrs.append(f"#{r:02x}{g:02x}{b:02x}")

        bars = ax.barh(locs, sales, color=clrs, edgecolor="white",
                       linewidth=0.5, height=0.55)
        max_sale = max(sales) if sales else 1

        # Labels: sales amount + meal count
        for bar, val, mc in zip(bars, sales, meals):
            label_x = bar.get_width() + max_sale * 0.015
            y_center = bar.get_y() + bar.get_height() / 2
            ax.text(label_x, y_center,
                    f"${val:,.2f}   ({mc:,} meals)",
                    ha="left", va="center", fontsize=9,
                    color=TEXT_SEC, fontweight="bold")

        ax.set_title("Revenue by Location (ranked)", fontsize=13,
                     fontweight="bold", color=TEXT_PRIMARY, pad=12, loc="left")
        ax.invert_yaxis()
        ax.tick_params(axis="y", labelsize=10, labelcolor=TEXT_PRIMARY)
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"${x:,.2f}"))
        ax.grid(axis="x", color=BORDER, linewidth=0.5, alpha=0.5)
        if max_sale > 0:
            ax.set_xlim(right=max_sale * 1.30)
        fig.tight_layout()
        fig.subplots_adjust(left=0.25)
        self._embed(fig)

    # ══════════════════════════════════════════════════════════════
    #  TAB 3 — PAYMENT MIX: donut by CATEGORY + detail sub-table
    # ══════════════════════════════════════════════════════════════
    def _chart_payment_mix(self):
        s = self._summary
        fig = Figure(figsize=(10.5, 5.0), dpi=100, facecolor=CARD_BG)
        gs = fig.add_gridspec(1, 2, width_ratios=[3, 2], wspace=0.05)
        ax = fig.add_subplot(gs[0, 0])
        ax_leg = fig.add_subplot(gs[0, 1])
        ax_leg.set_axis_off()

        labels, sizes, clrs = [], [], []
        for cat_name, cat_info in TENDER_CATEGORIES.items():
            v = _sum_category(s, cat_info["keys"])
            if v > 0:
                labels.append(cat_name)
                sizes.append(v)
                clrs.append(cat_info["color"])

        if not sizes:
            ax.text(0.5, 0.5, "No tender data", ha="center", va="center",
                    fontsize=13, color=TEXT_MUTED, transform=ax.transAxes)
            ax.set_axis_off()
        else:
            total = sum(sizes)
            wedges, _, autotexts = ax.pie(
                sizes, labels=None,
                autopct=lambda p: f"{p:.1f}%" if p >= 5 else "",
                colors=clrs, startangle=140, pctdistance=0.75,
                wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2.5))
            for t in autotexts:
                t.set_fontsize(10)
                t.set_color("white")
                t.set_fontweight("bold")

            ax.text(0, 0.04, f"${total:,.2f}", ha="center", va="center",
                    fontsize=18, fontweight="bold", color=TEXT_PRIMARY)
            ax.text(0, -0.12, "Total Revenue", ha="center", va="center",
                    fontsize=9, color=TEXT_SEC)

            # Legend with category breakdown
            legend_lines = []
            for lbl, sz in zip(labels, sizes):
                pct = sz / total * 100
                legend_lines.append(f"{lbl}  —  ${sz:,.2f}  ({pct:.1f}%)")

            handles = [ax_leg.barh(0, 0, color=c)[0] for c in clrs]
            ax_leg.legend(handles, legend_lines, loc="center left",
                          bbox_to_anchor=(0, 0.5), fontsize=10,
                          frameon=False, labelspacing=1.4,
                          handlelength=1.2, handletextpad=0.8)

        fig.suptitle("Payment Category Mix", fontsize=13, fontweight="bold",
                     color=TEXT_PRIMARY, y=0.97)
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        self._embed(fig)

        # ── Individual tender detail below the donut ─────────────
        self._render_tender_detail_card()

    def _render_tender_detail_card(self):
        """Breakdown of individual tenders within each category."""
        s = self._summary
        card = ctk.CTkFrame(self._chart_scroll, fg_color=CARD_BG,
                            corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=4)

        ctk.CTkLabel(card, text="  Individual Tender Breakdown",
                     font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TEXT_PRIMARY, anchor="w"
                     ).pack(fill="x", padx=16, pady=(14, 4))

        grand = sum(float(s.get(k, 0)) for k in TENDER_LABELS)

        for cat_name, cat_info in TENDER_CATEGORIES.items():
            cat_total = _sum_category(s, cat_info["keys"])
            if cat_total == 0:
                continue

            # Category header
            hdr = ctk.CTkFrame(
                card, fg_color=cat_info["color"], corner_radius=6, height=28)
            hdr.pack(fill="x", padx=16, pady=(8, 2))
            hdr.pack_propagate(False)
            ctk.CTkLabel(hdr, text=f"  {cat_info['icon']}  {cat_name}  —  ${cat_total:,.2f}",
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color="white").pack(side="left", padx=8)

            # Individual tenders in this category
            for key in cat_info["keys"]:
                val = float(s.get(key, 0))
                if val == 0:
                    continue
                pct = (val / grand * 100) if grand else 0
                label = TENDER_LABELS.get(key, key)

                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=24, pady=1)
                ctk.CTkLabel(row, text=f"  {label}",
                             font=ctk.CTkFont(family=FONT, size=11),
                             text_color=TEXT_PRIMARY, anchor="w"
                             ).pack(side="left")
                ctk.CTkLabel(row, text=f"${val:,.2f}  ({pct:.1f}%)",
                             font=ctk.CTkFont(family=FONT, size=11),
                             text_color=TEXT_SEC, anchor="e"
                             ).pack(side="right", padx=(0, 16))

        ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

    # ══════════════════════════════════════════════════════════════
    #  TAB 4 — TRENDS: individual lines by CATEGORY (readable!)
    # ══════════════════════════════════════════════════════════════
    def _chart_trends(self):
        daily = self._daily
        if not daily or len(daily) < 2:
            ctk.CTkLabel(self._chart_scroll,
                         text="Need at least 2 days of data for trends.",
                         font=ctk.CTkFont(family=FONT, size=13),
                         text_color=TEXT_MUTED).pack(pady=60)
            return

        # ── Revenue trend with prior period comparison ───────────
        fig = Figure(figsize=(10.5, 4.0), dpi=100, facecolor=CARD_BG)
        ax = fig.add_subplot(111)
        self._style_ax(ax, dollar_y=True)

        dates = []
        points = []
        for d in daily:
            parsed = _to_plot_datetime(d.get("report_date"))
            if parsed is None:
                continue
            dates.append(parsed)
            points.append(d)

        if len(points) < 2:
            ctk.CTkLabel(self._chart_scroll,
                         text="Need at least 2 valid dates for trends.",
                         font=ctk.CTkFont(family=FONT, size=13),
                         text_color=TEXT_MUTED).pack(pady=60)
            return

        sales = [float(d["total_sales"]) for d in points]
        ax.plot(dates, sales, color=ACCENT, linewidth=2.5, marker="o",
                markersize=5, label="Current Period", zorder=4)
        ax.fill_between(dates, sales, alpha=0.08, color=ACCENT)

        # Prior period as ghost line
        if self._prev_daily and len(self._prev_daily) >= 2:
            prev_sales = [float(d["total_sales"]) for d in self._prev_daily]
            # Align to same x-axis length
            if len(prev_sales) == len(dates):
                ax.plot(dates, prev_sales, color="#CBD5E1", linewidth=1.5,
                        linestyle="--", label="Prior Period", zorder=3)
            elif len(prev_sales) > 0:
                # Resample to match current period length
                x_prev = list(range(len(prev_sales)))
                x_curr = [i * (len(prev_sales) - 1) / max(len(dates) - 1, 1)
                          for i in range(len(dates))]
                resampled = np.interp(x_curr, x_prev, prev_sales)
                ax.plot(dates, resampled, color="#CBD5E1", linewidth=1.5,
                        linestyle="--", label="Prior Period", zorder=3)

        ax.set_title("Revenue Trend", fontsize=13, fontweight="bold",
                     color=TEXT_PRIMARY, pad=12, loc="left")
        ax.legend(fontsize=9, frameon=False, loc="upper right")
        ax.grid(axis="y", color=BORDER, linewidth=0.5, alpha=0.5)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        fig.tight_layout()
        self._embed(fig)

        # ── Category trend lines (the fix for the rainbow brick) ─
        fig2 = Figure(figsize=(10.5, 4.5), dpi=100, facecolor=CARD_BG)
        ax2 = fig2.add_subplot(111)
        self._style_ax(ax2, dollar_y=True)

        for cat_name, cat_info in TENDER_CATEGORIES.items():
            vals = [_sum_category(d, cat_info["keys"]) for d in points]
            if any(v > 0 for v in vals):
                ax2.plot(dates, vals, color=cat_info["color"], linewidth=2,
                         marker="o", markersize=4, label=cat_name)

        ax2.set_title("Trend by Payment Category", fontsize=13,
                      fontweight="bold", color=TEXT_PRIMARY, pad=12, loc="left")
        ax2.legend(fontsize=10, frameon=False, loc="upper right",
                   ncol=2, columnspacing=1.5)
        ax2.grid(axis="y", color=BORDER, linewidth=0.5, alpha=0.5)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        fig2.tight_layout()
        self._embed(fig2)

    # ══════════════════════════════════════════════════════════════
    #  TAB 5 — DETAIL TABLE: grouped by category
    # ══════════════════════════════════════════════════════════════
    def _render_table(self):
        s = self._summary
        n_days = len(self._daily) if self._daily else 1

        card = ctk.CTkFrame(self._chart_scroll, fg_color=CARD_BG,
                            corner_radius=12, border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, pady=4)

        # Header
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 10))
        ctk.CTkLabel(hdr, text="Revenue Detail",
                     font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkLabel(hdr, text=f"{n_days} days",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(side="right")

        # Table grid
        table = ctk.CTkFrame(card, fg_color="transparent")
        table.pack(fill="x", padx=14, pady=(0, 6))
        table.grid_columnconfigure(0, weight=3)
        table.grid_columnconfigure(1, weight=2)
        table.grid_columnconfigure(2, weight=2)
        table.grid_columnconfigure(3, weight=1)

        # Column headers
        for col, (txt, anchor) in enumerate([
            ("Category / Tender", "w"), ("Total", "e"),
            ("Daily Avg", "e"), ("Share", "e"),
        ]):
            ctk.CTkLabel(table, text=txt,
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=TEXT_MUTED, anchor=anchor
                         ).grid(row=0, column=col, sticky="ew", padx=14, pady=(0, 4))

        ctk.CTkFrame(table, fg_color=BORDER, height=1).grid(
            row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=2)

        grand = sum(float(s.get(k, 0)) for k in TENDER_LABELS)
        grid_row = 2

        for cat_name, cat_info in TENDER_CATEGORIES.items():
            cat_total = _sum_category(s, cat_info["keys"])
            cat_avg = cat_total / n_days
            cat_pct = (cat_total / grand * 100) if grand else 0

            # Category header row
            for col, (txt, anchor) in enumerate([
                (f"{cat_info['icon']}  {cat_name}", "w"),
                (f"${cat_total:,.2f}", "e"),
                (f"${cat_avg:,.2f}", "e"),
                (f"{cat_pct:.1f}%", "e"),
            ]):
                weight = "bold"
                fg = cat_info["bg"]
                ctk.CTkLabel(
                    table, text=txt,
                    font=ctk.CTkFont(family=FONT, size=12, weight=weight),
                    text_color=cat_info["color"], anchor=anchor,
                    fg_color=fg, corner_radius=4,
                ).grid(row=grid_row, column=col, sticky="ew",
                       padx=(14 if col == 0 else 4, 14 if col == 3 else 4), pady=1)
            grid_row += 1

            # Individual tenders in this category
            for key in cat_info["keys"]:
                val = float(s.get(key, 0))
                avg = val / n_days
                pct = (val / grand * 100) if grand else 0
                label = TENDER_LABELS.get(key, key)

                row_bg = BG if grid_row % 2 == 0 else CARD_BG
                for col, (txt, anchor, tc) in enumerate([
                    (f"    {label}", "w", TEXT_PRIMARY),
                    (f"${val:,.2f}", "e", TEXT_PRIMARY),
                    (f"${avg:,.2f}", "e", TEXT_SEC),
                    (f"{pct:.1f}%" if val > 0 else "—", "e", TEXT_SEC),
                ]):
                    ctk.CTkLabel(
                        table, text=txt,
                        font=ctk.CTkFont(family=FONT, size=11),
                        text_color=tc, anchor=anchor,
                        fg_color=row_bg, corner_radius=4,
                    ).grid(row=grid_row, column=col, sticky="ew",
                           padx=(14 if col == 0 else 4, 14 if col == 3 else 4), pady=1)
                grid_row += 1

        # Grand total
        g_avg = grand / n_days
        for col, (txt, anchor) in enumerate([
            ("Grand Total", "w"),
            (f"${grand:,.2f}", "e"),
            (f"${g_avg:,.2f}", "e"),
            ("100%", "e"),
        ]):
            ctk.CTkLabel(
                table, text=txt,
                font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                text_color=ACCENT, anchor=anchor,
                fg_color=ACCENT_LIGHT, corner_radius=6,
            ).grid(row=grid_row, column=col, sticky="ew",
                   padx=(14 if col == 0 else 4, 14 if col == 3 else 4),
                   pady=(8, 14))

        # ── Summary metrics at bottom ────────────────────────────
        summary_row = ctk.CTkFrame(card, fg_color="transparent")
        summary_row.pack(fill="x", padx=20, pady=(4, 16))

        total_sales = float(s.get("total_sales", 0))
        total_tax = float(s.get("tax", 0))
        total_meals = int(s.get("meal_count", 0))

        for txt in [
            f"Total Sales: ${total_sales:,.2f}",
            f"Total Tax: ${total_tax:,.2f}",
            f"Meals Served: {total_meals:,}",
            f"Effective Tax Rate: {(total_tax / total_sales * 100) if total_sales else 0:.2f}%",
        ]:
            ctk.CTkLabel(summary_row, text=txt,
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_SEC).pack(side="left", padx=(0, 20))

    # ══════════════════════════════════════════════════════════════
    #  LOCATION PICKER POPUP
    # ══════════════════════════════════════════════════════════════
    def _show_location_picker(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Select Locations")
        popup.geometry("340x460")
        popup.resizable(False, False)
        popup.configure(fg_color=BG)
        popup.attributes("-topmost", True)
        popup.grab_set()
        popup.focus()

        ctk.CTkLabel(popup, text="Filter by Location",
                     font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(popup, text="Leave all unchecked for company-wide view.",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(padx=20, anchor="w")

        ctk.CTkFrame(popup, fg_color=BORDER, height=1).pack(
            fill="x", padx=20, pady=(10, 0))

        filter_var = ctk.StringVar(value="")
        filter_entry = ctk.CTkEntry(
            popup,
            textvariable=filter_var,
            placeholder_text="Search locations",
            height=34,
            corner_radius=8,
            border_color=BORDER,
            fg_color=CARD_BG,
            text_color=TEXT_PRIMARY,
        )
        filter_entry.pack(fill="x", padx=16, pady=(10, 0))

        scroll = ctk.CTkScrollableFrame(popup, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(6, 0))

        locations = self.db.get_locations()

        vmap: dict[str, ctk.BooleanVar] = {}
        for loc in locations:
            vmap[loc] = ctk.BooleanVar(value=loc in self._selected_locations)

        count_label = ctk.CTkLabel(
            popup,
            text="",
            font=ctk.CTkFont(family=FONT, size=11),
            text_color=TEXT_SEC,
        )
        count_label.pack(fill="x", padx=20, pady=(4, 0), anchor="w")

        def _render_location_options(*_args):
            query = filter_var.get().strip().lower()
            for child in scroll.winfo_children():
                child.destroy()

            visible = [loc for loc in locations if query in loc.lower()]
            count_label.configure(text=f"{len(visible)} location(s)")

            if not visible:
                ctk.CTkLabel(
                    scroll,
                    text="No matching locations.",
                    font=ctk.CTkFont(family=FONT, size=12),
                    text_color=TEXT_MUTED,
                ).pack(anchor="w", pady=8, padx=4)
                return

            for loc in visible:
                ctk.CTkCheckBox(
                    scroll, text=loc, variable=vmap[loc],
                    font=ctk.CTkFont(family=FONT, size=12),
                    text_color=TEXT_PRIMARY, fg_color=ACCENT,
                    hover_color=ACCENT_LIGHT, border_color=BORDER,
                    corner_radius=4, height=28).pack(anchor="w", pady=2, padx=4)

        filter_var.trace_add("write", _render_location_options)
        _render_location_options()
        filter_entry.focus_set()

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(8, 14))

        ctk.CTkButton(btn_frame, text="Select All", width=80, height=28,
                      corner_radius=6, fg_color=ACCENT_LIGHT, text_color=ACCENT,
                      hover_color=BLUE_LIGHT,
                      font=ctk.CTkFont(family=FONT, size=11),
                      command=lambda: [v.set(True) for v in vmap.values()],
                      cursor="hand2").pack(side="left", padx=(0, 6))
        ctk.CTkButton(btn_frame, text="Clear", width=60, height=28,
                      corner_radius=6, fg_color=RED_BG, text_color=RED,
                      hover_color=RED_LIGHT,
                      font=ctk.CTkFont(family=FONT, size=11),
                      command=lambda: [v.set(False) for v in vmap.values()],
                      cursor="hand2").pack(side="left")

        def _apply():
            self._selected_locations = [
                loc for loc, var in vmap.items() if var.get()]
            n = len(self._selected_locations)
            if n == 0:
                self._loc_btn.configure(text="All Locations ▾")
            elif n <= 2:
                self._loc_btn.configure(text=", ".join(
                    self._selected_locations) + " ▾")
            else:
                self._loc_btn.configure(text=f"{n} Locations ▾")
            popup.destroy()
            self._select_preset(self._active_preset)

        ctk.CTkButton(btn_frame, text="Apply", width=80, height=28,
                      corner_radius=6, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      text_color="white",
                      font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                      command=_apply, cursor="hand2").pack(side="right")

    # ══════════════════════════════════════════════════════════════
    #  HELPER FUNCTIONS
    # ══════════════════════════════════════════════════════════════  
    def _is_in(self, widget, ancestor):
        """True if widget is ancestor or a descendant of it."""
        while widget is not None:
            if widget is ancestor:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _maybe_release_flex(self, event):
        """Click anywhere outside the flex entry → trigger save."""
        entry = self._kpi_refs[1]["value"]
        try:
            focused = self.focus_get()
        except KeyError:
            return
        if focused is None or not self._is_in(focused, entry):
            return
        # Click was on the entry itself → leave it alone
        if self._is_in(event.widget, entry):
            return
        # Move focus to root (best-effort) and trigger save explicitly
        self.winfo_toplevel().focus_set()
        self._on_flex_total_focus_out()
    # ══════════════════════════════════════════════════════════════
    #  CLEANUP
    # ══════════════════════════════════════════════════════════════
    def _destroy_charts(self):
        for c in self._chart_canvases:
            try:
                c.get_tk_widget().destroy()
            except Exception:
                pass
        self._chart_canvases.clear()
