"""
Windows-only printer support for reports and cash sheets.

Uses Excel COM (via pywin32) so spreadsheets keep their existing layout when
they hit the page. ``print_all`` is the only entry point the engine calls;
everything else is private machinery to keep that one method readable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class PrinterError(RuntimeError):
    """Raised when printing cannot continue safely."""


@dataclass
class PrintSettings:
    printer_name: str | None = None
    color_mode: str = "color"
    paper_size: str = "Letter"
    duplex: bool = False
    copies: int = 1
    # Retained for UI compatibility; Windows report layout is hardcoded portrait.
    orientation: str = "landscape"
    collate: bool = True

    @classmethod
    def from_dict(cls, values: dict | None) -> "PrintSettings":
        if not values:
            return cls()
        return cls(
            printer_name=values.get("printer_name") or None,
            color_mode=values.get("color_mode", "color"),
            paper_size=values.get("paper_size", "Letter"),
            duplex=bool(values.get("duplex", False)),
            copies=max(1, int(values.get("copies", 1) or 1)),
            orientation=values.get("orientation", "landscape"),
            collate=bool(values.get("collate", True)),
        )


class ExcelPrinter:
    """Handles report and cash-sheet printing with explicit printer errors."""

    _PAPER_SIZES = {
        "Letter": 1,
        "Legal": 5,
        "A4": 9,
        "A3": 8,
        "Tabloid": 3,
    }

    def __init__(self, printer_name=None, tracker=None, settings=None):
        self.settings = PrintSettings.from_dict(settings)
        if printer_name and not self.settings.printer_name:
            self.settings.printer_name = printer_name
        self.printer_name = self.settings.printer_name
        self.tracker = tracker
        self._windows_default_printer_original = None

    def _log(self, msg, kind="info"):
        """
        Forward a printer status line to the tracker (so the UI can color it)
        or to stdout when running headless. ``kind`` mirrors the tracker
        vocabulary: 'info', 'section', 'detail', 'success', 'warning', 'error'.
        """
        if self.tracker:
            emit = {
                "section": getattr(self.tracker, "section", None),
                "detail":  getattr(self.tracker, "detail", None),
                "warning": getattr(self.tracker, "warning", None),
            }.get(kind)
            if emit:
                emit(msg)
            else:
                self.tracker.log(msg)
        else:
            print(msg)

    # === PRINTER DISCOVERY ===

    @staticmethod
    def get_available_printers():
        """Return printer names installed on this Windows machine."""
        return ExcelPrinter._get_windows_printers()

    @staticmethod
    def get_default_printer():
        """Return the Windows default printer name, or None if none is set."""
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except Exception:
            return None

    @staticmethod
    def _get_windows_printers():
        try:
            import win32print
            printers = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS,
                None, 1)
            return [p[2] for p in printers]
        except Exception:
            return []

    # === MAIN BATCH PRINT ===

    def print_all(self, reports_dir, casheet_dir,
                  sheet_names_by_file, printable_reports=None):
        """
        Print reports first, then cash sheets.

        Args:
            reports_dir:         Folder of source reports (Infor / Tavlo / Grubhub).
            casheet_dir:         Folder of cash-sheet workbooks.
            sheet_names_by_file: ``{casheet_path: {weekday, ...}}`` — only the
                                 listed workbooks are printed, and only the
                                 listed weekday tabs within each.
            printable_reports:   Set of report filenames (basenames) that had
                                 non-zero data and should be printed. Reports
                                 whose names aren't in this set are skipped.
                                 Pass ``None`` to print every report file in
                                 the folder (legacy behavior).

        Returns True when printing ran to completion, False when it was stopped
        before or during printing. A selected printer is never replaced with a
        different printer automatically.
        """
        try:
            return self._print_all_windows(
                reports_dir, casheet_dir,
                sheet_names_by_file, printable_reports)
        except PrinterError as exc:
            # We deliberately do NOT silently fall back to another printer
            # — surface a clear, actionable message to the user instead.
            self._log("PRINTING STOPPED", kind="section")
            self._log(f"Reason: {exc}", kind="detail")
            self._log(
                "Fix the printer or settings and run again.", kind="detail")
            return False

    # === WINDOWS / EXCEL COM ===

    def _open_excel(self):
        try:
            import win32com.client
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            return excel
        except ImportError as exc:
            raise PrinterError(
                "Windows Excel printing requires pywin32. "
                "Run 'pip install -r requirements.txt', then try again."
            ) from exc
        except Exception as exc:
            raise PrinterError(
                f"Could not start Microsoft Excel: {exc}. "
                "Close stuck Excel windows and confirm Excel opens normally."
            ) from exc

    def _close_excel(self, excel):
        try:
            if excel:
                excel.Quit()
                del excel
        except Exception:
            pass

    def _print_all_windows(self, reports_dir, casheet_dir,
                           sheet_names_by_file, printable_reports):
        excel = None
        try:
            self._set_windows_default_printer_for_excel()
            excel = self._open_excel()
            self._set_windows_printer(excel)
            self._print_reports_windows(excel, reports_dir, printable_reports)
            self._print_cash_sheets_windows(
                excel, casheet_dir, sheet_names_by_file)
            self.check_print_queue()
            self._log("Print complete.", kind="section")
            return True
        finally:
            self._close_excel(excel)
            self._restore_windows_default_printer()

    def _get_installed_windows_printer_name(self, requested):
        available = self._get_windows_printers()
        if available and requested.lower() not in {p.lower() for p in available}:
            raise PrinterError(
                f"Printer '{requested}' is not installed. "
                f"Available printers: {', '.join(available)}"
            )
        return next(
            (p for p in available if p.lower() == requested.lower()),
            requested)

    def _set_windows_default_printer_for_excel(self):
        if not self.printer_name:
            return

        requested = str(self.printer_name).strip()
        installed_name = self._get_installed_windows_printer_name(requested)
        try:
            import win32print
            original = win32print.GetDefaultPrinter()
            if original.strip().lower() == installed_name.lower():
                return
            self._log(
                f"  Note: Temporarily setting Windows default printer to '{installed_name}' "
                "so Excel can print to the selected printer. Original default "
                "will be restored when printing finishes.",
                kind="detail")
            win32print.SetDefaultPrinter(installed_name)
            self._windows_default_printer_original = original
        except Exception as exc:
            self._log(
                f"  WARNING: Could not temporarily set Windows default printer "
                f"to '{installed_name}': {exc}. Trying Excel printer selection directly.",
                kind="warning")

    def _restore_windows_default_printer(self):
        if not self._windows_default_printer_original:
            return
        original = self._windows_default_printer_original
        try:
            import win32print
            win32print.SetDefaultPrinter(original)
            self._log(
                f"  Restored Windows default printer to '{original}'.",
                kind="detail")
        except Exception as exc:
            self._log(
                f"  WARNING: Could not restore Windows default printer to '{original}': {exc}. "
                "You may need to reset your default printer manually in Windows Settings.",
                kind="warning")
        finally:
            self._windows_default_printer_original = None

    def _set_windows_printer(self, excel):
        if not self.printer_name:
            return

        requested = str(self.printer_name).strip()
        installed_name = self._get_installed_windows_printer_name(requested)

        current_active = ""
        try:
            current_active = str(excel.ActivePrinter)
        except Exception:
            pass
        active_name = current_active.split(" on ", 1)[0].strip()
        if active_name.lower() == installed_name.lower():
            self._log(f"Printer selected: {installed_name}", kind="detail")
            return

        candidates = [requested]
        if installed_name != requested:
            candidates.append(installed_name)
        if " on " in current_active:
            current_port = current_active.split(" on ", 1)[1].strip()
            candidates.append(f"{installed_name} on {current_port}")

        try:
            import winreg
            for registry_path in (
                r"Software\Microsoft\Windows NT\CurrentVersion\Devices",
                r"Software\Microsoft\Windows NT\CurrentVersion\PrinterPorts",
            ):
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
                    for index in range(winreg.QueryInfoKey(key)[1]):
                        name, value, _ = winreg.EnumValue(key, index)
                        if name.lower() != installed_name.lower():
                            continue
                        parts = [part.strip() for part in str(value).split(",")]
                        if len(parts) > 1 and parts[1]:
                            port = parts[1]
                            candidates.append(
                                f"{name} on {port if port.endswith(':') else port + ':'}")
        except Exception:
            pass

        try:
            import win32print
            handle = win32print.OpenPrinter(installed_name)
            info = win32print.GetPrinter(handle, 2)
            win32print.ClosePrinter(handle)
            raw_port = str(info.get("pPortName", "")).strip()
            if raw_port:
                candidates.append(
                    f"{installed_name} on {raw_port if raw_port.endswith(':') else raw_port + ':'}")
        except Exception:
            pass

        # Network printers in Excel COM use virtual ports Ne00:–Ne99:.
        # These are allocated dynamically per Excel session and don't match the
        # real Windows port name, so we have to enumerate them.
        for i in range(100):
            candidates.append(f"{installed_name} on Ne{i:02d}:")

        # Try each candidate name (Excel sometimes wants "Name on Port:").
        # Stop at the first one Excel accepts.
        last_error = None
        for candidate in dict.fromkeys(candidates):
            try:
                excel.ActivePrinter = candidate
                self._log(f"Printer selected: {requested}", kind="detail")
                return
            except Exception as exc:
                last_error = exc

        try:
            import win32print
            default_printer = win32print.GetDefaultPrinter()
            if default_printer.strip().lower() == installed_name.lower():
                self._log(
                    f"Printer selected: {installed_name} (Windows default)",
                    kind="detail")
                return
        except Exception:
            pass

        raise PrinterError(
            f"Excel could not select printer '{requested}': {last_error}. "
            "Open Excel's Print dialog once, confirm the printer appears there, "
            "then retry with the same printer selected."
        )

    def _print_reports_windows(self, excel, reports_dir, printable_reports):
        try:
            all_files = os.listdir(reports_dir)
        except (FileNotFoundError, PermissionError) as exc:
            raise PrinterError(f"Cannot access reports folder: {exc}") from exc

        # Filter to recognized report files first.
        infor = [f for f in all_files
                 if f.lower().endswith(".csv") and f.startswith("Operations Report")]
        tavlo = [f for f in all_files if f.lower().endswith(".xls")]
        grubhub = [f for f in all_files
                   if f.lower().endswith(".csv") and f.startswith("TransactionDetailbyVenue")]

        # Then narrow to "had non-zero data" reports if the engine gave us a
        # filter set. ``None`` keeps the legacy behavior of printing every file
        # — useful if this method is ever called outside the autofill engine.
        if printable_reports is not None:
            infor = [f for f in infor if f in printable_reports]
            tavlo = [f for f in tavlo if f in printable_reports]
            grubhub = [f for f in grubhub if f in printable_reports]

        total_reports = len(infor) + len(tavlo) + len(grubhub)
        if total_reports == 0:
            return

        self._log(
            f"Printing reports — {len(infor)} Infor · "
            f"{len(tavlo)} Tavlo · {len(grubhub)} Grubhub",
            kind="section")

        printed, failed = 0, 0
        for name in infor:
            printed, failed = self._count_print(
                self._print_infor(excel, os.path.join(reports_dir, name)),
                printed, failed)
        for name in tavlo:
            printed, failed = self._count_print(
                self._print_tavlo(excel, os.path.join(reports_dir, name)),
                printed, failed)
        for name in grubhub:
            printed, failed = self._count_print(
                self._print_grubhub(excel, os.path.join(reports_dir, name)),
                printed, failed)

        self._log(
            f"Reports: {printed} printed, {failed} failed", kind="detail")

    def _print_cash_sheets_windows(self, excel, casheet_dir, sheet_names_by_file):
        if not sheet_names_by_file:
            return

        # Only consider workbooks that actually had at least one day filled.
        # Defensively skip Excel lock files (~$...) and sort for stable logs.
        targets = sorted(
            (path, days) for path, days in sheet_names_by_file.items()
            if days and not os.path.basename(path).startswith("~$")
        )
        if not targets:
            return

        self._log(
            f"Printing {len(targets)} cash sheet(s)", kind="section")

        cs_printed, cs_failed = 0, 0
        for xlsx_path, sheet_names in targets:
            filename = os.path.basename(xlsx_path)
            wb = None
            try:
                wb = excel.Workbooks.Open(os.path.abspath(xlsx_path))
                ws_map = {ws.Name.lower(): ws for ws in wb.Worksheets}
                count = 0
                for name in sheet_names:
                    target = ws_map.get(name.lower())
                    if target:
                        target.Select()
                        self._print_sheet(target)
                        count += 1
                if count > 0:
                    self._log(
                        f"   ✓ {filename}  ({count} sheet(s))",
                        kind="detail")
                    cs_printed += 1
                else:
                    self._log(
                        f"{filename}: no matching sheets",
                        kind="warning")
                    cs_failed += 1
            except Exception as exc:
                self._log(f"   ✗ {filename}: {exc}", kind="detail")
                cs_failed += 1
            finally:
                if wb:
                    try:
                        wb.Close(SaveChanges=False)
                    except Exception:
                        pass

        self._log(
            f"Cash sheets: {cs_printed} printed, {cs_failed} failed",
            kind="detail")

    @staticmethod
    def _count_print(success, printed, failed):
        return (printed + 1, failed) if success else (printed, failed + 1)

    def _apply_page_setup(self, ws, excel):
        """Apply page settings used by Excel before printing."""
        try:
            excel.PrintCommunication = False
        except Exception:
            pass

        ws.PageSetup.Orientation = 1  # xlPortrait — reports always vertical
        ws.PageSetup.Zoom = 100  # no scaling — preserve column widths even if multi-page
        ws.PageSetup.LeftMargin = 18
        ws.PageSetup.RightMargin = 18
        ws.PageSetup.TopMargin = 36
        ws.PageSetup.BottomMargin = 36
        ws.PageSetup.BlackAndWhite = self.settings.color_mode == "bw"
        paper_size = self._PAPER_SIZES.get(self.settings.paper_size)
        if paper_size:
            ws.PageSetup.PaperSize = paper_size

        try:
            excel.PrintCommunication = True
        except Exception:
            pass

    def _print_sheet(self, ws):
        ws.PrintOut(Copies=self.settings.copies, Collate=self.settings.collate)

    def _print_infor(self, excel, file_path):
        return self._print_workbook(
            excel, file_path, kind="Infor",
            sheet_picker=lambda wb: wb.ActiveSheet,
            adjust=lambda ws: ws.UsedRange.Columns.AutoFit(),
        )

    def _print_tavlo(self, excel, file_path):
        # Tavlo workbooks have many sheets; we want the "Financials" one.
        def _pick_financials(wb):
            for ws in wb.Worksheets:
                if ws.Name.lower() == "financials":
                    return ws
            return None

        def _adjust(ws):
            ws.Select()
            ws.UsedRange.Columns.AutoFit()

        return self._print_workbook(
            excel, file_path, kind="Tavlo",
            sheet_picker=_pick_financials,
            adjust=_adjust,
            missing_sheet_msg="No Financials sheet",
        )

    def _print_grubhub(self, excel, file_path):
        return self._print_workbook(
            excel, file_path, kind="Grubhub",
            sheet_picker=lambda wb: wb.ActiveSheet,
            adjust=lambda ws: ws.UsedRange.Columns.AutoFit(),
        )

    def _print_workbook(self, excel, file_path, kind, sheet_picker,
                        adjust=None, missing_sheet_msg="Sheet not found"):
        """
        Open one workbook, run an optional pre-print adjust step, and print.

        Returns True/False so the caller can tally printed/failed counts.
        Pulled out of the per-source variants to avoid the same try/finally
        boilerplate three times over.
        """
        filename = os.path.basename(file_path)
        wb = None
        try:
            wb = excel.Workbooks.Open(os.path.abspath(file_path))
            ws = sheet_picker(wb)
            if ws is None:
                self._log(
                    f"{kind} — {filename}: {missing_sheet_msg}",
                    kind="warning")
                return False
            if adjust:
                adjust(ws)
            self._apply_page_setup(ws, excel)
            self._print_sheet(ws)
            self._log(f"   ✓ {kind}: {filename}", kind="detail")
            return True
        except Exception as exc:
            self._log(f"   ✗ {kind}: {filename} — {exc}", kind="detail")
            return False
        finally:
            if wb:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass

    def check_print_queue(self):
        """Emit one short status line about the selected printer's queue."""
        try:
            import win32print
            name = self.printer_name or win32print.GetDefaultPrinter()
            handle = win32print.OpenPrinter(name)
            jobs = win32print.EnumJobs(handle, 0, 100, 1)
            win32print.ClosePrinter(handle)
        except Exception as exc:
            self._log(f"Could not check queue: {exc}", kind="detail")
            return
        pending = len(jobs)
        if pending > 0:
            self._log(
                f"Queue: {pending} job(s) pending on '{name}'", kind="detail")
        else:
            self._log(f"Queue empty — all jobs sent to '{name}'", kind="detail")