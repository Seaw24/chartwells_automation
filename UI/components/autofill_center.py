"""
AutoFill Center - Cash Sheet & Tender Breakdown Autofill UI
Compact, lightweight version with inline result log.
"""

import customtkinter as ctk  # noqa: E402
from tkinter import filedialog, messagebox  # noqa: E402
import threading  # noqa: E402
# Printer dropdown
from BE.src.printer import ExcelPrinter
from BE.src.cash_sheet_filler.main import CashSheetAutofillEngine  # noqa: E402
from BE.src.cash_sheet_filler.config import (  # noqa: E402
    REPORTS_CASHSHEET_MAP, FILL_COL_MAP, CHECKING_COL_MAP,
    INFOR_TENDERS, TAVLO_TENDERS, CASHEET_TENDERS,
    CASH_SHEET_FOLDER, REPORTS_FOLDER, GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP,
    load_config as load_cash_sheet_config,
    save_config as save_cash_sheet_config,
)
from BE.src.time_tracker import TimeTracker  # noqa: E402

# Tender imports
try:
    from BE.src.tender_break.main import TenderBreakdownEngine  # noqa: E402
    from BE.src.tender_break.config import (  # noqa: E402
        FILENAME_TO_MASTER_NAME, LOCATION_START_COL,
        IMPORTANT_CASHEET_DATA_COL, DIRECTORY_PATHS,
        FIRST_DATE_ROW, DATE_COL,
        load_config as load_tender_config,
        save_config as save_tender_config,
    )
    _HAS_TENDER = True
except Exception:
    _HAS_TENDER = False

# ── Color Palette ──────────────────────────────────────────────────────────
PURPLE = "#6C5CE7"
PURPLE_DARK = "#5B4CD6"
PURPLE_LIGHT = "#EDE9FF"
PURPLE_SUBTLE = "#F4F1FF"
BG = "#F5F5F7"
TEXT = "#1a1a1a"
TEXT_SEC = "#8E8E93"
TEXT_MUTED = "#AEAEB2"
CARD = "#FFFFFF"
BORDER = "#E5E5EA"
GREEN = "#34C759"
GREEN_BG = "#E8F9EE"
RED = "#FF3B30"
RED_BG = "#FFE5E3"
ORANGE = "#FF9500"
ORANGE_BG = "#FFF3E0"
FONT = "Arial"


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN CLASS
# ═══════════════════════════════════════════════════════════════════════════
class AutoFillCenter(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=BG, corner_radius=0)
        self._time_tracker = TimeTracker()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=0)   # tab bar
        self.grid_rowconfigure(2, weight=1)   # content

        self._build_header()
        self._build_tab_bar()
        self._build_pages()
        self._select_tab("cash_sheet")
        if not self._time_tracker.is_enabled():
            self._time_tracker.toggle_tracking()
        self._refresh_tracking_ui()

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

    # ══════════════════════════════════════════════════════════════
    #  FOLDER / FILE PICKERS
    # ══════════════════════════════════════════════════════════════
    def _folder_row(self, parent, grid_r, label, sync_target=None):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT).grid(row=grid_r, column=0, sticky="w", pady=(6, 0))
        entry = ctk.CTkEntry(parent, height=30, state="readonly",
                             border_color=BORDER,
                             font=ctk.CTkFont(family=FONT, size=11))
        entry.grid(row=grid_r, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        ctk.CTkButton(parent, text="Browse", width=70, height=30,
                      corner_radius=8, fg_color=PURPLE, hover_color=PURPLE_DARK,
                      font=ctk.CTkFont(family=FONT, size=11),
                      command=lambda e=entry, s=sync_target: self._pick_folder(
                          e, s),
                      cursor="hand2").grid(row=grid_r, column=2, padx=(6, 0), pady=(6, 0))
        return entry

    def _file_row(self, parent, grid_r, label, sync_target=None):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT).grid(row=grid_r, column=0, sticky="w", pady=(6, 0))
        entry = ctk.CTkEntry(parent, height=30, state="readonly",
                             border_color=BORDER,
                             font=ctk.CTkFont(family=FONT, size=11))
        entry.grid(row=grid_r, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))
        ctk.CTkButton(parent, text="Browse", width=70, height=30,
                      corner_radius=8, fg_color=PURPLE, hover_color=PURPLE_DARK,
                      font=ctk.CTkFont(family=FONT, size=11),
                      command=lambda e=entry, s=sync_target: self._pick_file(
                          e, s),
                      cursor="hand2").grid(row=grid_r, column=2, padx=(6, 0), pady=(6, 0))
        return entry

    def _pick_folder(self, entry, sync_target=None):
        path = filedialog.askdirectory(title="Select Folder")
        if not path:
            return
        self._set_entry(entry, path)
        if sync_target == "cash_sheet":
            for other in (self._cs_folder1_entry, self._config_cs_folder, self._tb_folder_entry):
                if other is not entry:
                    self._set_entry(other, path)
        elif sync_target == "reports":
            for other in (self._cs_folder2_entry, self._config_rep_folder):
                if other is not entry:
                    self._set_entry(other, path)
        self._save_config()

    def _set_entry(self, entry, value):
        try:
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, value)
            entry.configure(state="readonly")
        except (AttributeError, Exception):
            pass

    def _pick_file(self, entry, sync_target=None):
        path = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if not path:
            return
        self._set_entry(entry, path)
        if sync_target == "master_path":
            for attr in ("_tb_file_entry", "_config_tb_master"):
                other = getattr(self, attr, None)
                if other is not None and other is not entry:
                    self._set_entry(other, path)
            self._save_tender_config()

    # ══════════════════════════════════════════════════════════════
    #  LOG HELPERS
    # ══════════════════════════════════════════════════════════════
    def _append_log(self, log_widget, text):
        def _do():
            log_widget.configure(state="normal")
            log_widget.insert("end", text + "\n")
            log_widget.see("end")
            log_widget.configure(state="disabled")
        self.after(0, _do)

    def _clear_log(self, log_widget):
        log_widget.configure(state="normal")
        log_widget.delete("1.0", "end")
        log_widget.configure(state="disabled")

    def _set_status(self, label, text, color=TEXT_MUTED):
        self.after(0, lambda: label.configure(text=text, text_color=color))

    # ══════════════════════════════════════════════════════════════
    #  RUN CASH SHEET AUTOFILL
    # ══════════════════════════════════════════════════════════════
    def _stop_cash_sheet_autofill(self):
        if hasattr(self, '_cs_stop_event'):
            self._cs_stop_event.set()
        self._cs_run_btn.configure(state="disabled", text="🛑  Stopping...")

    def _run_cash_sheet_autofill(self):
        casheet_dir = self._cs_folder1_entry.get().strip()
        reports_dir = self._cs_folder2_entry.get().strip()
        if not casheet_dir:
            messagebox.showwarning("Missing", "Select the Cash Sheet folder.")
            return
        if not reports_dir:
            messagebox.showwarning("Missing", "Select the Day Reports folder.")
            return

        self._cs_stop_event = threading.Event()
        self._cs_run_btn.configure(
            state="normal", text="🛑  Stop Autofill",
            fg_color="#D9534F", hover_color="#C9302C",
            command=self._stop_cash_sheet_autofill)
        self._clear_log(self._cs_log)
        self._set_status(self._cs_status, "Processing...", ORANGE)

        def _on_event(kind, msg):
            self._append_log(self._cs_log, msg)

        def _worker():
            try:
                printer_name = self._printer_var.get()
                if printer_name == "System Default":
                    printer_name = None

                engine = CashSheetAutofillEngine(
                    reports_dir=reports_dir, casheet_dir=casheet_dir,
                    on_event=_on_event, stop_event=self._cs_stop_event,
                    auto_print=self._cs_auto_print.get() == 1,
                    printer_name=printer_name)
                engine.execute()
                self.after(0, lambda: self._on_cash_sheet_done(engine.tracker))
            except Exception as exc:
                self._append_log(self._cs_log, f"\n❌ Unexpected error: {exc}")
                self.after(0, lambda: self._on_cash_sheet_done(None))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_cash_sheet_done(self, tracker):
        self._cs_run_btn.configure(
            state="normal", text="🚀  Run Cash Sheet Autofill",
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            command=self._run_cash_sheet_autofill)
        if tracker is None:
            self._set_status(self._cs_status, "Error", RED)
            return
        if hasattr(self, '_cs_stop_event') and self._cs_stop_event.is_set():
            self._set_status(self._cs_status, "Cancelled", ORANGE)
            return
        s, f, w = len(tracker.successful), len(
            tracker.failed), len(tracker.warnings)
        if f == 0:
            self._set_status(
                self._cs_status, f"Done: {s} ok, {w} warnings", GREEN)
        else:
            self._set_status(
                self._cs_status, f"Done: {s} ok, {f} failed, {w} warnings", RED)
        if s > 0:
            self._record_and_refresh("cash_sheet")

    # ══════════════════════════════════════════════════════════════
    #  RUN TENDER BREAKDOWN AUTOFILL
    # ══════════════════════════════════════════════════════════════
    def _stop_tender_autofill(self):
        if hasattr(self, '_tb_stop_event'):
            self._tb_stop_event.set()
        self._tb_run_btn.configure(state="disabled", text="🛑  Stopping...")

    def _run_tender_autofill(self):
        if not _HAS_TENDER:
            self._append_log(self._tb_log, "❌ Tender module not available.")
            return

        casheet_dir = self._tb_folder_entry.get().strip()
        master_path = self._tb_file_entry.get().strip()

        if not casheet_dir:
            messagebox.showwarning("Missing", "Select the Cash Sheets folder.")
            return
        if not master_path:
            messagebox.showwarning(
                "Missing", "Select the Tender Breakdown file.")
            return

        self._tb_stop_event = threading.Event()
        self._tb_run_btn.configure(
            state="normal", text="🛑  Stop Autofill",
            fg_color="#D9534F", hover_color="#C9302C",
            command=self._stop_tender_autofill)
        self._clear_log(self._tb_log)
        self._set_status(self._tb_status, "Processing...", ORANGE)

        def _on_event(kind, msg):
            self._append_log(self._tb_log, msg)

        def _worker():
            try:
                engine = TenderBreakdownEngine(
                    casheet_dir=casheet_dir, master_path=master_path,
                    on_event=_on_event, stop_event=self._tb_stop_event)
                engine.execute()
                self.after(0, lambda: self._on_tender_done(engine.tracker))
            except Exception as exc:
                self._append_log(self._tb_log, f"\n❌ Unexpected error: {exc}")
                self.after(0, lambda: self._on_tender_done(None))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_tender_done(self, tracker):
        self._tb_run_btn.configure(
            state="normal", text="🚀  Run Tender Breakdown Autofill",
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            command=self._run_tender_autofill)
        if tracker is None:
            self._set_status(self._tb_status, "Error", RED)
            return
        if hasattr(self, '_tb_stop_event') and self._tb_stop_event.is_set():
            self._set_status(self._tb_status, "Cancelled", ORANGE)
            return
        s, f = len(tracker.successful), len(tracker.failed)
        if f == 0:
            self._set_status(self._tb_status, f"Done: {s} ok", GREEN)
        else:
            self._set_status(self._tb_status, f"Done: {s} ok, {f} failed", RED)
        if s > 0:
            self._record_and_refresh("tender")

    # ══════════════════════════════════════════════════════════════
    #  CONFIG TABLE REFRESHERS (Cash Sheet)
    # ══════════════════════════════════════════════════════════════
    def _refresh_cs_loc_table(self):
        for w in self._cs_loc_container.winfo_children():
            w.destroy()
        if hasattr(self, "_cs_loc_count"):
            self._cs_loc_count.configure(
                text=f"({len(REPORTS_CASHSHEET_MAP)} locations)")
        tbl = ctk.CTkFrame(self._cs_loc_container,
                           fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not REPORTS_CASHSHEET_MAP:
            ctk.CTkLabel(tbl, text="No locations configured yet",
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        for col, (txt, wt) in enumerate([("Report Name", 1), ("Cash Sheet", 1), ("Register", 1), ("", 0)]):
            hr.grid_columnconfigure(col, weight=wt)
            ctk.CTkLabel(hr, text=txt, font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 16, 0))
        for i, (report, mv) in enumerate(REPORTS_CASHSHEET_MAP.items()):
            sheet, register = (mv[0], mv[1]) if isinstance(
                mv, (list, tuple)) and len(mv) >= 2 else (str(mv), "")
            r = ctk.CTkFrame(tbl, fg_color=CARD if i %
                             2 == 0 else BG, corner_radius=4, height=30)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            for c in range(5):
                r.grid_columnconfigure(c, weight=1 if c < 3 else 0)
            ctk.CTkLabel(r, text=report, font=ctk.CTkFont(
                family=FONT, size=11), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=sheet, font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="w", padx=(16, 0))
            ctk.CTkLabel(r, text=register, font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_SEC).grid(row=0, column=2, sticky="w", padx=(16, 0))
            ctk.CTkButton(r, text="✏️", width=26, height=22, corner_radius=5, fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC", font=ctk.CTkFont(
                size=10), command=lambda rn=report: self._edit_cs_row(rn), cursor="hand2").grid(row=0, column=3, padx=(8, 2))
            ctk.CTkButton(r, text="🗑", width=26, height=22, corner_radius=5, fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9", font=ctk.CTkFont(
                size=10), command=lambda rn=report: self._del_cs_loc(rn), cursor="hand2").grid(row=0, column=4, padx=(2, 10))

    def _refresh_gh_venue_table(self):
        for w in self._gh_loc_container.winfo_children():
            w.destroy()
        if hasattr(self, "_gh_loc_count"):
            self._gh_loc_count.configure(
                text=f"({len(GRUBHUB_VENUE_MAP)} venues)")
        tbl = ctk.CTkFrame(self._gh_loc_container,
                           fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not GRUBHUB_VENUE_MAP:
            ctk.CTkLabel(tbl, text="No venues configured yet",
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        for col, (txt, wt) in enumerate([("Grubhub Venue", 1), ("Cash Sheet", 1), ("Register", 1), ("", 0)]):
            hr.grid_columnconfigure(col, weight=wt)
            ctk.CTkLabel(hr, text=txt, font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 16, 0))
        for i, (venue, mv) in enumerate(GRUBHUB_VENUE_MAP.items()):
            sheet, register = (mv[0], mv[1]) if isinstance(
                mv, (list, tuple)) and len(mv) >= 2 else (str(mv), "")
            r = ctk.CTkFrame(tbl, fg_color=CARD if i %
                             2 == 0 else BG, corner_radius=4, height=30)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            for c in range(5):
                r.grid_columnconfigure(c, weight=1 if c < 3 else 0)
            ctk.CTkLabel(r, text=venue, font=ctk.CTkFont(
                family=FONT, size=11), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=sheet, font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="w", padx=(16, 0))
            ctk.CTkLabel(r, text=register, font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_SEC).grid(row=0, column=2, sticky="w", padx=(16, 0))
            ctk.CTkButton(r, text="✏️", width=26, height=22, corner_radius=5, fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC", font=ctk.CTkFont(
                size=10), command=lambda v=venue: self._edit_gh_venue(v), cursor="hand2").grid(row=0, column=3, padx=(8, 2))
            ctk.CTkButton(r, text="🗑", width=26, height=22, corner_radius=5, fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9", font=ctk.CTkFont(
                size=10), command=lambda v=venue: self._del_gh_venue(v), cursor="hand2").grid(row=0, column=4, padx=(2, 10))

    def _refresh_kv_table(self, container, mapping):
        for w in container.winfo_children():
            w.destroy()
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not mapping:
            ctk.CTkLabel(tbl, text="No mappings configured yet",
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        hr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hr, text="Field", font=ctk.CTkFont(family=FONT, size=10,
                     weight="bold"), text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hr, text="Column", font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e", padx=(0, 70))
        for i, (k, v) in enumerate(mapping.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i %
                             2 == 0 else BG, corner_radius=4, height=28)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=str(k), font=ctk.CTkFont(
                family=FONT, size=11), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=str(v), font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="e", padx=10)
            ctk.CTkButton(r, text="✏️", width=26, height=20, corner_radius=5, fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC", font=ctk.CTkFont(
                size=10), command=lambda key=k, m=mapping, c=container: self._edit_kv_row(m, key, c), cursor="hand2").grid(row=0, column=2, padx=(4, 2))
            ctk.CTkButton(r, text="🗑", width=26, height=20, corner_radius=5, fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9", font=ctk.CTkFont(
                size=10), command=lambda key=k, m=mapping, c=container: self._del_kv(m, key, c), cursor="hand2").grid(row=0, column=3, padx=(2, 10))

    def _refresh_tender_table(self, container, mapping, kl="Key", vl="Value"):
        for w in container.winfo_children():
            w.destroy()
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not mapping:
            ctk.CTkLabel(tbl, text="No entries configured yet",
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        hr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hr, text=kl, font=ctk.CTkFont(family=FONT, size=10,
                     weight="bold"), text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hr, text=vl, font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e", padx=(0, 70))
        for i, (k, v) in enumerate(mapping.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i %
                             2 == 0 else BG, corner_radius=4, height=28)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=str(k), font=ctk.CTkFont(
                family=FONT, size=11), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=str(v), font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="e", padx=10)
            ctk.CTkButton(r, text="✏️", width=26, height=20, corner_radius=5, fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC", font=ctk.CTkFont(
                size=10), command=lambda key=k, m=mapping, c=container, _kl=kl, _vl=vl: self._edit_tender_row(m, key, c, _kl, _vl), cursor="hand2").grid(row=0, column=2, padx=(4, 2))
            ctk.CTkButton(r, text="🗑", width=26, height=20, corner_radius=5, fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9", font=ctk.CTkFont(
                size=10), command=lambda key=k, m=mapping, c=container, _kl=kl, _vl=vl: self._del_tender_row(m, key, c, _kl, _vl), cursor="hand2").grid(row=0, column=3, padx=(2, 10))

    # ══════════════════════════════════════════════════════════════
    #  CONFIG TABLE REFRESHERS (Tender Breakdown)
    # ══════════════════════════════════════════════════════════════
    def _refresh_filename_mapping_table(self):
        """Render the filename_to_master_name as a flat table."""
        if not _HAS_TENDER:
            return
        for w in self._fn_map_container.winfo_children():
            w.destroy()
        # Update count badge
        total = sum(len(d) for lst in FILENAME_TO_MASTER_NAME.values()
                    for d in lst)
        if hasattr(self, "_fn_map_count"):
            self._fn_map_count.configure(text=f"({total} mappings)")
        tbl = ctk.CTkFrame(self._fn_map_container,
                           fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not FILENAME_TO_MASTER_NAME:
            ctk.CTkLabel(tbl, text="No filename mappings configured yet",
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        for col, (txt, wt) in enumerate([("Filename Key", 1), ("Master Location", 1), ("Casheet Keyword", 1), ("", 0)]):
            hr.grid_columnconfigure(col, weight=wt)
            ctk.CTkLabel(hr, text=txt, font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 16, 0))

        row_i = 0
        for fn_key, mappings_list in FILENAME_TO_MASTER_NAME.items():
            for mapping_dict in mappings_list:
                for master_loc, kw in mapping_dict.items():
                    kw_display = ", ".join(kw) if isinstance(
                        kw, list) else str(kw)
                    r = ctk.CTkFrame(tbl, fg_color=CARD if row_i %
                                     2 == 0 else BG, corner_radius=4, height=30)
                    r.pack(fill="x", padx=6, pady=1)
                    r.pack_propagate(False)
                    for c in range(5):
                        r.grid_columnconfigure(c, weight=1 if c < 3 else 0)
                    ctk.CTkLabel(r, text=fn_key, font=ctk.CTkFont(
                        family=FONT, size=11), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
                    ctk.CTkLabel(r, text=master_loc, font=ctk.CTkFont(
                        family=FONT, size=11, weight="bold"), text_color=PURPLE).grid(row=0, column=1, sticky="w", padx=(16, 0))
                    ctk.CTkLabel(r, text=kw_display, font=ctk.CTkFont(
                        family=FONT, size=11), text_color=TEXT_SEC).grid(row=0, column=2, sticky="w", padx=(16, 0))
                    ctk.CTkButton(r, text="✏️", width=26, height=22, corner_radius=5, fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC", font=ctk.CTkFont(size=10),
                                  command=lambda fk=fn_key, ml=master_loc: self._edit_filename_mapping(fk, ml), cursor="hand2").grid(row=0, column=3, padx=(8, 2))
                    ctk.CTkButton(r, text="🗑", width=26, height=22, corner_radius=5, fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9", font=ctk.CTkFont(size=10),
                                  command=lambda fk=fn_key, ml=master_loc: self._del_filename_mapping(fk, ml), cursor="hand2").grid(row=0, column=4, padx=(2, 10))
                    row_i += 1

    def _refresh_tender_kv_table(self, container, mapping, kl, vl):
        """Generic key/value table for tender config dicts."""
        for w in container.winfo_children():
            w.destroy()
        # Update count badge if attached
        if hasattr(container, '_count_label'):
            container._count_label.configure(
                text=f"({len(mapping)} entries)")
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not mapping:
            ctk.CTkLabel(tbl, text="No entries configured yet",
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        hr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hr, text=kl, font=ctk.CTkFont(family=FONT, size=10,
                     weight="bold"), text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hr, text=vl, font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e", padx=(0, 70))
        for i, (k, v) in enumerate(mapping.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i %
                             2 == 0 else BG, corner_radius=4, height=28)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=str(k), font=ctk.CTkFont(
                family=FONT, size=11), text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=str(v), font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="e", padx=10)
            ctk.CTkButton(r, text="✏️", width=26, height=20, corner_radius=5, fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC", font=ctk.CTkFont(size=10),
                          command=lambda key=k, m=mapping, c=container, _kl=kl, _vl=vl: self._edit_tender_kv(m, key, c, _kl, _vl), cursor="hand2").grid(row=0, column=2, padx=(4, 2))
            ctk.CTkButton(r, text="🗑", width=26, height=20, corner_radius=5, fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9", font=ctk.CTkFont(size=10),
                          command=lambda key=k, m=mapping, c=container, _kl=kl, _vl=vl: self._del_tender_kv(m, key, c, _kl, _vl), cursor="hand2").grid(row=0, column=3, padx=(2, 10))

    # ══════════════════════════════════════════════════════════════
    #  DIALOG + CRUD (CASH SHEET)
    # ══════════════════════════════════════════════════════════════
    def _save_config(self):
        try:
            reports_dir = self._config_rep_folder.get().strip()
        except AttributeError:
            reports_dir = REPORTS_FOLDER
        try:
            casheet_dir = self._config_cs_folder.get().strip()
        except AttributeError:
            casheet_dir = CASH_SHEET_FOLDER
        full_config = {
            "reports_cashsheet_map": REPORTS_CASHSHEET_MAP,
            "grubhub_venue_map": GRUBHUB_VENUE_MAP,
            "fill_col_map": FILL_COL_MAP,
            "checking_col_map": CHECKING_COL_MAP,
            "infor_tenders": INFOR_TENDERS,
            "tavlo_tenders": TAVLO_TENDERS,
            "grubhub_tenders": GRUBHUB_TENDERS,
            "casheet_tenders": CASHEET_TENDERS,
            "summary_data_map": {},
            "reports_folder": reports_dir,
            "cash_sheets_folder": casheet_dir,
        }
        save_cash_sheet_config(full_config)

    def _input_dialog(self, title, fields, defaults=None):
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry(f"400x{50 + len(fields) * 52 + 55}")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(fg_color=BG)
        entries = {}
        for i, f in enumerate(fields):
            ctk.CTkLabel(dlg, text=f, font=ctk.CTkFont(family=FONT, size=12), text_color=TEXT).pack(
                anchor="w", padx=16, pady=(10 if i == 0 else 3, 0))
            e = ctk.CTkEntry(dlg, height=30, border_color=BORDER,
                             font=ctk.CTkFont(family=FONT, size=12))
            e.pack(fill="x", padx=16, pady=(2, 0))
            if defaults and f in defaults:
                e.insert(0, str(defaults[f]))
            entries[f] = e
        result = {}
        cancelled = [True]

        def save():
            for f, e in entries.items():
                result[f] = e.get().strip()
            cancelled[0] = False
            dlg.destroy()
        bf = ctk.CTkFrame(dlg, fg_color="transparent")
        bf.pack(fill="x", padx=16, pady=(12, 10))
        ctk.CTkButton(bf, text="Cancel", width=80, height=32, fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
                      border_width=1, border_color=BORDER, corner_radius=8, command=dlg.destroy).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bf, text="Save", width=80, height=32, fg_color=PURPLE,
                      hover_color=PURPLE_DARK, corner_radius=8, command=save).pack(side="left")
        dlg.wait_window()
        return result if not cancelled[0] else None

    def _add_cs_location(self):
        r = self._input_dialog(
            "Add Location", ["Report Name", "Cash Sheet", "Register"])
        if r and r["Report Name"]:
            REPORTS_CASHSHEET_MAP[r["Report Name"]] = [
                r["Cash Sheet"], r["Register"]]
            self._save_config()
            self._refresh_cs_loc_table()

    def _edit_cs_row(self, report_name):
        mv = REPORTS_CASHSHEET_MAP[report_name]
        sheet, register = (mv[0], mv[1]) if isinstance(
            mv, (list, tuple)) and len(mv) >= 2 else (str(mv), "")
        r = self._input_dialog(f"Edit Location", ["Report Name", "Cash Sheet", "Register"], defaults={
                               "Report Name": report_name, "Cash Sheet": sheet, "Register": register})
        if r and r["Report Name"]:
            new_name = r["Report Name"].strip()
            if new_name != report_name:
                REPORTS_CASHSHEET_MAP.pop(report_name, None)
            REPORTS_CASHSHEET_MAP[new_name] = [
                r["Cash Sheet"], r["Register"]]
            self._save_config()
            self._refresh_cs_loc_table()

    def _del_cs_loc(self, name):
        if messagebox.askyesno("Delete", f"Delete '{name}'?"):
            REPORTS_CASHSHEET_MAP.pop(name, None)
            self._refresh_cs_loc_table()
            self._save_config()

    def _add_gh_venue(self):
        r = self._input_dialog("Add Grubhub Venue", [
                               "Grubhub Venue", "Cash Sheet", "Register"])
        if r and r["Grubhub Venue"]:
            GRUBHUB_VENUE_MAP[r["Grubhub Venue"]] = [
                r["Cash Sheet"], r["Register"]]
            self._save_config()
            self._refresh_gh_venue_table()

    def _edit_gh_venue(self, venue_name):
        mv = GRUBHUB_VENUE_MAP[venue_name]
        sheet, register = (mv[0], mv[1]) if isinstance(
            mv, (list, tuple)) and len(mv) >= 2 else (str(mv), "")
        r = self._input_dialog(f"Edit Venue", ["Grubhub Venue", "Cash Sheet", "Register"], defaults={
                               "Grubhub Venue": venue_name, "Cash Sheet": sheet, "Register": register})
        if r and r["Grubhub Venue"]:
            new_name = r["Grubhub Venue"].strip()
            if new_name != venue_name:
                GRUBHUB_VENUE_MAP.pop(venue_name, None)
            GRUBHUB_VENUE_MAP[new_name] = [r["Cash Sheet"], r["Register"]]
            self._save_config()
            self._refresh_gh_venue_table()

    def _del_gh_venue(self, name):
        if messagebox.askyesno("Delete", f"Delete '{name}'?"):
            GRUBHUB_VENUE_MAP.pop(name, None)
            self._save_config()
            self._refresh_gh_venue_table()

    def _add_kv(self, mapping, container):
        r = self._input_dialog("Add Mapping", ["Field Name", "Column Number"])
        if r and r["Field Name"]:
            try:
                mapping[r["Field Name"]] = int(r["Column Number"])
            except ValueError:
                mapping[r["Field Name"]] = r["Column Number"]
            self._save_config()
            self._refresh_kv_table(container, mapping)

    def _edit_kv_row(self, mapping, key, container):
        r = self._input_dialog(f"Edit Mapping", [
                               "Field Name", "Column Number"], defaults={"Field Name": key, "Column Number": mapping[key]})
        if r and r["Field Name"]:
            new_key = r["Field Name"].strip()
            try:
                val = int(r["Column Number"])
            except ValueError:
                val = r["Column Number"]
            if new_key != key:
                mapping.pop(key, None)
            mapping[new_key] = val
            self._save_config()
            self._refresh_kv_table(container, mapping)

    def _del_kv(self, mapping, key, container):
        if messagebox.askyesno("Delete", f"Delete '{key}'?"):
            mapping.pop(key, None)
            self._save_config()
            self._refresh_kv_table(container, mapping)

    def _add_tender(self, mapping, container, kl="Key", vl="Value"):
        r = self._input_dialog("Add Entry", [kl, vl])
        if r and r[kl]:
            nv = r[vl].strip()
            try:
                nv = float(nv) if "." in nv else int(nv)
            except ValueError:
                pass
            mapping[r[kl].strip()] = nv
            self._save_config()
            self._refresh_tender_table(container, mapping, kl, vl)

    def _edit_tender_row(self, mapping, key, container, kl="Key", vl="Value"):
        r = self._input_dialog(f"Edit: {key}", [kl, vl], defaults={
                               kl: key, vl: mapping[key]})
        if r and r[kl]:
            nk, nv = r[kl].strip(), r[vl].strip()
            try:
                nv = float(nv) if "." in nv else int(nv)
            except ValueError:
                pass
            if nk != key:
                mapping.pop(key, None)
            mapping[nk] = nv
            self._save_config()
            self._refresh_tender_table(container, mapping, kl, vl)

    def _del_tender_row(self, mapping, key, container, kl="Key", vl="Value"):
        if messagebox.askyesno("Delete", f"Delete '{key}'?"):
            mapping.pop(key, None)
            self._save_config()
            self._refresh_tender_table(container, mapping, kl, vl)

    def _toggle_printer_dropdown(self):
        """Show/hide printer selector based on checkbox state."""
        if self._cs_auto_print.get() == 1:
            self._printer_frame.pack(side="left")
        else:
            self._printer_frame.pack_forget()

    def _refresh_printers(self):
        """Re-scan available printers and update dropdown."""
        printers = ExcelPrinter.get_available_printers()
        default = ExcelPrinter.get_default_printer() or "System Default"
        self._printer_dropdown.configure(values=["System Default"] + printers)
        self._printer_var.set(default)

    # ══════════════════════════════════════════════════════════════
    #  CRUD (TENDER BREAKDOWN CONFIG)
    # ══════════════════════════════════════════════════════════════
    def _save_tender_config(self):
        if not _HAS_TENDER:
            return
        # Read master path from config entry
        try:
            master = self._config_tb_master.get().strip()
        except AttributeError:
            master = DIRECTORY_PATHS.get("master_path", "")
        try:
            casheets = self._tb_folder_entry.get().strip()
        except AttributeError:
            casheets = DIRECTORY_PATHS.get("casheets_dir", "")

        full = {
            "filename_to_master_name": FILENAME_TO_MASTER_NAME,
            "location_start_col": LOCATION_START_COL,
            "directory_paths": {"casheets_dir": casheets, "master_path": master},
            "important_casheet_data_col": IMPORTANT_CASHEET_DATA_COL,
            "first_date_row": FIRST_DATE_ROW,
            "date_col": DATE_COL,
        }
        save_tender_config(full)

    def _save_tender_settings(self):
        """Save the date_col and first_date_row fields."""
        if not _HAS_TENDER:
            return
        global FIRST_DATE_ROW, DATE_COL
        try:
            from BE.src.tender_break import config as tc
            tc.FIRST_DATE_ROW = int(self._config_first_row.get().strip())
            tc.DATE_COL = int(self._config_date_col.get().strip())
            FIRST_DATE_ROW = tc.FIRST_DATE_ROW
            DATE_COL = tc.DATE_COL
        except (ValueError, AttributeError):
            messagebox.showerror(
                "Error", "Date Column and First Date Row must be integers.")
            return
        self._save_tender_config()
        messagebox.showinfo("Saved", "Tender settings saved.")

    def _save_tender_data_cols(self):
        """Save the important_casheet_data_col list."""
        if not _HAS_TENDER:
            return
        try:
            vals = [int(x.strip())
                    for x in self._config_data_cols.get().split(",") if x.strip()]
        except ValueError:
            messagebox.showerror(
                "Error", "Enter comma-separated integers only.")
            return
        from BE.src.tender_break import config as tc
        tc.IMPORTANT_CASHEET_DATA_COL.clear()
        tc.IMPORTANT_CASHEET_DATA_COL.extend(vals)
        IMPORTANT_CASHEET_DATA_COL.clear()
        IMPORTANT_CASHEET_DATA_COL.extend(vals)
        self._save_tender_config()
        messagebox.showinfo("Saved", f"Data columns updated: {vals}")

    # -- Filename Mapping CRUD --
    def _add_filename_mapping(self):
        r = self._input_dialog("Add Filename Mapping",
                               ["Filename Key", "Master Location", "Casheet Keyword"])
        if r and r["Filename Key"] and r["Master Location"]:
            fn_key = r["Filename Key"].strip().lower()
            master_loc = r["Master Location"].strip()
            kw_raw = r["Casheet Keyword"].strip()
            # If comma-separated, make a list (for heritage-style)
            kw = [x.strip() for x in kw_raw.split(
                ",")] if "," in kw_raw else kw_raw
            if fn_key not in FILENAME_TO_MASTER_NAME:
                FILENAME_TO_MASTER_NAME[fn_key] = []
            FILENAME_TO_MASTER_NAME[fn_key].append({master_loc: kw})
            self._save_tender_config()
            self._refresh_filename_mapping_table()

    def _edit_filename_mapping(self, fn_key, master_loc):
        # Find the current keyword
        current_kw = ""
        for md in FILENAME_TO_MASTER_NAME.get(fn_key, []):
            if master_loc in md:
                kw = md[master_loc]
                current_kw = ", ".join(kw) if isinstance(kw, list) else str(kw)
                break
        r = self._input_dialog(f"Edit Filename Mapping",
                               ["Filename Key", "Master Location", "Casheet Keyword"],
                               defaults={"Filename Key": fn_key, "Master Location": master_loc, "Casheet Keyword": current_kw})
        if r and r["Filename Key"] and r["Master Location"]:
            new_fn_key = r["Filename Key"].strip().lower()
            new_loc = r["Master Location"].strip()
            kw_raw = r["Casheet Keyword"].strip()
            kw = [x.strip() for x in kw_raw.split(
                ",")] if "," in kw_raw else kw_raw
            # Remove old entry
            for md in FILENAME_TO_MASTER_NAME.get(fn_key, []):
                if master_loc in md:
                    FILENAME_TO_MASTER_NAME[fn_key].remove(md)
                    break
            # Clean up empty key
            if fn_key != new_fn_key and not FILENAME_TO_MASTER_NAME.get(fn_key):
                FILENAME_TO_MASTER_NAME.pop(fn_key, None)
            # Add under (possibly new) key
            if new_fn_key not in FILENAME_TO_MASTER_NAME:
                FILENAME_TO_MASTER_NAME[new_fn_key] = []
            FILENAME_TO_MASTER_NAME[new_fn_key].append({new_loc: kw})
            self._save_tender_config()
            self._refresh_filename_mapping_table()

    def _del_filename_mapping(self, fn_key, master_loc):
        if messagebox.askyesno("Delete", f"Delete '{fn_key} → {master_loc}'?"):
            for md in FILENAME_TO_MASTER_NAME.get(fn_key, []):
                if master_loc in md:
                    FILENAME_TO_MASTER_NAME[fn_key].remove(md)
                    break
            if not FILENAME_TO_MASTER_NAME.get(fn_key):
                FILENAME_TO_MASTER_NAME.pop(fn_key, None)
            self._save_tender_config()
            self._refresh_filename_mapping_table()

    # -- Location Start Col CRUD (tender) --
    def _add_tender_kv(self, mapping, container, kl, vl):
        r = self._input_dialog("Add Entry", [kl, vl])
        if r and r[kl]:
            try:
                mapping[r[kl].strip().lower()] = int(r[vl])
            except ValueError:
                mapping[r[kl].strip().lower()] = r[vl]
            self._save_tender_config()
            self._refresh_tender_kv_table(container, mapping, kl, vl)

    def _edit_tender_kv(self, mapping, key, container, kl, vl):
        r = self._input_dialog(f"Edit: {key}", [kl, vl], defaults={
                               kl: key, vl: mapping[key]})
        if r and r[kl]:
            nk, nv = r[kl].strip().lower(), r[vl].strip()
            try:
                nv = int(nv)
            except ValueError:
                pass
            if nk != key:
                mapping.pop(key, None)
            mapping[nk] = nv
            self._save_tender_config()
            self._refresh_tender_kv_table(container, mapping, kl, vl)

    def _del_tender_kv(self, mapping, key, container, kl, vl):
        if messagebox.askyesno("Delete", f"Delete '{key}'?"):
            mapping.pop(key, None)
            self._save_tender_config()
            self._refresh_tender_kv_table(container, mapping, kl, vl)


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER WIDGETS
# ═══════════════════════════════════════════════════════════════════════════
class _Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=CARD, corner_radius=12,
                         border_width=1, border_color=BORDER, **kw)


def _section_label(parent, text, grid_pos=None):
    lbl = ctk.CTkLabel(parent, text=text,
                       font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                       text_color=TEXT)
    if grid_pos:
        row, col, span = grid_pos
        lbl.grid(row=row, column=col, columnspan=span, sticky="w", pady=(0, 8))
    else:
        lbl.pack(anchor="w", pady=(0, 6))


def _add_button(parent, add_cb):
    ctk.CTkButton(
        parent, text="＋ Add", width=60, height=26, corner_radius=6,
        fg_color=GREEN_BG, text_color=GREEN, hover_color="#D4F5DD",
        font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
        command=add_cb, cursor="hand2").pack(side="right")
