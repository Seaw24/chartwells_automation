"""
Main Execution Module
Processes Infor (CSV), Tavlo (XLS/XML), and Grubhub (CSV) reports
and fills the corresponding cash sheet Excel workbooks.
"""

import os
import sys
from pathlib import Path
from datetime import date, timedelta
from dateutil.parser import parse as dateutil_parse

# Allow running this file directly (`python main.py`) as well as `-m BE.src.cash_sheet_filler.main`.
# Sibling modules use imports like `from ..utils import ...` which require the package context
# to be `BE.src.cash_sheet_filler`, so we bootstrap sys.path and __package__ when run as a script.
if __package__ in (None, ""):
    _PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))
    __package__ = "BE.src.cash_sheet_filler"

from ..db.tendersdb_manager import TendersDBManager
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
from ..utils import strip_accents


# ═══════════════════════════════════════════════════════════════
#  PROCESSING TRACKER
# ═══════════════════════════════════════════════════════════════

class ProcessingTracker:
    """
    Collects results across all reports and emits structured events.

    The UI subscribes via ``on_event(kind, message)`` and uses ``kind`` to
    color-code each line. Keeping the vocabulary small and consistent is what
    lets the UI stay clean — every message belongs to exactly one kind:

        section  – start of a new file/group (bold header line)
        detail   – secondary text under a section (muted color)
        info     – neutral status line
        success  – a row was filled successfully
        warning  – row filled but with a non-fatal issue
        error    – a row failed
        summary  – final results block at the end of the run
    """

    def __init__(self, on_event=None):
        self.successful = []
        self.failed = []
        self.warnings = []
        self._on_event = on_event

    # ── event plumbing ────────────────────────────────────────────
    def _emit(self, kind, msg):
        """Forward the message to the UI (if any) and to stdout."""
        if self._on_event:
            try:
                self._on_event(kind, msg)
            except Exception:
                pass
        print(msg)

    # ── public emitters ───────────────────────────────────────────
    def log(self, msg):
        """Plain neutral line."""
        self._emit("info", msg)

    def section(self, title):
        """Header for a new file or logical group."""
        self._emit("section", f"▸ {title}")

    def detail(self, msg):
        """Secondary line shown indented under a section header."""
        self._emit("detail", f"   {msg}")

    def warning(self, msg):
        """Standalone warning line (not tied to a specific success/failure)."""
        self._emit("warning", f"   ⚠ {msg}")

    def add_success(self, location, filename, warning=None):
        self.successful.append({"location": location, "filename": filename})
        self._emit("success", f"   ✓ {location}")
        if warning:
            self.warnings.append(
                {"location": location, "filename": filename, "msg": warning})
            self._emit("warning", f"   ⚠ {location}: {warning}")

    def add_failure(self, location, filename, message):
        self.failed.append(
            {"location": location, "filename": filename, "msg": message})
        self._emit("error", f"   ✗ {location}: {message}")

    # ── final summary ─────────────────────────────────────────────
    def print_summary(self):
        """Emit the final results block. Kept short — long output gets ignored."""
        s, f, w = len(self.successful), len(self.failed), len(self.warnings)

        self._emit("summary", "")
        self._emit("summary", "── Summary ─────────────────────────────────────")
        self._emit("summary",
                   f"   ✓ {s} succeeded     ⚠ {w} warnings     ✗ {f} failed")

        if self.warnings:
            self._emit("info", "")
            self._emit("detail", "Warnings:")
            for item in self.warnings:
                self._emit("warning",
                           f"   ⚠ {item['location']}: {item['msg']}")

        if self.failed:
            self._emit("info", "")
            self._emit("detail", "Failed:")
            for item in self.failed:
                loc = item["location"] or "Unknown"
                self._emit("error",
                           f"   ✗ {loc} ({item['filename']}): {item['msg']}")


# ═══════════════════════════════════════════════════════════════
#  AUTOFILL ENGINE
# ═══════════════════════════════════════════════════════════════

class CashSheetAutofillEngine:
    """Core engine to process reports and fill cash sheets."""

    def __init__(
        self,
        reports_dir,
        casheet_dir,
        on_event=None,
        stop_event=None,
        auto_print=False,
        printer_name=None,
        print_settings=None,
    ):
        self.casheet_dir = casheet_dir
        self.reports_dir = reports_dir
        self.tracker = ProcessingTracker(on_event=on_event)
        self.casheet_files = []
        self.stop_event = stop_event
        self.auto_print = auto_print
        self.printer_name = printer_name
        self.print_settings = print_settings
        self.filled_days = {}  # Track which weekdays we filled for optional auto-printing at the end
        self.db_manager = TendersDBManager()
        self.printable_reports = set()   # ← ADD: report basenames with non-zero data


    # ═══════════════════════════════════════════════════════════════
    #  MAIN EXECUTE
    # ═══════════════════════════════════════════════════════════════

    def execute(self):
        """
        Process all reports in ``reports_dir`` and fill the matching cash sheets.

        File-type detection by name:
            ``Operations Report*.csv``        → Infor (1 venue per file)
            ``TransactionDetailbyVenue*.csv`` → Grubhub (many venues per file)
            ``*.xls``                         → Tavlo  (1 venue per file)

        Returns the populated ``ProcessingTracker`` so the caller can read
        ``tracker.successful``, ``tracker.failed``, ``tracker.warnings``.
        """
        # ── 1. List files in both folders (fail fast if either is missing) ─
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

        # ── 2. Bucket files by source type ─────────────────────────────────
        infor_files, tavlo_files, grubhub_files = [], [], []
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

        # One concise inventory line — the UI doesn't need a banner.
        self.tracker.log(
            f"Found {total} file(s):  "
            f"{len(infor_files)} Infor · "
            f"{len(tavlo_files)} Tavlo · "
            f"{len(grubhub_files)} Grubhub"
        )

        # ── 3. Process each bucket. Stop early if the user pressed Stop. ──
        # Infor and Tavlo: one venue per file.
        for name in infor_files:
            if self._stopped("Infor"):
                return self.tracker
            path = os.path.join(self.reports_dir, name)
            self.process_single_report(InforParser(path, self.tracker), name)

        for name in tavlo_files:
            if self._stopped("Tavlo"):
                return self.tracker
            path = os.path.join(self.reports_dir, name)
            self.process_single_report(TavloParser(path, self.tracker), name)

        # Grubhub: one file contains many venues × many dates.
        for name in grubhub_files:
            if self._stopped("Grubhub"):
                return self.tracker
            path = os.path.join(self.reports_dir, name)
            self.process_grubhub(GrubhubParser(path, self.tracker), path)

        # ── 4. Final summary block ─────────────────────────────────────────
        self.tracker.print_summary()

        # Print reports then cash sheets if enabled
        if self.auto_print and self.filled_days_by_file:
            from ..printer import ExcelPrinter
            printer = ExcelPrinter(
            self.printer_name,
            self.tracker,
            settings=self.print_settings,
        )
        printer.print_all(self.reports_dir,
                        self.casheet_dir, self.filled_days_by_file, self.printable_reports,)


        return self.tracker

    # ═══════════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _stopped(self, stage):
        """Return True (and emit one line) if the user pressed Stop."""
        if self.stop_event and self.stop_event.is_set():
            self.tracker.log(f"Stopped during {stage} processing.")
            return True
        return False

    def _get_weekday_name(self, date_str):
        """Convert a date string (e.g. MM/DD/YYYY) to its weekday name."""
        try:
            return dateutil_parse(date_str).strftime("%A")
        except (ValueError, TypeError):
            self.tracker.log(
                f"   Could not parse date '{date_str}' "
                "(expected MM/DD/YYYY).")
            return None
        
    @staticmethod
    def _report_has_data(data):
        """True if parsed report data has any non-zero sales / count / tenders."""
        if not data:
            return False
        if data.get("total_sales", 0):
            return True
        if data.get("count", 0):
            return True
        if any(data.get("tenders", {}).values()):
            return True
        return False

    def find_casheet_file(self, casheet_pattern):
        """Find a cash-sheet file whose name contains *casheet_pattern*."""
        for f in self.casheet_files:
            if casheet_pattern.strip().lower() in f.strip().lower():
                return f
        return None

    def fill_and_save(self, casheet_path, location_in_casheet, raw_location,
                      location_in_db, data_dict, label, source="infor"):
        """
        Open a cash-sheet workbook, fill one location row, save, validate,
        and persist a DB record.

        Args:
            casheet_path:        Absolute path to the .xlsx workbook.
            location_in_casheet: Row label as written in the cash sheet.
            raw_location:        Raw venue/location name from the report.
            location_in_db:      Canonical name used in the database.
            data_dict:           Parsed data (date, total_sales, tax, etc.).
            label:               Display label for tracker entries.
            source:              'infor' | 'tavlo' | 'grubhub' — used by the DB.

        Returns:
            True if filling completed (success or validation warning),
            False if the workbook could not be opened or filled.
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

        if not valid:
            # Validation only — workbook was saved, but tenders don't reconcile.
            self.tracker.add_failure(
                label, casheet_path, "Tender over/short != 0")
            return True

        # After
        self.tracker.add_success(label, casheet_path)
        self.filled_days_by_file.setdefault(casheet_path, set()).add(week_day)

        # Persist a record in the analytics DB. Failure here is logged but
        # never blocks the autofill — the cash sheet is already saved.
        saved = self.db_manager.insert_record(
            report_date=data_dict.get("date"),
            raw_location=raw_location,
            location=location_in_db,
            total_sales=data_dict.get("total_sales", 0.0),
            tax=data_dict.get("tax", 0.0),
            meal_count=data_dict.get("count", 0),
            tenders=data_dict.get("tenders", {}),
            source=source,
        )
        if not saved:
            self.tracker.log("   ⚠ DB record was not saved")
        return True

    # ═══════════════════════════════════════════════════════════════
    #  PROCESS ONE INFOR / TAVLO REPORT  (one file = one venue)
    # ═══════════════════════════════════════════════════════════════

    def process_single_report(self, report_parser, report_filename):
        """
        Parse an Infor or Tavlo report and fill its matching cash sheet.
        Each file represents a single venue's data for a single date.
        """
        # Header line for the file. The UI renders this in a bold/colored tag.
        self.tracker.section(report_filename)

        # 1. Parse
        if not report_parser.parse():
            self.tracker.add_failure(
                "Unknown", report_filename, "Parse failed")
            return

        data = report_parser.get_data_dict()
        location = strip_accents(data["location"])
        self.tracker.detail(f"{data['location']}  ·  {data['date']}")

        if self._report_has_data(data):
            self.printable_reports.add(report_filename)

        # 2. Look up cash-sheet mapping
        if location not in REPORTS_CASHSHEET_MAP:
            self.tracker.add_failure(
                location, report_filename,
                "Location not in REPORTS_CASHSHEET_MAP")
            return
        casheet_pattern, location_in_casheet, location_in_db = (
            REPORTS_CASHSHEET_MAP[location])

        # 3. Find the cash-sheet file on disk
        casheet_file = self.find_casheet_file(casheet_pattern)
        if casheet_file is None:
            self.tracker.add_failure(
                location, report_filename,
                f"No casheet file matching '{casheet_pattern}'")
            return

        # 4. Fill, save, and validate. Source is derived from the parser type
        #    so the DB row records where the data originated.
        source = "tavlo" if isinstance(report_parser, TavloParser) else "infor"
        casheet_path = os.path.join(self.casheet_dir, casheet_file)
        self.fill_and_save(
            casheet_path, location_in_casheet, location, location_in_db,
            data, f"{location} ({report_filename})", source=source)

    # ═══════════════════════════════════════════════════════════════
    #  PROCESS GRUBHUB REPORT  (one file = ALL venues × ALL dates)
    # ═══════════════════════════════════════════════════════════════

    def _add_discounts(self, data: dict):
        """
        Fold any Grubhub discounts into the Visa tender.

        Discounts on Grubhub reports are deducted from sales but the cash
        sheet expects the gross figure, so we add the discount amount back
        to both ``total_sales`` and the ``visa`` tender column. Logs are
        intentionally quiet here — the per-row dollars don't help the user.
        """
        disc = data.get("discounts", 0.0)
        if disc:
            data.setdefault("tenders", {})
            data["tenders"]["visa"] = data["tenders"].get("visa", 0.0) + disc
            data["total_sales"] = data.get("total_sales", 0.0) + disc
        data.pop("discounts", None)

    def _aggregate_data_dicts(self, data_list):
        """Sum multiple data dicts that target the same cash-sheet row."""
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
        Parse a Grubhub CSV (which contains many venues × many dates) and
        fill the matching cash sheet row for each (date, venue) combination.
        """
        grubhub_filename = os.path.basename(grubhub_path)
        self.tracker.section(f"Grubhub: {grubhub_filename}")

        if not parser.parse(self.stop_event):
            self.tracker.add_failure(
                "Grubhub", grubhub_filename, "Parse failed")
            return

        if not parser.get_dates():
            self.tracker.detail("No Grubhub data found in file.")
            return

        # Iterate one date at a time. Within each date we group venues that
        # share a cash sheet row so they're filled in a single pass.
        for grub_date in parser.get_dates():
            weekday = self._get_weekday_name(grub_date)
            if not weekday:
                continue
            if self._stopped("Grubhub"):
                return

            venues = parser.get_venues(grub_date)
            self.tracker.detail(
                f"{grub_date} ({weekday}) — {len(venues)} venue(s)")

            date_groups = self._group_grubhub_venues(
                grub_date, venues, parser, grubhub_filename)

            for (casheet_path, loc_in_casheet, loc_in_db), grp in date_groups.items():
                if self._stopped("Grubhub"):
                    return
                self._fill_grubhub_group(
                    grub_date, grp, casheet_path, loc_in_casheet, loc_in_db)

        # Surface anything we saw but couldn't map. These don't fail the run
        # but are useful hints for the user to update their config.
        unmapped_v = parser.get_unmapped_venues()
        unmapped_t = parser.get_unmapped_tenders()
        if unmapped_v:
            self.tracker.warning(f"Unmapped venues: {', '.join(unmapped_v)}")
        if unmapped_t:
            self.tracker.warning(f"Unmapped tenders: {', '.join(unmapped_t)}")

    def _group_grubhub_venues(self, grub_date, venues, parser, grubhub_filename):
        """
        Build a {(casheet_path, loc_in_casheet, loc_in_db): {venues, data_list}}
        map. Multiple Grubhub venues can land on the same cash sheet row — for
        example a base venue and its "Meal Transfer" sibling — so we aggregate.
        """
        date_groups = {}
        for venue in venues:
            if venue not in GRUBHUB_VENUE_MAP:
                self.tracker.add_failure(
                    venue, grubhub_filename,
                    "Venue not in GRUBHUB_VENUE_MAP")
                continue

            casheet_pattern, loc_in_casheet, loc_in_db = GRUBHUB_VENUE_MAP[venue]
            casheet_file = self.find_casheet_file(casheet_pattern)
            if casheet_file is None:
                self.tracker.add_failure(
                    venue, grubhub_filename,
                    f"No casheet file matching '{casheet_pattern}'")
                continue

            casheet_path = os.path.join(self.casheet_dir, casheet_file)
            data = parser.get_data_dict(grub_date, venue)
            data["date"] = grub_date

            key = (casheet_path, loc_in_casheet, loc_in_db)
            grp = date_groups.setdefault(key, {"venues": [], "data_list": []})
            grp["venues"].append(venue)
            grp["data_list"].append(data)
        return date_groups

    def _fill_grubhub_group(self, grub_date, grp, casheet_path,
                            loc_in_casheet, loc_in_db):
        """Aggregate (if needed), fold discounts in, and fill one cash row."""
        venue_names = grp["venues"]
        data_list = grp["data_list"]

        if len(data_list) > 1:
            label = f"{grub_date} : {', '.join(venue_names)} (combined)"
            raw_location = "Grubhub" + ", ".join(venue_names)
            merged_data = self._aggregate_data_dicts(data_list)
            venue_display = f"{venue_names[0]} +{len(venue_names) - 1} more"
        else:
            label = f"{grub_date} : {venue_names[0]}"
            raw_location = venue_names[0]
            merged_data = data_list[0]
            venue_display = venue_names[0]

        self._add_discounts(merged_data)

        # One compact summary line per cash row before we fill.
        sales = merged_data.get("total_sales", 0)
        tax = merged_data.get("tax", 0)
        count = merged_data.get("count", 0)
        self.tracker.detail(
            f"{venue_display:<40} ${sales:>9.2f}  tax ${tax:>6.2f}  "
            f"count {count}")

        self.fill_and_save(
            casheet_path, loc_in_casheet, raw_location, loc_in_db,
            merged_data, label, source="grubhub")


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
