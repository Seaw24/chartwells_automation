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
    GREEN,
    FONT,
    show_input_dialog,
)

try:
    from BE.src.tender_break.config import (
        FILENAME_TO_MASTER_NAME,
        LOCATION_START_COL,
        IMPORTANT_CASHEET_DATA_COL,
        DIRECTORY_PATHS,
        FIRST_DATE_ROW,
        DATE_COL,
        save_config as save_tender_config,
    )
    _HAS_TENDER = True
except (ImportError, ModuleNotFoundError):
    _HAS_TENDER = False


class AutoFillConfigController:
    def __init__(self, view):
        self.view = view

    def _input_dialog(self, title, fields, defaults=None):
        return show_input_dialog(self.view, title, fields, defaults=defaults)

    def _save_config(self):
        try:
            reports_dir = self.view._config_rep_folder.get().strip()
        except AttributeError:
            reports_dir = REPORTS_FOLDER
        try:
            casheet_dir = self.view._config_cs_folder.get().strip()
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

    def _refresh_cs_loc_table(self):
        for w in self.view._cs_loc_container.winfo_children():
            w.destroy()
        if hasattr(self.view, "_cs_loc_count"):
            self.view._cs_loc_count.configure(
                text=f"({len(REPORTS_CASHSHEET_MAP)} locations)")
        tbl = ctk.CTkFrame(self.view._cs_loc_container,
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
        for w in self.view._gh_loc_container.winfo_children():
            w.destroy()
        if hasattr(self.view, "_gh_loc_count"):
            self.view._gh_loc_count.configure(
                text=f"({len(GRUBHUB_VENUE_MAP)} venues)")
        tbl = ctk.CTkFrame(self.view._gh_loc_container,
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

    def _refresh_filename_mapping_table(self):
        if not _HAS_TENDER:
            return
        for w in self.view._fn_map_container.winfo_children():
            w.destroy()
        total = sum(len(d) for lst in FILENAME_TO_MASTER_NAME.values()
                    for d in lst)
        if hasattr(self.view, "_fn_map_count"):
            self.view._fn_map_count.configure(text=f"({total} mappings)")
        tbl = ctk.CTkFrame(self.view._fn_map_container,
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
        for w in container.winfo_children():
            w.destroy()
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
                r["Cash Sheet"], r["Register"], mv[-1]]
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
            GRUBHUB_VENUE_MAP[new_name] = [
                r["Cash Sheet"], r["Register"], mv[-1]]
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

    def _save_tender_config(self):
        if not _HAS_TENDER:
            return
        try:
            master = self.view._config_tb_master.get().strip()
        except AttributeError:
            master = DIRECTORY_PATHS.get("master_path", "")
        try:
            casheets = self.view._tb_folder_entry.get().strip()
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
        if not _HAS_TENDER:
            return
        try:
            from BE.src.tender_break import config as tc
            tc.FIRST_DATE_ROW = int(self.view._config_first_row.get().strip())
            tc.DATE_COL = int(self.view._config_date_col.get().strip())
            globals()["FIRST_DATE_ROW"] = tc.FIRST_DATE_ROW
            globals()["DATE_COL"] = tc.DATE_COL
        except (ValueError, AttributeError):
            messagebox.showerror(
                "Error", "Date Column and First Date Row must be integers.")
            return
        self._save_tender_config()
        messagebox.showinfo("Saved", "Tender settings saved.")

    def _save_tender_data_cols(self):
        if not _HAS_TENDER:
            return
        try:
            vals = [int(x.strip())
                    for x in self.view._config_data_cols.get().split(",") if x.strip()]
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

    def _add_filename_mapping(self):
        r = self._input_dialog("Add Filename Mapping",
                               ["Filename Key", "Master Location", "Casheet Keyword"])
        if r and r["Filename Key"] and r["Master Location"]:
            fn_key = r["Filename Key"].strip().lower()
            master_loc = r["Master Location"].strip()
            kw_raw = r["Casheet Keyword"].strip()
            kw = [x.strip() for x in kw_raw.split(
                ",")] if "," in kw_raw else kw_raw
            if fn_key not in FILENAME_TO_MASTER_NAME:
                FILENAME_TO_MASTER_NAME[fn_key] = []
            FILENAME_TO_MASTER_NAME[fn_key].append({master_loc: kw})
            self._save_tender_config()
            self._refresh_filename_mapping_table()

    def _edit_filename_mapping(self, fn_key, master_loc):
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
            for md in FILENAME_TO_MASTER_NAME.get(fn_key, []):
                if master_loc in md:
                    FILENAME_TO_MASTER_NAME[fn_key].remove(md)
                    break
            if fn_key != new_fn_key and not FILENAME_TO_MASTER_NAME.get(fn_key):
                FILENAME_TO_MASTER_NAME.pop(fn_key, None)
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
