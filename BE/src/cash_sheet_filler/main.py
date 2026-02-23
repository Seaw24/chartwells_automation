"""
Main Execution Module
Processes Infor (CSV), Tavlo (XLS/XML), and Grubhub (CSV) reports
and fills the corresponding cash sheet Excel workbooks.
"""

import os
from datetime import date, timedelta
from dateutil.parser import parse as dateutil_parse
from openpyxl import load_workbook

try:
    from .infor_parser import InforParser
    from .tavlo_parser import TavloParser
    from .grubhub_parser import GrubhubParser
    from .excel_autofiller import ExcelAutofiller
    from .config import (
        REPORTS_CASHSHEET_MAP,
        GRUBHUB_VENUE_MAP,
        FILL_COL_MAP,
        REPORTS_FOLDER,
        CASH_SHEET_FOLDER,
    )
except ImportError:
    from infor_parser import InforParser
    from tavlo_parser import TavloParser
    from grubhub_parser import GrubhubParser
    from excel_autofiller import ExcelAutofiller
    from config import (
        REPORTS_CASHSHEET_MAP,
        GRUBHUB_VENUE_MAP,
        FILL_COL_MAP,
        REPORTS_FOLDER,
        CASH_SHEET_FOLDER,
    )
from ..utils import strip_accents


# ═══════════════════════════════════════════════════════════════
#  PROCESSING TRACKER
# ═══════════════════════════════════════════════════════════════

class ProcessingTracker:
    """Tracks successes, failures, and warnings across all reports."""

    def __init__(self, on_event=None):
        """
        Args:
            on_event: Optional callback(type, message) where type is
                      'info', 'success', 'warning', 'error', or 'progress'.
        """
        self.successful = []
        self.failed = []
        self.warnings = []
        self._on_event = on_event

    def _emit(self, kind, msg):
        """Send an event to the UI callback (if registered)."""
        if self._on_event:
            try:
                self._on_event(kind, msg)
            except Exception:
                pass
        print(msg)

    def log(self, msg):
        self._emit("info", msg)

    def add_success(self, location, filename, warning=None):
        self.successful.append({"location": location, "filename": filename})
        self._emit("success", f"  ✓ {location}")
        if warning:
            self.warnings.append(
                {"location": location, "filename": filename, "msg": warning})
            self._emit("warning", f"  ⚠ {location}: {warning}")

    def add_failure(self, location, filename, message):
        self.failed.append(
            {"location": location, "filename": filename, "msg": message})
        self._emit("error", f"  ✗ {location}: {message}")

    def print_summary(self):
        total = len(self.successful) + len(self.failed)
        summary = (
            f"\nSUMMARY:  {len(self.successful)} succeeded, "
            f"{len(self.failed)} failed, {len(self.warnings)} warnings  "
            f"({total} total)"
        )
        self._emit("info", "=" * 60)
        self._emit("info", summary)

        if self.warnings:
            self._emit("info", "\nWARNINGS:")
            for w in self.warnings:
                self._emit("warning", f"  - {w['location']}: {w['msg']}")

        if self.failed:
            self._emit("info", "\nFAILED:")
            for f in self.failed:
                loc = f["location"] or "Unknown"
                self._emit("error",
                           f"  - {loc} ({f['filename']}): {f['msg']}")

        self._emit("info", "=" * 60)


# ═══════════════════════════════════════════════════════════════
#  AUTOFILL ENGINE
# ═══════════════════════════════════════════════════════════════

class CashSheetAutofillEngine:
    """Core engine to process reports and fill cash sheets."""

    def __init__(self, reports_dir, casheet_dir, on_event=None, stop_event=None):
        self.casheet_dir = casheet_dir
        self.reports_dir = reports_dir
        self.tracker = ProcessingTracker(on_event=on_event)
        self.casheet_files = []
        self.stop_event = stop_event
    # ═══════════════════════════════════════════════════════════════
    #  MAIN EXECUTE
    # ═══════════════════════════════════════════════════════════════

    def execute(self):
        """
        Process all reports in reports_dir and fill cash sheets in casheet_dir.

        File-type detection:
            .csv starting with "Operations Report" → Infor
            .csv starting with "SalesbyVenue"       → Grubhub
            .xls                                    → Tavlo
        """

        # ── Gather files ──────────────────────────────────────────────────
        try:
            all_report_files = os.listdir(self.reports_dir)
        except (FileNotFoundError, PermissionError) as e:
            self.tracker.log(f"Cannot access reports folder: {e}")
            return self.tracker

        try:
            self.casheet_files = os.listdir(self.casheet_dir)
        except (FileNotFoundError, PermissionError) as e:
            self.tracker.log(f"Cannot access cash-sheets folder: {e}")
            return self.tracker

        infor_files = []
        tavlo_files = []
        grubhub_files = []

        for name in all_report_files:
            if name.lower().endswith(".csv"):
                if name.startswith("Operations Report"):
                    infor_files.append(name)
                elif name.startswith("SalesbyVenue"):
                    grubhub_files.append(name)
            elif name.lower().endswith(".xls"):
                tavlo_files.append(name)

        total = len(infor_files) + len(tavlo_files) + len(grubhub_files)
        if total == 0:
            self.tracker.log("No report files found.")
            return self.tracker

        self.tracker.log(
            f"Found {len(infor_files)} Infor, {len(tavlo_files)} Tavlo, "
            f"{len(grubhub_files)} Grubhub file(s)")

        # ── Process Infor (CSV, one venue per file) ───────────────────────
        for name in infor_files:
            # Check for stop signal before processing the next file
            if self.stop_event and self.stop_event.is_set():
                self.tracker.log("🛑 Aborting Infor processing...")
                return self.tracker

            path = os.path.join(self.reports_dir, name)
            parser = InforParser(path, self.tracker)
            self.process_single_report(parser, name)

        # ── Process Tavlo (XLS/XML, one venue per file) ───────────────────
        for name in tavlo_files:
            # Check for stop signal before processing the next file
            if self.stop_event and self.stop_event.is_set():
                self.tracker.log("🛑 Aborting Tavlo processing...")
                return self.tracker

            path = os.path.join(self.reports_dir, name)
            parser = TavloParser(path, self.tracker)
            self.process_single_report(parser, name)

        # ── Process Grubhub (CSV, all venues in one file) ─────────────────
        for name in grubhub_files:
            # Check for stop signal before processing the next file
            if self.stop_event and self.stop_event.is_set():
                self.tracker.log("🛑 Aborting Grubhub processing...")
                return self.tracker

            path = os.path.join(self.reports_dir, name)
            parser = GrubhubParser(path, self.tracker)
            self.process_grubhub(parser, path)

        # ── Summary ───────────────────────────────────────────────────────
        self.tracker.print_summary()
        return self.tracker

    # ═══════════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _get_weekday_name(self, date_str):
        """Convert a date string (e.g. MM/DD/YYYY) to its weekday name."""
        try:
            return dateutil_parse(date_str).strftime("%A")
        except (ValueError, TypeError):
            self.tracker.log(f"  Error: Could not parse date '{date_str}'.")
            self.tracker.log("  Please use MM/DD/YYYY or similar format.")
            return None

    def find_casheet_file(self, casheet_pattern):
        """Find a cash-sheet file whose name contains *casheet_pattern*."""
        for f in self.casheet_files:
            if casheet_pattern.strip().lower() in f.strip().lower():
                return f
        return None

    def fill_and_save(self, casheet_path, location_in_casheet, data_dict, label):
        """
        Open a cash-sheet workbook, fill one location row, save, and validate.

        Returns:
            bool
        """
        week_day = self._get_weekday_name(data_dict.get("date"))
        filler = ExcelAutofiller(
            casheet_path, location_in_casheet, week_day, tracker=self.tracker)

        if not filler.open_workbook():
            self.tracker.add_failure(
                label, casheet_path, "Failed to open workbook")
            return False

        if not filler.filling(data_dict):
            self.tracker.add_failure(
                label, casheet_path, "Failed to fill data")
            filler.close()
            return False

        valid = filler.save()
        filler.close()

        if valid:
            self.tracker.add_success(label, casheet_path)
        else:
            self.tracker.add_failure(label, casheet_path,
                                     warning="Tender over/short != 0")
        self.tracker.log(f"{'=' * 70}")
        self.tracker.log(f"{'=' * 70}")

        return True

    # ═══════════════════════════════════════════════════════════════
    #  PROCESS ONE INFOR / TAVLO REPORT  (one file = one venue)
    # ═══════════════════════════════════════════════════════════════

    def process_single_report(self, report_parser, report_filename):
        """
        Parse an Infor or Tavlo report and fill the matching cash sheet.
        """
        self.tracker.log(f"{'=' * 70}")
        self.tracker.log(f"{'=' * 70}")
        self.tracker.log(f"\n--- {report_filename} ---")
        # 1. Parse
        if not report_parser.parse():
            self.tracker.add_failure(
                "Unknown", report_filename, "Parse failed")
            self.tracker.log(f"{'=' * 70}")
            return
        data = report_parser.get_data_dict()
        location = strip_accents(data["location"])
        self.tracker.log(f"Parsing: {report_parser.file_path}")
        self.tracker.log(f"Location: {data['location']}")
        self.tracker.log(f"Date: {data['date']}")
        self.tracker.log(f"\n{'=' * 70}")

        # 2. Look up cash-sheet mapping
        if location not in REPORTS_CASHSHEET_MAP:
            self.tracker.add_failure(location, report_filename,
                                     "Location not in REPORTS_CASHSHEET_MAP")
            return

        casheet_pattern, location_in_casheet = REPORTS_CASHSHEET_MAP[location]

        # 3. Find the cash-sheet file
        casheet_file = self.find_casheet_file(casheet_pattern)
        if casheet_file is None:
            self.tracker.add_failure(location, report_filename,
                                     f"No casheet file matching '{casheet_pattern}'")
            return

        # 4. Fill and save
        casheet_path = os.path.join(self.casheet_dir, casheet_file)
        self.fill_and_save(casheet_path, location_in_casheet,
                           data, f"{location} ({report_filename})")

    # ═══════════════════════════════════════════════════════════════
    #  PROCESS GRUBHUB REPORT  (one file = ALL venues × ALL dates)
    # ═══════════════════════════════════════════════════════════════

    def _aggregate_data_dicts(self, data_list):
        """
        Merge/sum multiple data dicts that target the same cash-sheet row.
        """
        merged = {
            "date": data_list[0]["date"],
            "count": 0,
            "total_sales": 0.0,
            "tax": 0.0,
            "tenders": {},
        }
        for d in data_list:
            merged["count"] += d.get("count", 0)
            merged["total_sales"] += d.get("total_sales", 0.0)
            merged["tax"] += d.get("tax", 0.0)
            for k, v in d.get("tenders", {}).items():
                merged["tenders"][k] = merged["tenders"].get(k, 0.0) + v
        return merged

    def process_grubhub(self, parser, grubhub_path):
        """
        Parse a Grubhub CSV and fill each venue's cash sheet for every date.

        Groups ALL data by cash-sheet file across ALL dates, so each workbook
        is opened only once (avoids corruption from repeated open/save cycles).
        Venues that share a row are aggregated (summed).
        """
        grubhub_filename = os.path.basename(grubhub_path)
        self.tracker.log(f"\n--- Grubhub: {grubhub_filename} ---")

        if not parser.parse():
            self.tracker.add_failure(
                "Grubhub", grubhub_filename, "Parse failed")
            return

        if not parser.get_dates():
            self.tracker.log("  No Grubhub data found in file.")
            return

        # ── Step 1: Collect ALL data grouped by casheet_path ──────────────
        # Structure: {casheet_path: [(weekday, location, merged_data, label), ...]}
        file_tasks = {}

        for grub_date in parser.get_dates():
            weekday = self._get_weekday_name(grub_date)
            if not weekday:
                continue

            venues = parser.get_venues(grub_date)
            self.tracker.log(
                f"\n  Date: {grub_date} ({weekday})  —  {len(venues)} venue(s)")

            # Group venues by (casheet_path, location) for this date
            date_groups = {}
            for venue in venues:
                if venue not in GRUBHUB_VENUE_MAP:
                    self.tracker.add_failure(venue, grubhub_filename,
                                             "Venue not in GRUBHUB_VENUE_MAP")
                    continue

                casheet_pattern, location_in_casheet = GRUBHUB_VENUE_MAP[venue]
                casheet_file = self.find_casheet_file(casheet_pattern)
                if casheet_file is None:
                    self.tracker.add_failure(venue, grubhub_filename,
                                             f"No casheet file matching '{casheet_pattern}'")
                    continue

                casheet_path = os.path.join(self.casheet_dir, casheet_file)
                data = parser.get_data_dict(grub_date, venue)
                data["date"] = grub_date

                key = (casheet_path, location_in_casheet)
                if key not in date_groups:
                    date_groups[key] = {"venues": [], "data_list": []}
                date_groups[key]["venues"].append(venue)
                date_groups[key]["data_list"].append(data)

            # Aggregate same-row venues and queue tasks per file
            for (casheet_path, location_in_casheet), grp in date_groups.items():
                venue_names = grp["venues"]
                data_list = grp["data_list"]

                if len(data_list) > 1:
                    merged_data = self._aggregate_data_dicts(data_list)
                    label = f"{grub_date} : Grubhub → {', '.join(venue_names)} (combined)"
                else:
                    merged_data = data_list[0]
                    label = f"{grub_date} : Grubhub → {venue_names[0]}"

                if casheet_path not in file_tasks:
                    file_tasks[casheet_path] = []
                file_tasks[casheet_path].append(
                    (weekday, location_in_casheet, merged_data, label))

        # ── Step 2: Open each workbook once, fill all dates, save once ────
        for casheet_path, tasks in file_tasks.items():
            # --- Quick stop check ---
            if self.stop_event and self.stop_event.is_set():
                self.tracker.log("🛑 Aborting Grubhub workbook filling...")
                return

            wb = None
            try:
                wb = load_workbook(casheet_path)
            except Exception as e:
                for (_, _, _, label) in tasks:
                    self.tracker.add_failure(label, casheet_path,
                                             f"Failed to open workbook: {e}")
                continue

            all_ok = True
            for (weekday, location_in_casheet, merged_data, label) in tasks:
                try:
                    # Find sheet (case-insensitive)
                    sheet_map = {s.lower(): s for s in wb.sheetnames}
                    actual_sheet = sheet_map.get(weekday.lower())
                    if actual_sheet is None:
                        self.tracker.add_failure(label, casheet_path,
                                                 f"Worksheet '{weekday}' not found")
                        all_ok = False
                        continue

                    ws = wb[actual_sheet]

                    # Find row for location
                    location_col = FILL_COL_MAP.get("location")
                    target_row = None
                    for r in range(4, ws.max_row + 1):
                        cell_val = ws.cell(r, location_col).value
                        if cell_val and cell_val.strip().lower() == location_in_casheet.lower():
                            target_row = r
                            break

                    if target_row is None:
                        self.tracker.add_failure(label, casheet_path,
                                                 f"Location '{location_in_casheet}' not found")
                        all_ok = False
                        continue

                    tax_row = target_row + 1

                    # Fill data directly
                    date_col = FILL_COL_MAP.get("date")
                    if date_col:
                        ws.cell(1, date_col).value = merged_data.get("date")

                    count_col = FILL_COL_MAP.get("count")
                    if count_col:
                        ws.cell(target_row, count_col).value = merged_data.get(
                            "count")

                    total_sales_col = FILL_COL_MAP.get("total_sales")
                    if total_sales_col:
                        ws.cell(target_row, total_sales_col).value = merged_data.get(
                            "total_sales")

                    tax_col = FILL_COL_MAP.get("tax")
                    if tax_col:
                        ws.cell(tax_row, tax_col).value = merged_data.get("tax")

                    tenders = merged_data.get("tenders", {})
                    for tender_name, amount in tenders.items():
                        if tender_name not in FILL_COL_MAP:
                            continue
                        col = FILL_COL_MAP[tender_name]
                        if amount != 0:
                            ws.cell(target_row, col).value = amount
                        else:
                            ws.cell(target_row, col).value = None

                    self.tracker.add_success(label, casheet_path)

                except Exception as e:
                    self.tracker.add_failure(
                        label, casheet_path, f"Fill error: {e}")
                    all_ok = False

            # Save once for the entire workbook
            try:
                wb.save(casheet_path)
                self.tracker.log(
                    f"  💾 Saved: {os.path.basename(casheet_path)}")
            except PermissionError:
                self.tracker.add_failure(
                    os.path.basename(casheet_path), casheet_path,
                    "Cannot save: file is open in another program")
            except Exception as e:
                self.tracker.add_failure(
                    os.path.basename(casheet_path), casheet_path,
                    f"Save error: {e}")
            finally:
                wb.close()

        # Log any unmapped items
        unmapped_v = parser.get_unmapped_venues()
        unmapped_t = parser.get_unmapped_tenders()
        if unmapped_v:
            self.tracker.log(f"\n  Unmapped venues : {unmapped_v}")
        if unmapped_t:
            self.tracker.log(f"  Unmapped tenders: {unmapped_t}")


# ═══════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    reports_dir = REPORTS_FOLDER
    casheet_dir = CASH_SHEET_FOLDER

    if not reports_dir:
        reports_dir = input("Path to reports folder: ").strip()
    if not casheet_dir:
        casheet_dir = input("Path to cash-sheets folder: ").strip()

    report_date = input(
        "Report date (e.g. MM/DD/YYYY, blank for yesterday): ").strip()
    if not report_date:
        report_date = (date.today() - timedelta(days=1)).strftime("%m/%d/%Y")

    engine = CashSheetAutofillEngine(reports_dir, casheet_dir, report_date)
    engine.execute()
