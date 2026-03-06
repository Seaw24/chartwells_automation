"""
Main Execution Module
Processes Infor (CSV), Tavlo (XLS/XML), and Grubhub (CSV) reports
and fills the corresponding cash sheet Excel workbooks.
"""

import os
from datetime import date, timedelta
from dateutil.parser import parse as dateutil_parse

try:
    from ..db.tendersdb_manager import TendersDBManager
except ImportError:
    try:
        from BE.src.db.tendersdb_manager import TendersDBManager
    except ImportError:
        from db.tendersdb_manager import TendersDBManager

try:
    from .infor_parser import InforParser
    from .tavlo_parser import TavloParser
    from .grubhub_parser import GrubhubParser
    from .excel_autofiller import ExcelAutofiller
    from .config import (
        REPORTS_CASHSHEET_MAP,
        GRUBHUB_VENUE_MAP,
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

    def __init__(self, reports_dir, casheet_dir, on_event=None, stop_event=None, auto_print=False, printer_name=None):
        self.casheet_dir = casheet_dir
        self.reports_dir = reports_dir
        self.tracker = ProcessingTracker(on_event=on_event)
        self.casheet_files = []
        self.stop_event = stop_event
        self.auto_print = auto_print
        self.printer_name = printer_name
        self.filled_days = set()
        self.db_manager = TendersDBManager()

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
                elif name.startswith("TransactionDetailbyVenue"):
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

        # Print reports then cash sheets if enabled
        if self.auto_print and self.filled_days:
            from ..printer import ExcelPrinter
            printer = ExcelPrinter(self.printer_name, self.tracker)
            printer.print_all(self.reports_dir,
                              self.casheet_dir, list(self.filled_days))

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

    def fill_and_save(self, casheet_path, location_in_casheet, location_in_db, data_dict, label, source="infor"):
        """
        Open a cash-sheet workbook, fill one location row, save, and validate.

        Args:
            source: Data origin — 'infor', 'tavlo', or 'grubhub'.

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
            self.filled_days.add(week_day)
            saved = self.db_manager.insert_record(
                report_date=data_dict.get("date"),
                location=location_in_db,
                total_sales=data_dict.get("total_sales", 0.0),
                tax=data_dict.get("tax", 0.0),
                meal_count=data_dict.get("count", 0),
                tenders=data_dict.get("tenders", {}),
                source=source,
            )
            if not saved:
                self.tracker.log("  ⚠ DB record was not saved")

        else:
            self.tracker.add_failure(label, casheet_path,
                                     warning="Tender over/short != 0")
        self.tracker.log(f"{'=' * 80}")
        return True

    # ═══════════════════════════════════════════════════════════════
    #  PROCESS ONE INFOR / TAVLO REPORT  (one file = one venue)
    # ═══════════════════════════════════════════════════════════════

    def process_single_report(self, report_parser, report_filename):
        """
        Parse an Infor or Tavlo report and fill the matching cash sheet.
        """
        self.tracker.log(f"{'=' * 80}")
        self.tracker.log(f"{'=' * 80}")
        self.tracker.log(f"\n--- {report_filename} ---")
        # 1. Parse
        if not report_parser.parse():
            self.tracker.add_failure(
                "Unknown", report_filename, "Parse failed")
            self.tracker.log(f"{'=' * 80}")
            return
        data = report_parser.get_data_dict()
        location = strip_accents(data["location"])
        self.tracker.log(f"Parsing: {report_parser.file_path}")
        self.tracker.log(f"Location: {data['location']}")
        self.tracker.log(f"Date: {data['date']}")
        self.tracker.log(f"\n{'=' * 80}")

        # 2. Look up cash-sheet mapping
        if location not in REPORTS_CASHSHEET_MAP:
            self.tracker.add_failure(location, report_filename,
                                     "Location not in REPORTS_CASHSHEET_MAP")
            return

        casheet_pattern, location_in_casheet, location_in_db = REPORTS_CASHSHEET_MAP[
            location]

        # 3. Find the cash-sheet file
        casheet_file = self.find_casheet_file(casheet_pattern)
        if casheet_file is None:
            self.tracker.add_failure(location, report_filename,
                                     f"No casheet file matching '{casheet_pattern}'")
            return

        # 4. Fill and save — detect source from parser type
        source = "tavlo" if isinstance(report_parser, TavloParser) else "infor"
        casheet_path = os.path.join(self.casheet_dir, casheet_file)
        self.fill_and_save(casheet_path, location_in_casheet, location_in_db,
                           data, f"{location} ({report_filename})", source=source)

    # ═══════════════════════════════════════════════════════════════
    #  PROCESS GRUBHUB REPORT  (one file = ALL venues × ALL dates)
    # ═══════════════════════════════════════════════════════════════

    def _add_discounts(self, data: dict):
        """Move any Grubhub discounts amount into the visa tender."""
        disc = data.get("discounts", 0.0)
        if disc != 0.0:
            data.setdefault("tenders", {})
            data["tenders"]["visa"] = data["tenders"].get("visa", 0.0) + disc
            data["total_sales"] = data.get("total_sales", 0.0) + disc
            self.tracker.log(
                f"ℹ Discounts ${disc:.2f} added to visa"
                f" → ${data['tenders']['visa']:.2f}")
            data.pop("discounts", None)
            self.tracker.log(
                f"ℹ Total sales updated to ${data['total_sales']:.2f}")

    def _aggregate_data_dicts(self, data_list):
        """Merge/sum multiple data dicts that target the same cash-sheet row."""
        merged = {
            "date": data_list[0]["date"],
            "count": 0,
            "total_sales": 0.0,
            "tax": 0.0,
            "tenders": {},
            "discounts": 0.0,
        }
        for d in data_list:
            merged["count"] += d.get("count", 0)
            merged["total_sales"] += d.get("total_sales", 0.0)
            merged["tax"] += d.get("tax", 0.0)
            merged["discounts"] += d.get("discounts", 0.0)
            for k, v in d.get("tenders", {}).items():
                merged["tenders"][k] = merged["tenders"].get(k, 0.0) + v

        return merged

    def process_grubhub(self, parser, grubhub_path):
        """
        Parse a Grubhub CSV and fill each venue's cash sheet.
        Now uses ExcelAutofiller (same as Infor/Tavlo) for consistency.
        """
        grubhub_filename = os.path.basename(grubhub_path)
        self.tracker.log(f"\n{'='*80}")
        self.tracker.log(f"  Grubhub: {grubhub_filename}")
        self.tracker.log(f"{'='*80}")

        if not parser.parse(self.stop_event):
            self.tracker.add_failure(
                "Grubhub", grubhub_filename, "Parse failed")
            return

        if not parser.get_dates():
            self.tracker.log("  No Grubhub data found in file.")
            return

        for grub_date in parser.get_dates():
            weekday = self._get_weekday_name(grub_date)
            if not weekday:
                continue

            if self.stop_event and self.stop_event.is_set():
                self.tracker.log("  🛑 Aborting Grubhub processing...")
                return

            venues = parser.get_venues(grub_date)
            self.tracker.log(
                f"\n  📅 {grub_date} ({weekday}) — {len(venues)} venue(s)")
            self.tracker.log(f"  {'─'*80}")

            # Group venues by (casheet_path, location) for aggregation
            date_groups = {}
            for venue in venues:
                if venue not in GRUBHUB_VENUE_MAP:
                    self.tracker.add_failure(venue, grubhub_filename,
                                             "Venue not in GRUBHUB_VENUE_MAP")
                    continue

                casheet_pattern, location_in_casheet, location_in_db = GRUBHUB_VENUE_MAP[venue]
                casheet_file = self.find_casheet_file(casheet_pattern)
                if casheet_file is None:
                    self.tracker.add_failure(venue, grubhub_filename,
                                             f"No casheet file matching '{casheet_pattern}'")
                    continue

                casheet_path = os.path.join(self.casheet_dir, casheet_file)
                data = parser.get_data_dict(grub_date, venue)
                data["date"] = grub_date

                key = (casheet_path, location_in_casheet, location_in_db)
                if key not in date_groups:
                    date_groups[key] = {"venues": [], "data_list": []}
                date_groups[key]["venues"].append(venue)
                date_groups[key]["data_list"].append(data)

            # Fill each group using ExcelAutofiller
            for (casheet_path, location_in_casheet, location_in_db), grp in date_groups.items():
                if self.stop_event and self.stop_event.is_set():
                    self.tracker.log("  🛑 Aborting Grubhub processing...")
                    return

                venue_names = grp["venues"]
                data_list = grp["data_list"]

                if len(data_list) > 1:
                    label = f"{grub_date} : {', '.join(venue_names)} (combined)"
                    merged_data = self._aggregate_data_dicts(
                        data_list)
                    venue_display = f"{venue_names[0]} +{len(venue_names)-1} more"
                else:
                    merged_data = data_list[0]
                    label = f"{grub_date} : {venue_names[0]}"
                    venue_display = venue_names[0]

                # Fold discounts into visa for every Grubhub entry
                self._add_discounts(merged_data)

                # Log summary
                sales = merged_data.get('total_sales', 0)
                tax = merged_data.get('tax', 0)
                count = merged_data.get('count', 0)
                self.tracker.log(
                    f"   Location: {venue_display:<40} ${sales:>8.2f}  tax ${tax:>6.2f}  count: {count}")

                # Use fill_and_save (same as Infor/Tavlo)
                self.fill_and_save(casheet_path, location_in_casheet, location_in_db,
                                   merged_data, label, source="grubhub")

        # Log unmapped items
        unmapped_v = parser.get_unmapped_venues()
        unmapped_t = parser.get_unmapped_tenders()
        if unmapped_v:
            self.tracker.log(
                f"\n  ⚠️ Unmapped venues: {', '.join(unmapped_v)}")
        if unmapped_t:
            self.tracker.log(f"  ⚠️ Unmapped tenders: {', '.join(unmapped_t)}")


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

    engine = CashSheetAutofillEngine(reports_dir, casheet_dir)
    engine.execute()
