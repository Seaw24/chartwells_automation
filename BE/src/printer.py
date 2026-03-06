"""
Excel Printer - prints reports and cash sheets via Windows COM automation.
Optimized for batch printing using a single Excel session and delayed printer communication.
"""

import os
import glob


class ExcelPrinter:
    """Handles all printing via Excel COM automation."""

    def __init__(self, printer_name=None, tracker=None):
        self.printer_name = printer_name
        self.tracker = tracker

    def _log(self, msg):
        if self.tracker:
            self.tracker.log(msg)
        else:
            print(msg)

    # === PRINTER DISCOVERY ===

    @staticmethod
    def get_available_printers():
        """Return list of printer names on this machine."""
        try:
            import win32print
            printers = win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS,
                None, 1)
            return [p[2] for p in printers]
        except Exception:
            return []

    @staticmethod
    def get_default_printer():
        """Return system default printer name, or None."""
        try:
            import win32print
            return win32print.GetDefaultPrinter()
        except Exception:
            return None

    # === COM HELPERS ===

    def _open_excel(self):
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            return excel
        except ImportError:
            self._log("  X win32com not installed - cannot print")
            return None
        except Exception as e:
            self._log(f"  X Failed to start Excel: {e}")
            return None

    def _close_excel(self, excel):
        try:
            if excel:
                excel.Quit()
                del excel
        except Exception:
            pass

    def _set_printer(self, excel):
        if not self.printer_name:
            return

        requested = str(self.printer_name).strip()

        def _printer_only(active_printer_value):
            if not active_printer_value:
                return ""
            text = str(active_printer_value)
            if " on " in text:
                return text.split(" on ", 1)[0].strip()
            return text.strip()

        current_active = ""
        try:
            current_active = str(excel.ActivePrinter)
        except Exception:
            current_active = ""

        if _printer_only(current_active).lower() == requested.lower():
            return

        candidates = [requested]

        if " on " in current_active:
            active_suffix = current_active.split(" on ", 1)[1].strip()
            candidates.append(f"{requested} on {active_suffix}")

        try:
            import win32print
            handle = win32print.OpenPrinter(requested)
            info = win32print.GetPrinter(handle, 2)
            win32print.ClosePrinter(handle)
            raw_port = str(info.get("pPortName", "")).strip()
            if raw_port:
                if not raw_port.endswith(":"):
                    raw_port += ":"
                candidates.append(f"{requested} on {raw_port}")
        except Exception:
            pass

        for i in range(100):
            candidates.append(f"{requested} on Ne{i:02d}:")

        seen = set()
        last_error = None
        for candidate in candidates:
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                excel.ActivePrinter = candidate
                return
            except Exception as e:
                last_error = e

        try:
            import win32print
            default_printer = win32print.GetDefaultPrinter()
            if str(default_printer).strip().lower() == requested.lower():
                self._log(
                    f"  Note: Excel could not switch ActivePrinter, but '{requested}' is already the system default.")
                return
        except Exception:
            pass

        self._log(f"  ⚠️ Could not set printer '{requested}': {last_error}")
        self._log("  Using default printer instead.")

    # === MAIN BATCH PRINT ===

    def print_all(self, reports_dir, casheet_dir, sheet_names):
        """
        Print everything in one Excel session: reports first, then cash sheets.
        Much faster than opening/closing Excel per file.
        """
        excel = self._open_excel()
        if not excel:
            return

        self._set_printer(excel)

        # ── 1. Print Reports ──
        try:
            all_files = os.listdir(reports_dir)
        except (FileNotFoundError, PermissionError) as e:
            self._log(f"  X Cannot access reports folder: {e}")
            self._close_excel(excel)
            return

        infor = [f for f in all_files if f.lower().endswith(
            ".csv") and f.startswith("Operations Report")]
        tavlo = [f for f in all_files if f.lower().endswith(".xls")]
        grubhub = [f for f in all_files if f.lower().endswith(
            ".csv") and f.startswith("TransactionDetailbyVenue")]

        total_reports = len(infor) + len(tavlo) + len(grubhub)

        if total_reports > 0:
            self._log(f"\n  {'='*80}")
            self._log(
                f"  Printing {len(infor)} Infor + {len(tavlo)} Tavlo + {len(grubhub)} Grubhub")
            self._log(f"  {'='*80}")

        printed, failed = 0, 0

        for name in infor:
            if self._print_infor(excel, os.path.join(reports_dir, name)):
                printed += 1
            else:
                failed += 1

        for name in tavlo:
            if self._print_tavlo(excel, os.path.join(reports_dir, name)):
                printed += 1
            else:
                failed += 1

        for name in grubhub:
            if self._print_grubhub(excel, os.path.join(reports_dir, name)):
                printed += 1
            else:
                failed += 1

        if total_reports > 0:
            self._log(f"  Reports: {printed} printed, {failed} failed")

        # ── 2. Print Cash Sheets ──
        xlsx_files = sorted(glob.glob(os.path.join(casheet_dir, "*.xlsx")))
        xlsx_files = [
            f for f in xlsx_files if not os.path.basename(f).startswith("~$")]

        if xlsx_files and sheet_names:
            self._log(f"\n  {'='*80}")
            self._log(f"  Printing {len(xlsx_files)} cash sheet(s)")
            self._log(f"  {'='*80}")

            cs_printed, cs_failed = 0, 0
            for xlsx_path in xlsx_files:
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
                            target.PrintOut()
                            count += 1

                    if count > 0:
                        self._log(
                            f"    Printed: {filename:<35} {count} sheet(s)")
                        cs_printed += 1
                    else:
                        self._log(
                            f"    Warning: {filename:<35} no matching sheets")
                        cs_failed += 1
                except Exception as e:
                    self._log(f"    X {filename:<35} {e}")
                    cs_failed += 1
                finally:
                    if wb:
                        try:
                            wb.Close(SaveChanges=False)
                        except Exception:
                            pass

            self._log(
                f"  Cash sheets: {cs_printed} printed, {cs_failed} failed")

        # Check queue and close Excel once at the end
        self.check_print_queue()
        self._close_excel(excel)
        self._log(f"\n  Print complete.")

    # === INTERNAL RECIPES ===

    def _apply_page_setup(self, ws, excel):
        """Internal helper with PrintCommunication optimization."""
        try:
            excel.PrintCommunication = False
        except Exception:
            pass

        ws.PageSetup.Orientation = 2  # xlLandscape
        ws.PageSetup.FitToPagesWide = 1
        ws.PageSetup.FitToPagesTall = False
        ws.PageSetup.LeftMargin = 18
        ws.PageSetup.RightMargin = 18
        ws.PageSetup.TopMargin = 36
        ws.PageSetup.BottomMargin = 36

        try:
            excel.PrintCommunication = True
        except Exception:
            pass

    def _print_infor(self, excel, file_path):
        wb = None
        try:
            wb = excel.Workbooks.Open(os.path.abspath(file_path))
            ws = wb.ActiveSheet
            ws.Columns("A").ColumnWidth = 35
            ws.Columns("B").AutoFit()
            self._apply_page_setup(ws, excel)
            ws.PrintOut()
            self._log(f"    Printed Infor: {os.path.basename(file_path)}")
            return True
        except Exception as e:
            self._log(f"    X Infor: {e}")
            return False
        finally:
            if wb:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass

    def _print_tavlo(self, excel, file_path):
        wb = None
        try:
            wb = excel.Workbooks.Open(os.path.abspath(file_path))
            target = None
            for ws in wb.Worksheets:
                if ws.Name.lower() == "financials":
                    target = ws
                    break
            if target is None:
                self._log(
                    f"    Warning: No Financials in {os.path.basename(file_path)}")
                return False

            target.Select()
            target.Columns("A").ColumnWidth = 35
            target.Columns("B").AutoFit()
            self._apply_page_setup(target, excel)
            target.PrintOut()
            self._log(f"    Printed Tavlo: {os.path.basename(file_path)}")
            return True
        except Exception as e:
            self._log(f"    X Tavlo: {e}")
            return False
        finally:
            if wb:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass

    def _print_grubhub(self, excel, file_path):
        wb = None
        try:
            wb = excel.Workbooks.Open(os.path.abspath(file_path))
            ws = wb.ActiveSheet
            self._apply_page_setup(ws, excel)
            ws.PrintOut()
            self._log(f"    Printed Grubhub: {os.path.basename(file_path)}")
            return True
        except Exception as e:
            self._log(f"    X Grubhub: {e}")
            return False
        finally:
            if wb:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass

    def check_print_queue(self):
        """Show how many jobs are in the queue for the selected printer."""
        try:
            import win32print
            name = self.printer_name or win32print.GetDefaultPrinter()
            handle = win32print.OpenPrinter(name)
            jobs = win32print.EnumJobs(handle, 0, 100, 1)
            win32print.ClosePrinter(handle)
            pending = len(jobs)
            if pending > 0:
                self._log(
                    f"  📋 Print queue: {pending} job(s) pending for '{name}'")
            else:
                self._log(f"  ✅ Print queue empty — all jobs sent to '{name}'")
        except Exception as e:
            self._log(f"  ⚠️ Could not check queue: {e}")
