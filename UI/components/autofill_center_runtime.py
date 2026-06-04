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
    """
    Glue between the AutoFillCenter view and the backend engines.

    Responsibilities:
      • Wire up Run / Stop button state.
      • Marshall background-thread events back to the Tk main thread.
      • Render log events with severity colors and update the live
        success / warning / error badges.
    """

    # Characters that appear in legacy "decorative divider" lines we want
    # to suppress in the UI (the cleaner sections + tags do the visual job).
    _DIVIDER_CHARS = set("=-─━")

    def __init__(self, view):
        self.view = view

    # ── log rendering ─────────────────────────────────────────────
    def _append_log(self, log_widget, text, kind="info"):
        """
        Append one line to ``log_widget`` on the Tk main thread.

        ``kind`` is the structured event type emitted by the tracker
        ('info', 'detail', 'section', 'success', 'warning', 'error',
        'summary'). Each kind maps to a Text-widget tag that carries the
        color/weight, configured once in ``autofill_center._configure_log_tags``.
        """
        # Skip the legacy "===" / "---" decorator lines entirely — the
        # styled section tag is the divider now.
        stripped = text.strip()
        if stripped and set(stripped) <= self._DIVIDER_CHARS:
            return

        def _do():
            log_widget.configure(state="normal")
            log_widget.insert("end", text + "\n", kind)
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

    # ── live stat badges (✓ / ⚠ / ✗) ──────────────────────────────
    def _reset_stats(self, prefix):
        """Reset the counters and their on-screen badges before a new run."""
        setattr(self.view, f"{prefix}_succ_count", 0)
        setattr(self.view, f"{prefix}_warn_count", 0)
        setattr(self.view, f"{prefix}_fail_count", 0)
        self._refresh_stats(prefix)

    def _bump_stats(self, prefix, kind):
        """Increment the right counter for the event ``kind`` and re-render."""
        if kind == "success":
            attr = f"{prefix}_succ_count"
        elif kind == "warning":
            attr = f"{prefix}_warn_count"
        elif kind == "error":
            attr = f"{prefix}_fail_count"
        else:
            return
        setattr(self.view, attr, getattr(self.view, attr, 0) + 1)
        self.view.after(0, lambda: self._refresh_stats(prefix))

    def _refresh_stats(self, prefix):
        """Update the three badge labels for the given log card prefix."""
        succ = getattr(self.view, f"{prefix}_succ_count", 0)
        warn = getattr(self.view, f"{prefix}_warn_count", 0)
        fail = getattr(self.view, f"{prefix}_fail_count", 0)
        succ_lbl = getattr(self.view, f"{prefix}_succ_badge", None)
        warn_lbl = getattr(self.view, f"{prefix}_warn_badge", None)
        fail_lbl = getattr(self.view, f"{prefix}_fail_badge", None)
        if succ_lbl is not None:
            succ_lbl.configure(text=f"✓ {succ}")
        if warn_lbl is not None:
            warn_lbl.configure(text=f"⚠ {warn}")
        if fail_lbl is not None:
            fail_lbl.configure(text=f"✗ {fail}")

    def _stop_cash_sheet_autofill(self):
        if hasattr(self.view, '_cs_stop_event'):
            self.view._cs_stop_event.set()
        self.view._cs_run_btn.configure(
            state="disabled", text="Stopping...")

    def _run_cash_sheet_autofill(self):
        casheet_dir = self.view._cs_folder1_entry.get().strip()
        reports_dir = self.view._cs_folder2_entry.get().strip()
        if not casheet_dir:
            messagebox.showwarning("Missing", "Select the Cash Sheet folder.")
            return
        if not reports_dir:
            messagebox.showwarning("Missing", "Select the Day Reports folder.")
            return
        print_settings = None
        if self.view._cs_auto_print.get() == 1:
            printer_name = self.view._printer_var.get()
            if printer_name == "System Default":
                printer_name = None
            try:
                copies = int(self.view._print_copies_var.get())
            except Exception:
                messagebox.showwarning(
                    "Printer Settings",
                    "Copies must be a whole number, like 1 or 2.")
                return
            if copies < 1:
                messagebox.showwarning(
                    "Printer Settings",
                    "Copies must be at least 1.")
                return
            color_choice = self.view._print_color_var.get().strip().lower()
            orientation = self.view._print_orientation_var.get().strip().lower()
            print_settings = {
                "printer_name": printer_name,
                "color_mode": (
                    "bw" if "black" in color_choice or color_choice == "bw"
                    else "color"),
                "paper_size": self.view._print_paper_var.get(),
                "duplex": self.view._print_duplex_var.get() == 1,
                "copies": copies,
                "orientation": orientation,
                "collate": self.view._print_collate_var.get() == 1,
            }

        self.view._cs_stop_event = threading.Event()
        self.view._cs_run_btn.configure(
            state="normal", text="Stop Autofill",
            fg_color="#D9534F", hover_color="#C9302C",
            command=self._stop_cash_sheet_autofill)
        self._clear_log(self.view._cs_log)
        self._reset_stats("_cs")
        self._set_status(self.view._cs_status, "Processing…", ORANGE)

        def _on_event(kind, msg):
            self._append_log(self.view._cs_log, msg, kind=kind)
            self._bump_stats("_cs", kind)

        def _worker():
            try:
                engine = CashSheetAutofillEngine(
                    reports_dir=reports_dir, casheet_dir=casheet_dir,
                    on_event=_on_event, stop_event=self.view._cs_stop_event,
                    auto_print=self.view._cs_auto_print.get() == 1,
                    printer_name=print_settings.get("printer_name") if print_settings else None,
                    print_settings=print_settings)
                engine.execute()
                self.view.after(
                    0, lambda: self._on_cash_sheet_done(engine.tracker))
            except Exception as exc:
                self._append_log(
                    self.view._cs_log,
                    f"Unexpected error: {exc}", kind="error")
                self.view.after(0, lambda: self._on_cash_sheet_done(None))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_cash_sheet_done(self, tracker):
        # Restore the Run button regardless of how the run ended.
        self.view._cs_run_btn.configure(
            state="normal", text="Run Cash Sheet Autofill",
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            command=self._run_cash_sheet_autofill)
        if tracker is None:
            self._set_status(self.view._cs_status, "Error", RED)
            return
        if hasattr(self.view, '_cs_stop_event') and self.view._cs_stop_event.is_set():
            self._set_status(self.view._cs_status, "Cancelled", ORANGE)
            return
        # Single status word — the badges already show the counts.
        s, f, _ = len(tracker.successful), len(tracker.failed), len(tracker.warnings)
        if f == 0:
            self._set_status(self.view._cs_status, "Done", GREEN)
        else:
            self._set_status(self.view._cs_status, "Done with errors", RED)
        if s > 0:
            self.view._record_and_refresh("cash_sheet")

    def _stop_tender_autofill(self):
        if hasattr(self.view, '_tb_stop_event'):
            self.view._tb_stop_event.set()
        self.view._tb_run_btn.configure(
            state="disabled", text="Stopping...")

    def _run_tender_autofill(self):
        if not _HAS_TENDER:
            self._append_log(
                self.view._tb_log, "Tender module not available.",
                kind="error")
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
            state="normal", text="Stop Autofill",
            fg_color="#D9534F", hover_color="#C9302C",
            command=self._stop_tender_autofill)
        self._clear_log(self.view._tb_log)
        self._reset_stats("_tb")
        self._set_status(self.view._tb_status, "Processing…", ORANGE)

        def _on_event(kind, msg):
            self._append_log(self.view._tb_log, msg, kind=kind)
            self._bump_stats("_tb", kind)

        def _worker():
            try:
                engine = TenderBreakdownEngine(
                    casheet_dir=casheet_dir, master_path=master_path,
                    on_event=_on_event, stop_event=self.view._tb_stop_event)
                engine.execute()
                self.view.after(
                    0, lambda: self._on_tender_done(engine.tracker))
            except Exception as exc:
                self._append_log(
                    self.view._tb_log,
                    f"Unexpected error: {exc}", kind="error")
                self.view.after(0, lambda: self._on_tender_done(None))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_tender_done(self, tracker):
        self.view._tb_run_btn.configure(
            state="normal", text="Run Tender Breakdown Autofill",
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
            self._set_status(self.view._tb_status, "Done", GREEN)
        else:
            self._set_status(self.view._tb_status, "Done with errors", RED)
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
        """Enable the 'Print options' button + summary when auto-print is on.

        The full printer UI now lives in a popup dialog (see
        AutoFillCenter._open_print_dialog), so toggling no longer grows the
        Run Setup card — the Result Log keeps its full height.
        """
        enabled = self.view._cs_auto_print.get() == 1
        self.view._print_options_btn.configure(
            state="normal" if enabled else "disabled")
        self.view._refresh_print_summary()

    def _refresh_printers(self):
        printers = ExcelPrinter.get_available_printers()
        default = ExcelPrinter.get_default_printer() or "System Default"
        if getattr(self.view, "_printer_dropdown", None) is not None:
            self.view._printer_dropdown.configure(
                values=["System Default"] + printers)
        self.view._printer_var.set(default)
