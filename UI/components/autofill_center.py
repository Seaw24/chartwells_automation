"""
AutoFill Center - Cash Sheet & Tender Breakdown Autofill UI
Compact, lightweight version with inline result log.
"""

import customtkinter as ctk  # noqa: E402


try:
    from .autofill_center_ui import (
        PURPLE,
        PURPLE_DARK,
        PURPLE_LIGHT,
        PURPLE_SUBTLE,
        BG,
        TEXT,
        TEXT_SEC,
        TEXT_MUTED,
        CARD,
        BORDER,
        GREEN,
        GREEN_BG,
        RED,
        RED_BG,
        ORANGE,
        ORANGE_BG,
        FONT,
        Card as _Card,
        section_label as _section_label,
        card_header as _card_header,
    )
except ImportError:
    from autofill_center_ui import (
        PURPLE,
        PURPLE_DARK,
        PURPLE_LIGHT,
        PURPLE_SUBTLE,
        BG,
        TEXT,
        TEXT_SEC,
        TEXT_MUTED,
        CARD,
        BORDER,
        GREEN,
        GREEN_BG,
        RED,
        RED_BG,
        ORANGE,
        ORANGE_BG,
        FONT,
        Card as _Card,
        section_label as _section_label,
        card_header as _card_header,
    )

try:
    from .autofill_center_runtime import AutoFillRuntimeController
    from .autofill_center_config import AutoFillConfigController
except ImportError:
    try:
        from UI.components.autofill_center_runtime import AutoFillRuntimeController
        from UI.components.autofill_center_config import AutoFillConfigController
    except ImportError:
        from components.autofill_center_runtime import AutoFillRuntimeController
        from components.autofill_center_config import AutoFillConfigController

try:
    from .icons import get_icon
except ImportError:
    from icons import get_icon

# Printer dropdown
from BE.src.printer import ExcelPrinter
from BE.src.cash_sheet_filler.config import (  # noqa: E402
    REPORTS_CASHSHEET_MAP, FILL_COL_MAP, CHECKING_COL_MAP,
    INFOR_TENDERS, TAVLO_TENDERS, CASHEET_TENDERS,
    CASH_SHEET_FOLDER, REPORTS_FOLDER, GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP,
)
from BE.src.time_tracker import TimeTracker  # noqa: E402

# Tender imports
try:
    from BE.src.tender_break.main import TenderBreakdownEngine  # noqa: E402
    from BE.src.tender_break.config import (  # noqa: E402
        FILENAME_TO_MASTER_NAME, LOCATION_START_COL,
        IMPORTANT_CASHEET_DATA_COL, DIRECTORY_PATHS,
        FIRST_DATE_ROW, DATE_COL,
    )
    _HAS_TENDER = True
except (ImportError, ModuleNotFoundError):
    _HAS_TENDER = False


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN CLASS
# ═══════════════════════════════════════════════════════════════════════════
class AutoFillCenter(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self._time_tracker = TimeTracker()
        self._runtime_controller = AutoFillRuntimeController(self)
        self._config_controller = AutoFillConfigController(self)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=0)   # tab bar
        self.grid_rowconfigure(2, weight=1)   # content

        self._build_header()
        self._build_tab_bar()
        self._build_pages()
        self._select_tab("cash_sheet")
        self._refresh_tracking_ui()

    def __getattr__(self, name):
        # Forward any private attribute access to one of the helper
        # controllers — keeps the public surface of AutoFillCenter focused
        # on view construction while the runtime/config logic lives elsewhere.
        if name.startswith("_"):
            runtime_controller = self.__dict__.get("_runtime_controller")
            config_controller = self.__dict__.get("_config_controller")
            for controller in (runtime_controller, config_controller):
                if controller is not None and hasattr(controller, name):
                    return getattr(controller, name)
        raise AttributeError(
            f"{type(self).__name__!s} has no attribute {name!r}")

    # ── Log card helpers (shared by both autofill tabs) ─────────────
    def _build_stat_badge(self, parent, color, initial="0"):
        """Pill-style label for one of the live ✓ / ⚠ / ✗ counters."""
        badge = ctk.CTkLabel(
            parent, text=initial,
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            text_color=color, fg_color="transparent")
        badge.pack(side="right", padx=(4, 0))
        return badge

    def _configure_log_tags(self, log_widget):
        """
        Attach Text-widget tags so structured log events get the right color.

        The tag names match the ``kind`` strings emitted by ProcessingTracker
        (and by the printer's ``_log`` helper). Lines come in via
        ``log_widget.insert("end", text + "\\n", kind)``.
        """
        log_widget.tag_config("info",    foreground=TEXT)
        log_widget.tag_config("detail",  foreground=TEXT_SEC)
        log_widget.tag_config("section", foreground=PURPLE)
        log_widget.tag_config("success", foreground=GREEN)
        log_widget.tag_config("warning", foreground=ORANGE)
        log_widget.tag_config("error",   foreground=RED)
        log_widget.tag_config("summary", foreground=TEXT)

    # ══════════════════════════════════════════════════════════════
    #  PRINT SETTINGS DIALOG
    #  Keeps the heavy printer UI out of the page so the Result Log
    #  always keeps its full height (previously the inline panel
    #  squeezed the log until it was unreadable).
    # ══════════════════════════════════════════════════════════════
    def _print_summary_text(self) -> str:
        """One-line description of the current print settings."""
        printer = self._printer_var.get()
        color = self._print_color_var.get()
        copies = self._print_copies_var.get().strip() or "1"
        plural = "copy" if copies == "1" else "copies"
        return f"{printer}  ·  {color}  ·  {copies} {plural}"

    def _refresh_print_summary(self):
        if self._cs_auto_print.get() == 1:
            self._print_summary.configure(text=self._print_summary_text())
        else:
            self._print_summary.configure(
                text="Reports first, then filled cash-sheet tabs")

    def _open_print_dialog(self):
        if self._cs_auto_print.get() != 1:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Print Settings")
        dialog.geometry("480x360")
        dialog.resizable(False, False)
        dialog.configure(fg_color=BG)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        body = ctk.CTkFrame(dialog, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=18)
        body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            body, text="Print Settings",
            font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
            text_color=TEXT).grid(row=0, column=0, columnspan=3,
                                  sticky="w", pady=(0, 12))

        # Printer + refresh
        ctk.CTkLabel(body, text="Printer",
                     font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TEXT_SEC).grid(row=1, column=0, sticky="w",
                                               pady=(0, 2))
        printers = ExcelPrinter.get_available_printers()
        if self._printer_var.get() not in (["System Default"] + printers):
            self._printer_var.set("System Default")
        self._printer_dropdown = ctk.CTkOptionMenu(
            body, variable=self._printer_var,
            values=["System Default"] + printers,
            font=ctk.CTkFont(family=FONT, size=11),
            fg_color=CARD, button_color=PURPLE,
            button_hover_color=PURPLE_DARK, text_color=TEXT,
            dropdown_font=ctk.CTkFont(family=FONT, size=11),
            height=32, corner_radius=6, dynamic_resizing=False)
        self._printer_dropdown.grid(row=2, column=0, columnspan=2,
                                    sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            body, text="Refresh", image=get_icon("refresh", 14, TEXT_SEC),
            width=88, height=32, corner_radius=6, fg_color=CARD,
            text_color=TEXT_SEC, hover_color=BORDER, border_width=1,
            border_color=BORDER, font=ctk.CTkFont(family=FONT, size=11),
            command=self._refresh_printers, cursor="hand2"
        ).grid(row=2, column=2, sticky="w")

        # Option grid
        opts = ctk.CTkFrame(body, fg_color="transparent")
        opts.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        for col in range(4):
            opts.grid_columnconfigure(col, weight=1)

        def _cell(col, label, build):
            cell = ctk.CTkFrame(opts, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=(0, 8))
            ctk.CTkLabel(
                cell, text=label,
                font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 3))
            build(cell).pack(fill="x")

        def _menu(parent, var, values):
            return ctk.CTkOptionMenu(
                parent, variable=var, values=values, height=32,
                font=ctk.CTkFont(family=FONT, size=11),
                fg_color=CARD, button_color=PURPLE,
                button_hover_color=PURPLE_DARK, text_color=TEXT,
                dropdown_font=ctk.CTkFont(family=FONT, size=11),
                dynamic_resizing=False)

        _cell(0, "Color", lambda p: _menu(
            p, self._print_color_var, ["Color", "Black and white"]))
        _cell(1, "Paper", lambda p: _menu(
            p, self._print_paper_var, ["Letter", "Legal", "A4", "A3", "Tabloid"]))
        _cell(2, "Orientation", lambda p: _menu(
            p, self._print_orientation_var, ["Landscape", "Portrait"]))
        _cell(3, "Copies", lambda p: ctk.CTkEntry(
            p, textvariable=self._print_copies_var, height=32,
            font=ctk.CTkFont(family=FONT, size=11), border_color=BORDER))

        check_row = ctk.CTkFrame(body, fg_color="transparent")
        check_row.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        ctk.CTkCheckBox(
            check_row, text="Double-sided", variable=self._print_duplex_var,
            font=ctk.CTkFont(family=FONT, size=11),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            border_color=BORDER).pack(side="left", padx=(0, 18))
        ctk.CTkCheckBox(
            check_row, text="Collate", variable=self._print_collate_var,
            font=ctk.CTkFont(family=FONT, size=11),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            border_color=BORDER).pack(side="left")

        # Buttons
        btns = ctk.CTkFrame(dialog, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(0, 16))

        def _save():
            self._refresh_print_summary()
            self._printer_dropdown = None
            dialog.destroy()

        def _cancel():
            self._printer_dropdown = None
            dialog.destroy()

        ctk.CTkButton(
            btns, text="Cancel", width=90, height=34, corner_radius=8,
            fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
            border_width=1, border_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=12),
            command=_cancel).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btns, text="Save", width=90, height=34, corner_radius=8,
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            command=_save).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", _cancel)

    # ══════════════════════════════════════════════════════════════
    #  HEADER (with time-saved badge)
    # ══════════════════════════════════════════════════════════════

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left")

        icon = ctk.CTkFrame(left, width=36, height=36, corner_radius=8,
                            fg_color=PURPLE_LIGHT)
        icon.pack(side="left", padx=(0, 10))
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text="", image=get_icon("autofill", 20, PURPLE)).place(
            relx=.5, rely=.5, anchor="center")

        tf = ctk.CTkFrame(left, fg_color="transparent")
        tf.pack(side="left")
        ctk.CTkLabel(tf, text="Autofill Center",
                     font=ctk.CTkFont(family=FONT, size=20, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(tf, text="Cash sheets, tender breakdowns, and print runs",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(anchor="w")

        # ── Time-saved badge ──
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right")

        ts_card = ctk.CTkFrame(right, fg_color=GREEN_BG, corner_radius=8,
                               border_width=1, border_color="#C8F0D4")
        ts_card.pack(side="right", padx=(8, 0))

        ts_inner = ctk.CTkFrame(ts_card, fg_color="transparent")
        ts_inner.pack(padx=14, pady=8)

        top_row = ctk.CTkFrame(ts_inner, fg_color="transparent")
        top_row.pack(anchor="e")
        ctk.CTkLabel(top_row, text="⏱",
                     font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 6))
        self._time_saved_value = ctk.CTkLabel(
            top_row,
            text=TimeTracker.format_time(
                self._time_tracker.get_total_minutes()),
            font=ctk.CTkFont(family=FONT, size=18, weight="bold"),
            text_color=GREEN)
        self._time_saved_value.pack(side="left")
        ctk.CTkLabel(top_row, text=" saved",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color="#2DA44E").pack(side="left", padx=(2, 6))
        self._tracking_toggle_btn = ctk.CTkButton(
            top_row, text="⏸", width=24, height=24, corner_radius=6,
            fg_color=PURPLE_SUBTLE, text_color=PURPLE, hover_color=PURPLE_LIGHT,
            font=ctk.CTkFont(size=11),
            command=self._toggle_tracking, cursor="hand2")
        self._tracking_toggle_btn.pack(side="left")

        last_run = self._time_tracker.get_last_run()
        self._last_run_label = ctk.CTkLabel(
            ts_inner,
            text=f"Last run: {last_run}" if last_run else "No runs yet",
            font=ctk.CTkFont(family=FONT, size=10), text_color=TEXT_MUTED)
        self._last_run_label.pack(anchor="e")
        self._refresh_tracking_ui()

    # ── Time Tracking Helpers ──
    def _refresh_tracking_ui(self):
        total = self._time_tracker.get_total_minutes()
        self._time_saved_value.configure(text=TimeTracker.format_time(total))
        last_run = self._time_tracker.get_last_run()
        self._last_run_label.configure(
            text=f"Last run: {last_run}" if last_run else "No runs yet")
        if self._time_tracker.is_enabled():
            self._tracking_toggle_btn.configure(
                text="⏸", fg_color=PURPLE_SUBTLE,
                text_color=PURPLE, hover_color=PURPLE_LIGHT)
        else:
            self._tracking_toggle_btn.configure(
                text="▶", fg_color=ORANGE_BG,
                text_color=ORANGE, hover_color="#FFE8CC")

    def _toggle_tracking(self):
        self._time_tracker.toggle_tracking()
        self._refresh_tracking_ui()

    def _record_and_refresh(self, run_type):
        self._time_tracker.record_run(run_type)
        self._refresh_tracking_ui()

    # ══════════════════════════════════════════════════════════════
    #  TAB BAR
    # ══════════════════════════════════════════════════════════════
    def _build_tab_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent", height=38)
        bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 0))
        self._tab_btns = {}
        self._tab_lines = {}
        tabs = [
            ("cash_sheet",  "Cash Sheet"),
            ("tender",      "Tender Breakdown"),
            ("cs_config",   "Cash Sheet Settings"),
            ("tb_config",   "Tender Settings"),
        ]
        for key, label in tabs:
            wrapper = ctk.CTkFrame(bar, fg_color="transparent")
            wrapper.pack(side="left", padx=(0, 2))
            btn = ctk.CTkButton(
                wrapper, text=label,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                fg_color="transparent", text_color=TEXT_MUTED,
                hover_color=PURPLE_SUBTLE, height=32, corner_radius=8,
                command=lambda k=key: self._select_tab(k), cursor="hand2")
            btn.pack(side="top")
            line = ctk.CTkFrame(wrapper, height=3, corner_radius=2,
                                fg_color="transparent")
            line.pack(fill="x", padx=6)
            self._tab_btns[key] = btn
            self._tab_lines[key] = line

    def _select_tab(self, key):
        for k in self._tab_btns:
            active = (k == key)
            self._tab_btns[k].configure(
                text_color=PURPLE if active else TEXT_MUTED,
                fg_color=PURPLE_SUBTLE if active else "transparent")
            self._tab_lines[k].configure(
                fg_color=PURPLE if active else "transparent")
        for page in self._pages.values():
            page.grid_forget()
        self._pages[key].grid(row=2, column=0, sticky="nsew")

    # ══════════════════════════════════════════════════════════════
    #  PAGES
    # ══════════════════════════════════════════════════════════════
    def _build_pages(self):
        self._pages = {}
        self._pages["cash_sheet"] = self._build_cash_sheet_page()
        self._pages["tender"] = self._build_tender_page()
        self._pages["cs_config"] = self._build_cs_config_page()
        self._pages["tb_config"] = self._build_tb_config_page()

    # ══════════════════════════════════════════════════════════════
    #  CASH SHEET PAGE
    # ══════════════════════════════════════════════════════════════
    def _build_cash_sheet_page(self):
        page = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=0)
        page.grid_rowconfigure(1, weight=1)

        card = _Card(page)
        card.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 8))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        inner.grid_columnconfigure(1, weight=1)
        _section_label(inner, "Run Setup", grid_pos=(0, 0, 2))

        self._cs_folder1_entry = self._folder_row(
            inner, 1, "Cash Sheet Folder:", sync_target="cash_sheet")
        self._cs_folder1_entry.configure(state="normal")
        self._cs_folder1_entry.insert(0, CASH_SHEET_FOLDER)
        self._cs_folder1_entry.configure(state="readonly")

        self._cs_folder2_entry = self._folder_row(
            inner, 2, "Day Reports Folder:", sync_target="reports")
        self._cs_folder2_entry.configure(state="normal")
        self._cs_folder2_entry.insert(0, REPORTS_FOLDER)
        self._cs_folder2_entry.configure(state="readonly")
        # ── Print Settings (compact row — full options live in a dialog) ──
        # State vars persist on the view so the runtime controller and the
        # popup dialog share them; the heavy printer UI is built on demand
        # in _open_print_dialog() so it can never squeeze the Result Log.
        default = ExcelPrinter.get_default_printer() or ""
        self._printer_var = ctk.StringVar(
            value=default if default else "System Default")
        self._print_color_var = ctk.StringVar(value="Color")
        self._print_paper_var = ctk.StringVar(value="Letter")
        self._print_orientation_var = ctk.StringVar(value="Landscape")
        self._print_duplex_var = ctk.IntVar(value=0)
        self._print_collate_var = ctk.IntVar(value=1)
        self._print_copies_var = ctk.StringVar(value="1")
        self._printer_dropdown = None  # created lazily inside the dialog

        print_frame = ctk.CTkFrame(
            inner, fg_color=BG, corner_radius=8,
            border_width=1, border_color=BORDER)
        print_frame.grid(row=3, column=0, columnspan=3,
                         sticky="ew", pady=(12, 0))
        print_frame.grid_columnconfigure(1, weight=1)

        self._cs_auto_print = ctk.CTkCheckBox(
            print_frame, text="Auto-print after filling",
            font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK, border_color=BORDER,
            command=self._toggle_printer_dropdown)
        self._cs_auto_print.grid(row=0, column=0, sticky="w",
                                 padx=12, pady=10)

        self._print_summary = ctk.CTkLabel(
            print_frame, text="Reports first, then filled cash-sheet tabs",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_MUTED)
        self._print_summary.grid(row=0, column=1, sticky="e", padx=(8, 8))

        self._print_options_btn = ctk.CTkButton(
            print_frame, text="Print options", image=get_icon("printer", 15, PURPLE),
            width=128, height=30, corner_radius=6,
            fg_color=CARD, text_color=PURPLE, hover_color=PURPLE_LIGHT,
            border_width=1, border_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            command=self._open_print_dialog, cursor="hand2", state="disabled")
        self._print_options_btn.grid(row=0, column=2, sticky="e",
                                     padx=(0, 12), pady=10)

        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._cs_run_btn = ctk.CTkButton(
            bf, text="Run Cash Sheet Autofill",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            height=40, corner_radius=8,
            command=self._run_cash_sheet_autofill, cursor="hand2")
        self._cs_run_btn.pack(fill="x")

        log_card = _Card(page)
        log_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(log_header, text="Result Log",
                     font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            log_header, text="Clear", width=50, height=24, corner_radius=6,
            fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=11),
            command=lambda: self._clear_log(self._cs_log)).pack(side="right")
        # Live counters — updated as events stream in. Order on the right
        # is: [Clear button] [✗ fail] [⚠ warn] [✓ ok] [Status]
        self._cs_fail_badge = self._build_stat_badge(log_header, RED, "✗ 0")
        self._cs_warn_badge = self._build_stat_badge(log_header, ORANGE, "⚠ 0")
        self._cs_succ_badge = self._build_stat_badge(log_header, GREEN, "✓ 0")
        self._cs_status = ctk.CTkLabel(
            log_header, text="Ready",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_MUTED)
        self._cs_status.pack(side="right", padx=(8, 10))

        # Thin divider between the header row and the textbox — replaces
        # the noisy "===" lines we used to print into the log.
        ctk.CTkFrame(log_card, fg_color=BORDER, height=1).pack(
            fill="x", padx=12, pady=(0, 6))

        self._cs_log = ctk.CTkTextbox(
            log_card, fg_color=BG, corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT, wrap="word", state="disabled",
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        self._cs_log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._configure_log_tags(self._cs_log)
        return page

    # ══════════════════════════════════════════════════════════════
    #  TENDER BREAKDOWN PAGE
    # ══════════════════════════════════════════════════════════════
    def _build_tender_page(self):
        page = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=0)
        page.grid_rowconfigure(1, weight=1)

        card = _Card(page)
        card.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 8))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        inner.grid_columnconfigure(1, weight=1)
        _section_label(inner, "Settings", grid_pos=(0, 0, 2))

        # Cash Sheets folder (same folder as cash sheet tab)
        self._tb_folder_entry = self._folder_row(
            inner, 1, "Cash Sheets Folder:", sync_target="cash_sheet")
        self._tb_folder_entry.configure(state="normal")
        self._tb_folder_entry.insert(0, CASH_SHEET_FOLDER)
        self._tb_folder_entry.configure(state="readonly")

        # Master Breakdown file
        self._tb_file_entry = self._file_row(
            inner, 2, "Tender Breakdown File:", sync_target="master_path")
        if _HAS_TENDER:
            master = DIRECTORY_PATHS.get("master_path", "")
            self._tb_file_entry.configure(state="normal")
            self._tb_file_entry.insert(0, master)
            self._tb_file_entry.configure(state="readonly")

        # Run button
        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._tb_run_btn = ctk.CTkButton(
            bf, text="Run Tender Breakdown Autofill",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            height=40, corner_radius=10,
            command=self._run_tender_autofill, cursor="hand2")
        self._tb_run_btn.pack(fill="x")

        if not _HAS_TENDER:
            self._tb_run_btn.configure(state="disabled",
                                       text="Tender module not found")

        # Result log — same structure as the cash sheet card so the user
        # gets a consistent experience across tabs.
        log_card = _Card(page)
        log_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(log_header, text="Result Log",
                     font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            log_header, text="Clear", width=50, height=24, corner_radius=6,
            fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=11),
            command=lambda: self._clear_log(self._tb_log)).pack(side="right")
        self._tb_fail_badge = self._build_stat_badge(log_header, RED, "✗ 0")
        self._tb_warn_badge = self._build_stat_badge(log_header, ORANGE, "⚠ 0")
        self._tb_succ_badge = self._build_stat_badge(log_header, GREEN, "✓ 0")
        self._tb_status = ctk.CTkLabel(
            log_header, text="Ready",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_MUTED)
        self._tb_status.pack(side="right", padx=(8, 10))

        ctk.CTkFrame(log_card, fg_color=BORDER, height=1).pack(
            fill="x", padx=12, pady=(0, 6))

        self._tb_log = ctk.CTkTextbox(
            log_card, fg_color=BG, corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT, wrap="word", state="disabled",
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        self._tb_log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self._configure_log_tags(self._tb_log)
        return page

    # ══════════════════════════════════════════════════════════════
    #  CASH SHEET CONFIGURATION PAGE
    # ══════════════════════════════════════════════════════════════
    def _build_cs_config_page(self):
        page = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        page.grid_columnconfigure(0, weight=1)
        grid_row = 0

        # ── Page Header ────────────────────────────────────────
        hdr_frame = ctk.CTkFrame(page, fg_color="transparent")
        hdr_frame.grid(row=grid_row, column=0,
                       sticky="ew", padx=20, pady=(16, 4))
        icon = ctk.CTkFrame(hdr_frame, width=32, height=32, corner_radius=8,
                            fg_color=PURPLE_LIGHT)
        icon.pack(side="left", padx=(0, 10))
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text="", image=get_icon("revenue", 17, PURPLE)).place(
            relx=.5, rely=.5, anchor="center")
        lbl_frame = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        lbl_frame.pack(side="left")
        ctk.CTkLabel(lbl_frame, text="Cash Sheet Settings",
                     font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
                     text_color=PURPLE).pack(anchor="w")
        ctk.CTkLabel(lbl_frame, text="Folders, location mappings, column numbers, and tender names for the cash sheet autofill",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(anchor="w")
        grid_row += 1

        # ── Folder Paths ───────────────────────────────────────
        c_paths = _Card(page)
        c_paths.grid(row=grid_row, column=0,
                     sticky="ew", padx=20, pady=(10, 8))
        grid_row += 1
        w_paths = ctk.CTkFrame(c_paths, fg_color="transparent")
        w_paths.pack(fill="x", padx=16, pady=12)
        w_paths.grid_columnconfigure(1, weight=1)
        _section_label(w_paths, "Folder Paths", grid_pos=(0, 0, 2))
        self._config_cs_folder = self._folder_row(
            w_paths, 1, "Cash Sheet Folder:", sync_target="cash_sheet")
        self._config_cs_folder.configure(state="normal")
        self._config_cs_folder.insert(0, CASH_SHEET_FOLDER)
        self._config_cs_folder.configure(state="readonly")
        self._config_rep_folder = self._folder_row(
            w_paths, 2, "Day Reports Folder:", sync_target="reports")
        self._config_rep_folder.configure(state="normal")
        self._config_rep_folder.insert(0, REPORTS_FOLDER)
        self._config_rep_folder.configure(state="readonly")

        # ── Cash Sheet Locations ───────────────────────────────
        c1 = _Card(page)
        c1.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        w1 = ctk.CTkFrame(c1, fg_color="transparent")
        w1.pack(fill="x", padx=16, pady=12)
        self._cs_loc_container = ctk.CTkFrame(w1, fg_color="transparent")
        self._cs_loc_container._count_label = _card_header(
            w1, "Cash Sheet Locations",
            subtitle=("Where each Infor / Tavlo report location lands: "
                      "which cash-sheet file, which register row inside it, "
                      "and the name shown on the Analytics page."),
            add_cb=self._add_cs_location)
        self._cs_loc_container.pack(fill="x")
        self._refresh_cs_loc_table()

        # ── Grubhub Venues ─────────────────────────────────────
        c_gh = _Card(page)
        c_gh.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        w_gh = ctk.CTkFrame(c_gh, fg_color="transparent")
        w_gh.pack(fill="x", padx=16, pady=12)
        self._gh_loc_container = ctk.CTkFrame(w_gh, fg_color="transparent")
        self._gh_loc_container._count_label = _card_header(
            w_gh, "Grubhub Venues",
            subtitle=("Where each venue on the Grubhub report lands: "
                      "which cash-sheet file, which row inside it, and the "
                      "name shown on the Analytics page."),
            add_cb=self._add_gh_venue)
        self._gh_loc_container.pack(fill="x")
        self._refresh_gh_venue_table()

        # ── Fill Columns ───────────────────────────────────────
        c2 = _Card(page)
        c2.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        w2 = ctk.CTkFrame(c2, fg_color="transparent")
        w2.pack(fill="x", padx=16, pady=12)
        self._fill_tbl = ctk.CTkFrame(w2, fg_color="transparent")
        self._fill_tbl._count_label = _card_header(
            w2, "Fill Columns",
            subtitle=("Cash-sheet column each report value is written to "
                      "(column A = 1)."),
            add_cb=lambda: self._add_kv(FILL_COL_MAP, self._fill_tbl))
        self._fill_tbl.pack(fill="x")
        self._refresh_kv_table(self._fill_tbl, FILL_COL_MAP)

        # ── Checking Columns ───────────────────────────────────
        ctk.CTkFrame(w2, fg_color=BORDER, height=1).pack(fill="x", pady=10)
        self._chk_tbl = ctk.CTkFrame(w2, fg_color="transparent")
        self._chk_tbl._count_label = _card_header(
            w2, "Checking Columns",
            subtitle=("Columns read back after filling to double-check the "
                      "sheet's totals (column A = 1)."),
            add_cb=lambda: self._add_kv(CHECKING_COL_MAP, self._chk_tbl))
        self._chk_tbl.pack(fill="x")
        self._refresh_kv_table(self._chk_tbl, CHECKING_COL_MAP)

        # ── Tender Mappings (Cash Sheet) ───────────────────────
        tender_maps = [
            ("Infor Tenders", "Tender Name", "Internal Key", INFOR_TENDERS,
             "How each tender named on Infor day reports is counted: "
             "report name → internal tender key."),
            ("Tavlo Tenders", "Tender Name", "Internal Key", TAVLO_TENDERS,
             "How each tender named on Tavlo reports is counted: "
             "report name → internal tender key."),
            ("Grubhub Tenders", "Payment Method", "Internal Key",
             GRUBHUB_TENDERS,
             "How each Grubhub payment method is counted: "
             "payment method → internal tender key."),
            ("Cash Sheet Tenders", "Tender Key", "Default Value",
             CASHEET_TENDERS,
             "Internal tender keys tracked on every cash-sheet row, with "
             "the starting amount for each."),
        ]
        for heading, kl, vl, data, subtitle in tender_maps:
            tc = _Card(page)
            tc.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
            grid_row += 1
            wt = ctk.CTkFrame(tc, fg_color="transparent")
            wt.pack(fill="x", padx=16, pady=12)
            container = ctk.CTkFrame(wt, fg_color="transparent")
            container._count_label = _card_header(
                wt, heading, subtitle=subtitle,
                add_cb=lambda d=data, c=container, k=kl, v=vl:
                self._add_tender(d, c, k, v))
            container.pack(fill="x")
            self._refresh_tender_table(container, data, kl, vl)

        return page

    # ══════════════════════════════════════════════════════════════
    #  TENDER BREAKDOWN CONFIGURATION PAGE
    # ══════════════════════════════════════════════════════════════
    def _build_tb_config_page(self):
        page = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        page.grid_columnconfigure(0, weight=1)
        grid_row = 0

        # ── Page Header ────────────────────────────────────────
        hdr_frame = ctk.CTkFrame(page, fg_color="transparent")
        hdr_frame.grid(row=grid_row, column=0,
                       sticky="ew", padx=20, pady=(16, 4))
        icon = ctk.CTkFrame(hdr_frame, width=32, height=32, corner_radius=8,
                            fg_color=PURPLE_LIGHT)
        icon.pack(side="left", padx=(0, 10))
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text="", image=get_icon("analytics", 17, PURPLE)).place(
            relx=.5, rely=.5, anchor="center")
        lbl_frame = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        lbl_frame.pack(side="left")
        ctk.CTkLabel(lbl_frame, text="Tender Breakdown Settings",
                     font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
                     text_color=PURPLE).pack(anchor="w")
        ctk.CTkLabel(lbl_frame, text="Master breakdown file, date settings, filename mappings, and column layout",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(anchor="w")
        grid_row += 1

        if not _HAS_TENDER:
            # ── Module not found notice ────────────────────────
            notice = _Card(page)
            notice.grid(row=grid_row, column=0,
                        sticky="ew", padx=20, pady=(10, 8))
            nw = ctk.CTkFrame(notice, fg_color="transparent")
            nw.pack(fill="x", padx=16, pady=16)
            ctk.CTkLabel(nw, text="Tender breakdown module not found",
                         font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                         text_color=ORANGE).pack(anchor="w")
            ctk.CTkLabel(nw, text="Install or configure the tender_break module to enable this section.",
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_SEC).pack(anchor="w", pady=(4, 0))
            return page

        # ── Paths & Settings ───────────────────────────────────
        ct_paths = _Card(page)
        ct_paths.grid(row=grid_row, column=0,
                      sticky="ew", padx=20, pady=(10, 8))
        grid_row += 1
        wtp = ctk.CTkFrame(ct_paths, fg_color="transparent")
        wtp.pack(fill="x", padx=16, pady=12)
        wtp.grid_columnconfigure(1, weight=1)
        _section_label(wtp, "Paths & Settings", grid_pos=(0, 0, 2))
        self._config_tb_master = self._file_row(
            wtp, 1, "Breakdown File:", sync_target="master_path")
        self._config_tb_master.configure(state="normal")
        self._config_tb_master.insert(
            0, DIRECTORY_PATHS.get("master_path", ""))
        self._config_tb_master.configure(state="readonly")

        # Date col + first date row
        ctk.CTkLabel(wtp,
                     text=("Where dates live on each cash sheet: the column "
                           "holding the date (A = 1) and the first row that "
                           "contains one."),
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ctk.CTkLabel(wtp, text="Date Column:",
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT).grid(row=3, column=0, sticky="w", pady=(6, 0))
        self._config_date_col = ctk.CTkEntry(
            wtp, height=30, border_color=BORDER, width=80,
            font=ctk.CTkFont(family=FONT, size=11))
        self._config_date_col.grid(
            row=3, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        self._config_date_col.insert(0, str(DATE_COL))

        ctk.CTkLabel(wtp, text="First Date Row:",
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT).grid(row=4, column=0, sticky="w", pady=(6, 0))
        self._config_first_row = ctk.CTkEntry(
            wtp, height=30, border_color=BORDER, width=80,
            font=ctk.CTkFont(family=FONT, size=11))
        self._config_first_row.grid(
            row=4, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        self._config_first_row.insert(0, str(FIRST_DATE_ROW))

        # Save settings button
        ctk.CTkButton(
            wtp, text="Save Date Settings", width=140, height=30,
            corner_radius=8, fg_color=GREEN, hover_color="#2DA44E",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            command=self._save_tender_settings
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # ── Filename Mappings ──────────────────────────────────
        cf = _Card(page)
        cf.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        wf = ctk.CTkFrame(cf, fg_color="transparent")
        wf.pack(fill="x", padx=16, pady=12)
        self._fn_map_container = ctk.CTkFrame(wf, fg_color="transparent")
        self._fn_map_container._count_label = _card_header(
            wf, "Filename Mappings",
            subtitle=("Connects each cash-sheet file (by filename keyword) "
                      "to its location block in the master breakdown file."),
            add_cb=self._add_filename_mapping)
        self._fn_map_container.pack(fill="x")
        self._refresh_filename_mapping_table()

        # ── Location Start Columns ─────────────────────────────
        cl = _Card(page)
        cl.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        wl = ctk.CTkFrame(cl, fg_color="transparent")
        wl.pack(fill="x", padx=16, pady=12)
        self._loc_col_container = ctk.CTkFrame(wl, fg_color="transparent")
        self._loc_col_container._count_label = _card_header(
            wl, "Location Start Columns",
            subtitle=("First column of each location's block in the master "
                      "breakdown file (column A = 1)."),
            add_cb=lambda: self._add_tender_kv(
                LOCATION_START_COL, self._loc_col_container,
                "Location Name", "Start Column"))
        self._loc_col_container.pack(fill="x")
        self._refresh_tender_kv_table(
            self._loc_col_container, LOCATION_START_COL,
            "Location Name", "Start Column")

        # ── Data Columns to Copy ───────────────────────────────
        ci = _Card(page)
        ci.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 12))
        grid_row += 1
        wi = ctk.CTkFrame(ci, fg_color="transparent")
        wi.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(wi, text="Data Columns to Copy",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(wi, text=("Cash-sheet columns copied into the master "
                               "breakdown for every row. Whole numbers "
                               "separated by commas (column A = 1)."),
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(anchor="w", pady=(0, 6))
        self._config_data_cols = ctk.CTkEntry(
            wi, height=30, border_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=12))
        self._config_data_cols.pack(fill="x", pady=(4, 0))
        self._config_data_cols.insert(
            0, ", ".join(str(c) for c in IMPORTANT_CASHEET_DATA_COL))
        ctk.CTkButton(
            wi, text="Save Columns", width=120, height=30,
            corner_radius=8, fg_color=GREEN, hover_color="#2DA44E",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            command=self._save_tender_data_cols
        ).pack(anchor="w", pady=(8, 0))

        return page
