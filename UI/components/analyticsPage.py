"""
Analytics Page v2 – Premium sales & tender dashboard.
-----------------------------------------------------
* Auto-loads data on open (no empty state).
* Calendar date-pickers instead of text input.
* Preset date-range chips (7 d / 30 d / Month / All / Custom).
* KPI cards always visible above the fold.
* Tabbed chart area (Daily | Tender Mix | Locations | Trends | Table).
"""

from __future__ import annotations

import calendar as cal_mod
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import customtkinter as ctk
import matplotlib
import matplotlib.ticker as mticker
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ── ensure imports resolve ────────────────────────────────────────────
_UI_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR = _UI_DIR.parent
for _p in (_UI_DIR, _ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from BE.src.db.tendersdb_manager import TendersDBManager
except ImportError:
    from src.db.tendersdb_manager import TendersDBManager
matplotlib.use("Agg")

# ══════════════════════════════════════════════════════════════════════
#  PALETTE
# ══════════════════════════════════════════════════════════════════════
PURPLE = "#6C5CE7"
PURPLE_DARK = "#5B4CD6"
PURPLE_LIGHT = "#EDE9FF"
PURPLE_SUBTLE = "#F4F1FF"
BG = "#F5F5F7"
TEXT_PRIMARY = "#1a1a1a"
TEXT_SEC = "#8E8E93"
TEXT_MUTED = "#AEAEB2"
CARD_BG = "#FFFFFF"
BORDER = "#E5E5EA"
GREEN = "#34C759"
GREEN_BG = "#E8F9EE"
RED = "#FF3B30"
ORANGE = "#FF9500"
BLUE = "#0984E3"
CYAN = "#00CEC9"
FONT = "Segoe UI"

CHART_COLORS = [
    "#6C5CE7", "#00B894", "#0984E3", "#E17055", "#FDCB6E",
    "#636E72", "#A29BFE", "#55EFC4", "#74B9FF", "#FAB1A0",
    "#FF7675", "#FD79A8", "#81ECEC",
]

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

TAB_DAILY = "\u2003📊  Daily Sales"
TAB_TENDER = "\u2003🍩  Tender Mix"
TAB_LOCATION = "\u2003📍  Locations"
TAB_TRENDS = "\u2003📈  Trends"
TAB_TABLE = "\u2003📋  Table"
ALL_TABS = [TAB_DAILY, TAB_TENDER, TAB_LOCATION, TAB_TRENDS, TAB_TABLE]


# ══════════════════════════════════════════════════════════════════════
#  CUSTOM CALENDAR POPUP
# ══════════════════════════════════════════════════════════════════════
class _CalendarPopup(ctk.CTkToplevel):
    """Compact, borderless month-view calendar with day selection."""

    W, H = 296, 340

    def __init__(
        self,
        anchor: ctk.CTkBaseClass,
        on_select,
        initial: date | None = None,
    ):
        super().__init__(anchor)
        self.overrideredirect(True)
        self.configure(fg_color=CARD_BG)
        self.attributes("-topmost", True)
        self._on_select = on_select
        self._selected = initial
        ref = initial or date.today()
        self._year, self._month = ref.year, ref.month

        # position beneath the anchor widget
        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 4
        self.geometry(f"{self.W}x{self.H}+{x}+{y}")

        self._build()
        self.grab_set()
        self.focus_set()
        self.bind("<Escape>", lambda _: self.destroy())

    # ── layout ────────────────────────────────────────────────────
    def _build(self):
        outer = ctk.CTkFrame(
            self, fg_color=CARD_BG, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        # ── month navigation header ──────────────────────────────
        hdr = ctk.CTkFrame(outer, fg_color="transparent", height=42)
        hdr.pack(fill="x", padx=10, pady=(10, 2))
        hdr.pack_propagate(False)

        ctk.CTkButton(
            hdr, text="◀", width=30, height=30, corner_radius=8,
            fg_color="transparent", text_color=TEXT_PRIMARY,
            hover_color=PURPLE_LIGHT, font=ctk.CTkFont(size=14),
            command=self._prev,
        ).pack(side="left")

        self._title = ctk.CTkLabel(
            hdr, text="",
            font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        )
        self._title.pack(side="left", expand=True)

        ctk.CTkButton(
            hdr, text="▶", width=30, height=30, corner_radius=8,
            fg_color="transparent", text_color=TEXT_PRIMARY,
            hover_color=PURPLE_LIGHT, font=ctk.CTkFont(size=14),
            command=self._next,
        ).pack(side="right")

        # ── weekday labels ────────────────────────────────────────
        wd = ctk.CTkFrame(outer, fg_color="transparent", height=22)
        wd.pack(fill="x", padx=12, pady=(6, 0))
        wd.pack_propagate(False)
        for i, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            ctk.CTkLabel(
                wd, text=name, width=36,
                font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                text_color=TEXT_MUTED,
            ).grid(row=0, column=i)
            wd.grid_columnconfigure(i, weight=1)

        # ── day grid ──────────────────────────────────────────────
        self._grid = ctk.CTkFrame(outer, fg_color="transparent")
        self._grid.pack(fill="both", expand=True, padx=8, pady=(2, 2))
        for i in range(7):
            self._grid.grid_columnconfigure(i, weight=1)

        # ── bottom bar ────────────────────────────────────────────
        bot = ctk.CTkFrame(outer, fg_color="transparent", height=38)
        bot.pack(fill="x", padx=10, pady=(0, 10))
        bot.pack_propagate(False)

        ctk.CTkButton(
            bot, text="Today", width=60, height=28, corner_radius=6,
            fg_color=PURPLE_SUBTLE, text_color=PURPLE,
            hover_color=PURPLE_LIGHT,
            font=ctk.CTkFont(family=FONT, size=11),
            command=self._go_today,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            bot, text="Clear", width=52, height=28, corner_radius=6,
            fg_color="#FFE5E5", text_color=RED, hover_color="#FFD0D0",
            font=ctk.CTkFont(family=FONT, size=11),
            command=self._clear,
        ).pack(side="right", padx=4)

        self._render_days()

    # ── draw day buttons ──────────────────────────────────────────
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
                fg, tc, hov = PURPLE, "white", PURPLE_DARK
            elif is_today:
                fg, tc, hov = PURPLE_LIGHT, PURPLE, PURPLE_SUBTLE
            else:
                fg, tc, hov = "transparent", TEXT_PRIMARY, PURPLE_SUBTLE

            ctk.CTkButton(
                self._grid, text=str(day), width=34, height=30,
                corner_radius=8, fg_color=fg, text_color=tc,
                hover_color=hov,
                font=ctk.CTkFont(family=FONT, size=12),
                command=lambda d=d: self._pick(d),
            ).grid(row=row, column=col, padx=1, pady=1)

            col += 1
            if col > 6:
                col = 0
                row += 1

    # ── callbacks ─────────────────────────────────────────────────
    def _pick(self, d: date):
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
            self._month = 12
            self._year -= 1
        self._render_days()

    def _next(self):
        self._month += 1
        if self._month > 12:
            self._month = 1
            self._year += 1
        self._render_days()


# ══════════════════════════════════════════════════════════════════════
#  DATE-PICKER BUTTON
# ══════════════════════════════════════════════════════════════════════
class _DatePickerBtn(ctk.CTkFrame):
    """A styled button that displays a date and opens a calendar popup."""

    def __init__(
        self,
        parent,
        placeholder: str = "Pick date",
        initial: date | None = None,
        on_change=None,
        **kw,
    ):
        super().__init__(parent, fg_color="transparent", **kw)
        self._date: date | None = initial
        self._on_change = on_change
        self._ph = placeholder

        self._btn = ctk.CTkButton(
            self, width=160, height=34, corner_radius=8,
            fg_color=CARD_BG, text_color=TEXT_PRIMARY,
            hover_color=PURPLE_SUBTLE, border_width=1, border_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=12),
            anchor="w", command=self._open, cursor="hand2",
        )
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

    def _on_picked(self, d: date | None):
        self._date = d
        self._refresh()
        if self._on_change:
            self._on_change(d)

    @property
    def value(self) -> date | None:
        return self._date

    @value.setter
    def value(self, d: date | None):
        self._date = d
        self._refresh()


# ══════════════════════════════════════════════════════════════════════
#  MAIN ANALYTICS PAGE
# ══════════════════════════════════════════════════════════════════════
class AnalyticsPage(ctk.CTkFrame):
    """Full-page premium analytics dashboard."""

    def __init__(self, parent):
        super().__init__(parent, fg_color=BG)
        self.db = TendersDBManager()
        self._chart_canvases: list[FigureCanvasTkAgg] = []
        self._selected_locations: list[str] = []
        self._active_preset: str = "all"

        # cached query results
        self._summary: dict = {}
        self._daily: list[dict] = []
        self._by_location: list[dict] = []

        # grid: header(0) | date-bar(1) | KPIs(2) | tab-bar(3) | chart(4)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._build_header()       # row 0
        self._build_date_bar()     # row 1
        self._build_kpi_row()      # row 2
        self._build_chart_area()   # rows 3 + 4

        # auto-load "All Time" once the widget is mapped
        self.after(250, self._auto_load)

    # ══════════════════════════════════════════════════════════════
    #  HEADER  (row 0)
    # ══════════════════════════════════════════════════════════════
    def _build_header(self):
        bar = ctk.CTkFrame(
            self, fg_color=CARD_BG, corner_radius=14,
            border_width=1, border_color=BORDER, height=58,
        )
        bar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        # icon
        badge = ctk.CTkFrame(bar, width=36, height=36, corner_radius=10,
                             fg_color=PURPLE_LIGHT)
        badge.grid(row=0, column=0, padx=(14, 0), pady=11, sticky="w")
        badge.grid_propagate(False)
        ctk.CTkLabel(badge, text="📊", font=ctk.CTkFont(size=16)).place(
            relx=0.5, rely=0.5, anchor="center")

        # title
        ctk.CTkLabel(
            bar, text="Sales Analytics",
            font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).grid(row=0, column=1, sticky="w", padx=(10, 0), pady=11)

        # record count badge
        self._rec_badge = ctk.CTkLabel(
            bar, text="",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_SEC,
        )
        self._rec_badge.grid(row=0, column=2, sticky="e", padx=(0, 6),
                             pady=11)

        # location picker
        self._loc_btn = ctk.CTkButton(
            bar, text="All Locations ▾", width=160, height=32,
            corner_radius=8, fg_color=PURPLE_SUBTLE, text_color=PURPLE,
            hover_color=PURPLE_LIGHT,
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=self._show_location_picker, cursor="hand2",
        )
        self._loc_btn.grid(row=0, column=3, padx=(0, 14), pady=11,
                           sticky="e")

    # ══════════════════════════════════════════════════════════════
    #  DATE BAR  (row 1) – preset chips + custom range pickers
    # ══════════════════════════════════════════════════════════════
    def _build_date_bar(self):
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 2))
        wrapper.grid_columnconfigure(0, weight=1)

        # ── preset chip row ───────────────────────────────────────
        chip_row = ctk.CTkFrame(wrapper, fg_color="transparent")
        chip_row.grid(row=0, column=0, sticky="w")

        self._preset_btns: dict[str, ctk.CTkButton] = {}
        presets = [
            ("7d", "Last 7 Days"),
            ("30d", "Last 30 Days"),
            ("month", "This Month"),
            ("all", "All Time"),
            ("custom", "Custom Range"),
        ]
        for key, label in presets:
            btn = ctk.CTkButton(
                chip_row, text=label, height=30, corner_radius=8,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                cursor="hand2",
                command=lambda k=key: self._select_preset(k),
            )
            btn.pack(side="left", padx=(0, 6))
            self._preset_btns[key] = btn

        # ── custom date-range row (hidden by default) ─────────────
        self._custom_row = ctk.CTkFrame(wrapper, fg_color="transparent")

        ctk.CTkLabel(
            self._custom_row, text="From",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=TEXT_SEC,
        ).pack(side="left", padx=(0, 4))

        self._dp_from = _DatePickerBtn(
            self._custom_row, placeholder="Start date")
        self._dp_from.pack(side="left", padx=(0, 12))

        ctk.CTkLabel(
            self._custom_row, text="To",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=TEXT_SEC,
        ).pack(side="left", padx=(0, 4))

        self._dp_to = _DatePickerBtn(
            self._custom_row, placeholder="End date")
        self._dp_to.pack(side="left", padx=(0, 14))

        ctk.CTkButton(
            self._custom_row, text="Apply", width=80, height=32,
            corner_radius=8, fg_color=PURPLE, hover_color=PURPLE_DARK,
            text_color="white",
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=self._on_custom_apply, cursor="hand2",
        ).pack(side="left")

        # initial style
        self._style_presets("all")

    def _style_presets(self, active: str):
        for key, btn in self._preset_btns.items():
            if key == active:
                btn.configure(fg_color=PURPLE, text_color="white",
                              hover_color=PURPLE_DARK)
            else:
                btn.configure(fg_color=PURPLE_SUBTLE, text_color=PURPLE,
                              hover_color=PURPLE_LIGHT)

    def _select_preset(self, key: str):
        self._active_preset = key
        self._style_presets(key)

        if key == "custom":
            self._custom_row.grid(row=1, column=0, sticky="w", pady=(6, 0))
            return                                  # user picks dates first

        self._custom_row.grid_forget()

        today = date.today()
        if key == "7d":
            d_from, d_to = today - timedelta(days=6), today
        elif key == "30d":
            d_from, d_to = today - timedelta(days=29), today
        elif key == "month":
            d_from, d_to = today.replace(day=1), today
        else:                                       # "all"
            d_from, d_to = None, None

        self._query(d_from, d_to)

    def _on_custom_apply(self):
        self._query(self._dp_from.value, self._dp_to.value)

    # ══════════════════════════════════════════════════════════════
    #  KPI CARDS  (row 2) – always visible above charts
    # ══════════════════════════════════════════════════════════════
    def _build_kpi_row(self):
        self._kpi_container = ctk.CTkFrame(self, fg_color="transparent")
        self._kpi_container.grid(row=2, column=0, sticky="ew",
                                 padx=16, pady=(6, 2))
        for i in range(4):
            self._kpi_container.grid_columnconfigure(i, weight=1)

        self._kpi_refs: list[dict] = []
        meta = [
            ("💰", "Total Sales", "$0.00", PURPLE, PURPLE_LIGHT),
            ("📈", "Average / Day", "$0.00", BLUE, "#E3F2FD"),
            ("🍱", "Meal Count", "0", GREEN, GREEN_BG),
            ("🧾", "Total Tax", "$0.00", ORANGE, "#FFF3E0"),
        ]
        for i, (icon, label, default, accent, bg) in enumerate(meta):
            refs = self._make_kpi_card(
                self._kpi_container, i, icon, label, default, accent, bg)
            self._kpi_refs.append(refs)

    def _make_kpi_card(self, parent, col, icon, label, value,
                       accent, icon_bg) -> dict:
        card = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=14,
                            border_width=1, border_color=BORDER)
        card.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=14)

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x")

        badge = ctk.CTkFrame(top, width=34, height=34, corner_radius=9,
                             fg_color=icon_bg)
        badge.pack(side="left")
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=icon, font=ctk.CTkFont(size=15)).place(
            relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            top, text=label,
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_SEC,
        ).pack(side="left", padx=(8, 0))

        val_lbl = ctk.CTkLabel(
            inner, text=value,
            font=ctk.CTkFont(family=FONT, size=24, weight="bold"),
            text_color=accent,
        )
        val_lbl.pack(anchor="w", pady=(8, 0))

        sub_lbl = ctk.CTkLabel(
            inner, text="",
            font=ctk.CTkFont(family=FONT, size=10), text_color=TEXT_MUTED,
        )
        sub_lbl.pack(anchor="w")

        return {"value": val_lbl, "sub": sub_lbl}

    def _update_kpis(self):
        s = self._summary
        rc = s.get("record_count", 0)
        total = s.get("total_sales", 0)
        avg = total / rc if rc else 0
        meals = s.get("meal_count", 0)
        tax = s.get("tax", 0)

        data = [
            (f"${total:,.2f}", f"{rc} record(s)"),
            (f"${avg:,.2f}", "per record"),
            (f"{meals:,}", "total meals"),
            (f"${tax:,.2f}", "collected"),
        ]
        for ref, (v, sub) in zip(self._kpi_refs, data):
            ref["value"].configure(text=v)
            ref["sub"].configure(text=sub)

        self._rec_badge.configure(
            text=f"{rc} record(s) found" if rc else "")

    # ══════════════════════════════════════════════════════════════
    #  CHART AREA  (rows 3 + 4) – tab bar + scrollable content
    # ══════════════════════════════════════════════════════════════
    def _build_chart_area(self):
        # row 3 – tab bar
        tab_container = ctk.CTkFrame(self, fg_color="transparent")
        tab_container.grid(row=3, column=0, sticky="ew", padx=16,
                           pady=(4, 0))

        self._tab_bar = ctk.CTkFrame(
            tab_container, fg_color=CARD_BG, corner_radius=10,
            border_width=1, border_color=BORDER, height=42,
        )
        self._tab_bar.pack(fill="x")
        self._tab_bar.pack_propagate(False)

        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for tab in ALL_TABS:
            btn = ctk.CTkButton(
                self._tab_bar, text=tab, height=32, corner_radius=8,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                cursor="hand2",
                command=lambda t=tab: self._switch_tab(t),
            )
            btn.pack(side="left", padx=3, pady=5)
            self._tab_btns[tab] = btn

        self._active_tab = TAB_DAILY
        self._style_tabs()

        # row 4 – scrollable chart content
        self._chart_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6",
        )
        self._chart_scroll.grid(row=4, column=0, sticky="nsew",
                                padx=16, pady=(4, 14))
        self._chart_scroll.grid_columnconfigure(0, weight=1)

    def _style_tabs(self):
        for tab, btn in self._tab_btns.items():
            if tab == self._active_tab:
                btn.configure(fg_color=PURPLE, text_color="white",
                              hover_color=PURPLE_DARK)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_SEC,
                              hover_color=PURPLE_SUBTLE)

    def _switch_tab(self, tab: str):
        if tab == self._active_tab:
            return
        self._active_tab = tab
        self._style_tabs()
        self._render_active_chart()

    # ══════════════════════════════════════════════════════════════
    #  QUERY + AUTO-LOAD
    # ══════════════════════════════════════════════════════════════
    def _query(self, d_from: date | None, d_to: date | None):
        locs = self._selected_locations or None
        sf = d_from.isoformat() if d_from else None
        st = d_to.isoformat() if d_to else None

        self._summary = self.db.get_summary(locs, sf, st)
        self._daily = self.db.get_daily_totals(locs, sf, st)
        self._by_location = self.db.get_location_totals(locs, sf, st)

        self._update_kpis()
        self._render_active_chart()

    def _auto_load(self):
        """Runs once after widget init — seeds date pickers & loads data."""
        self._refresh_dates_and_query()

    def on_show(self):
        """Called every time the page becomes visible (navigated to)."""
        self._refresh_dates_and_query()

    def _refresh_dates_and_query(self):
        """Update date-picker bounds from DB and re-run the active query."""
        min_d, max_d = self.db.get_date_range()
        if min_d:
            try:
                self._dp_from.value = datetime.strptime(
                    min_d, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass
        if max_d:
            try:
                self._dp_to.value = datetime.strptime(
                    max_d, "%Y-%m-%d").date()
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

        if not self._summary or self._summary.get("record_count", 0) == 0:
            ctk.CTkLabel(
                self._chart_scroll,
                text="No records found — adjust filters or date range.",
                font=ctk.CTkFont(family=FONT, size=14),
                text_color=TEXT_MUTED, justify="center",
            ).pack(pady=60)
            return

        dispatch = {
            TAB_DAILY: self._chart_daily,
            TAB_TENDER: self._chart_tender_pie,
            TAB_LOCATION: self._chart_location,
            TAB_TRENDS: self._chart_trends,
            TAB_TABLE: self._render_table,
        }
        dispatch.get(self._active_tab, lambda: None)()

    # ── embed helper ──────────────────────────────────────────────
    def _embed(self, fig: Figure):
        card = ctk.CTkFrame(
            self._chart_scroll, fg_color=CARD_BG, corner_radius=14,
            border_width=1, border_color=BORDER,
        )
        card.pack(fill="both", expand=True, pady=4)
        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        w = canvas.get_tk_widget()
        w.configure(highlightthickness=0, bd=0)
        w.pack(fill="both", expand=True, padx=8, pady=8)
        self._chart_canvases.append(canvas)

    def _style_ax(self, ax, dollar_y: bool = False):
        ax.set_facecolor("#FAFAFA")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_color(BORDER)
        ax.tick_params(colors=TEXT_SEC, labelsize=9)
        if dollar_y:
            ax.yaxis.set_major_formatter(
                mticker.FuncFormatter(
                    lambda x, _: f"${x:,.0f}" if x >= 1 else f"${x:,.2f}"))

    # ══════════════════════════════════════════════════════════════
    #  CHART 1 — Daily Sales bar + trend line
    # ══════════════════════════════════════════════════════════════
    def _chart_daily(self):
        daily = self._daily
        if not daily:
            return

        fig = Figure(figsize=(10.5, 4.2), dpi=100, facecolor=CARD_BG)
        ax = fig.add_subplot(111)
        self._style_ax(ax, dollar_y=True)

        dates = [d["report_date"] for d in daily]
        sales = [d["total_sales"] for d in daily]
        short = []
        for d in dates:
            try:
                short.append(
                    datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d"))
            except (ValueError, TypeError):
                short.append(d)

        x_pos = list(range(len(short)))
        bars = ax.bar(x_pos, sales, color=PURPLE, alpha=0.88,
                      edgecolor="white", linewidth=0.6, width=0.55,
                      zorder=3)

        # Smart labels — only show if bars don't overlap
        max_sale = max(sales) if sales else 1
        for bar, val in zip(bars, sales):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max_sale * 0.015,
                    f"${val:,.0f}",
                    ha="center", va="bottom", fontsize=8,
                    color=TEXT_SEC, fontweight="bold",
                )

        if len(sales) > 2:
            ax.plot(x_pos, sales, color=PURPLE_DARK, linewidth=1.8,
                    marker="o", markersize=5, alpha=0.5, zorder=4)

        ax.set_xticks(x_pos)
        ax.set_xticklabels(short)
        ax.set_title("Daily Total Sales", fontsize=13, fontweight="bold",
                     color=TEXT_PRIMARY, pad=12)
        ax.grid(axis="y", color=BORDER, linewidth=0.5, alpha=0.6)
        if len(short) > 10:
            ax.tick_params(axis="x", rotation=45)
        # Add breathing room at top for value labels
        if max_sale > 0:
            ax.set_ylim(top=max_sale * 1.15)
        fig.tight_layout()
        self._embed(fig)

    # ══════════════════════════════════════════════════════════════
    #  CHART 2 — Tender donut with centre total
    # ══════════════════════════════════════════════════════════════
    def _chart_tender_pie(self):
        s = self._summary
        fig = Figure(figsize=(10.5, 5.2), dpi=100, facecolor=CARD_BG)

        labels, sizes, clrs = [], [], []
        for i, (key, label) in enumerate(TENDER_LABELS.items()):
            v = s.get(key, 0.0)
            if v > 0:
                labels.append(label)
                sizes.append(v)
                clrs.append(CHART_COLORS[i % len(CHART_COLORS)])

        if not sizes:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, "No tender data", ha="center", va="center",
                    fontsize=13, color=TEXT_MUTED, transform=ax.transAxes)
            ax.set_axis_off()
        else:
            # Use gridspec: donut on left, legend on right
            gs = fig.add_gridspec(1, 2, width_ratios=[3, 2], wspace=0.05)
            ax = fig.add_subplot(gs[0, 0])
            ax_leg = fig.add_subplot(gs[0, 1])
            ax_leg.set_axis_off()

            total = sum(sizes)

            # Only show percentage on wedges that are big enough (>= 4%)
            def _autopct(pct):
                return f"{pct:.1f}%" if pct >= 4.0 else ""

            wedges, _, autotexts = ax.pie(
                sizes, labels=None, autopct=_autopct,
                colors=clrs, startangle=140, pctdistance=0.78,
                wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2.5),
            )
            for t in autotexts:
                t.set_fontsize(8)
                t.set_color(TEXT_PRIMARY)
                t.set_fontweight("bold")

            # Centre label
            ax.text(0, 0.04, f"${total:,.0f}", ha="center", va="center",
                    fontsize=17, fontweight="bold", color=TEXT_PRIMARY)
            ax.text(0, -0.11, "Total", ha="center", va="center",
                    fontsize=9, color=TEXT_SEC)

            # Build a clean legend table on the right subplot
            legend_handles = [
                ax_leg.barh(0, 0, color=c)[0] for c in clrs
            ]
            leg = ax_leg.legend(
                legend_handles,
                [f"{lbl}  —  ${sz:,.0f}  ({sz/total*100:.1f}%)"
                 for lbl, sz in zip(labels, sizes)],
                loc="center left", bbox_to_anchor=(0.0, 0.5),
                fontsize=9, frameon=False, labelspacing=1.2,
                handlelength=1.2, handletextpad=0.8,
            )

        fig.suptitle("Tender Distribution", fontsize=13, fontweight="bold",
                     color=TEXT_PRIMARY, y=0.97)
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        self._embed(fig)

    # ══════════════════════════════════════════════════════════════
    #  CHART 3 — Location comparison (horizontal bars)
    # ══════════════════════════════════════════════════════════════
    def _chart_location(self):
        by_loc = self._by_location
        if not by_loc:
            ctk.CTkLabel(
                self._chart_scroll,
                text="Not enough location data to display.",
                font=ctk.CTkFont(family=FONT, size=13),
                text_color=TEXT_MUTED,
            ).pack(pady=60)
            return

        fig_h = max(3.5, len(by_loc) * 0.65 + 1.5)
        fig = Figure(figsize=(10.5, min(fig_h, 8)), dpi=100,
                     facecolor=CARD_BG)
        ax = fig.add_subplot(111)
        self._style_ax(ax)

        locs = [d["location"] for d in by_loc]
        sales = [d["total_sales"] for d in by_loc]
        clr = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(locs))]

        bars = ax.barh(locs, sales, color=clr, edgecolor="white",
                       linewidth=0.6, height=0.55)
        max_sale = max(sales) if sales else 1
        for bar, val in zip(bars, sales):
            ax.text(
                bar.get_width() + max_sale * 0.015,
                bar.get_y() + bar.get_height() / 2,
                f"${val:,.0f}", ha="left", va="center",
                fontsize=9, color=TEXT_SEC, fontweight="bold",
            )

        ax.set_title("Sales by Location", fontsize=13, fontweight="bold",
                     color=TEXT_PRIMARY, pad=12)
        ax.invert_yaxis()
        ax.tick_params(axis="y", labelsize=9, labelcolor=TEXT_PRIMARY)
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.grid(axis="x", color=BORDER, linewidth=0.5, alpha=0.6)
        # Give room for long location names + value labels
        if max_sale > 0:
            ax.set_xlim(right=max_sale * 1.18)
        fig.tight_layout()
        # Override left margin after tight_layout for long labels
        fig.subplots_adjust(left=0.28)
        self._embed(fig)

    # ══════════════════════════════════════════════════════════════
    #  CHART 4 — Tender stacked area (trends)
    # ══════════════════════════════════════════════════════════════
    def _chart_trends(self):
        daily = self._daily
        if not daily or len(daily) < 2:
            ctk.CTkLabel(
                self._chart_scroll,
                text="Need at least 2 dates for trend analysis.",
                font=ctk.CTkFont(family=FONT, size=13),
                text_color=TEXT_MUTED,
            ).pack(pady=60)
            return

        fig = Figure(figsize=(10.5, 5.0), dpi=100, facecolor=CARD_BG)
        # Use gridspec: chart top, legend bottom
        gs = fig.add_gridspec(
            2, 1, height_ratios=[4, 1], hspace=0.05)
        ax = fig.add_subplot(gs[0, 0])
        ax_leg = fig.add_subplot(gs[1, 0])
        ax_leg.set_axis_off()
        self._style_ax(ax, dollar_y=True)

        dates: list = []
        for d in daily:
            try:
                dates.append(
                    datetime.strptime(d["report_date"], "%Y-%m-%d"))
            except (ValueError, TypeError):
                dates.append(d["report_date"])

        series: dict[str, list[float]] = {}
        for key, label in TENDER_LABELS.items():
            vals = [d.get(key, 0.0) for d in daily]
            if any(v > 0 for v in vals):
                series[label] = vals

        if series:
            labels = list(series.keys())
            data = list(series.values())
            clrs = CHART_COLORS[: len(labels)]
            ax.stackplot(dates, *data, labels=labels, colors=clrs, alpha=0.8)

            # Place legend in dedicated bottom area — never overlaps chart
            handles, leg_labels = ax.get_legend_handles_labels()
            ncol = min(4, len(labels))
            ax_leg.legend(
                handles, leg_labels,
                loc="center", ncol=ncol, fontsize=9,
                frameon=False, handlelength=1.5, handletextpad=0.6,
                columnspacing=1.5,
            )

        ax.set_title("Tender Trends Over Time", fontsize=13,
                     fontweight="bold", color=TEXT_PRIMARY, pad=12)
        ax.grid(axis="y", color=BORDER, linewidth=0.5, alpha=0.6)
        if isinstance(dates[0] if dates else None, datetime):
            import matplotlib.dates as mdates
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
            fig.autofmt_xdate(rotation=0, ha="center")
        fig.tight_layout()
        self._embed(fig)

    # ══════════════════════════════════════════════════════════════
    #  TABLE TAB — tender breakdown  (grid layout for perfect alignment)
    # ══════════════════════════════════════════════════════════════
    def _render_table(self):
        s = self._summary
        rc = s.get("record_count", 1) or 1

        card = ctk.CTkFrame(
            self._chart_scroll, fg_color=CARD_BG, corner_radius=14,
            border_width=1, border_color=BORDER,
        )
        card.pack(fill="both", expand=True, pady=4)

        # ── header ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 10))
        ctk.CTkLabel(
            hdr, text="Tender Breakdown",
            font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")
        ctk.CTkLabel(
            hdr, text=f"{rc} record(s)",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_SEC,
        ).pack(side="right")

        # ── table container (grid) ────────────────────────────────
        table = ctk.CTkFrame(card, fg_color="transparent")
        table.pack(fill="x", padx=14, pady=(0, 6))
        table.grid_columnconfigure(0, weight=3)   # Tender name
        table.grid_columnconfigure(1, weight=2)   # Total
        table.grid_columnconfigure(2, weight=2)   # Avg / Record
        table.grid_columnconfigure(3, weight=1)   # % share

        # ── column headers ────────────────────────────────────────
        for col, (txt, anchor) in enumerate([
            ("Tender", "w"), ("Total", "e"),
            ("Avg / Record", "e"), ("Share", "e"),
        ]):
            ctk.CTkLabel(
                table, text=txt,
                font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                text_color=TEXT_MUTED, anchor=anchor,
            ).grid(row=0, column=col, sticky="ew", padx=14, pady=(0, 4))

        # Separator
        sep = ctk.CTkFrame(table, fg_color=BORDER, height=1)
        sep.grid(row=1, column=0, columnspan=4, sticky="ew", padx=10, pady=2)

        # ── compute grand total first (for % share) ──────────────
        grand = sum(s.get(key, 0.0) for key in TENDER_LABELS)

        # ── data rows ─────────────────────────────────────────────
        grid_row = 2
        for idx, (key, label) in enumerate(TENDER_LABELS.items()):
            val = s.get(key, 0.0)
            avg = val / rc
            pct = (val / grand * 100) if grand else 0

            row_bg = BG if idx % 2 == 0 else CARD_BG
            # Tender name
            ctk.CTkLabel(
                table, text=label,
                font=ctk.CTkFont(family=FONT, size=12),
                text_color=TEXT_PRIMARY, anchor="w",
                fg_color=row_bg, corner_radius=4,
            ).grid(row=grid_row, column=0, sticky="ew", padx=(14, 4), pady=1)
            # Total
            ctk.CTkLabel(
                table, text=f"${val:,.2f}",
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                text_color=TEXT_PRIMARY, anchor="e",
                fg_color=row_bg, corner_radius=4,
            ).grid(row=grid_row, column=1, sticky="ew", padx=4, pady=1)
            # Average
            ctk.CTkLabel(
                table, text=f"${avg:,.2f}",
                font=ctk.CTkFont(family=FONT, size=12),
                text_color=TEXT_SEC, anchor="e",
                fg_color=row_bg, corner_radius=4,
            ).grid(row=grid_row, column=2, sticky="ew", padx=4, pady=1)
            # Share %
            ctk.CTkLabel(
                table, text=f"{pct:.1f}%" if val > 0 else "—",
                font=ctk.CTkFont(family=FONT, size=11),
                text_color=TEXT_SEC, anchor="e",
                fg_color=row_bg, corner_radius=4,
            ).grid(row=grid_row, column=3, sticky="ew", padx=(4, 14), pady=1)
            grid_row += 1

        # ── grand total row ───────────────────────────────────────
        g_avg = grand / rc
        gt_row = grid_row
        for col, (txt, anchor) in enumerate([
            ("Grand Total", "w"),
            (f"${grand:,.2f}", "e"),
            (f"${g_avg:,.2f}", "e"),
            ("100%", "e"),
        ]):
            ctk.CTkLabel(
                table, text=txt,
                font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                text_color=PURPLE, anchor=anchor,
                fg_color=PURPLE_SUBTLE, corner_radius=6,
            ).grid(
                row=gt_row, column=col, sticky="ew",
                padx=(14 if col == 0 else 4, 14 if col == 3 else 4),
                pady=(6, 14),
            )

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

        ctk.CTkLabel(
            popup, text="Choose Locations",
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(
            popup, text="Leave all unchecked to include every location.",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_SEC,
        ).pack(padx=20, anchor="w")

        ctk.CTkFrame(popup, fg_color=BORDER, height=1).pack(
            fill="x", padx=20, pady=(10, 0))

        scroll = ctk.CTkScrollableFrame(popup, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=(6, 0))

        locations = self.db.get_locations()
        try:
            from BE.src.cash_sheet_filler.config import REPORTS_CASHSHEET_MAP
        except ImportError:
            try:
                from cash_sheet_filler.config import REPORTS_CASHSHEET_MAP
            except ImportError:
                REPORTS_CASHSHEET_MAP = {}
        cfg_locs = sorted({v[0] for v in REPORTS_CASHSHEET_MAP.values()})
        all_locs = sorted(set(locations) | set(cfg_locs))

        vmap: dict[str, ctk.BooleanVar] = {}
        for loc in all_locs:
            var = ctk.BooleanVar(value=loc in self._selected_locations)
            vmap[loc] = var
            ctk.CTkCheckBox(
                scroll, text=loc, variable=var,
                font=ctk.CTkFont(family=FONT, size=12),
                text_color=TEXT_PRIMARY, fg_color=PURPLE,
                hover_color=PURPLE_LIGHT, border_color=BORDER,
                corner_radius=4, height=28,
            ).pack(anchor="w", pady=2, padx=4)

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(8, 14))

        def _sel_all():
            for v in vmap.values():
                v.set(True)

        def _clear():
            for v in vmap.values():
                v.set(False)

        ctk.CTkButton(
            btn_frame, text="Select All", width=80, height=28,
            corner_radius=6, fg_color=PURPLE_SUBTLE, text_color=PURPLE,
            hover_color=PURPLE_LIGHT,
            font=ctk.CTkFont(family=FONT, size=11),
            command=_sel_all, cursor="hand2",
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            btn_frame, text="Clear", width=60, height=28, corner_radius=6,
            fg_color="#FFE5E5", text_color=RED, hover_color="#FFD0D0",
            font=ctk.CTkFont(family=FONT, size=11),
            command=_clear, cursor="hand2",
        ).pack(side="left")

        def _apply():
            self._selected_locations = [
                loc for loc, var in vmap.items() if var.get()]
            n = len(self._selected_locations)
            if n == 0:
                self._loc_btn.configure(text="All Locations ▾")
            elif n <= 2:
                self._loc_btn.configure(
                    text=", ".join(self._selected_locations) + " ▾")
            else:
                self._loc_btn.configure(text=f"{n} Locations ▾")
            popup.destroy()
            # re-query with updated locations
            self._select_preset(self._active_preset)

        ctk.CTkButton(
            btn_frame, text="Apply", width=80, height=28, corner_radius=6,
            fg_color=PURPLE, hover_color=PURPLE_DARK, text_color="white",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            command=_apply, cursor="hand2",
        ).pack(side="right")

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
