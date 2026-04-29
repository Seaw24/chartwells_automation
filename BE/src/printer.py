"""
Cross-platform printer support for reports and cash sheets.

Windows uses Excel COM so spreadsheets keep their existing layout.
macOS uses the system CUPS tools (`lpstat`, `lp`) and returns clear errors
when a selected printer or print option is not accepted by the OS.
"""

from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
import tempfile
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
        self._windows_dev_mode_original = None

    def _log(self, msg, kind="info"):
        """
        Forward a printer status line to the tracker (so the UI can color it)
        or to stdout when running headless. ``kind`` mirrors the tracker
        vocabulary: 'info', 'section', 'detail', 'success', 'warning', 'error'.
        """
        if self.tracker:
            # Use the tracker's structured emitters when available so the
            # printer's lines are styled the same way as the autofill lines.
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
        """Return printer names on this machine."""
        system = platform.system()
        if system == "Windows":
            return ExcelPrinter._get_windows_printers()
        if system == "Darwin":
            return ExcelPrinter._get_cups_printers()
        return []

    @staticmethod
    def get_default_printer():
        """Return system default printer name, or None."""
        system = platform.system()
        if system == "Windows":
            try:
                import win32print
                return win32print.GetDefaultPrinter()
            except Exception:
                return None
        if system == "Darwin":
            return ExcelPrinter._get_cups_default_printer()
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

    @staticmethod
    def _run_cups(args):
        try:
            return subprocess.run(
                args, check=False, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError as exc:
            raise PrinterError(
                "macOS printing tools were not found. Install or enable CUPS, "
                "then try printing again."
            ) from exc

    @staticmethod
    def _get_cups_printers():
        try:
            result = ExcelPrinter._run_cups(["lpstat", "-a"])
        except PrinterError:
            return []
        if result.returncode != 0:
            return []
        printers = []
        for line in result.stdout.splitlines():
            if line.strip():
                printers.append(line.split()[0])
        return printers

    @staticmethod
    def _get_cups_default_printer():
        try:
            result = ExcelPrinter._run_cups(["lpstat", "-d"])
        except PrinterError:
            return None
        if result.returncode != 0:
            return None
        marker = "system default destination:"
        text = result.stdout.strip()
        if marker in text:
            return text.split(marker, 1)[1].strip()
        return None

    # === MAIN BATCH PRINT ===

    def print_all(self, reports_dir, casheet_dir, sheet_names):
        """
        Print reports first, then cash sheets.

        Returns True when printing ran to completion, False when it was stopped
        before or during printing. A selected printer is never replaced with a
        different printer automatically.
        """
        try:
            system = platform.system()
            if system == "Windows":
                return self._print_all_windows(reports_dir, casheet_dir, sheet_names)
            if system == "Darwin":
                return self._print_all_macos(reports_dir, casheet_dir, sheet_names)
            raise PrinterError(
                f"Printing is not configured for {system or 'this operating system'}. "
                "Use Windows or macOS, or add an OS-specific printer backend."
            )
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
            excel = win32com.client.Dispatch("Excel.Application")
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

    def _print_all_windows(self, reports_dir, casheet_dir, sheet_names):
        excel = self._open_excel()
        try:
            self._set_windows_printer(excel)
            self._apply_windows_printer_options()
            self._print_reports_windows(excel, reports_dir)
            self._print_cash_sheets_windows(excel, casheet_dir, sheet_names)
            self.check_print_queue()
            self._log("Print complete.", kind="section")
            return True
        finally:
            # Restore any DEVMODE we mutated and shut Excel down even on errors.
            self._restore_windows_printer_options()
            self._close_excel(excel)

    def _set_windows_printer(self, excel):
        if not self.printer_name:
            return

        requested = str(self.printer_name).strip()
        available = self._get_windows_printers()
        if available and requested.lower() not in {p.lower() for p in available}:
            raise PrinterError(
                f"Printer '{requested}' is not installed. "
                f"Available printers: {', '.join(available)}"
            )

        current_active = ""
        try:
            current_active = str(excel.ActivePrinter)
        except Exception:
            pass

        candidates = [requested]
        if " on " in current_active:
            candidates.append(f"{requested} on {current_active.split(' on ', 1)[1].strip()}")

        try:
            import win32print
            handle = win32print.OpenPrinter(requested)
            info = win32print.GetPrinter(handle, 2)
            win32print.ClosePrinter(handle)
            raw_port = str(info.get("pPortName", "")).strip()
            if raw_port:
                candidates.append(f"{requested} on {raw_port if raw_port.endswith(':') else raw_port + ':'}")
        except Exception:
            pass

        # Network printers in Excel COM use virtual ports Ne00:–Ne99:.
        # These are allocated dynamically per Excel session and don't match the
        # real Windows port name, so we have to enumerate them.
        for i in range(100):
            candidates.append(f"{requested} on Ne{i:02d}:")

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

        raise PrinterError(
            f"Excel could not select printer '{requested}': {last_error}. "
            "Open Excel's Print dialog once, confirm the printer appears there, "
            "then retry with the same printer selected."
        )

    def _apply_windows_printer_options(self):
        target_printer = self.printer_name or self.get_default_printer()
        if not target_printer:
            raise PrinterError(
                "No default printer is set on Windows. Select a printer in the app "
                "or set a default printer in Windows Settings."
            )
        if self.settings.color_mode == "color" and not self.settings.duplex:
            return

        try:
            import win32con
            import win32print
        except ImportError as exc:
            raise PrinterError(
                "Color/duplex printer options on Windows require pywin32."
            ) from exc

        try:
            handle = win32print.OpenPrinter(target_printer)
            info = win32print.GetPrinter(handle, 2)
            devmode = info["pDevMode"]
            original = {
                "Color": getattr(devmode, "Color", None),
                "Duplex": getattr(devmode, "Duplex", None),
            }
            if self.settings.color_mode == "bw":
                devmode.Color = win32con.DMCOLOR_MONOCHROME
            if self.settings.duplex:
                devmode.Duplex = win32con.DMDUP_VERTICAL
            info["pDevMode"] = devmode
            self._log(
                f"  Note: Temporarily modifying system defaults for '{target_printer}' "
                f"(color={self.settings.color_mode}, duplex={self.settings.duplex}). "
                f"Original settings will be restored when printing finishes."
            )
            win32print.SetPrinter(handle, 2, info, 0)
            self._windows_dev_mode_original = (handle, info, original, target_printer)
        except Exception as exc:
            try:
                win32print.ClosePrinter(handle)
            except Exception:
                pass
            raise PrinterError(
                f"Could not apply printer options to '{target_printer}': {exc}. "
                "Check printer permissions or change the settings in the printer driver."
            ) from exc

    def _restore_windows_printer_options(self):
        if not self._windows_dev_mode_original:
            return
        handle, info, original, target_printer_name = self._windows_dev_mode_original
        try:
            devmode = info["pDevMode"]
            for key, value in original.items():
                if value is not None:
                    setattr(devmode, key, value)
            info["pDevMode"] = devmode
            import win32print
            win32print.SetPrinter(handle, 2, info, 0)
            self._log(
                f"  Restored original printer defaults for '{target_printer_name}'."
            )
        except Exception as exc:
            self._log(
                f"  WARNING: Could not restore printer defaults for '{target_printer_name}': {exc}. "
                f"You may need to reset color/duplex settings manually in Windows printer properties.",
                kind="warning")
        finally:
            try:
                import win32print
                win32print.ClosePrinter(handle)
            except Exception:
                pass
            self._windows_dev_mode_original = None

    def _print_reports_windows(self, excel, reports_dir):
        try:
            all_files = os.listdir(reports_dir)
        except (FileNotFoundError, PermissionError) as exc:
            raise PrinterError(f"Cannot access reports folder: {exc}") from exc

        infor = [f for f in all_files if f.lower().endswith(".csv") and f.startswith("Operations Report")]
        tavlo = [f for f in all_files if f.lower().endswith(".xls")]
        grubhub = [f for f in all_files if f.lower().endswith(".csv") and f.startswith("TransactionDetailbyVenue")]

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

    def _print_cash_sheets_windows(self, excel, casheet_dir, sheet_names):
        xlsx_files = sorted(glob.glob(os.path.join(casheet_dir, "*.xlsx")))
        xlsx_files = [f for f in xlsx_files if not os.path.basename(f).startswith("~$")]
        if not xlsx_files or not sheet_names:
            return

        self._log(
            f"Printing {len(xlsx_files)} cash sheet(s)", kind="section")

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

    # === macOS / CUPS ===

    def _print_all_macos(self, reports_dir, casheet_dir, sheet_names):
        self._validate_cups_printer()
        files = self._collect_macos_files(reports_dir, casheet_dir)
        if not files:
            self._log("Nothing to print.", kind="detail")
            return True

        self._log(
            f"Sending {len(files)} file(s) to printer", kind="section")
        with tempfile.TemporaryDirectory(prefix="chartwells_print_") as tmp_dir:
            for file_path in files:
                filename = os.path.basename(file_path)
                extension = os.path.splitext(filename)[1].lower()
                if extension in {".xlsx", ".xls", ".csv"}:
                    self._log(f"   Converting: {filename}", kind="detail")
                    pdf_path = self._convert_to_pdf_macos(file_path, tmp_dir)
                    self._lp_print(pdf_path, original_name=filename)
                elif extension == ".pdf":
                    self._lp_print(file_path)
                else:
                    raise PrinterError(
                        f"macOS printing does not support '{extension or 'unknown'}' files: "
                        f"{filename}. Supported file types are PDF, XLSX, XLS, and CSV."
                    )
        self.check_print_queue()
        self._log("Print complete.", kind="section")
        return True

    def _convert_to_pdf_macos(self, file_path, tmp_dir):
        soffice = None
        for candidate in (
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/usr/local/bin/soffice",
            "/opt/homebrew/bin/soffice",
        ):
            if os.path.exists(candidate):
                soffice = candidate
                break
        if not soffice:
            soffice = shutil.which("soffice")
        if not soffice:
            raise PrinterError(
                "LibreOffice is required to print Excel/CSV files on macOS. "
                "Install it from https://www.libreoffice.org/download, then try again."
            )

        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", tmp_dir,
            file_path,
        ]
        try:
            result = subprocess.run(
                cmd, check=False, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=60)
        except subprocess.TimeoutExpired as exc:
            raise PrinterError(
                f"LibreOffice timed out while converting '{os.path.basename(file_path)}' to PDF."
            ) from exc
        except OSError as exc:
            raise PrinterError(
                f"Could not run LibreOffice to convert '{os.path.basename(file_path)}' to PDF: {exc}"
            ) from exc

        if result.returncode != 0:
            stdout = result.stdout.strip() or "(empty)"
            stderr = result.stderr.strip() or "(empty)"
            raise PrinterError(
                f"LibreOffice could not convert '{os.path.basename(file_path)}' to PDF. "
                f"stdout: {stdout}\nstderr: {stderr}"
            )

        pdf_path = os.path.join(
            tmp_dir,
            f"{os.path.splitext(os.path.basename(file_path))[0]}.pdf")
        if not os.path.exists(pdf_path):
            raise PrinterError(
                f"LibreOffice reported success but did not create '{os.path.basename(pdf_path)}'."
            )
        return pdf_path

    def _validate_cups_printer(self):
        available = self._get_cups_printers()
        default = self._get_cups_default_printer()
        if self.printer_name:
            requested = self.printer_name.strip()
            if requested not in available:
                raise PrinterError(
                    f"Printer '{requested}' is not available on macOS. "
                    f"Available printers: {', '.join(available) if available else 'none found'}. "
                    "Open System Settings > Printers & Scanners, add/fix the printer, "
                    "then press the refresh button in this app."
                )
        elif not default:
            raise PrinterError(
                "No default printer is set on macOS. Select a printer in the app "
                "or set one in System Settings > Printers & Scanners."
            )

    def _collect_macos_files(self, reports_dir, casheet_dir):
        try:
            all_reports = os.listdir(reports_dir)
        except (FileNotFoundError, PermissionError) as exc:
            raise PrinterError(f"Cannot access reports folder: {exc}") from exc

        report_files = []
        for name in all_reports:
            lower = name.lower()
            is_report = (
                lower.endswith(".xls")
                or (lower.endswith(".csv") and name.startswith("Operations Report"))
                or (lower.endswith(".csv") and name.startswith("TransactionDetailbyVenue"))
            )
            if is_report:
                report_files.append(os.path.join(reports_dir, name))

        xlsx_files = sorted(glob.glob(os.path.join(casheet_dir, "*.xlsx")))
        xlsx_files = [f for f in xlsx_files if not os.path.basename(f).startswith("~$")]
        return report_files + xlsx_files

    def _lp_options(self):
        options = [
            "-n", str(self.settings.copies),
            "-o", f"media={self.settings.paper_size}",
            "-o", "landscape" if self.settings.orientation == "landscape" else "portrait",
            "-o", "Collate=True" if self.settings.collate else "Collate=False",
            "-o", "sides=two-sided-long-edge" if self.settings.duplex else "sides=one-sided",
        ]
        if self.settings.color_mode == "bw":
            options.extend(["-o", "print-color-mode=monochrome", "-o", "ColorModel=Gray"])
        else:
            options.extend(["-o", "print-color-mode=color"])
        return options

    def _lp_print(self, file_path, original_name=None):
        if not os.path.exists(file_path):
            raise PrinterError(f"File no longer exists: {file_path}")
        display_name = original_name or os.path.basename(file_path)
        cmd = ["lp"]
        if self.printer_name:
            cmd.extend(["-d", self.printer_name])
        cmd.extend(self._lp_options())
        cmd.append(file_path)

        result = self._run_cups(cmd)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise PrinterError(
                f"macOS rejected print job for '{display_name}': {detail}. "
                "Confirm the printer supports this file type and the selected options."
            )
        self._log(f"   ✓ Sent: {display_name}", kind="detail")

    def check_print_queue(self):
        """Emit one short status line about the selected printer's queue."""
        system = platform.system()
        if system == "Windows":
            self._check_queue_windows()
        elif system == "Darwin":
            self._check_queue_macos()

    def _check_queue_windows(self):
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

    def _check_queue_macos(self):
        name = self.printer_name or self._get_cups_default_printer()
        if not name:
            self._log("Could not check queue: no printer selected", kind="detail")
            return
        result = self._run_cups(["lpstat", "-o", name])
        if result.returncode == 0 and result.stdout.strip():
            count = len(result.stdout.splitlines())
            self._log(
                f"Queue: {count} job(s) pending on '{name}'", kind="detail")
        elif result.returncode in (0, 1):
            self._log(f"Queue empty — all jobs sent to '{name}'", kind="detail")
        else:
            detail = (result.stderr or result.stdout).strip()
            self._log(f"Could not check queue: {detail}", kind="detail")
