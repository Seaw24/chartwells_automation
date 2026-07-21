"""
Controller for the two configuration tabs of the AutoFill Center.

All mapping tables share the same renderers / add-edit-delete flows so
every card behaves the same way: live entry counts, zebra rows, dialogs
with helper text + validation, duplicate-key protection, and renames
that keep the entry's position in the file.
"""

from tkinter import messagebox

import customtkinter as ctk

from BE.src.cash_sheet_filler.config import (
    REPORTS_CASHSHEET_MAP,
    FILL_COL_MAP,
    CHECKING_COL_MAP,
    INFOR_TENDERS,
    TAVLO_TENDERS,
    CASHEET_TENDERS,
    CASH_SHEET_FOLDER,
    REPORTS_FOLDER,
    GRUBHUB_TENDERS,
    GRUBHUB_VENUE_MAP,
    load_config as load_cash_sheet_config,
    save_config as save_cash_sheet_config,
)

from .autofill_center_ui import (
    PURPLE,
    BG,
    TEXT,
    TEXT_SEC,
    TEXT_MUTED,
    CARD,
    RED,
    RED_BG,
    ORANGE,
    ORANGE_BG,
    FONT,
    show_input_dialog,
)

try:
    from BE.src.tender_break.config import (
        FILENAME_TO_MASTER_NAME,
        LOCATION_START_COL,
        IMPORTANT_CASHEET_DATA_COL,
        DIRECTORY_PATHS,
        load_config as load_tender_config,
        save_config as save_tender_config,
    )
    _HAS_TENDER = True
except (ImportError, ModuleNotFoundError):
    _HAS_TENDER = False


class AutoFillConfigController:
    # ── Location dialog field labels (Cash Sheet + Grubhub cards) ──
    _F_SHEET = "Cash Sheet File"
    _F_ROW = "Row in Cash Sheet"
    _F_DB = "Analytics Name"
    _CS_KEY = "Report Location"
    _CS_KEY_HELP = ("Location name exactly as it appears in the "
                    "Infor / Tavlo day report file.")
    _GH_KEY = "Grubhub Venue"
    _GH_KEY_HELP = "Venue name exactly as it appears in the Grubhub report."

    _COLUMN_HELPERS = {
        "Field": "Report value this column holds, e.g. 'total_sales'.",
        "Column #": "Column number in the cash sheet, where column A = 1.",
    }
    _TENDER_HELPERS = {
        "Tender Name": "Tender name exactly as it appears on the report.",
        "Payment Method": ("Payment method exactly as it appears on the "
                           "Grubhub report."),
        "Internal Key": ("Internal tender key the cash sheet tracks, "
                         "e.g. 'flex' or 'contract_card'."),
        "Tender Key": "Internal tender key, e.g. 'flex' or 'contract_card'.",
        "Default Value": "Starting amount for this tender (usually 0).",
    }
    _TB_LOC_HELPERS = {
        "Location Name": ("Location name (lower-case) as used in the master "
                          "breakdown file."),
        "Start Column": ("First column of this location's block in the "
                         "master file, where column A = 1."),
    }
    _FN_MAP_HELPERS = {
        "Filename Keyword": ("Lower-case keyword matched against cash-sheet "
                             "file names, e.g. 'gardner'."),
        "Master Location": "Location block name in the master breakdown file.",
        "Cash Sheet Keyword(s)": ("Keyword(s) identifying this location's "
                                  "rows inside the cash sheet. Use 'TOTALS' "
                                  "for the totals row; separate several "
                                  "keywords with commas."),
    }

    def __init__(self, view):
        self.view = view

    # ══════════════════════════════════════════════════════════════
    #  Shared plumbing
    # ══════════════════════════════════════════════════════════════
    def _input_dialog(self, title, fields, defaults=None, helpers=None,
                      required=None, numeric=None):
        return show_input_dialog(self.view, title, fields, defaults=defaults,
                                 helpers=helpers, required=required,
                                 numeric=numeric)

    def _confirm_delete(self, name):
        return messagebox.askyesno(
            "Delete", f"Delete '{name}'?\nThis cannot be undone.",
            parent=self.view)

    def _duplicate_error(self, key):
        messagebox.showerror(
            "Already exists",
            f"An entry named '{key}' already exists.\n"
            "Edit that row instead of adding a duplicate.",
            parent=self.view)

    @staticmethod
    def _replace_key(mapping, old, new, value):
        """Set mapping[old→new] = value, keeping the entry's position."""
        if old == new:
            mapping[old] = value
            return
        items = [(new, value) if k == old else (k, v)
                 for k, v in mapping.items()]
        mapping.clear()
        mapping.update(items)

    @staticmethod
    def _parse_number_or_text(raw):
        try:
            return float(raw) if "." in raw else int(raw)
        except ValueError:
            return raw

    def _save_config(self):
        try:
            reports_dir = self.view._config_rep_folder.get().strip()
        except AttributeError:
            reports_dir = REPORTS_FOLDER
        try:
            casheet_dir = self.view._config_cs_folder.get().strip()
        except AttributeError:
            casheet_dir = CASH_SHEET_FOLDER
        # Start from the file on disk so keys this panel doesn't manage
        # (e.g. summary_data_map) survive a save untouched.
        try:
            full_config = load_cash_sheet_config()
        except (FileNotFoundError, ValueError):
            full_config = {}
        full_config.update({
            "reports_cashsheet_map": REPORTS_CASHSHEET_MAP,
            "grubhub_venue_map": GRUBHUB_VENUE_MAP,
            "fill_col_map": FILL_COL_MAP,
            "checking_col_map": CHECKING_COL_MAP,
            "infor_tenders": INFOR_TENDERS,
            "tavlo_tenders": TAVLO_TENDERS,
            "grubhub_tenders": GRUBHUB_TENDERS,
            "casheet_tenders": CASHEET_TENDERS,
            "reports_folder": reports_dir,
            "cash_sheets_folder": casheet_dir,
        })
        full_config.setdefault("summary_data_map", {})
        save_cash_sheet_config(full_config)

    def _save_tender_config(self):
        if not _HAS_TENDER:
            return
        from BE.src.tender_break import config as tc
        try:
            master = self.view._config_tb_master.get().strip()
        except AttributeError:
            master = DIRECTORY_PATHS.get("master_path", "")
        try:
            casheets = self.view._tb_folder_entry.get().strip()
        except AttributeError:
            casheets = DIRECTORY_PATHS.get("casheets_dir", "")
        try:
            full = load_tender_config()
        except (FileNotFoundError, ValueError):
            full = {}
        full.update({
            "filename_to_master_name": FILENAME_TO_MASTER_NAME,
            "location_start_col": LOCATION_START_COL,
            "directory_paths": {"casheets_dir": casheets,
                                "master_path": master},
            "important_casheet_data_col": IMPORTANT_CASHEET_DATA_COL,
            "first_date_row": tc.FIRST_DATE_ROW,
            "date_col": tc.DATE_COL,
        })
        save_tender_config(full)

    # ══════════════════════════════════════════════════════════════
    #  Generic two-column mapping table (key → value)
    # ══════════════════════════════════════════════════════════════
    def _render_map_table(self, container, mapping, kl, vl,
                          edit_cb, del_cb, noun="entries"):
        for w in container.winfo_children():
            w.destroy()
        count_label = getattr(container, "_count_label", None)
        if count_label is not None:
            count_label.configure(text=f"({len(mapping)} {noun})")
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not mapping:
            ctk.CTkLabel(tbl, text='Nothing here yet — use "+ Add" above',
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        hr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hr, text=kl,
                     font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hr, text=vl,
                     font=ctk.CTkFont(family=FONT, size=10, weight="bold"),
                     text_color=TEXT_MUTED).grid(row=0, column=1, sticky="e",
                                                 padx=(0, 70))
        for i, (k, v) in enumerate(mapping.items()):
            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=28)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            r.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(r, text=str(k),
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT).grid(row=0, column=0,
                                               sticky="w", padx=10)
            ctk.CTkLabel(r, text=str(v),
                         font=ctk.CTkFont(family=FONT, size=11,
                                          weight="bold"),
                         text_color=PURPLE).grid(row=0, column=1,
                                                 sticky="e", padx=10)
            ctk.CTkButton(r, text="✏️", width=26, height=20, corner_radius=5,
                          fg_color=ORANGE_BG, text_color=ORANGE,
                          hover_color="#FFE8CC", font=ctk.CTkFont(size=10),
                          command=lambda key=k: edit_cb(key),
                          cursor="hand2").grid(row=0, column=2, padx=(4, 2))
            ctk.CTkButton(r, text="🗑", width=26, height=20, corner_radius=5,
                          fg_color=RED_BG, text_color=RED,
                          hover_color="#FFCCC9", font=ctk.CTkFont(size=10),
                          command=lambda key=k: del_cb(key),
                          cursor="hand2").grid(row=0, column=3, padx=(2, 10))

    def _map_add(self, mapping, kl, vl, refresh, save, *,
                 helpers=None, int_value=False, lower_key=False,
                 title="Entry"):
        r = self._input_dialog(f"Add {title}", [kl, vl], helpers=helpers,
                               required=[kl, vl],
                               numeric=[vl] if int_value else None)
        if not r:
            return
        key = r[kl].lower() if lower_key else r[kl]
        if key in mapping:
            self._duplicate_error(key)
            return
        mapping[key] = (int(r[vl]) if int_value
                        else self._parse_number_or_text(r[vl]))
        save()
        refresh()

    def _map_edit(self, mapping, key, kl, vl, refresh, save, *,
                  helpers=None, int_value=False, lower_key=False,
                  title="Entry"):
        r = self._input_dialog(f"Edit {title}", [kl, vl],
                               defaults={kl: key, vl: mapping[key]},
                               helpers=helpers, required=[kl, vl],
                               numeric=[vl] if int_value else None)
        if not r:
            return
        new_key = r[kl].lower() if lower_key else r[kl]
        if new_key != key and new_key in mapping:
            self._duplicate_error(new_key)
            return
        value = (int(r[vl]) if int_value
                 else self._parse_number_or_text(r[vl]))
        self._replace_key(mapping, key, new_key, value)
        save()
        refresh()

    def _map_delete(self, mapping, key, refresh, save):
        if self._confirm_delete(key):
            mapping.pop(key, None)
            save()
            refresh()

    # ── Fill / checking column maps (cash-sheet config) ───────────
    def _refresh_kv_table(self, container, mapping):
        def refresh():
            self._refresh_kv_table(container, mapping)
        self._render_map_table(
            container, mapping, "Field", "Column #",
            edit_cb=lambda k: self._map_edit(
                mapping, k, "Field", "Column #", refresh, self._save_config,
                helpers=self._COLUMN_HELPERS, int_value=True,
                title="Column Mapping"),
            del_cb=lambda k: self._map_delete(
                mapping, k, refresh, self._save_config),
            noun="fields")

    def _add_kv(self, mapping, container):
        self._map_add(
            mapping, "Field", "Column #",
            lambda: self._refresh_kv_table(container, mapping),
            self._save_config, helpers=self._COLUMN_HELPERS,
            int_value=True, title="Column Mapping")

    # ── Tender maps (cash-sheet config) ───────────────────────────
    def _refresh_tender_table(self, container, mapping, kl="Key", vl="Value"):
        def refresh():
            self._refresh_tender_table(container, mapping, kl, vl)
        self._render_map_table(
            container, mapping, kl, vl,
            edit_cb=lambda k: self._map_edit(
                mapping, k, kl, vl, refresh, self._save_config,
                helpers=self._TENDER_HELPERS, title="Tender"),
            del_cb=lambda k: self._map_delete(
                mapping, k, refresh, self._save_config),
            noun="tenders")

    def _add_tender(self, mapping, container, kl="Key", vl="Value"):
        self._map_add(
            mapping, kl, vl,
            lambda: self._refresh_tender_table(container, mapping, kl, vl),
            self._save_config, helpers=self._TENDER_HELPERS, title="Tender")

    # ── Location start columns (tender-breakdown config) ──────────
    def _refresh_tender_kv_table(self, container, mapping, kl, vl):
        def refresh():
            self._refresh_tender_kv_table(container, mapping, kl, vl)
        self._render_map_table(
            container, mapping, kl, vl,
            edit_cb=lambda k: self._map_edit(
                mapping, k, kl, vl, refresh, self._save_tender_config,
                helpers=self._TB_LOC_HELPERS, int_value=True, lower_key=True,
                title="Location"),
            del_cb=lambda k: self._map_delete(
                mapping, k, refresh, self._save_tender_config),
            noun="locations")

    def _add_tender_kv(self, mapping, container, kl, vl):
        self._map_add(
            mapping, kl, vl,
            lambda: self._refresh_tender_kv_table(container, mapping, kl, vl),
            self._save_tender_config, helpers=self._TB_LOC_HELPERS,
            int_value=True, lower_key=True, title="Location")

    # ══════════════════════════════════════════════════════════════
    #  Location tables (Cash Sheet Locations + Grubhub Venues)
    #  Each value is [file keyword, row label, analytics name] — the
    #  autofill engine unpacks all three, so all three are editable.
    # ══════════════════════════════════════════════════════════════
    @staticmethod
    def _location_parts(key, value):
        """Normalize a stored value to (file_keyword, row_label, db_name)."""
        if isinstance(value, (list, tuple)):
            vals = [str(v) for v in value] + ["", "", ""]
            return vals[0], vals[1], vals[2] or key
        return str(value), "", key

    def _location_dialog(self, title, key_label, key_helper, defaults=None):
        helpers = {
            key_label: key_helper,
            self._F_SHEET: ("Part of the cash-sheet workbook's file name — "
                            "any file containing this text is used, "
                            "e.g. 'gardner'."),
            self._F_ROW: ("Register / location label inside the cash sheet "
                          "that this data is written to, e.g. 'Register 1'."),
            self._F_DB: ("Name saved to the database and shown on the "
                         "Analytics page. Leave blank to reuse the "
                         f"{key_label.lower()}."),
        }
        return self._input_dialog(
            title,
            [key_label, self._F_SHEET, self._F_ROW, self._F_DB],
            defaults=defaults, helpers=helpers,
            required=[key_label, self._F_SHEET, self._F_ROW])

    def _render_location_table(self, container, mapping, key_header,
                               edit_cb, del_cb, noun):
        for w in container.winfo_children():
            w.destroy()
        count_label = getattr(container, "_count_label", None)
        if count_label is not None:
            count_label.configure(text=f"({len(mapping)} {noun})")
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not mapping:
            ctk.CTkLabel(tbl, text='Nothing here yet — use "+ Add" above',
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        headers = [key_header, self._F_SHEET, self._F_ROW, self._F_DB]
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        for col, txt in enumerate(headers):
            hr.grid_columnconfigure(col, weight=1, uniform="loc")
            ctk.CTkLabel(hr, text=txt,
                         font=ctk.CTkFont(family=FONT, size=10,
                                          weight="bold"),
                         text_color=TEXT_MUTED).grid(
                row=0, column=col, sticky="w",
                padx=(0 if col == 0 else 12, 0))
        # Spacer matching the edit/delete buttons so headers line up
        # with the row cells below.
        ctk.CTkFrame(hr, fg_color="transparent", width=62,
                     height=1).grid(row=0, column=len(headers))
        for i, (key, value) in enumerate(mapping.items()):
            sheet, row_label, db_name = self._location_parts(key, value)
            r = ctk.CTkFrame(tbl, fg_color=CARD if i % 2 == 0 else BG,
                             corner_radius=4, height=30)
            r.pack(fill="x", padx=6, pady=1)
            r.pack_propagate(False)
            for c in range(4):
                r.grid_columnconfigure(c, weight=1, uniform="loc")
            cells = [(key, TEXT, "normal"), (sheet, PURPLE, "bold"),
                     (row_label, TEXT_SEC, "normal"),
                     (db_name, TEXT_SEC, "normal")]
            for c, (txt, color, weight) in enumerate(cells):
                ctk.CTkLabel(r, text=txt,
                             font=ctk.CTkFont(family=FONT, size=11,
                                              weight=weight),
                             text_color=color, anchor="w").grid(
                    row=0, column=c, sticky="w",
                    padx=(10 if c == 0 else 12, 0))
            ctk.CTkButton(r, text="✏️", width=26, height=22, corner_radius=5,
                          fg_color=ORANGE_BG, text_color=ORANGE,
                          hover_color="#FFE8CC", font=ctk.CTkFont(size=10),
                          command=lambda k=key: edit_cb(k),
                          cursor="hand2").grid(row=0, column=4, padx=(8, 2))
            ctk.CTkButton(r, text="🗑", width=26, height=22, corner_radius=5,
                          fg_color=RED_BG, text_color=RED,
                          hover_color="#FFCCC9", font=ctk.CTkFont(size=10),
                          command=lambda k=key: del_cb(k),
                          cursor="hand2").grid(row=0, column=5, padx=(2, 10))

    def _location_add(self, mapping, key_label, key_helper, refresh, title):
        r = self._location_dialog(f"Add {title}", key_label, key_helper)
        if not r:
            return
        key = r[key_label]
        if key in mapping:
            self._duplicate_error(key)
            return
        mapping[key] = [r[self._F_SHEET], r[self._F_ROW],
                        r[self._F_DB] or key]
        self._save_config()
        refresh()

    def _location_edit(self, mapping, key, key_label, key_helper,
                       refresh, title):
        sheet, row_label, db_name = self._location_parts(key, mapping[key])
        r = self._location_dialog(
            f"Edit {title}", key_label, key_helper,
            defaults={key_label: key, self._F_SHEET: sheet,
                      self._F_ROW: row_label, self._F_DB: db_name})
        if not r:
            return
        new_key = r[key_label]
        if new_key != key and new_key in mapping:
            self._duplicate_error(new_key)
            return
        self._replace_key(mapping, key, new_key,
                          [r[self._F_SHEET], r[self._F_ROW],
                           r[self._F_DB] or new_key])
        self._save_config()
        refresh()

    def _location_delete(self, mapping, key, refresh):
        if self._confirm_delete(key):
            mapping.pop(key, None)
            self._save_config()
            refresh()

    # ── Cash Sheet Locations card ─────────────────────────────────
    def _refresh_cs_loc_table(self):
        self._render_location_table(
            self.view._cs_loc_container, REPORTS_CASHSHEET_MAP, self._CS_KEY,
            edit_cb=lambda k: self._location_edit(
                REPORTS_CASHSHEET_MAP, k, self._CS_KEY, self._CS_KEY_HELP,
                self._refresh_cs_loc_table, "Cash Sheet Location"),
            del_cb=lambda k: self._location_delete(
                REPORTS_CASHSHEET_MAP, k, self._refresh_cs_loc_table),
            noun="locations")

    def _add_cs_location(self):
        self._location_add(
            REPORTS_CASHSHEET_MAP, self._CS_KEY, self._CS_KEY_HELP,
            self._refresh_cs_loc_table, "Cash Sheet Location")

    # ── Grubhub Venues card ───────────────────────────────────────
    def _refresh_gh_venue_table(self):
        self._render_location_table(
            self.view._gh_loc_container, GRUBHUB_VENUE_MAP, self._GH_KEY,
            edit_cb=lambda k: self._location_edit(
                GRUBHUB_VENUE_MAP, k, self._GH_KEY, self._GH_KEY_HELP,
                self._refresh_gh_venue_table, "Grubhub Venue"),
            del_cb=lambda k: self._location_delete(
                GRUBHUB_VENUE_MAP, k, self._refresh_gh_venue_table),
            noun="venues")

    def _add_gh_venue(self):
        self._location_add(
            GRUBHUB_VENUE_MAP, self._GH_KEY, self._GH_KEY_HELP,
            self._refresh_gh_venue_table, "Grubhub Venue")

    # ══════════════════════════════════════════════════════════════
    #  Tender-breakdown page: filename → master mappings
    # ══════════════════════════════════════════════════════════════
    def _refresh_filename_mapping_table(self):
        if not _HAS_TENDER:
            return
        container = self.view._fn_map_container
        for w in container.winfo_children():
            w.destroy()
        total = sum(len(d) for lst in FILENAME_TO_MASTER_NAME.values()
                    for d in lst)
        count_label = getattr(container, "_count_label", None)
        if count_label is not None:
            count_label.configure(text=f"({total} mappings)")
        tbl = ctk.CTkFrame(container, fg_color=BG, corner_radius=8)
        tbl.pack(fill="x")
        if not FILENAME_TO_MASTER_NAME:
            ctk.CTkLabel(tbl, text='Nothing here yet — use "+ Add" above',
                         font=ctk.CTkFont(family=FONT, size=11),
                         text_color=TEXT_MUTED).pack(pady=16)
            return
        hr = ctk.CTkFrame(tbl, fg_color="transparent")
        hr.pack(fill="x", padx=12, pady=(8, 4))
        headers = ["Filename Keyword", "Master Location",
                   "Cash Sheet Keyword(s)"]
        for col, txt in enumerate(headers):
            hr.grid_columnconfigure(col, weight=1, uniform="fn")
            ctk.CTkLabel(hr, text=txt,
                         font=ctk.CTkFont(family=FONT, size=10,
                                          weight="bold"),
                         text_color=TEXT_MUTED).grid(
                row=0, column=col, sticky="w",
                padx=(0 if col == 0 else 12, 0))
        ctk.CTkFrame(hr, fg_color="transparent", width=62,
                     height=1).grid(row=0, column=len(headers))
        row_i = 0
        for fn_key, mappings_list in FILENAME_TO_MASTER_NAME.items():
            for mapping_dict in mappings_list:
                for master_loc, kw in mapping_dict.items():
                    kw_display = (", ".join(kw) if isinstance(kw, list)
                                  else str(kw))
                    r = ctk.CTkFrame(tbl,
                                     fg_color=CARD if row_i % 2 == 0 else BG,
                                     corner_radius=4, height=30)
                    r.pack(fill="x", padx=6, pady=1)
                    r.pack_propagate(False)
                    for c in range(3):
                        r.grid_columnconfigure(c, weight=1, uniform="fn")
                    cells = [(fn_key, TEXT, "normal"),
                             (master_loc, PURPLE, "bold"),
                             (kw_display, TEXT_SEC, "normal")]
                    for c, (txt, color, weight) in enumerate(cells):
                        ctk.CTkLabel(r, text=txt,
                                     font=ctk.CTkFont(family=FONT, size=11,
                                                      weight=weight),
                                     text_color=color, anchor="w").grid(
                            row=0, column=c, sticky="w",
                            padx=(10 if c == 0 else 12, 0))
                    ctk.CTkButton(
                        r, text="✏️", width=26, height=22, corner_radius=5,
                        fg_color=ORANGE_BG, text_color=ORANGE,
                        hover_color="#FFE8CC", font=ctk.CTkFont(size=10),
                        command=lambda fk=fn_key, ml=master_loc:
                        self._edit_filename_mapping(fk, ml),
                        cursor="hand2").grid(row=0, column=3, padx=(8, 2))
                    ctk.CTkButton(
                        r, text="🗑", width=26, height=22, corner_radius=5,
                        fg_color=RED_BG, text_color=RED,
                        hover_color="#FFCCC9", font=ctk.CTkFont(size=10),
                        command=lambda fk=fn_key, ml=master_loc:
                        self._del_filename_mapping(fk, ml),
                        cursor="hand2").grid(row=0, column=4, padx=(2, 10))
                    row_i += 1

    @staticmethod
    def _parse_keywords(raw):
        return ([x.strip() for x in raw.split(",")]
                if "," in raw else raw)

    def _add_filename_mapping(self):
        r = self._input_dialog(
            "Add Filename Mapping",
            ["Filename Keyword", "Master Location", "Cash Sheet Keyword(s)"],
            helpers=self._FN_MAP_HELPERS,
            required=["Filename Keyword", "Master Location",
                      "Cash Sheet Keyword(s)"])
        if not r:
            return
        fn_key = r["Filename Keyword"].lower()
        master_loc = r["Master Location"]
        kw = self._parse_keywords(r["Cash Sheet Keyword(s)"])
        FILENAME_TO_MASTER_NAME.setdefault(fn_key, []).append({master_loc: kw})
        self._save_tender_config()
        self._refresh_filename_mapping_table()

    def _edit_filename_mapping(self, fn_key, master_loc):
        current_kw = ""
        for md in FILENAME_TO_MASTER_NAME.get(fn_key, []):
            if master_loc in md:
                kw = md[master_loc]
                current_kw = ", ".join(kw) if isinstance(kw, list) else str(kw)
                break
        r = self._input_dialog(
            "Edit Filename Mapping",
            ["Filename Keyword", "Master Location", "Cash Sheet Keyword(s)"],
            defaults={"Filename Keyword": fn_key,
                      "Master Location": master_loc,
                      "Cash Sheet Keyword(s)": current_kw},
            helpers=self._FN_MAP_HELPERS,
            required=["Filename Keyword", "Master Location",
                      "Cash Sheet Keyword(s)"])
        if not r:
            return
        new_fn_key = r["Filename Keyword"].lower()
        new_loc = r["Master Location"]
        kw = self._parse_keywords(r["Cash Sheet Keyword(s)"])
        for md in FILENAME_TO_MASTER_NAME.get(fn_key, []):
            if master_loc in md:
                FILENAME_TO_MASTER_NAME[fn_key].remove(md)
                break
        if fn_key != new_fn_key and not FILENAME_TO_MASTER_NAME.get(fn_key):
            FILENAME_TO_MASTER_NAME.pop(fn_key, None)
        FILENAME_TO_MASTER_NAME.setdefault(
            new_fn_key, []).append({new_loc: kw})
        self._save_tender_config()
        self._refresh_filename_mapping_table()

    def _del_filename_mapping(self, fn_key, master_loc):
        if self._confirm_delete(f"{fn_key} → {master_loc}"):
            for md in FILENAME_TO_MASTER_NAME.get(fn_key, []):
                if master_loc in md:
                    FILENAME_TO_MASTER_NAME[fn_key].remove(md)
                    break
            if not FILENAME_TO_MASTER_NAME.get(fn_key):
                FILENAME_TO_MASTER_NAME.pop(fn_key, None)
            self._save_tender_config()
            self._refresh_filename_mapping_table()

    # ══════════════════════════════════════════════════════════════
    #  Tender-breakdown page: date / data-column settings
    # ══════════════════════════════════════════════════════════════
    def _save_tender_settings(self):
        if not _HAS_TENDER:
            return
        from BE.src.tender_break import config as tc
        try:
            tc.FIRST_DATE_ROW = int(self.view._config_first_row.get().strip())
            tc.DATE_COL = int(self.view._config_date_col.get().strip())
        except (ValueError, AttributeError):
            messagebox.showerror(
                "Invalid input",
                "Date Column and First Date Row must be whole numbers.",
                parent=self.view)
            return
        self._save_tender_config()
        messagebox.showinfo("Saved", "Date settings saved.",
                            parent=self.view)

    def _save_tender_data_cols(self):
        if not _HAS_TENDER:
            return
        try:
            vals = [int(x.strip())
                    for x in self.view._config_data_cols.get().split(",")
                    if x.strip()]
        except ValueError:
            messagebox.showerror(
                "Invalid input",
                "Enter whole numbers separated by commas, like 3, 4, 6.",
                parent=self.view)
            return
        IMPORTANT_CASHEET_DATA_COL.clear()
        IMPORTANT_CASHEET_DATA_COL.extend(vals)
        self._save_tender_config()
        messagebox.showinfo("Saved", f"Data columns updated: {vals}",
                            parent=self.view)
