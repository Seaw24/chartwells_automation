"""
Cash Sheet Autofill UI - Tabbed Layout
Three tabs: Cash Sheet Autofill | Tender Breakdown Autofill | Configuration
"""
import importlib
import sys
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta
from ctkdateentry import CTkDateEntry

# ── Path setup ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

    from src_cash_sheet_filler.config import (
        REPORTS_CASHSHEET_MAP, FILL_COL_MAP, CHECKING_COL_MAP)

# Tender breakdown config lives in a hyphenated folder
_TB_DIR = BASE_DIR / "src-tender_break"
if str(_TB_DIR) not in sys.path:
    sys.path.insert(0, str(_TB_DIR))

# Avoid name collision with the config we already imported
_tb_config = importlib.import_module("config")
FILENAME_TO_MASTER_NAME = _tb_config.FILENAME_TO_MASTER_NAME
LOCATION_START_COL = _tb_config.LOCATION_START_COL
IMPORTANT_CASHEET_DATA_COL = _tb_config.IMPORTANT_CASHEET_DATA_COL

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

class CashSheetAutofillUI(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=BG, corner_radius=0)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # header
        self.grid_rowconfigure(1, weight=0)  # tab bar
        self.grid_rowconfigure(2, weight=1)  # content area

        self._build_header()
        self._build_tab_bar()
        self._build_pages()
        self._select_tab("cash_sheet")

    # ── Header ─────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 6))

        left = ctk.CTkFrame(hdr, fg_color="transparent")
        left.pack(side="left")

        icon = ctk.CTkFrame(left, width=42, height=42, corner_radius=12,
                            fg_color=PURPLE_LIGHT)
        icon.pack(side="left", padx=(0, 14))
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text="💰", font=ctk.CTkFont(size=20)).place(
            relx=.5, rely=.5, anchor="center")

        tf = ctk.CTkFrame(left, fg_color="transparent")
        tf.pack(side="left")
        ctk.CTkLabel(tf, text="Autofill Center",
                     font=ctk.CTkFont(family=FONT, size=24, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(tf, text="Configure and run automatic data filling",
                     font=ctk.CTkFont(family=FONT, size=13),
                     text_color=TEXT_SEC).pack(anchor="w")

    # ── Tab Bar ────────────────────────────────────────────────────────────
    def _build_tab_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent", height=44)
        bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(6, 0))

        self._tab_btns = {}
        self._tab_lines = {}
        tabs = [
            ("cash_sheet", "💰  Cash Sheet"),
            ("tender", "📊  Tender Breakdown"),
            ("config", "⚙️  Configuration"),
        ]
        for key, label in tabs:
            wrapper = ctk.CTkFrame(bar, fg_color="transparent")
            wrapper.pack(side="left", padx=(0, 4))

            btn = ctk.CTkButton(
                wrapper, text=label,
                font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                fg_color="transparent", text_color=TEXT_MUTED,
                hover_color=PURPLE_SUBTLE, height=36, corner_radius=8,
                command=lambda k=key: self._select_tab(k), cursor="hand2",
            )
            btn.pack(side="top")

            line = ctk.CTkFrame(wrapper, height=3, corner_radius=2,
                                fg_color="transparent")
            line.pack(fill="x", padx=8)

            self._tab_btns[key] = btn
            self._tab_lines[key] = line

    def _select_tab(self, key):
        for k in self._tab_btns:
            if k == key:
                self._tab_btns[k].configure(text_color=PURPLE,
                                            fg_color=PURPLE_SUBTLE)
                self._tab_lines[k].configure(fg_color=PURPLE)
            else:
                self._tab_btns[k].configure(text_color=TEXT_MUTED,
                                            fg_color="transparent")
                self._tab_lines[k].configure(fg_color="transparent")

        for page in self._pages.values():
            page.grid_forget()
        self._pages[key].grid(row=2, column=0, sticky="nsew")

    # ── Page Builder ───────────────────────────────────────────────────────
    def _build_pages(self):
        self._pages = {}

        # Cash Sheet tab
        self._pages["cash_sheet"] = self._build_autofill_page(
            page_key="cash_sheet",
            folder1_label="📁 Cash Sheet Folder:",
            folder2_label="📊 Day Reports Folder:",
            folder2_is_file=False,
            run_label="🚀  Run Cash Sheet Autofill",
            fill_map=FILL_COL_MAP,
            check_map=CHECKING_COL_MAP,
        )

        # Tender Breakdown tab
        self._pages["tender"] = self._build_autofill_page(
            page_key="tender",
            folder1_label="📁 Cash Sheets Folder:",
            folder2_label="📄 Breakdown File:",
            folder2_is_file=True,
            run_label="🚀  Run Tender Breakdown Autofill",
            fill_map=None,
            check_map=None,
            extra_configs=[
                ("📍 Location Start Columns", LOCATION_START_COL),
                ("📌 Important Data Columns", IMPORTANT_CASHEET_DATA_COL),
                ("🗂️ Filename → Master Name", FILENAME_TO_MASTER_NAME),
            ],
        )

        # Configuration tab
        self._pages["config"] = self._build_config_page()

    # ══════════════════════════════════════════════════════════════════════
    #  AUTOFILL PAGE (reused for Cash Sheet & Tender tabs)
    # ══════════════════════════════════════════════════════════════════════
    def _build_autofill_page(self, page_key, folder1_label, folder2_label,
                             folder2_is_file, run_label,
                             fill_map, check_map, extra_configs=None):
        page = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        page.grid_columnconfigure(0, weight=1)

        setattr(self, f"{page_key}_folder1", None)
        setattr(self, f"{page_key}_folder2", None)
        grid_row = 0

        # ── Settings card ──────────────────────────────────────────────
        settings = _Card(page)
        settings.grid(row=grid_row, column=0, sticky="ew",
                      padx=24, pady=(16, 12))
        grid_row += 1

        inner = ctk.CTkFrame(settings, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=16)
        inner.grid_columnconfigure(1, weight=1)

        _section_label(inner, "⚙️ Settings", grid_pos=(0, 0, 2))

        # Folder / file rows
        self._folder_row(inner, 1, folder1_label, page_key, "folder1")
        if folder2_is_file:
            self._file_row(inner, 2, folder2_label, page_key, "folder2")
        else:
            self._folder_row(inner, 2, folder2_label, page_key, "folder2")

        # Date picker
        dframe = ctk.CTkFrame(inner, fg_color="transparent")
        dframe.grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)
        dframe.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dframe, text="📅 Date:",
                     font=ctk.CTkFont(family=FONT, size=13),
                     text_color=TEXT_SEC).grid(row=0, column=0, sticky="w",
                                               padx=(0, 12))
        de = CTkDateEntry(
            dframe, height=38, corner_radius=10,
            border_color=BORDER, border_width=1, fg_color=BG,
            font=ctk.CTkFont(size=13), text_color=TEXT)
        de.grid(row=0, column=1, sticky="ew")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        de.set_date(yesterday)
        setattr(self, f"{page_key}_date", de)

        # Run button
        bf = ctk.CTkFrame(inner, fg_color="transparent")
        bf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        ctk.CTkButton(
            bf, text=run_label,
            font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            height=46, corner_radius=12,
            command=lambda: self._run_autofill(page_key), cursor="hand2",
        ).pack(fill="x")

        # ── Column mapping cards (Cash Sheet only) ─────────────────────
        if fill_map:
            mc = _Card(page)
            mc.grid(row=grid_row, column=0, sticky="ew", padx=24, pady=(0, 12))
            grid_row += 1
            wrap = ctk.CTkFrame(mc, fg_color="transparent")
            wrap.pack(fill="x", padx=20, pady=16)

            hdr_f = ctk.CTkFrame(wrap, fg_color="transparent")
            hdr_f.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(hdr_f, text="📋 Fill Column Mappings",
                         font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
                         text_color=TEXT).pack(side="left")
            _add_button(hdr_f, lambda: self._add_kv(
                fill_map, f"{page_key}_fill_tbl"))

            container_f = ctk.CTkFrame(wrap, fg_color="transparent")
            container_f.pack(fill="x")
            setattr(self, f"{page_key}_fill_tbl", container_f)
            self._refresh_kv_table(container_f, fill_map)

            if check_map:
                ctk.CTkFrame(wrap, fg_color=BORDER, height=1).pack(
                    fill="x", pady=(14, 10))

                hdr_c = ctk.CTkFrame(wrap, fg_color="transparent")
                hdr_c.pack(fill="x", pady=(0, 8))
                ctk.CTkLabel(hdr_c, text="✅ Checking Column Mappings",
                             font=ctk.CTkFont(family=FONT, size=15,
                                              weight="bold"),
                             text_color=TEXT).pack(side="left")
                _add_button(hdr_c, lambda: self._add_kv(
                    check_map, f"{page_key}_chk_tbl"))

                container_c = ctk.CTkFrame(wrap, fg_color="transparent")
                container_c.pack(fill="x")
                setattr(self, f"{page_key}_chk_tbl", container_c)
                self._refresh_kv_table(container_c, check_map)

        # ── Extra config cards (Tender) ────────────────────────────────
        if extra_configs:
            for idx, (heading, data) in enumerate(extra_configs):
                ec = _Card(page)
                ec.grid(row=grid_row, column=0, sticky="ew",
                        padx=24, pady=(0, 12))
                grid_row += 1
                wrap = ctk.CTkFrame(ec, fg_color="transparent")
                wrap.pack(fill="x", padx=20, pady=16)

                hdr_e = ctk.CTkFrame(wrap, fg_color="transparent")
                hdr_e.pack(fill="x", pady=(0, 8))
                ctk.CTkLabel(hdr_e, text=heading,
                             font=ctk.CTkFont(family=FONT, size=15,
                                              weight="bold"),
                             text_color=TEXT).pack(side="left")

                if isinstance(data, dict) and data and isinstance(
                        next(iter(data.values())), list):
                    _filename_mapping_table(wrap, data)
                elif isinstance(data, dict):
                    tbl_attr = f"{page_key}_extra_{idx}"
                    _add_button(hdr_e, lambda d=data,
                                a=tbl_attr: self._add_kv(d, a))
                    container_e = ctk.CTkFrame(wrap, fg_color="transparent")
                    container_e.pack(fill="x")
                    setattr(self, tbl_attr, container_e)
                    self._refresh_kv_table(container_e, data)
                elif isinstance(data, list):
                    container_l = ctk.CTkFrame(wrap, fg_color="transparent")
                    container_l.pack(fill="x")
                    _edit_button(hdr_e, lambda d=data, c=container_l:
                                 self._edit_list(d, c))
                    _badge_list(container_l, data)

        return page

    # ══════════════════════════════════════════════════════════════════════
    #  CONFIGURATION PAGE  (Location Mappings only)
    # ══════════════════════════════════════════════════════════════════════
    def _build_config_page(self):
        page = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color="#D1D1D6",
            scrollbar_button_hover_color="#A1A1A6")
        page.grid_columnconfigure(0, weight=1)

        # ── Cash Sheet Location Mappings ───────────────────────────────
        c1 = _Card(page)
        c1.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 20))

        w1 = ctk.CTkFrame(c1, fg_color="transparent")
        w1.pack(fill="x", padx=20, pady=16)

        hdr1 = ctk.CTkFrame(w1, fg_color="transparent")
        hdr1.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(hdr1, text="🏢 Cash Sheet Location Mappings",
                     font=ctk.CTkFont(family=FONT, size=16, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self._cs_loc_count_lbl = ctk.CTkLabel(
            hdr1, text=f"({len(REPORTS_CASHSHEET_MAP)} locations)",
            font=ctk.CTkFont(family=FONT, size=12), text_color=TEXT_MUTED)
        self._cs_loc_count_lbl.pack(side="left", padx=(8, 0))
        _add_button(hdr1, self._add_cs_location)

        self._cs_loc_container = ctk.CTkFrame(w1, fg_color="transparent")
        self._cs_loc_container.pack(fill="x")
        self._refresh_cs_loc_table()

        return page

    # ══════════════════════════════════════════════════════════════════════
    #  FOLDER / FILE ROWS
    # ══════════════════════════════════════════════════════════════════════
    def _folder_row(self, parent, grid_r, label, page_key, attr):
        rf = ctk.CTkFrame(parent, fg_color="transparent")
        rf.grid(row=grid_r, column=0, columnspan=2, sticky="ew", pady=8)
        rf.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(rf, text=label,
                     font=ctk.CTkFont(family=FONT, size=13),
                     text_color=TEXT_SEC).grid(row=0, column=0, sticky="w",
                                               padx=(0, 12))
        entry = ctk.CTkEntry(rf, placeholder_text="No folder selected",
                             font=ctk.CTkFont(family=FONT, size=12),
                             height=36, border_color=BORDER, state="readonly")
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            rf, text="Browse", width=80, height=36, corner_radius=8,
            fg_color=PURPLE_LIGHT, text_color=PURPLE, hover_color=PURPLE_SUBTLE,
            font=ctk.CTkFont(family=FONT, size=12),
            command=lambda: self._pick_folder(page_key, attr, entry),
            cursor="hand2",
        ).grid(row=0, column=2)

        setattr(self, f"{page_key}_{attr}_entry", entry)

    def _file_row(self, parent, grid_r, label, page_key, attr):
        rf = ctk.CTkFrame(parent, fg_color="transparent")
        rf.grid(row=grid_r, column=0, columnspan=2, sticky="ew", pady=8)
        rf.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(rf, text=label,
                     font=ctk.CTkFont(family=FONT, size=13),
                     text_color=TEXT_SEC).grid(row=0, column=0, sticky="w",
                                               padx=(0, 12))
        entry = ctk.CTkEntry(rf, placeholder_text="No file selected",
                             font=ctk.CTkFont(family=FONT, size=12),
                             height=36, border_color=BORDER, state="readonly")
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            rf, text="Browse", width=80, height=36, corner_radius=8,
            fg_color=PURPLE_LIGHT, text_color=PURPLE, hover_color=PURPLE_SUBTLE,
            font=ctk.CTkFont(family=FONT, size=12),
            command=lambda: self._pick_file(page_key, attr, entry),
            cursor="hand2",
        ).grid(row=0, column=2)

        setattr(self, f"{page_key}_{attr}_entry", entry)

    def _pick_folder(self, page_key, attr, entry):
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, path)
            entry.configure(state="readonly")
            setattr(self, f"{page_key}_{attr}", path)

    def _pick_file(self, page_key, attr, entry):
        path = filedialog.askopenfilename(
            title="Select File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")])
        if path:
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, path)
            entry.configure(state="readonly")
            setattr(self, f"{page_key}_{attr}", path)

    # ══════════════════════════════════════════════════════════════════════
    #  CONFIG TABLE REFRESHERS
    # ══════════════════════════════════════════════════════════════════════
    def _refresh_cs_loc_table(self):
        for w in self._cs_loc_container.winfo_children():
            w.destroy()

        # Update count label if it exists
        if hasattr(self, '_cs_loc_count_lbl'):
            self._cs_loc_count_lbl.configure(
                text=f"({len(REPORTS_CASHSHEET_MAP)} locations)")

        tbl = ctk.CTkFrame(self._cs_loc_container, fg_color=BG,
                           corner_radius=10)
        tbl.pack(fill="x")

        # Header
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=14, pady=(10, 4))
        for col, (txt, wt) in enumerate([
            ("Report Name", 1), ("Cash Sheet", 1), ("Register", 1), ("", 0)
        ]):
            hr.grid_columnconfigure(col, weight=wt)
            ctk.CTkLabel(hr, text=txt,
                         font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                         text_color=TEXT_MUTED).grid(
                row=0, column=col, sticky="w",
                padx=(0 if col == 0 else 20, 0))

        for i, (report, (sheet, register)) in enumerate(
                REPORTS_CASHSHEET_MAP.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=36)
            r.pack(fill="x", padx=8, pady=1)
            r.pack_propagate(False)
            for c in range(5):
                r.grid_columnconfigure(c, weight=1 if c < 3 else 0)

            ctk.CTkLabel(r, text=report,
                         font=ctk.CTkFont(family=FONT, size=12),
                         text_color=TEXT).grid(row=0, column=0, sticky="w",
                                               padx=12)
            ctk.CTkLabel(r, text=sheet,
                         font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="w",
                                                 padx=(20, 0))
            ctk.CTkLabel(r, text=register,
                         font=ctk.CTkFont(family=FONT, size=12),
                         text_color=TEXT_SEC).grid(row=0, column=2, sticky="w",
                                                   padx=(20, 0))
            ctk.CTkButton(
                r, text="✏️", width=30, height=26, corner_radius=6,
                fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC",
                font=ctk.CTkFont(size=12),
                command=lambda rpt=report: self._edit_cs_row(rpt),
                cursor="hand2",
            ).grid(row=0, column=3, padx=(10, 2))
            ctk.CTkButton(
                r, text="🗑", width=30, height=26, corner_radius=6,
                fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9",
                font=ctk.CTkFont(size=12),
                command=lambda rpt=report: self._del_cs_loc(rpt),
                cursor="hand2",
            ).grid(row=0, column=4, padx=(2, 12))

    def _refresh_kv_table(self, container, mapping):
        for w in container.winfo_children():
            w.destroy()

        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=10)
        tbl.pack(fill="x")

        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=14, pady=(10, 4))
        hr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hr, text="Field",
                     font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hr, text="Column",
                     font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e",
                                                 padx=(0, 80))

        for i, (k, v) in enumerate(mapping.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=32)
            r.pack(fill="x", padx=8, pady=1)
            r.pack_propagate(False)
            r.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(r, text=str(k).replace("_", " ").title(),
                         font=ctk.CTkFont(family=FONT, size=12),
                         text_color=TEXT).grid(row=0, column=0, sticky="w",
                                               padx=12)
            ctk.CTkLabel(r, text=f"Col {v}",
                         font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1, sticky="e",
                                                 padx=12)
            ctk.CTkButton(
                r, text="✏️", width=30, height=24, corner_radius=6,
                fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC",
                font=ctk.CTkFont(size=11),
                command=lambda key=k, m=mapping, c=container: self._edit_kv_row(
                    m, key, c),
                cursor="hand2",
            ).grid(row=0, column=2, padx=(4, 2))
            ctk.CTkButton(
                r, text="🗑", width=30, height=24, corner_radius=6,
                fg_color=RED_BG, text_color=RED, hover_color="#FFCCC9",
                font=ctk.CTkFont(size=11),
                command=lambda key=k, m=mapping, c=container: self._del_kv(
                    m, key, c),
                cursor="hand2",
            ).grid(row=0, column=3, padx=(2, 12))

    # ══════════════════════════════════════════════════════════════════════
    #  DIALOG + CRUD OPERATIONS
    # ══════════════════════════════════════════════════════════════════════
    def _input_dialog(self, title, fields, defaults=None):
        """Modal dialog returning dict of field→value, or None on cancel."""
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry(f"440x{60 + len(fields) * 56 + 60}")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.configure(fg_color=BG)

        entries = {}
        for i, f in enumerate(fields):
            ctk.CTkLabel(dlg, text=f,
                         font=ctk.CTkFont(family=FONT, size=13),
                         text_color=TEXT).pack(anchor="w", padx=20,
                                               pady=(12 if i == 0 else 4, 0))
            e = ctk.CTkEntry(dlg, height=34, border_color=BORDER,
                             font=ctk.CTkFont(family=FONT, size=13))
            e.pack(fill="x", padx=20, pady=(2, 0))
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
        bf.pack(fill="x", padx=20, pady=(16, 12))
        ctk.CTkButton(bf, text="Cancel", width=90, height=36,
                      fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
                      border_width=1, border_color=BORDER, corner_radius=8,
                      command=dlg.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bf, text="Save", width=90, height=36,
                      fg_color=PURPLE, hover_color=PURPLE_DARK,
                      corner_radius=8, command=save).pack(side="left")

        dlg.wait_window()
        return result if not cancelled[0] else None

    def _warn(self, message):
        messagebox.showwarning("Warning", message)

    # -- CS Location CRUD --
    def _add_cs_location(self):
        r = self._input_dialog("Add Location",
                               ["Report Name", "Cash Sheet", "Register"])
        if r and r["Report Name"]:
            REPORTS_CASHSHEET_MAP[r["Report Name"]] = (r["Cash Sheet"],
                                                       r["Register"])
            self._refresh_cs_loc_table()

    def _edit_cs_row(self, report_name):
        """Edit a specific location row — pre-fills current values."""
        sheet, register = REPORTS_CASHSHEET_MAP[report_name]
        r = self._input_dialog(
            f"Edit: {report_name}",
            ["Cash Sheet", "Register"],
            defaults={"Cash Sheet": sheet, "Register": register})
        if r:
            REPORTS_CASHSHEET_MAP[report_name] = (r["Cash Sheet"],
                                                  r["Register"])
            self._refresh_cs_loc_table()

    def _del_cs_loc(self, name):
        if messagebox.askyesno("Delete", f"Delete '{name}'?"):
            REPORTS_CASHSHEET_MAP.pop(name, None)
            self._refresh_cs_loc_table()

    # -- Key/Value CRUD --
    def _add_kv(self, mapping, attr_name):
        r = self._input_dialog("Add Mapping", ["Field Name", "Column Number"])
        if r and r["Field Name"]:
            try:
                mapping[r["Field Name"]] = int(r["Column Number"])
            except ValueError:
                mapping[r["Field Name"]] = r["Column Number"]
            self._refresh_kv_table(getattr(self, attr_name), mapping)

    def _edit_kv_row(self, mapping, key, container):
        """Edit a specific key/value row — pre-fills current value."""
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
            self._refresh_kv_table(container, mapping)

    def _del_kv(self, mapping, key, container):
        if messagebox.askyesno("Delete", f"Delete '{key}'?"):
            mapping.pop(key, None)
            self._refresh_kv_table(container, mapping)

    def _edit_list(self, lst, container):
        """Edit the entire list as comma-separated values."""
        current = ", ".join(str(x) for x in lst)
        r = self._input_dialog(
            "Edit Important Data Columns",
            ["Column Numbers (comma-separated)"],
            defaults={"Column Numbers (comma-separated)": current})
        if r and r["Column Numbers (comma-separated)"]:
            try:
                new_lst = []
                for x in r["Column Numbers (comma-separated)"].split(","):
                    if int(x.strip()) > 0:  # Skip empty entries
                        # Validate all are integers
                        new_lst.append(int(x.strip()))

                new_lst = list(set(new_lst))  # Remove duplicates
                new_lst.sort()
            except ValueError:
                self._warn("Please enter valid integers separated by commas.")
                return
            lst.clear()
            lst.extend(new_lst)
            _badge_list(container, new_lst)
    # ══════════════════════════════════════════════════════════════════════
    #  RUN AUTOFILL
    # ══════════════════════════════════════════════════════════════════════

    def _run_autofill(self, key):
        f1 = getattr(self, f"{key}_folder1", None)
        f2 = getattr(self, f"{key}_folder2", None)
        de = getattr(self, f"{key}_date", None)

        if not f1:
            messagebox.showwarning("Missing",
                                   "Please select the first folder/file.")
            return
        if not f2:
            messagebox.showwarning("Missing",
                                   "Please select the second folder/file.")
            return
        date_str = de.variable.get().strip() if de else ""
        if not date_str:
            messagebox.showwarning("Missing", "Please select a date.")
            return

        if key == "cash_sheet":
            print(
                f"Cash Sheet Autofill: folder={f1}, reports={f2}, date={date_str}")
            messagebox.showinfo("Success", "Cash Sheet autofill completed!")
        elif key == "tender":
            print(f"Tender Breakdown: sheets={f1}, file={f2}, date={date_str}")
            messagebox.showinfo(
                "Success", "Tender Breakdown autofill completed!")


# ═══════════════════════════════════════════════════════════════════════════
#  HELPER WIDGETS (module-level)
# ═══════════════════════════════════════════════════════════════════════════

class _Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=CARD, corner_radius=16,
                         border_width=1, border_color=BORDER, **kw)


def _section_label(parent, text, grid_pos=None):
    lbl = ctk.CTkLabel(parent, text=text,
                       font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
                       text_color=TEXT)
    if grid_pos:
        row, col, span = grid_pos
        lbl.grid(row=row, column=col, columnspan=span, sticky="w",
                 pady=(0, 10))
    else:
        lbl.pack(anchor="w", pady=(0, 8))


def _add_button(parent, add_cb):
    """Single ＋ Add button for a section header."""
    ctk.CTkButton(
        parent, text="＋ Add", width=70, height=30, corner_radius=8,
        fg_color=GREEN_BG, text_color=GREEN, hover_color="#D4F5DD",
        font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
        command=add_cb, cursor="hand2").pack(side="right")


def _edit_button(parent, edit_cb):
    """Single ✏️ Edit button for a section header."""
    ctk.CTkButton(
        parent, text="✏️ Edit", width=70, height=30, corner_radius=8,
        fg_color=ORANGE_BG, text_color=ORANGE, hover_color="#FFE8CC",
        font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
        command=edit_cb, cursor="hand2").pack(side="right", padx=(0, 8))


def _badge_list(parent, items):
    for w in parent.winfo_children():
        w.destroy()

    frame = ctk.CTkFrame(parent, fg_color=BG, corner_radius=10)
    frame.pack(fill="x", pady=(4, 0))
    inner = ctk.CTkFrame(frame, fg_color="transparent")
    inner.pack(fill="x", padx=14, pady=10)
    for item in items:
        b = ctk.CTkFrame(inner, fg_color=PURPLE_LIGHT, corner_radius=6)
        b.pack(side="left", padx=(0, 6), pady=2)
        ctk.CTkLabel(b, text=f"  Col {item}  ",
                     font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                     text_color=PURPLE).pack(padx=4, pady=4)


def _filename_mapping_table(parent, mapping):
    tbl = ctk.CTkFrame(parent, fg_color=BG, corner_radius=10)
    tbl.pack(fill="x", pady=(4, 0))

    hr = ctk.CTkFrame(tbl, fg_color="transparent")
    hr.pack(fill="x", padx=14, pady=(10, 4))
    hr.grid_columnconfigure(0, weight=1)
    hr.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(hr, text="Filename Keyword",
                 font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                 text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(hr, text="Master Name → Search Key",
                 font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
                 text_color=TEXT_MUTED).grid(row=0, column=1, sticky="w",
                                             padx=(20, 0))

    for i, (fname, entries) in enumerate(mapping.items()):
        for entry in entries:
            for master, search_key in entry.items():
                r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                                 corner_radius=4, height=34)
                r.pack(fill="x", padx=8, pady=1)
                r.pack_propagate(False)
                r.grid_columnconfigure(0, weight=1)
                r.grid_columnconfigure(1, weight=1)

                ctk.CTkLabel(r, text=fname.title(),
                             font=ctk.CTkFont(family=FONT, size=12),
                             text_color=TEXT).grid(row=0, column=0, sticky="w",
                                                   padx=12)
                val = str(search_key) if isinstance(search_key, str) \
                    else ", ".join(search_key)
                ctk.CTkLabel(
                    r, text=f"{master.title()} → {val}",
                    font=ctk.CTkFont(family=FONT, size=12),
                    text_color=PURPLE
                ).grid(row=0, column=1, sticky="w", padx=(20, 12))


def _render_filename_table(container, mapping):
    for w in container.winfo_children():
        w.destroy()
    _filename_mapping_table(container, mapping)
