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
    orientation: str = "landscape"
    collate: bool = True

    @classmethod
    def from_dict(cls, values: dict | None) -> "PrintSettings":
        if not values:
            return cls()
        color_mode = str(values.get("color_mode", "color")).lower()
        if color_mode in {"black and white", "black & white", "b&w"}:
            color_mode = "bw"
        orientation = str(values.get("orientation", "landscape")).lower()
        return cls(
            printer_name=values.get("printer_name") or None,
            color_mode=color_mode if color_mode in {"color", "bw"} else "color",
            paper_size=values.get("paper_size", "Letter"),
            duplex=bool(values.get("duplex", False)),
            copies=max(1, int(values.get("copies", 1) or 1)),
            orientation=(
                orientation
                if orientation in {"portrait", "landscape"}
                else "landscape"
            ),
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
    _ORIENTATIONS = {
        "portrait": 1,
        "landscape": 2,
    }

    def __init__(self, printer_name=None, tracker=None, settings=None):
        self.settings = PrintSettings.from_dict(settings)
        if printer_name and not self.settings.printer_name:
            self.settings.printer_name = printer_name
        self.printer_name = self.settings.printer_name
        self.tracker = tracker
        self._windows_default_printer_original = None
        self._printer_driver_original = None
        self._excel_active_printer = None
        self._duplex_batch_excel = None
        self._duplex_batch_workbook = None
        self._duplex_batch_staged_sheet_count = 0

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
            reports_dir:         Folder of source reports. Only Infor and
                                 Tavlo files are printed; Grubhub CSVs are
                                 skipped (autofill-only).
            casheet_dir:         Folder of cash-sheet workbooks.
            sheet_names_by_file: ``{casheet_path: {sheet name, ...}}`` — only
                                 the listed workbooks are printed, and only the
                                 listed tabs within each (weekday tabs, plus
                                 "Totals" when the Totals print option is on).
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
            self._apply_windows_driver_print_settings()
            excel = self._open_excel()
            self._set_windows_printer(excel)
            if self.settings.duplex:
                self._start_duplex_batch(excel)
            self._print_reports_windows(excel, reports_dir, printable_reports)
            self._print_cash_sheets_windows(
                excel, casheet_dir, sheet_names_by_file)
            if self.settings.duplex:
                self._finish_duplex_batch()
            self.check_print_queue()
            self._log("Print complete.", kind="section")
            return True
        finally:
            self._close_duplex_batch()
            self._close_excel(excel)
            self._restore_windows_driver_print_settings()
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

    def _get_effective_windows_printer_name(self):
        if self.printer_name:
            return self._get_installed_windows_printer_name(
                str(self.printer_name).strip())
        import win32print
        return win32print.GetDefaultPrinter()

    @staticmethod
    def _open_windows_printer(win32print, name):
        try:
            return win32print.OpenPrinter(
                name, {"DesiredAccess": win32print.PRINTER_ACCESS_USE})
        except TypeError:
            return win32print.OpenPrinter(name)

    @staticmethod
    def _get_devmode_attr(devmode, attr):
        for name in (attr, f"dm{attr}"):
            if hasattr(devmode, name):
                return getattr(devmode, name)
        return None

    @staticmethod
    def _set_devmode_attr(devmode, attr, value):
        for name in (attr, f"dm{attr}"):
            if hasattr(devmode, name):
                setattr(devmode, name, value)
                return True
        return False

    def _snapshot_devmode(self, devmode):
        return {
            "Fields": self._get_devmode_attr(devmode, "Fields"),
            "Duplex": self._get_devmode_attr(devmode, "Duplex"),
            "Color": self._get_devmode_attr(devmode, "Color"),
        }

    def _set_devmode_setting(self, devmode, attr, value, field_flag):
        fields = self._get_devmode_attr(devmode, "Fields")
        if fields is not None:
            self._set_devmode_attr(devmode, "Fields", fields | field_flag)
        return self._set_devmode_attr(devmode, attr, value)

    @staticmethod
    def _read_stored_devmode(win32print, handle):
        """Return the per-user DEVMODE, or the printer default as a seed."""
        try:
            devmode = win32print.GetPrinter(handle, 9).get("pDevMode")
        except Exception:
            devmode = None
        if devmode is None:
            devmode = win32print.GetPrinter(handle, 2).get("pDevMode")
        return devmode

    @staticmethod
    def _read_driver_devmode(win32print, handle, name):
        """
        Allocate and initialize the printer driver's *full* DEVMODE.

        A driver's DEVMODE can be larger than the public Windows structure
        because it may append private options.  Allocating only the public
        portion makes some drivers discard duplex even though ``Duplex`` reads
        back correctly in Python.  DocumentProperties is the Windows API that
        reports the required size and fills those private bytes.
        """
        seed = ExcelPrinter._read_stored_devmode(win32print, handle)
        try:
            import pywintypes
            import win32con
            size = win32print.DocumentProperties(
                0, handle, name, None, None, 0)
            public_size = pywintypes.DEVMODEType().Size
            if size < public_size:
                raise PrinterError(
                    "Printer driver returned an invalid settings size "
                    f"({size}).")

            devmode = pywintypes.DEVMODEType(size - public_size)
            out_flag = getattr(win32con, "DM_OUT_BUFFER", 2)
            if seed is None:
                result = win32print.DocumentProperties(
                    0, handle, name, devmode, None, out_flag)
            else:
                flags = getattr(win32con, "DM_IN_BUFFER", 8) | out_flag
                result = win32print.DocumentProperties(
                    0, handle, name, devmode, seed, flags)
            if result < 0:
                raise PrinterError(
                    f"Printer driver could not initialize its settings ({result}).")
            return devmode
        except ImportError:
            if seed is not None:
                return seed
            raise

    @staticmethod
    def _validate_devmode(win32print, handle, name, devmode):
        """Let the driver merge and validate changed DEVMODE fields."""
        import win32con
        flags = (getattr(win32con, "DM_IN_BUFFER", 8)
                 | getattr(win32con, "DM_OUT_BUFFER", 2))
        result = win32print.DocumentProperties(
            0, handle, name, devmode, devmode, flags)
        if result < 0:
            raise PrinterError(
                f"Printer driver rejected the requested options ({result}).")

    @staticmethod
    def _printer_supports_duplex(name):
        """
        Ask the driver whether it can print double-sided at all (DC_DUPLEX).

        An unknown answer is deferred to the write/read-back verification so a
        quirky driver is not rejected before it gets a chance to accept duplex.
        """
        try:
            import win32con
            import win32print
            result = win32print.DeviceCapabilities(
                name, None, getattr(win32con, "DC_DUPLEX", 7))
            if result < 0:
                return None
            return bool(result)
        except Exception:
            return None

    def _read_back_devmode(self, win32print, name):
        """Re-open the printer and return the settings the driver kept."""
        handle = None
        try:
            handle = self._open_windows_printer(win32print, name)
            devmode = self._read_stored_devmode(win32print, handle)
            return {} if devmode is None else self._snapshot_devmode(devmode)
        except Exception:
            return {}
        finally:
            if handle is not None:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass

    @staticmethod
    def _write_driver_devmode(win32print, handle, name, devmode):
        """
        Persist ``devmode`` as the printing defaults Excel will pick up.

        Per-user defaults (SetPrinter level 9) come first: they live in the
        user's registry and need only normal printer access, so standard
        Windows accounts can enable duplex without elevation. Only if that
        fails do we touch the printer's global defaults (level 2), which
        require manage-printer permission.
        """
        try:
            win32print.SetPrinter(handle, 9, {"pDevMode": devmode}, 0)
            return
        except Exception:
            pass

        admin_handle = win32print.OpenPrinter(
            name, {"DesiredAccess": win32print.PRINTER_ALL_ACCESS})
        try:
            info = win32print.GetPrinter(admin_handle, 2)
            info["pDevMode"] = devmode
            # SetPrinter rejects a non-NULL security descriptor unless the
            # caller can also rewrite the printer's ACL, so never send it back.
            info["pSecurityDescriptor"] = None
            win32print.SetPrinter(admin_handle, 2, info, 0)
        finally:
            win32print.ClosePrinter(admin_handle)

    def _apply_windows_driver_print_settings(self):
        """
        Apply printer-driver settings Excel does not expose directly.

        Excel PageSetup handles paper/orientation/black-and-white at the sheet
        level and PrintOut handles copies/collate. Duplex is a Windows printer
        driver setting, so we temporarily set it as the current user's
        printing defaults (no admin rights needed) and restore the previous
        values after the batch.
        """
        handle = None
        try:
            import win32con
            import win32print

            name = self._get_effective_windows_printer_name()
            handle = self._open_windows_printer(win32print, name)
            devmode = self._read_driver_devmode(win32print, handle, name)
            if devmode is None:
                message = f"Printer '{name}' has no editable driver settings."
                if self.settings.duplex:
                    raise PrinterError(message)
                self._log(message, kind="warning")
                return

            original = self._snapshot_devmode(devmode)
            changed = []

            duplex_value = (
                getattr(win32con, "DMDUP_VERTICAL", 2)
                if self.settings.duplex
                else getattr(win32con, "DMDUP_SIMPLEX", 1)
            )
            supports_duplex = self._printer_supports_duplex(name)
            if self.settings.duplex and supports_duplex is False:
                raise PrinterError(
                    f"Printer '{name}' reports that automatic double-sided "
                    "printing is not supported.")
            duplex_changed = self._set_devmode_setting(
                    devmode, "Duplex", duplex_value,
                    getattr(win32con, "DM_DUPLEX", 0x1000))
            if duplex_changed:
                changed.append(
                    "double-sided" if self.settings.duplex else "single-sided")
            elif self.settings.duplex:
                raise PrinterError(
                    f"Printer driver for '{name}' does not expose a duplex "
                    "setting.")

            color_value = (
                getattr(win32con, "DMCOLOR_MONOCHROME", 1)
                if self.settings.color_mode == "bw"
                else getattr(win32con, "DMCOLOR_COLOR", 2)
            )
            if self._set_devmode_setting(
                    devmode, "Color", color_value,
                    getattr(win32con, "DM_COLOR", 0x800)):
                changed.append(
                    "black and white"
                    if self.settings.color_mode == "bw" else "color")

            if not changed:
                return

            self._validate_devmode(win32print, handle, name, devmode)
            self._write_driver_devmode(win32print, handle, name, devmode)
            self._printer_driver_original = (name, original)

            # Report what the driver actually kept, not what we asked for: a
            # printer that silently drops the duplex bit used to be logged as
            # "applied" while every page still came out single-sided.
            stored = self._read_back_devmode(win32print, name)
            stored_duplex = stored.get("Duplex")
            if self.settings.duplex and stored_duplex != duplex_value:
                raise PrinterError(
                    f"Printer '{name}' did not retain the double-sided "
                    "setting. No pages were printed. Open Windows Settings > "
                    "Printers > Printing preferences, confirm automatic "
                    "duplex is installed for this printer, and try again.")
            if (not self.settings.duplex
                    and stored_duplex is not None
                    and stored_duplex != duplex_value):
                wanted = ("double-sided" if self.settings.duplex
                          else "single-sided")
                changed = [c for c in changed if c != wanted]
                self._log(
                    f"WARNING: Printer '{name}' did not accept the "
                    f"{wanted} setting and kept its own default. Set it in "
                    "Windows Settings > Printers > Printing preferences for "
                    "this printer, then run again.",
                    kind="warning")

            if changed:
                self._log(
                    f"Printer options applied: {', '.join(changed)}",
                    kind="detail")
        except PrinterError:
            raise
        except Exception as exc:
            if self.settings.duplex:
                raise PrinterError(
                    f"Could not guarantee double-sided printing on the "
                    f"selected printer: {exc}") from exc
            self._log(
                f"WARNING: Could not apply printer driver options: {exc}. "
                "Color selection may not take effect; Excel page settings "
                "will still be applied.",
                kind="warning")
        finally:
            if handle is not None:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass

    def _restore_windows_driver_print_settings(self):
        if not self._printer_driver_original:
            return

        name, snapshot = self._printer_driver_original
        handle = None
        try:
            import win32print

            handle = self._open_windows_printer(win32print, name)
            devmode = self._read_driver_devmode(win32print, handle, name)
            if devmode is None:
                return

            for attr in ("Duplex", "Color"):
                value = snapshot.get(attr)
                if value is not None:
                    self._set_devmode_attr(devmode, attr, value)
            fields = snapshot.get("Fields")
            if fields is not None:
                self._set_devmode_attr(devmode, "Fields", fields)

            self._validate_devmode(win32print, handle, name, devmode)
            self._write_driver_devmode(win32print, handle, name, devmode)
            self._log("Restored printer driver options.", kind="detail")
        except Exception as exc:
            self._log(
                f"WARNING: Could not restore printer driver options for "
                f"'{name}': {exc}. Check Windows printer settings manually.",
                kind="warning")
        finally:
            if handle is not None:
                try:
                    win32print.ClosePrinter(handle)
                except Exception:
                    pass
            self._printer_driver_original = None

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
            self._excel_active_printer = current_active or installed_name
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
                self._excel_active_printer = candidate
                self._log(f"Printer selected: {requested}", kind="detail")
                return
            except Exception as exc:
                last_error = exc

        try:
            import win32print
            default_printer = win32print.GetDefaultPrinter()
            if default_printer.strip().lower() == installed_name.lower():
                try:
                    self._excel_active_printer = str(excel.ActivePrinter)
                except Exception:
                    self._excel_active_printer = installed_name
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

        # Filter to recognized report files first. Grubhub CSVs (both the
        # TransactionDetailbyVenue export and the Sales-at-a-Glance counts
        # file) are deliberately NOT printed — they are parsed for autofill
        # only, so only Infor and Tavlo reports go to the printer.
        infor = [f for f in all_files
                 if f.lower().endswith(".csv") and f.startswith("Operations Report")]
        tavlo = [f for f in all_files if f.lower().endswith(".xls")]

        # Then narrow to "had non-zero data" reports if the engine gave us a
        # filter set. ``None`` keeps the legacy behavior of printing every file
        # — useful if this method is ever called outside the autofill engine.
        if printable_reports is not None:
            infor = [f for f in infor if f in printable_reports]
            tavlo = [f for f in tavlo if f in printable_reports]

        total_reports = len(infor) + len(tavlo)
        if total_reports == 0:
            return

        self._log(
            f"Printing reports — {len(infor)} Infor · "
            f"{len(tavlo)} Tavlo (Grubhub reports are not printed)",
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
                # The Totals sheet sums the weekday tabs by formula, so make
                # sure Excel recalculates against the freshly saved figures
                # before it hits the page.
                if any(n.lower() == "totals" for n in sheet_names):
                    try:
                        excel.CalculateFull()
                    except Exception:
                        pass
                # Weekday tabs first, Totals last, in a stable order.
                ordered = sorted(
                    sheet_names, key=lambda n: (n.lower() == "totals", n))
                targets = [ws_map[n.lower()] for n in ordered
                           if n.lower() in ws_map]
                for target in targets:
                    self._fit_hidden_numbers(target)
                    self._expand_print_area(target)
                count = len(targets)
                if count > 0:
                    self._print_sheets(wb, targets, fit_one_page=True)
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

    # === ###### (VALUE TOO WIDE FOR ITS COLUMN) ===

    @staticmethod
    def _hidden_rows(ws, col, rows):
        """Return the rows of ``col`` Excel is still rendering as ######."""
        hidden = []
        for row in rows:
            try:
                text = str(ws.Cells(row, col).Text).strip()
            except Exception:
                continue
            if text and set(text) == {"#"}:
                hidden.append(row)
        return hidden

    def _widen_column(self, ws, col, rows):
        """Grow one column until the values in ``rows`` are readable."""
        column = ws.Columns(col)
        original = column.ColumnWidth
        try:
            if column.Hidden or original <= 0:
                return      # a column hidden on purpose stays hidden
        except Exception:
            pass

        # AutoFit on a partial range sizes the column to just those cells, so
        # a long label further down the column can't blow the layout apart.
        ws.Range(ws.Cells(min(rows), col),
                 ws.Cells(max(rows), col)).Columns.AutoFit()
        if column.ColumnWidth < original:
            # Never make a template column narrower than it was saved.
            column.ColumnWidth = original

        # AutoFit ignores merged cells and some fonts still round short, so
        # nudge the width up until nothing is masked (bounded at ~18 chars).
        for _ in range(12):
            if not self._hidden_rows(ws, col, rows):
                return
            column.ColumnWidth = column.ColumnWidth + 1.5

    def _fit_hidden_numbers(self, ws):
        """
        Widen any column Excel is rendering as ###### so the value prints.

        Excel masks a number or date that is wider than its column — a total
        crossing 1,000 in a column sized for three digits becomes ######, and
        that is exactly what lands on the page. Cash sheets keep their saved
        column widths on purpose, so rather than auto-fitting the whole sheet
        we touch only the columns that are actually hiding something.
        """
        try:
            used = ws.UsedRange
            first_row, first_col = used.Row, used.Column
            values = used.Value
        except Exception:
            return
        if values is None:
            return
        if not isinstance(values, tuple):   # a one-cell range comes back flat
            values = ((values,),)

        # Only numbers and dates can hide behind ###### — text either spills
        # into the neighbouring cell or is clipped, never masked.
        candidates = {}
        for r, row in enumerate(values):
            if not isinstance(row, tuple):
                row = (row,)
            for c, value in enumerate(row):
                if value is None or isinstance(value, str):
                    continue
                candidates.setdefault(first_col + c, []).append(first_row + r)

        for col, rows in candidates.items():
            hidden = self._hidden_rows(ws, col, rows)
            if not hidden:
                continue
            try:
                self._widen_column(ws, col, hidden)
            except Exception:
                continue

    # === PRINT AREA (THE SHEET GREW PAST WHAT THE TEMPLATE PRINTS) ===

    # Excel constants for Range.Find — resolved here so the COM calls read
    # the same as the VBA they mirror.
    _XL_FORMULAS = -4123
    _XL_PART = 2
    _XL_BY_ROWS = 1
    _XL_BY_COLUMNS = 2
    _XL_PREVIOUS = 2

    def _last_content_cell(self, ws):
        """
        Return ``(row, col)`` of the furthest cell holding a value.

        ``UsedRange`` also counts cells that only carry formatting, which on
        these templates reaches far below the last real figure and would add
        blank pages, so search for content instead.
        """
        def _find(order):
            try:
                return ws.Cells.Find(
                    What="*", After=ws.Cells(1, 1),
                    LookIn=self._XL_FORMULAS, LookAt=self._XL_PART,
                    SearchOrder=order, SearchDirection=self._XL_PREVIOUS)
            except Exception:
                return None

        last_row = _find(self._XL_BY_ROWS)
        last_col = _find(self._XL_BY_COLUMNS)
        if last_row is None or last_col is None:
            return None
        try:
            return last_row.Row, last_col.Column
        except Exception:
            return None

    def _expand_print_area(self, ws):
        """
        Print the whole tab, shrunk to fit on a single sheet of paper.

        Cash-sheet tabs carry a print area saved when the layout was shorter
        (``$A$1:$W$62``). The sheet has since grown — the GL/tender breakdown
        now runs past row 80 — and everything below the old print area was
        silently dropped from the page. Stretch the print area to whatever
        the tab actually holds, then scale it to one page wide *and* one page
        tall: a cash sheet is read as one table, so the columns shrinking is
        a far better trade than the bottom rows landing on a second page.

        Each step that fails says so. Both halves used to swallow their
        errors, which meant a tab that quietly fell back to the template's
        frozen ``$A$1:$W$62`` was reported as printed exactly like one that
        worked, and the missing rows were only discovered at the printer.
        """
        name = self._sheet_name(ws)
        last = self._last_content_cell(ws)
        if not last:
            self._log(
                f"   {name}: could not find the last filled cell, so the "
                "print area saved in the template is what will print.",
                kind="warning")
        else:
            row, col = last
            try:
                ws.PageSetup.PrintArea = ws.Range(
                    ws.Cells(1, 1), ws.Cells(row, col)).Address
            except Exception as exc:
                self._log(
                    f"   {name}: could not widen the print area ({exc}), so "
                    "rows past the template's saved area will be cut off.",
                    kind="warning")
        self._fit_to_one_page(ws)

    # Excel refuses to scale below 10%, and no cash-sheet tab measured needs
    # anything under ~40%, so hitting this floor means the print area is
    # reaching somewhere it should not.
    _MIN_ZOOM = 10

    def _fit_to_one_page(self, ws):
        """
        Put one tab's whole print area on a single sheet of paper, verified.

        Two steps, because "fit to one page" is a request Excel does not
        always honour. First ask for it the normal way. Then read back
        ``Pages.Count`` — Excel's own pagination, the only ground truth
        available here — and if the tab still spans more than one page, drop
        to an explicit zoom percentage and shrink until it does not.

        The verify-and-shrink half exists because the request silently fails
        in more than one way: a tab copied into the double-sided batch
        workbook has its scaling re-derived by ``Worksheet.Copy``, and
        ``Zoom = False`` is rejected outright by some pywin32/Excel pairings.
        Both used to end the same way — a cash sheet cut off at the printer
        with the run reporting success. An explicit integer zoom is the one
        form Excel always accepts, so that is what the fallback uses.
        """
        name = self._sheet_name(ws)
        try:
            # A manual page break saved in the template splits the page even
            # at "fit to one page", so clear them before scaling.
            try:
                ws.ResetAllPageBreaks()
            except Exception:
                pass
            ws.PageSetup.Zoom = False    # FitToPages only applies with Zoom off
            ws.PageSetup.FitToPagesWide = 1
            ws.PageSetup.FitToPagesTall = 1
        except Exception as exc:
            self._log(
                f"   {name}: Excel refused fit-to-one-page ({exc}); "
                "scaling by percentage instead.",
                kind="detail")

        pages = self._page_count(ws)
        if pages is None or pages <= 1:
            return      # fits, or this Excel cannot tell us — nothing to do
        self._shrink_to_one_page(ws, name)

    @staticmethod
    def _page_count(ws):
        """
        Pages this tab would print right now, or None if Excel will not say.

        Reading it forces a repagination, so it is asked once per tab on the
        fast path and only repeated while actively searching for a zoom.
        """
        try:
            return int(ws.PageSetup.Pages.Count)
        except Exception:
            return None

    def _shrink_to_one_page(self, ws, name):
        """
        Binary-search the largest whole-percent zoom that still prints as one
        page, so a tab that has to shrink shrinks no further than it must.

        Bounded to a handful of probes: each one repaginates the sheet, and
        landing within a percent or two of the best zoom is worth far more
        than the last decimal.
        """
        low, high, best = self._MIN_ZOOM, 100, None
        while low <= high:
            zoom = (low + high) // 2
            try:
                ws.PageSetup.Zoom = zoom
            except Exception as exc:
                self._log(
                    f"   {name}: could not set the print scale ({exc}); this "
                    "tab may be cut off.",
                    kind="warning")
                return
            pages = self._page_count(ws)
            if pages is None:
                self._log(
                    f"   {name}: Excel stopped reporting its page count; "
                    f"left at {zoom}%.",
                    kind="warning")
                return
            if pages <= 1:
                best = zoom          # fits — try to give it more room
                low = zoom + 1
            else:
                high = zoom - 1      # still spilling — shrink further

        if best is None:
            self._log(
                f"   {name}: will not fit on one page even at "
                f"{self._MIN_ZOOM}% ({self._describe_area(ws)}). Check that "
                "tab for values sitting outside the table.",
                kind="warning")
            return

        try:
            ws.PageSetup.Zoom = best
        except Exception:
            pass
        self._log(
            f"   {name}: fit-to-one-page did not take, printed at {best}% "
            "instead.",
            kind="detail")

    @staticmethod
    def _describe_area(ws):
        try:
            return f"print area {ws.PageSetup.PrintArea or '?'}"
        except Exception:
            return "print area ?"

    @staticmethod
    def _sheet_name(ws):
        try:
            return str(ws.Name)
        except Exception:
            return "sheet"

    def _apply_page_setup(self, ws, excel):
        """Apply page settings used by Excel before printing."""
        try:
            excel.PrintCommunication = False
        except Exception:
            pass

        orientation = self._ORIENTATIONS.get(
            str(self.settings.orientation).lower(), 2)
        ws.PageSetup.Orientation = orientation
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

    def _start_duplex_batch(self, excel):
        """Enable staging so Excel can turn the run into one print job."""
        self._duplex_batch_excel = excel
        self._duplex_batch_workbook = None
        self._duplex_batch_staged_sheet_count = 0

    def _stage_for_duplex(self, sheets, fit_one_page=False):
        """
        Copy one worksheet or a selected-sheets collection into the batch.

        ``fit_one_page`` re-applies the one-page scaling to the copies. The
        print area rides along with ``Worksheet.Copy`` but the scaling does
        not, so without this a cash sheet printed double-sided reverts to the
        template's scaling and comes out cut off.
        """
        excel = self._duplex_batch_excel
        batch = self._duplex_batch_workbook
        if excel is None:
            raise PrinterError("The double-sided print batch was not initialized.")

        try:
            expected = max(1, int(sheets.Count))
        except Exception:
            expected = 1

        if batch is None:
            # Microsoft documents Copy() without Before/After as the reliable
            # way to create a new workbook containing the copied sheet(s).
            # Excel also makes that new workbook ActiveWorkbook, so this avoids
            # the driver-dependent failure seen when copying the first tab into
            # a separately pre-created blank workbook.
            sheets.Copy()
            batch = excel.ActiveWorkbook
            if batch is None:
                raise PrinterError(
                    "Excel did not create the double-sided print workbook.")
            self._duplex_batch_workbook = batch
            try:
                added = max(expected, int(batch.Worksheets.Count))
            except Exception:
                added = expected
            first_new = 1
        else:
            before = int(batch.Worksheets.Count)
            destination = batch.Worksheets(before)
            # Positional Before/After arguments are more dependable through
            # pywin32 than a named optional argument on some Office builds.
            sheets.Copy(None, destination)
            try:
                batch.Activate()
            except Exception:
                pass
            try:
                reported = int(batch.Worksheets.Count) - before
            except Exception:
                reported = 0
            # Copy is synchronous and raises a COM error when it fails.  Some
            # Office builds briefly return the old collection Count even after
            # a successful copy, so do not turn that stale count into a false
            # "pages were not added" failure.
            added = max(expected, reported)
            first_new = before + 1

        if fit_one_page:
            self._refit_staged_sheets(batch, first_new, added)
        self._duplex_batch_staged_sheet_count += added

    def _refit_staged_sheets(self, batch, first_index, count):
        """
        Redo the print area and one-page scaling on the tabs just copied in.

        The copy in the batch workbook is what actually prints, so it gets the
        same treatment from scratch rather than trusting ``Worksheet.Copy`` to
        have carried it over — it carries the print area but re-derives the
        scaling, and the copy is measured on its own terms anyway.
        """
        for index in range(first_index, first_index + count):
            try:
                ws = batch.Worksheets(index)
            except Exception:
                continue
            self._expand_print_area(ws)

    def _finish_duplex_batch(self):
        """Submit the staged batch as one print job, exactly once."""
        batch = self._duplex_batch_workbook
        if batch is None or self._duplex_batch_staged_sheet_count == 0:
            return

        self._log(
            f"Submitting {self._duplex_batch_staged_sheet_count} tab(s) as "
            "one double-sided print job.",
            kind="detail")
        self._send_to_printer(batch)

    def _close_duplex_batch(self):
        batch = self._duplex_batch_workbook
        self._duplex_batch_excel = None
        self._duplex_batch_workbook = None
        self._duplex_batch_staged_sheet_count = 0
        if batch is not None:
            try:
                batch.Close(SaveChanges=False)
            except Exception:
                pass

    def _print_sheets(self, wb, worksheets, fit_one_page=False):
        """
        Send several tabs of one workbook to the printer as a single job.

        Double-sided is decided per print job: a printer can only put page 2
        on the back of page 1 when both belong to the same document. Calling
        ``PrintOut`` once per tab hands the driver a stack of one-page
        documents, so every tab starts a fresh sheet of paper and the
        "Double-sided" option looks like it was ignored. Selecting the tabs
        as a group makes Excel emit one document, which the driver can then
        actually duplex. Grouped sheets print in workbook tab order.
        """
        if self._duplex_batch_excel is not None:
            # Staging every tab in the shared workbook is what joins sheets
            # from *different* source workbooks into the same physical job.
            for ws in worksheets:
                self._stage_for_duplex(ws, fit_one_page)
            return

        if len(worksheets) == 1:
            worksheets[0].Select()
            self._print_sheet(worksheets[0], fit_one_page)
            return

        try:
            for index, ws in enumerate(worksheets):
                # Replace:=True on the first tab, False to add the rest.
                ws.Select(index == 0)
            self._print_sheet(wb.Windows(1).SelectedSheets, fit_one_page)
            return
        except Exception as exc:
            self._log(
                f"   Note: could not group tabs into one job ({exc}); "
                "printing them one at a time, which prints single-sided.",
                kind="detail")

        for ws in worksheets:
            ws.Select()
            self._print_sheet(ws, fit_one_page)

    def _print_sheet(self, ws, fit_one_page=False):
        if self._duplex_batch_excel is not None:
            self._stage_for_duplex(ws, fit_one_page)
            return
        self._send_to_printer(ws)

    def _send_to_printer(self, printable):
        kwargs = {
            "Copies": self.settings.copies,
            "Collate": self.settings.collate,
        }
        if self._excel_active_printer:
            kwargs["ActivePrinter"] = self._excel_active_printer
        printable.PrintOut(**kwargs)

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

    def _print_workbook(self, excel, file_path, kind, sheet_picker,
                        adjust=None, missing_sheet_msg="Sheet not found"):
        """
        Open one workbook, run an optional pre-print adjust step, and print.

        Returns True/False so the caller can tally printed/failed counts.
        Pulled out of the per-source variants to avoid duplicating the
        same try/finally boilerplate.
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
