import threading

import customtkinter as ctk
from tkinter import filedialog, messagebox

from BE.src.printer import ExcelPrinter
from BE.src.cash_sheet_filler.main import CashSheetAutofillEngine

from .autofill_center_ui import (
    PURPLE,
    PURPLE_DARK,
    BG,
    TEXT_SEC,
    TEXT_MUTED,
    RED,
    ORANGE,
    GREEN,
    BORDER,
    FONT,
)

try:
    from BE.src.tender_break.main import TenderBreakdownEngine
    _HAS_TENDER = True
except (ImportError, ModuleNotFoundError):
    _HAS_TENDER = False


class AutoFillRuntimeController:
    def __init__(self, view):
        self.view = view

    def _append_log(self, log_widget, text):
        def _do():
            log_widget.configure(state="normal")
            log_widget.insert("end", text + "\n")
            log_widget.see("end")
            log_widget.configure(state="disabled")
        self.view.after(0, _do)

    def _clear_log(self, log_widget):
        log_widget.configure(state="normal")
        log_widget.delete("1.0", "end")
        log_widget.configure(state="disabled")

    def _set_status(self, label, text, color=TEXT_MUTED):
        self.view.after(0, lambda: label.configure(
            text=text, text_color=color))

    def _stop_cash_sheet_autofill(self):
        if hasattr(self.view, '_cs_stop_event'):
            self.view._cs_stop_event.set()
        self.view._cs_run_btn.configure(
            state="disabled", text="🛑  Stopping...")

    def _run_cash_sheet_autofill(self):
        casheet_dir = self.view._cs_folder1_entry.get().strip()
        reports_dir = self.view._cs_folder2_entry.get().strip()
        if not casheet_dir:
            messagebox.showwarning("Missing", "Select the Cash Sheet folder.")
            return
        if not reports_dir:
            messagebox.showwarning("Missing", "Select the Day Reports folder.")
            return

        self.view._cs_stop_event = threading.Event()
        self.view._cs_run_btn.configure(
            state="normal", text="🛑  Stop Autofill",
            fg_color="#D9534F", hover_color="#C9302C",
            command=self._stop_cash_sheet_autofill)
        self._clear_log(self.view._cs_log)
        self._set_status(self.view._cs_status, "Processing...", ORANGE)

        def _on_event(kind, msg):
            self._append_log(self.view._cs_log, msg)

        def _worker():
            try:
                printer_name = self.view._printer_var.get()
                if printer_name == "System Default":
                    printer_name = None

                engine = CashSheetAutofillEngine(
                    reports_dir=reports_dir, casheet_dir=casheet_dir,
                    on_event=_on_event, stop_event=self.view._cs_stop_event,
                    auto_print=self.view._cs_auto_print.get() == 1,
                    printer_name=printer_name)
                engine.execute()
                self.view.after(
                    0, lambda: self._on_cash_sheet_done(engine.tracker))
            except Exception as exc:
                self._append_log(self.view._cs_log,
                                 f"\n❌ Unexpected error: {exc}")
                self.view.after(0, lambda: self._on_cash_sheet_done(None))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_cash_sheet_done(self, tracker):
        self.view._cs_run_btn.configure(
            state="normal", text="🚀  Run Cash Sheet Autofill",
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            command=self._run_cash_sheet_autofill)
        if tracker is None:
            self._set_status(self.view._cs_status, "Error", RED)
            return
        if hasattr(self.view, '_cs_stop_event') and self.view._cs_stop_event.is_set():
            self._set_status(self.view._cs_status, "Cancelled", ORANGE)
            return
        s, f, w = len(tracker.successful), len(
            tracker.failed), len(tracker.warnings)
        if f == 0:
            self._set_status(
                self.view._cs_status, f"Done: {s} ok, {w} warnings", GREEN)
        else:
            self._set_status(
                self.view._cs_status, f"Done: {s} ok, {f} failed, {w} warnings", RED)
        if s > 0:
            self.view._record_and_refresh("cash_sheet")

    def _stop_tender_autofill(self):
        if hasattr(self.view, '_tb_stop_event'):
            self.view._tb_stop_event.set()
        self.view._tb_run_btn.configure(
            state="disabled", text="🛑  Stopping...")

    def _run_tender_autofill(self):
        if not _HAS_TENDER:
            self._append_log(self.view._tb_log,
                             "❌ Tender module not available.")
            return

        casheet_dir = self.view._tb_folder_entry.get().strip()
        master_path = self.view._tb_file_entry.get().strip()

        if not casheet_dir:
            messagebox.showwarning("Missing", "Select the Cash Sheets folder.")
            return
        if not master_path:
            messagebox.showwarning(
                "Missing", "Select the Tender Breakdown file.")
            return

        self.view._tb_stop_event = threading.Event()
        self.view._tb_run_btn.configure(
            state="normal", text="🛑  Stop Autofill",
            fg_color="#D9534F", hover_color="#C9302C",
            command=self._stop_tender_autofill)
        self._clear_log(self.view._tb_log)
        self._set_status(self.view._tb_status, "Processing...", ORANGE)

        def _on_event(kind, msg):
            self._append_log(self.view._tb_log, msg)

        def _worker():
            try:
                engine = TenderBreakdownEngine(
                    casheet_dir=casheet_dir, master_path=master_path,
                    on_event=_on_event, stop_event=self.view._tb_stop_event)
                engine.execute()
                self.view.after(
                    0, lambda: self._on_tender_done(engine.tracker))
            except Exception as exc:
                self._append_log(self.view._tb_log,
                                 f"\n❌ Unexpected error: {exc}")
                self.view.after(0, lambda: self._on_tender_done(None))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_tender_done(self, tracker):
        self.view._tb_run_btn.configure(
            state="normal", text="🚀  Run Tender Breakdown Autofill",
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            command=self._run_tender_autofill)
        if tracker is None:
            self._set_status(self.view._tb_status, "Error", RED)
            return
        if hasattr(self.view, '_tb_stop_event') and self.view._tb_stop_event.is_set():
            self._set_status(self.view._tb_status, "Cancelled", ORANGE)
            return
        s, f = len(tracker.successful), len(tracker.failed)
        if f == 0:
            self._set_status(self.view._tb_status, f"Done: {s} ok", GREEN)
        else:
            self._set_status(self.view._tb_status,
                             f"Done: {s} ok, {f} failed", RED)
        if s > 0:
            self.view._record_and_refresh("tender")

    def _folder_row(self, parent, grid_r, label, sync_target=None):
        ctk.CTkLabel(parent, text=label,
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT_SEC if "Reports" in label else None).grid(row=grid_r, column=0, sticky="w", pady=(6, 0))
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
                     text_color=TEXT_SEC if "Breakdown" in label else None).grid(row=grid_r, column=0, sticky="w", pady=(6, 0))
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
            for other in (self.view._cs_folder1_entry, self.view._config_cs_folder, self.view._tb_folder_entry):
                if other is not entry:
                    self._set_entry(other, path)
        elif sync_target == "reports":
            for other in (self.view._cs_folder2_entry, self.view._config_rep_folder):
                if other is not entry:
                    self._set_entry(other, path)
        self.view._save_config()

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
                other = getattr(self.view, attr, None)
                if other is not None and other is not entry:
                    self._set_entry(other, path)
            self.view._save_tender_config()

    def _toggle_printer_dropdown(self):
        if self.view._cs_auto_print.get() == 1:
            self.view._printer_frame.pack(side="left")
        else:
            self.view._printer_frame.pack_forget()

    def _refresh_printers(self):
        printers = ExcelPrinter.get_available_printers()
        default = ExcelPrinter.get_default_printer() or "System Default"
        self.view._printer_dropdown.configure(
            values=["System Default"] + printers)
        self.view._printer_var.set(default)
