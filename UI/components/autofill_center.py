"""
AutoFill Center - Cash Sheet & Tender Breakdown Autofill UI
Compact, lightweight version with inline result log.
"""
import sys
from pathlib import Path

# ── Path setup (must run before project imports) ───────────────────────────
_BASE_DIR = Path(__file__).resolve().parents[2]
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

import customtkinter as ctk  # noqa: E402
from tkinter import filedialog, messagebox  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
import threading  # noqa: E402

from BE.src.cash_sheet_filler.main import CashSheetAutofillEngine  # noqa: E402
from BE.src.cash_sheet_filler.config import (  # noqa: E402
    REPORTS_CASHSHEET_MAP, FILL_COL_MAP, CHECKING_COL_MAP,
    INFOR_TENDERS, TAVLO_TENDERS, CASHEET_TENDERS,
    CASH_SHEET_FOLDER, REPORTS_FOLDER, GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP,
    load_config as load_cash_sheet_config,
    save_config as save_cash_sheet_config,
)


# Try to import tender config (may not exist yet)
try:
    from BE.src.tender_break.config import (
        LOCATION_START_COL, IMPORTANT_CASHEET_DATA_COL,
        FILENAME_TO_MASTER_NAME,
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

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)   # header
        self.grid_rowconfigure(1, weight=0)   # tab bar
        self.grid_rowconfigure(2, weight=1)   # content

        self._build_header()
        self._build_tab_bar()
        self._build_pages()
        self._select_tab("cash_sheet")

    # ── Header ─────────────────────────────────────────────────────────
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

    # ── Tab Bar ────────────────────────────────────────────────────────
    def _build_tab_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent", height=38)
        bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(4, 0))

        self._tab_btns = {}
        self._tab_lines = {}
        tabs = [
            ("cash_sheet", "💰 Cash Sheet"),
            ("tender",     "📊 Tender Breakdown"),
            ("config",     "⚙️ Configuration"),
        ]
        for key, label in tabs:
            wrapper = ctk.CTkFrame(bar, fg_color="transparent")
            wrapper.pack(side="left", padx=(0, 2))
            btn = ctk.CTkButton(
                wrapper, text=label,
                font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                fg_color="transparent", text_color=TEXT_MUTED,
                hover_color=PURPLE_SUBTLE, height=32, corner_radius=8,
                command=lambda k=key: self._select_tab(k), cursor="hand2",
            )
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
                fg_color=PURPLE_SUBTLE if active else "transparent",
            )
            self._tab_lines[k].configure(
                fg_color=PURPLE if active else "transparent",
            )
        for page in self._pages.values():
            page.grid_forget()
        self._pages[key].grid(row=2, column=0, sticky="nsew")

    # ── Pages ──────────────────────────────────────────────────────────
    def _build_pages(self):
        self._pages = {}
        self._pages["cash_sheet"] = self._build_cash_sheet_page()
        self._pages["tender"] = self._build_tender_page()
        self._pages["config"] = self._build_config_page()

    # ══════════════════════════════════════════════════════════════
    #  CASH SHEET PAGE
    # ══════════════════════════════════════════════════════════════
    def _build_cash_sheet_page(self):
        page = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=0)  # settings card
        page.grid_rowconfigure(1, weight=1)  # result log

        # ── Settings card ──────────────────────────────────────────
        card = _Card(page)
        card.grid(row=0, column=0, sticky="ew", padx=20, pady=(12, 8))

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        inner.grid_columnconfigure(1, weight=1)

        _section_label(inner, "⚙️ Settings", grid_pos=(0, 0, 2))

        # Cash Sheet folder
        self._cs_folder1_entry = self._folder_row(
            inner, 1, "📁 Cash Sheet Folder:")
        self._cs_folder1_entry.configure(state="normal")
        self._cs_folder1_entry.insert(0, CASH_SHEET_FOLDER)
        self._cs_folder1_entry.configure(state="readonly")

        # Reports folder
        self._cs_folder2_entry = self._folder_row(
            inner, 2, "📊 Day Reports Folder:")
        self._cs_folder2_entry.configure(state="normal")
        self._cs_folder2_entry.insert(0, REPORTS_FOLDER)
        self._cs_folder2_entry.configure(state="readonly")

        # Run button
        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._cs_run_btn = ctk.CTkButton(
            bf, text="🚀  Run Cash Sheet Autofill",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            height=40, corner_radius=10,
            command=self._run_cash_sheet_autofill, cursor="hand2",
        )
        self._cs_run_btn.pack(fill="x")

        # ── Result Log ─────────────────────────────────────────────
        log_card = _Card(page)
        log_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))

        log_header = ctk.CTkFrame(log_card, fg_color="transparent")
        log_header.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(log_header, text="📋 Result Log",
                     font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                     text_color=TEXT).pack(side="left")

        self._cs_clear_btn = ctk.CTkButton(
            log_header, text="Clear", width=50, height=24, corner_radius=6,
            fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
            font=ctk.CTkFont(family=FONT, size=11),
            command=lambda: self._clear_log(self._cs_log))
        self._cs_clear_btn.pack(side="right")

        # Status bar
        self._cs_status = ctk.CTkLabel(
            log_header, text="Ready",
            font=ctk.CTkFont(family=FONT, size=11),
            text_color=TEXT_MUTED)
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
    #  TENDER BREAKDOWN PAGE (placeholder)
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

        self._tb_folder1_entry = self._folder_row(
            inner, 1, "📁 Cash Sheets Folder:")

        self._tb_file_entry = self._file_row(
            inner, 2, "📄 Breakdown File:")

        # Run button
        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self._tb_run_btn = ctk.CTkButton(
            bf, text="🚀  Run Tender Breakdown Autofill",
            font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            height=40, corner_radius=10,
            command=self._run_tender_autofill, cursor="hand2",
        )
        self._tb_run_btn.pack(fill="x")

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
            command=lambda: self._clear_log(self._tb_log)
        ).pack(side="right")

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
    #  CONFIGURATION PAGE
    # ══════════════════════════════════════════════════════════════
    def _build_config_page(self):
        page = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        page.grid_columnconfigure(0, weight=1)

        grid_row = 0

        # ── Location Mappings ──────────────────────────────────────
        c1 = _Card(page)
        c1.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(12, 8))
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
        self._cs_loc_count.pack(side="left", padx=(6, 0))
        _add_button(hdr, self._add_cs_location)

        self._cs_loc_container = ctk.CTkFrame(w1, fg_color="transparent")
        self._cs_loc_container.pack(fill="x")
        self._refresh_cs_loc_table()

        # ── Grubhub Venue Mappings ─────────────────────────────────
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
        self._gh_loc_count.pack(side="left", padx=(6, 0))
        _add_button(hdr_gh, self._add_gh_venue)

        self._gh_loc_container = ctk.CTkFrame(w_gh, fg_color="transparent")
        self._gh_loc_container.pack(fill="x")
        self._refresh_gh_venue_table()

        # ── Fill Column Mappings ───────────────────────────────────
        c2 = _Card(page)
        c2.grid(row=grid_row, column=0, sticky="ew", padx=20, pady=(0, 8))
        grid_row += 1
        w2 = ctk.CTkFrame(c2, fg_color="transparent")
        w2.pack(fill="x", padx=16, pady=12)

        hdr2 = ctk.CTkFrame(w2, fg_color="transparent")
        hdr2.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(hdr2, text="📋 Fill Column Mappings",
                     font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                     text_color=TEXT).pack(side="left")
        _add_button(hdr2, lambda: self._add_kv(FILL_COL_MAP, self._fill_tbl))

        self._fill_tbl = ctk.CTkFrame(w2, fg_color="transparent")
        self._fill_tbl.pack(fill="x")
        self._refresh_kv_table(self._fill_tbl, FILL_COL_MAP)

        # ── Checking Column Mappings ───────────────────────────────
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

        # ── Tender Mappings ────────────────────────────────────────
        tender_maps = [
            ("📄 Infor Tenders",   "Tender Name", "Internal Key", INFOR_TENDERS),
            ("📄 Tavlo Tenders",   "Tender Name", "Internal Key", TAVLO_TENDERS),
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
    #  FOLDER / FILE PICKERS
    # ══════════════════════════════════════════════════════════════

    def _folder_row(self, parent, grid_r, label):
        rf = ctk.CTkFrame(parent, fg_color="transparent")
        rf.grid(row=grid_r, column=0, columnspan=2, sticky="ew", pady=6)
        rf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rf, text=label,
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT_SEC).grid(row=0, column=0, sticky="w",
                                               padx=(0, 10))
        entry = ctk.CTkEntry(rf, placeholder_text="No folder selected",
                             font=ctk.CTkFont(family=FONT, size=11),
                             height=32, border_color=BORDER, state="readonly")
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            rf, text="Browse", width=70, height=32, corner_radius=8,
            fg_color=PURPLE_LIGHT, text_color=PURPLE,
            hover_color=PURPLE_SUBTLE,
            font=ctk.CTkFont(family=FONT, size=11),
            command=lambda: self._pick_folder(entry), cursor="hand2",
        ).grid(row=0, column=2)
        return entry

    def _file_row(self, parent, grid_r, label):
        rf = ctk.CTkFrame(parent, fg_color="transparent")
        rf.grid(row=grid_r, column=0, columnspan=2, sticky="ew", pady=6)
        rf.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(rf, text=label,
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT_SEC).grid(row=0, column=0, sticky="w",
                                               padx=(0, 10))
        entry = ctk.CTkEntry(rf, placeholder_text="No file selected",
                             font=ctk.CTkFont(family=FONT, size=11),
                             height=32, border_color=BORDER, state="readonly")
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            rf, text="Browse", width=70, height=32, corner_radius=8,
            fg_color=PURPLE_LIGHT, text_color=PURPLE,
            hover_color=PURPLE_SUBTLE,
            font=ctk.CTkFont(family=FONT, size=11),
            command=lambda: self._pick_file(entry), cursor="hand2",
        ).grid(row=0, column=2)
        return entry

    def _pick_folder(self, entry):
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, path)
            entry.configure(state="readonly")
        self._save_config()
        # Sync the UI: If they changed it in Config, update the Run page (and vice versa)
        try:
            # Update Cash Sheet tab boxes
            self._cs_folder1_entry.configure(state="normal")
            self._cs_folder1_entry.delete(0, "end")
            self._cs_folder1_entry.insert(0, self._config_cs_folder.get())
            self._cs_folder1_entry.configure(state="readonly")

            self._cs_folder2_entry.configure(state="normal")
            self._cs_folder2_entry.delete(0, "end")
            self._cs_folder2_entry.insert(0, self._config_rep_folder.get())
            self._cs_folder2_entry.configure(state="readonly")
        except AttributeError:
            pass  # Safe to ignore if a tab hasn't loaded yet

    def _pick_file(self, entry):
        path = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if path:
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, path)
            entry.configure(state="readonly")

    # ══════════════════════════════════════════════════════════════
    #  LOG HELPERS
    # ══════════════════════════════════════════════════════════════
    def _append_log(self, log_widget, text):
        """Thread-safe append to a CTkTextbox."""
        def _do():
            log_widget.configure(state="normal")
            log_widget.insert("end", text + "\n")
            log_widget.see("end")
            log_widget.configure(state="disabled")
        # Schedule on main thread if called from worker
        self.after(0, _do)

    def _clear_log(self, log_widget):
        log_widget.configure(state="normal")
        log_widget.delete("1.0", "end")
        log_widget.configure(state="disabled")

    def _set_status(self, label, text, color=TEXT_MUTED):
        self.after(0, lambda: label.configure(text=text, text_color=color))

    # --- Handles the Stop button click ---
    def _stop_cash_sheet_autofill(self):
        if hasattr(self, '_cs_stop_event'):
            self._cs_stop_event.set()  # Send the stop signal

        # Disable the button so they can't click it twice while it's stopping
        self._cs_run_btn.configure(state="disabled", text="🛑  Stopping...")
        self._append_log(
            self._cs_log, "\n⚠️ Stopping autofill process... Please wait.")

    def _run_cash_sheet_autofill(self):
        casheet_dir = self._cs_folder1_entry.get().strip()
        reports_dir = self._cs_folder2_entry.get().strip()

        if not casheet_dir:
            messagebox.showwarning("Missing", "Select the Cash Sheet folder.")
            return
        if not reports_dir:
            messagebox.showwarning("Missing", "Select the Day Reports folder.")
            return

        # Create a new stop event for this run
        self._cs_stop_event = threading.Event()

        # Change button to STOP mode (Red color, new command)
        self._cs_run_btn.configure(
            state="normal",
            text="🛑  Stop Autofill",
            fg_color="#D9534F",       # Red
            hover_color="#C9302C",    # Darker Red
            command=self._stop_cash_sheet_autofill
        )

        self._clear_log(self._cs_log)
        self._set_status(self._cs_status, "Processing...", ORANGE)

        def _on_event(kind, msg):
            """Callback from ProcessingTracker — runs on worker thread."""
            self._append_log(self._cs_log, msg)

        def _worker():
            try:
                engine = CashSheetAutofillEngine(
                    reports_dir=reports_dir,
                    casheet_dir=casheet_dir,
                    on_event=_on_event,
                    stop_event=self._cs_stop_event
                )
                engine.execute()
                # Back to main thread for final UI update
                self.after(0, lambda: self._on_cash_sheet_done(engine.tracker))
            except Exception as exc:
                self._append_log(self._cs_log, f"\n❌ Unexpected error: {exc}")
                self.after(0, lambda: self._on_cash_sheet_done(None))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_cash_sheet_done(self, tracker):
        import customtkinter as ctk  # Just in case it's not imported at the top

        # Reset the button back to standard Run mode (Blue color, normal command)
        self._cs_run_btn.configure(
            state="normal",
            text="🚀  Run Cash Sheet Autofill",
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            command=self._run_cash_sheet_autofill
        )

        if tracker is None:
            self._set_status(self._cs_status, "Error", RED)
            return

        # Check if the process finished because the user cancelled it
        if hasattr(self, '_cs_stop_event') and self._cs_stop_event.is_set():
            self._set_status(self._cs_status, "Cancelled", ORANGE)
            self._append_log(
                self._cs_log, "\n🛑 Autofill process was cancelled by user.")
            return

        s = len(tracker.successful)
        f = len(tracker.failed)
        w = len(tracker.warnings)

        if f == 0:
            self._set_status(self._cs_status,
                             f"Done: {s} ok, {w} warnings", GREEN)
        else:
            self._set_status(self._cs_status,
                             f"Done: {s} ok, {f} failed, {w} warnings", RED)
    # ══════════════════════════════════════════════════════════════
    #  RUN TENDER BREAKDOWN (placeholder)
    # ══════════════════════════════════════════════════════════════

    def _run_tender_autofill(self):
        self._append_log(self._tb_log,
                         "Tender Breakdown autofill not yet implemented.")
        self._set_status(self._tb_status, "Not implemented", ORANGE)

    # ══════════════════════════════════════════════════════════════
    #  CONFIG TABLE REFRESHERS
    # ══════════════════════════════════════════════════════════════
    def _refresh_cs_loc_table(self):
        for w in self._cs_loc_container.winfo_children():
            w.destroy()
        if hasattr(self, "_cs_loc_count"):
            self._cs_loc_count.configure(
                text=f"({len(REPORTS_CASHSHEET_MAP)} locations)")

        tbl = ctk.CTkFrame(self._cs_loc_container, fg_color=BG,
                           corner_radius=8)
        tbl.pack(fill="x")

        # Header
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        for col, (txt, wt) in enumerate([
            ("Report Name", 1), ("Cash Sheet", 1), ("Register", 1), ("", 0)
        ]):
            hr.grid_columnconfigure(col, weight=wt)
            ctk.CTkLabel(hr, text=txt,
                         font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(
                row=0, column=col, sticky="w",
                padx=(0 if col == 0 else 16, 0))

        for i, (report, mapping_val) in enumerate(
                REPORTS_CASHSHEET_MAP.items()):
            # Handle both list and tuple formats
            if isinstance(mapping_val, (list, tuple)) and len(mapping_val) >= 2:
                sheet, register = mapping_val[0], mapping_val[1]
            else:
                sheet, register = str(mapping_val), ""

            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=30)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            for c in range(5):
                r.grid_columnconfigure(c, weight=1 if c < 3 else 0)
            ctk.CTkLabel(r, text=report,
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=sheet,
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="w", padx=(16, 0))
            ctk.CTkLabel(r, text=register,
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_SEC).grid(row=0, column=2, sticky="w", padx=(16, 0))
            ctk.CTkButton(
                r, text="✏️", width=26, height=22, corner_radius=5,
                fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC",
                font=ctk.CTkFont(size=10),
                command=lambda rpt=report: self._edit_cs_row(rpt),
                cursor="hand2",
            ).grid(row=0, column=3, padx=(8, 2))
            ctk.CTkButton(
                r, text="🗑", width=26, height=22, corner_radius=5,
                fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9",
                font=ctk.CTkFont(size=10),
                command=lambda rpt=report: self._del_cs_loc(rpt),
                cursor="hand2",
            ).grid(row=0, column=4, padx=(2, 10))

    def _refresh_kv_table(self, container, mapping):
        for w in container.winfo_children():
            w.destroy()
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")

        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        hr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hr, text="Field",
                     font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hr, text="Column",
                     font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e", padx=(0, 70))

        for i, (k, v) in enumerate(mapping.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=28)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=str(k).replace("_", " ").title(),
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=f"Col {v}",
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="e", padx=10)
            ctk.CTkButton(
                r, text="✏️", width=26, height=20, corner_radius=5,
                fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC",
                font=ctk.CTkFont(size=10),
                command=lambda key=k, m=mapping, c=container:
                    self._edit_kv_row(m, key, c),
                cursor="hand2",
            ).grid(row=0, column=2, padx=(4, 2))
            ctk.CTkButton(
                r, text="🗑", width=26, height=20, corner_radius=5,
                fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9",
                font=ctk.CTkFont(size=10),
                command=lambda key=k, m=mapping, c=container:
                    self._del_kv(m, key, c),
                cursor="hand2",
            ).grid(row=0, column=3, padx=(2, 10))

    def _refresh_tender_table(self, container, mapping, kl="Key", vl="Value"):
        for w in container.winfo_children():
            w.destroy()
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")

        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        hr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hr, text=kl,
                     font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hr, text=vl,
                     font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e", padx=(0, 70))

        for i, (k, v) in enumerate(mapping.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=28)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=str(k),
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=str(v),
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="e", padx=10)
            ctk.CTkButton(
                r, text="✏️", width=26, height=20, corner_radius=5,
                fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC",
                font=ctk.CTkFont(size=10),
                command=lambda key=k, m=mapping, c=container,
                        _kl=kl, _vl=vl:
                self._edit_tender_row(m, key, c, _kl, _vl),
                cursor="hand2",
            ).grid(row=0, column=2, padx=(4, 2))
            ctk.CTkButton(
                r, text="🗑", width=26, height=20, corner_radius=5,
                fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9",
                font=ctk.CTkFont(size=10),
                command=lambda key=k, m=mapping, c=container,
                        _kl=kl, _vl=vl:
                self._del_tender_row(m, key, c, _kl, _vl),
                cursor="hand2",
            ).grid(row=0, column=3, padx=(2, 10))

    # ══════════════════════════════════════════════════════════════
    #  DIALOG + CRUD OPERATIONS
    # ══════════════════════════════════════════════════════════════
    def _save_config(self):
        # Grab paths from the new Config Page boxes
        try:
            reports_dir = self._config_rep_folder.get().strip()
            casheet_dir = self._config_cs_folder.get().strip()
        except AttributeError:
            # Fallback if the UI hasn't fully loaded yet
            reports_dir = REPORTS_FOLDER
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
            "cash_sheets_folder": casheet_dir
        }
        save_cash_sheet_config(full_config)

    def _input_dialog(self, title, fields, defaults=None):
        """Modal dialog returning dict of field->value, or None on cancel."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry(f"400x{50 + len(fields) * 52 + 55}")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(fg_color=BG)

        entries = {}
        for i, f in enumerate(fields):
            ctk.CTkLabel(dlg, text=f,
                         font=ctk.CTkFont(family=FONT, size=12),
                         text_color=TEXT).pack(anchor="w", padx=16,
                                               pady=(10 if i == 0 else 3, 0))
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
        ctk.CTkButton(bf, text="Cancel", width=80, height=32,
                      fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
                      border_width=1, border_color=BORDER, corner_radius=8,
                      command=dlg.destroy).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bf, text="Save", width=80, height=32,
                      fg_color=PURPLE, hover_color=PURPLE_DARK,
                      corner_radius=8, command=save).pack(side="left")

        dlg.wait_window()
        return result if not cancelled[0] else None

    # -- CS Location CRUD --
    def _add_cs_location(self):
        r = self._input_dialog("Add Location",
                               ["Report Name", "Cash Sheet", "Register"])
        if r and r["Report Name"]:
            REPORTS_CASHSHEET_MAP[r["Report Name"]] = [r["Cash Sheet"],
                                                       r["Register"]]
            self._save_config()  # Save after adding a new location
            self._refresh_cs_loc_table()

    def _edit_cs_row(self, report_name):
        mapping_val = REPORTS_CASHSHEET_MAP[report_name]
        if isinstance(mapping_val, (list, tuple)) and len(mapping_val) >= 2:
            sheet, register = mapping_val[0], mapping_val[1]
        else:
            sheet, register = str(mapping_val), ""
        r = self._input_dialog(
            f"Edit: {report_name}",
            ["Cash Sheet", "Register"],
            defaults={"Cash Sheet": sheet, "Register": register})
        if r:
            REPORTS_CASHSHEET_MAP[report_name] = [r["Cash Sheet"],
                                                  r["Register"]]
            self._save_config()  # Save after editing a location
            self._refresh_cs_loc_table()

    def _del_cs_loc(self, name):
        if messagebox.askyesno("Delete", f"Delete '{name}'?"):
            REPORTS_CASHSHEET_MAP.pop(name, None)
            self._refresh_cs_loc_table()
            self._save_config()  # Save after deleting a location
        # -- Grubhub Venue CRUD --

    def _refresh_gh_venue_table(self):
        for w in self._gh_loc_container.winfo_children():
            w.destroy()
        if hasattr(self, "_gh_loc_count"):
            self._gh_loc_count.configure(
                text=f"({len(GRUBHUB_VENUE_MAP)} venues)")

        tbl = ctk.CTkFrame(self._gh_loc_container, fg_color=BG,
                           corner_radius=8)
        tbl.pack(fill="x")

        # Header
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        for col, (txt, wt) in enumerate([
            ("Grubhub Venue", 1), ("Cash Sheet", 1), ("Register", 1), ("", 0)
        ]):
            hr.grid_columnconfigure(col, weight=wt)
            ctk.CTkLabel(hr, text=txt,
                         font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                         text_color=TEXT_MUTED).grid(
                row=0, column=col, sticky="w",
                padx=(0 if col == 0 else 16, 0))

        for i, (venue, mapping_val) in enumerate(
                GRUBHUB_VENUE_MAP.items()):
            if isinstance(mapping_val, (list, tuple)) and len(mapping_val) >= 2:
                sheet, register = mapping_val[0], mapping_val[1]
            else:
                sheet, register = str(mapping_val), ""

            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=30)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            for c in range(5):
                r.grid_columnconfigure(c, weight=1 if c < 3 else 0)
            ctk.CTkLabel(r, text=venue,
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT).grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(r, text=sheet,
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="w", padx=(16, 0))
            ctk.CTkLabel(r, text=register,
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_SEC).grid(row=0, column=2, sticky="w", padx=(16, 0))
            ctk.CTkButton(
                r, text="✏️", width=26, height=22, corner_radius=5,
                fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC",
                font=ctk.CTkFont(size=10),
                command=lambda v=venue: self._edit_gh_venue(v),
                cursor="hand2",
            ).grid(row=0, column=3, padx=(8, 2))
            ctk.CTkButton(
                r, text="🗑", width=26, height=22, corner_radius=5,
                fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9",
                font=ctk.CTkFont(size=10),
                command=lambda v=venue: self._del_gh_venue(v),
                cursor="hand2",
            ).grid(row=0, column=4, padx=(2, 10))

    def _add_gh_venue(self):
        r = self._input_dialog("Add Grubhub Venue",
                               ["Grubhub Venue", "Cash Sheet", "Register"])
        if r and r["Grubhub Venue"]:
            GRUBHUB_VENUE_MAP[r["Grubhub Venue"]] = [r["Cash Sheet"],
                                                     r["Register"]]
            self._save_config()
            self._refresh_gh_venue_table()

    def _edit_gh_venue(self, venue_name):
        mapping_val = GRUBHUB_VENUE_MAP[venue_name]
        if isinstance(mapping_val, (list, tuple)) and len(mapping_val) >= 2:
            sheet, register = mapping_val[0], mapping_val[1]
        else:
            sheet, register = str(mapping_val), ""
        r = self._input_dialog(
            f"Edit: {venue_name}",
            ["Cash Sheet", "Register"],
            defaults={"Cash Sheet": sheet, "Register": register})
        if r:
            GRUBHUB_VENUE_MAP[venue_name] = [r["Cash Sheet"],
                                             r["Register"]]
            self._save_config()
            self._refresh_gh_venue_table()

    def _del_gh_venue(self, name):
        if messagebox.askyesno("Delete", f"Delete '{name}'?"):
            GRUBHUB_VENUE_MAP.pop(name, None)
            self._save_config()
            self._refresh_gh_venue_table()

    # -- Key/Value CRUD --
    def _add_kv(self, mapping, container):
        r = self._input_dialog("Add Mapping", ["Field Name", "Column Number"])
        if r and r["Field Name"]:
            try:
                mapping[r["Field Name"]] = int(r["Column Number"])
            except ValueError:
                mapping[r["Field Name"]] = r["Column Number"]
            self._save_config()  # Save after adding a new mapping
            self._refresh_kv_table(container, mapping)

    def _edit_kv_row(self, mapping, key, container):
        current = mapping[key]
        r = self._input_dialog(
            f"Edit: {key.replace('_', ' ').title()}",
            ["Column Number"],
            defaults={"Column Number": current})
        if r:
            try:
                mapping[key] = int(r["Column Number"])
            except ValueError:
                mapping[key] = r["Column Number"]
            self._save_config()  # Save after editing a mapping
            self._refresh_kv_table(container, mapping)

    def _del_kv(self, mapping, key, container):
        if messagebox.askyesno("Delete", f"Delete '{key}'?"):
            mapping.pop(key, None)
            self._save_config()  # Save after deleting a mapping
            self._refresh_kv_table(container, mapping)

    # -- Tender Mapping CRUD --
    def _add_tender(self, mapping, container, kl="Key", vl="Value"):
        r = self._input_dialog("Add Entry", [kl, vl])
        if r and r[kl]:
            new_val = r[vl].strip()
            try:
                new_val = float(new_val) if "." in new_val else int(new_val)
            except ValueError:
                pass
            mapping[r[kl].strip()] = new_val
            self._save_config()  # Save after adding a new tender mapping
            self._refresh_tender_table(container, mapping, kl, vl)

    def _edit_tender_row(self, mapping, key, container, kl="Key", vl="Value"):
        current_val = mapping[key]
        r = self._input_dialog(
            f"Edit: {key}",
            [kl, vl],
            defaults={kl: key, vl: current_val})
        if r and r[kl]:
            new_key = r[kl].strip()
            new_val = r[vl].strip()
            try:
                new_val = float(new_val) if "." in new_val else int(new_val)
            except ValueError:
                pass
            if new_key != key:
                mapping.pop(key, None)
            mapping[new_key] = new_val
            self._save_config()  # Save after editing a tender mapping
            self._refresh_tender_table(container, mapping, kl, vl)

    def _del_tender_row(self, mapping, key, container, kl="Key", vl="Value"):
        if messagebox.askyesno("Delete", f"Delete '{key}'?"):
            mapping.pop(key, None)
            self._save_config()  # Save after deleting a tender mapping
            self._refresh_tender_table(container, mapping, kl, vl)


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
        lbl.grid(row=row, column=col, columnspan=span, sticky="w",
                 pady=(0, 8))
    else:
        lbl.pack(anchor="w", pady=(0, 6))


def _add_button(parent, add_cb):
    ctk.CTkButton(
        parent, text="＋ Add", width=60, height=26, corner_radius=6,
        fg_color=GREEN_BG, text_color=GREEN, hover_color="#D4F5DD",
        font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
        command=add_cb, cursor="hand2").pack(side="right")
