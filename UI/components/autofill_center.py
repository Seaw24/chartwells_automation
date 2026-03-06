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
        add_button as _add_button,
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
        add_button as _add_button,
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
        if name.startswith("_"):
            runtime_controller = self.__dict__.get("_runtime_controller")
            config_controller = self.__dict__.get("_config_controller")
            for controller in (runtime_controller, config_controller):
                if controller is not None and hasattr(controller, name):
                    return getattr(controller, name)
        raise AttributeError(
            f"{type(self).__name__!s} has no attribute {name!r}")

    # ══════════════════════════════════════════════════════════════
    #  HEADER (with time-saved badge)
    # ══════════════════════════════════════════════════════════════

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 4))

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left")

        icon = ctk.CTkFrame(left, width=36, height=36, corner_radius=10,
                            fg_color=PURPLE_LIGHT)
        icon.pack(side="left", padx=(0, 10))
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text="💰", font=ctk.CTkFont(size=16)).place(
            relx=.5, rely=.5, anchor="center")

        tf = ctk.CTkFrame(left, fg_color="transparent")
        tf.pack(side="left")
        ctk.CTkLabel(tf, text="Autofill Center",
                     font=ctk.CTkFont(family=FONT, size=20, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(tf, text="Configure and run automatic data filling",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(anchor="w")

        # ── Time-saved badge ──
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right")

        ts_card = ctk.CTkFrame(right, fg_color=GREEN_BG, corner_radius=12,
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
            ("cash_sheet",  "💰 Cash Sheet"),
            ("tender",      "📊 Tender Breakdown"),
            ("cs_config",   "⚙️ CS Config"),
            ("tb_config",   "⚙️ TB Config"),
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
        _section_label(inner, "⚙️ Settings", grid_pos=(0, 0, 2))

        self._cs_folder1_entry = self._folder_row(
            inner, 1, "📁 Cash Sheet Folder:", sync_target="cash_sheet")
        self._cs_folder1_entry.configure(state="normal")
        self._cs_folder1_entry.insert(0, CASH_SHEET_FOLDER)
        self._cs_folder1_entry.configure(state="readonly")

        self._cs_folder2_entry = self._folder_row(
            inner, 2, "📊 Day Reports Folder:", sync_target="reports")
        self._cs_folder2_entry.configure(state="normal")
        self._cs_folder2_entry.insert(0, REPORTS_FOLDER)
        self._cs_folder2_entry.configure(state="readonly")
        # ── Print Settings Row ──
        print_frame = ctk.CTkFrame(inner, fg_color="transparent")
        print_frame.grid(row=3, column=0, columnspan=3,
                         sticky="ew", pady=(10, 0))

        self._cs_auto_print = ctk.CTkCheckBox(
            print_frame, text="🖨️ Auto-print after filling",
            font=ctk.CTkFont(family=FONT, size=11),
            fg_color=PURPLE, hover_color=PURPLE_DARK, border_color=BORDER,
            command=self._toggle_printer_dropdown)
        self._cs_auto_print.pack(side="left")

        # Printer selector (hidden until checkbox is checked)
        self._printer_frame = ctk.CTkFrame(print_frame, fg_color="transparent")

        ctk.CTkLabel(self._printer_frame, text="Printer:",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(side="left", padx=(12, 4))

        printers = ExcelPrinter.get_available_printers()
        default = ExcelPrinter.get_default_printer() or ""
        self._printer_var = ctk.StringVar(
            value=default if default else "System Default")
        self._printer_dropdown = ctk.CTkOptionMenu(
            self._printer_frame, variable=self._printer_var,
            values=["System Default"] + printers,
            font=ctk.CTkFont(family=FONT, size=11),
            fg_color=PURPLE, button_color=PURPLE_DARK,
            button_hover_color=PURPLE,
            dropdown_font=ctk.CTkFont(family=FONT, size=11),
            width=350, height=28, corner_radius=8,
            dynamic_resizing=False)
        self._printer_dropdown.pack(side="left", padx=(0, 8))

        # Refresh printers button
        ctk.CTkButton(
            self._printer_frame, text="🔄", width=28, height=28,
            corner_radius=6, fg_color=BG, text_color=TEXT_SEC,
            hover_color=BORDER, font=ctk.CTkFont(size=12),
            command=self._refresh_printers, cursor="hand2"
        ).pack(side="left")

        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._cs_run_btn = ctk.CTkButton(
            bf, text="🚀  Run Cash Sheet Autofill",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            height=40, corner_radius=10,
            command=self._run_cash_sheet_autofill, cursor="hand2")
        self._cs_run_btn.pack(fill="x")

        log_card = _Card(page)
        log_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(log_header, text="📋 Result Log",
                     font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            log_header, text="Clear", width=50, height=24, corner_radius=6,
            fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=11),
            command=lambda: self._clear_log(self._cs_log)).pack(side="right")
        self._cs_status = ctk.CTkLabel(
            log_header, text="Ready",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_MUTED)
        self._cs_status.pack(side="right", padx=(0, 10))

        self._cs_log = ctk.CTkTextbox(
            log_card, fg_color=BG, corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT, wrap="word", state="disabled",
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        self._cs_log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
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
        _section_label(inner, "⚙️ Settings", grid_pos=(0, 0, 2))

        # Cash Sheets folder (same folder as cash sheet tab)
        self._tb_folder_entry = self._folder_row(
            inner, 1, "📁 Cash Sheets Folder:", sync_target="cash_sheet")
        self._tb_folder_entry.configure(state="normal")
        self._tb_folder_entry.insert(0, CASH_SHEET_FOLDER)
        self._tb_folder_entry.configure(state="readonly")

        # Master Breakdown file
        self._tb_file_entry = self._file_row(
            inner, 2, "📄 Tender Breakdown File:", sync_target="master_path")
        if _HAS_TENDER:
            master = DIRECTORY_PATHS.get("master_path", "")
            self._tb_file_entry.configure(state="normal")
            self._tb_file_entry.insert(0, master)
            self._tb_file_entry.configure(state="readonly")

        # Run button
        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._tb_run_btn = ctk.CTkButton(
            bf, text="🚀  Run Tender Breakdown Autofill",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            height=40, corner_radius=10,
            command=self._run_tender_autofill, cursor="hand2")
        self._tb_run_btn.pack(fill="x")

        if not _HAS_TENDER:
            self._tb_run_btn.configure(state="disabled",
                                       text="⚠️  Tender module not found")

        # Result log
        log_card = _Card(page)
        log_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(log_header, text="📋 Result Log",
                     font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(
            log_header, text="Clear", width=50, height=24, corner_radius=6,
            fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=11),
            command=lambda: self._clear_log(self._tb_log)).pack(side="right")
        self._tb_status = ctk.CTkLabel(
            log_header, text="Ready",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_MUTED)
        self._tb_status.pack(side="right", padx=(0, 10))

        self._tb_log = ctk.CTkTextbox(
            log_card, fg_color=BG, corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT, wrap="word", state="disabled",
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        self._tb_log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
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
        ctk.CTkLabel(icon, text="💰", font=ctk.CTkFont(size=14)).place(
            relx=.5, rely=.5, anchor="center")
        lbl_frame = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        lbl_frame.pack(side="left")
        ctk.CTkLabel(lbl_frame, text="Cash Sheet Configuration",
                     font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
                     text_color=PURPLE).pack(anchor="w")
        ctk.CTkLabel(lbl_frame, text="Manage folder paths, location mappings, column settings & tenders",
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
        _section_label(w_paths, "📂 Folder Paths", grid_pos=(0, 0, 2))
        self._config_cs_folder = self._folder_row(
            w_paths, 1, "📁 Cash Sheet Folder:", sync_target="cash_sheet")
        self._config_cs_folder.configure(state="normal")
        self._config_cs_folder.insert(0, CASH_SHEET_FOLDER)
        self._config_cs_folder.configure(state="readonly")
        self._config_rep_folder = self._folder_row(
            w_paths, 2, "📊 Day Reports Folder:", sync_target="reports")
        self._config_rep_folder.configure(state="normal")
        self._config_rep_folder.insert(0, REPORTS_FOLDER)
        self._config_rep_folder.configure(state="readonly")

        # ── CS Location Mappings ───────────────────────────────
        c1 = _Card(page)
        c1.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        w1 = ctk.CTkFrame(c1, fg_color="transparent")
        w1.pack(fill="x", padx=16, pady=12)
        hdr = ctk.CTkFrame(w1, fg_color="transparent")
        hdr.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hdr, text="🏢 Cash Sheet Location Mappings",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self._cs_loc_count = ctk.CTkLabel(
            hdr, text=f"({len(REPORTS_CASHSHEET_MAP)} locations)",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_MUTED)
        self._cs_loc_count.pack(side="left", padx=(8, 0))
        _add_button(hdr, self._add_cs_location)
        self._cs_loc_container = ctk.CTkFrame(w1, fg_color="transparent")
        self._cs_loc_container.pack(fill="x")
        self._refresh_cs_loc_table()

        # ── Grubhub Venue Mappings ─────────────────────────────
        c_gh = _Card(page)
        c_gh.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        w_gh = ctk.CTkFrame(c_gh, fg_color="transparent")
        w_gh.pack(fill="x", padx=16, pady=12)
        hdr_gh = ctk.CTkFrame(w_gh, fg_color="transparent")
        hdr_gh.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hdr_gh, text="🍔 Grubhub Venue Mappings",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self._gh_loc_count = ctk.CTkLabel(
            hdr_gh, text=f"({len(GRUBHUB_VENUE_MAP)} venues)",
            font=ctk.CTkFont(family=FONT, size=11), text_color=TEXT_MUTED)
        self._gh_loc_count.pack(side="left", padx=(8, 0))
        _add_button(hdr_gh, self._add_gh_venue)
        self._gh_loc_container = ctk.CTkFrame(w_gh, fg_color="transparent")
        self._gh_loc_container.pack(fill="x")
        self._refresh_gh_venue_table()

        # ── Fill Column Mappings ───────────────────────────────
        c2 = _Card(page)
        c2.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        w2 = ctk.CTkFrame(c2, fg_color="transparent")
        w2.pack(fill="x", padx=16, pady=12)
        hdr2 = ctk.CTkFrame(w2, fg_color="transparent")
        hdr2.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hdr2, text="📐 Fill Column Mappings",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        _add_button(hdr2, lambda: self._add_kv(FILL_COL_MAP, self._fill_tbl))
        self._fill_tbl = ctk.CTkFrame(w2, fg_color="transparent")
        self._fill_tbl.pack(fill="x")
        self._refresh_kv_table(self._fill_tbl, FILL_COL_MAP)

        # ── Checking Columns ───────────────────────────────────
        ctk.CTkFrame(w2, fg_color=BORDER, height=1).pack(fill="x", pady=10)
        hdr3 = ctk.CTkFrame(w2, fg_color="transparent")
        hdr3.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hdr3, text="✅ Checking Columns",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        _add_button(hdr3, lambda: self._add_kv(
            CHECKING_COL_MAP, self._chk_tbl))
        self._chk_tbl = ctk.CTkFrame(w2, fg_color="transparent")
        self._chk_tbl.pack(fill="x")
        self._refresh_kv_table(self._chk_tbl, CHECKING_COL_MAP)

        # ── Tender Mappings (Cash Sheet) ───────────────────────
        tender_maps = [
            ("📄 Infor Tenders", "Tender Name", "Internal Key", INFOR_TENDERS),
            ("📄 Tavlo Tenders", "Tender Name", "Internal Key", TAVLO_TENDERS),
            ("🍔 Grubhub Tenders", "Payment Method",
             "Internal Key", GRUBHUB_TENDERS),
            ("📋 Cash Sheet Tenders", "Key", "Default", CASHEET_TENDERS),
        ]
        for heading, kl, vl, data in tender_maps:
            tc = _Card(page)
            tc.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
            grid_row += 1
            wt = ctk.CTkFrame(tc, fg_color="transparent")
            wt.pack(fill="x", padx=16, pady=12)
            ht = ctk.CTkFrame(wt, fg_color="transparent")
            ht.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(ht, text=heading,
                         font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                         text_color=TEXT).pack(side="left")
            container = ctk.CTkFrame(wt, fg_color="transparent")
            container.pack(fill="x")
            _add_button(ht, lambda d=data, c=container, k=kl, v=vl:
                        self._add_tender(d, c, k, v))
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
        ctk.CTkLabel(icon, text="📊", font=ctk.CTkFont(size=14)).place(
            relx=.5, rely=.5, anchor="center")
        lbl_frame = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        lbl_frame.pack(side="left")
        ctk.CTkLabel(lbl_frame, text="Tender Breakdown Configuration",
                     font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
                     text_color=PURPLE).pack(anchor="w")
        ctk.CTkLabel(lbl_frame, text="Manage breakdown file, date settings, filename mappings & columns",
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
            ctk.CTkLabel(nw, text="⚠️  Tender breakdown module not found",
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
        _section_label(wtp, "📂 Paths & Settings", grid_pos=(0, 0, 2))
        self._config_tb_master = self._file_row(
            wtp, 1, "📄 Breakdown File:", sync_target="master_path")
        self._config_tb_master.configure(state="normal")
        self._config_tb_master.insert(
            0, DIRECTORY_PATHS.get("master_path", ""))
        self._config_tb_master.configure(state="readonly")

        # Date col + first date row
        ctk.CTkLabel(wtp, text="📅 Date Column:",
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self._config_date_col = ctk.CTkEntry(
            wtp, height=30, border_color=BORDER, width=80,
            font=ctk.CTkFont(family=FONT, size=11))
        self._config_date_col.grid(
            row=2, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        self._config_date_col.insert(0, str(DATE_COL))

        ctk.CTkLabel(wtp, text="📍 First Date Row:",
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT).grid(row=3, column=0, sticky="w", pady=(6, 0))
        self._config_first_row = ctk.CTkEntry(
            wtp, height=30, border_color=BORDER, width=80,
            font=ctk.CTkFont(family=FONT, size=11))
        self._config_first_row.grid(
            row=3, column=1, sticky="w", padx=(8, 0), pady=(6, 0))
        self._config_first_row.insert(0, str(FIRST_DATE_ROW))

        # Save settings button
        ctk.CTkButton(
            wtp, text="💾 Save Settings", width=120, height=30,
            corner_radius=8, fg_color=GREEN, hover_color="#2DA44E",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            command=self._save_tender_settings
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # ── Filename → Master Mappings ─────────────────────────
        cf = _Card(page)
        cf.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        wf = ctk.CTkFrame(cf, fg_color="transparent")
        wf.pack(fill="x", padx=16, pady=12)
        hf = ctk.CTkFrame(wf, fg_color="transparent")
        hf.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hf, text="📂 Filename → Master Name Mappings",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self._fn_map_count = ctk.CTkLabel(
            hf, text="", font=ctk.CTkFont(family=FONT, size=11),
            text_color=TEXT_MUTED)
        self._fn_map_count.pack(side="left", padx=(8, 0))
        _add_button(hf, self._add_filename_mapping)
        self._fn_map_container = ctk.CTkFrame(wf, fg_color="transparent")
        self._fn_map_container.pack(fill="x")
        self._refresh_filename_mapping_table()

        # ── Location Start Columns ─────────────────────────────
        cl = _Card(page)
        cl.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        wl = ctk.CTkFrame(cl, fg_color="transparent")
        wl.pack(fill="x", padx=16, pady=12)
        hl = ctk.CTkFrame(wl, fg_color="transparent")
        hl.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hl, text="📐 Location Start Columns",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self._loc_col_count = ctk.CTkLabel(
            hl, text="", font=ctk.CTkFont(family=FONT, size=11),
            text_color=TEXT_MUTED)
        self._loc_col_count.pack(side="left", padx=(8, 0))
        _add_button(hl, lambda: self._add_tender_kv(
            LOCATION_START_COL, self._loc_col_container,
            "Location Name", "Start Column"))
        self._loc_col_container = ctk.CTkFrame(wl, fg_color="transparent")
        self._loc_col_container.pack(fill="x")
        self._loc_col_container._count_label = self._loc_col_count
        self._refresh_tender_kv_table(
            self._loc_col_container, LOCATION_START_COL,
            "Location Name", "Start Column")

        # ── Important Data Columns ─────────────────────────────
        ci = _Card(page)
        ci.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 12))
        grid_row += 1
        wi = ctk.CTkFrame(ci, fg_color="transparent")
        wi.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(wi, text="📊 Important Casheet Data Columns",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(wi, text="Comma-separated column numbers extracted from each cash sheet row:",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(anchor="w")
        self._config_data_cols = ctk.CTkEntry(
            wi, height=30, border_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=12))
        self._config_data_cols.pack(fill="x", pady=(4, 0))
        self._config_data_cols.insert(
            0, ", ".join(str(c) for c in IMPORTANT_CASHEET_DATA_COL))
        ctk.CTkButton(
            wi, text="💾 Save Columns", width=120, height=30,
            corner_radius=8, fg_color=GREEN, hover_color="#2DA44E",
            font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
            command=self._save_tender_data_cols
        ).pack(anchor="w", pady=(8, 0))

        return page
