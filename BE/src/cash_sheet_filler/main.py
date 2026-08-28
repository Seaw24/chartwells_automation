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
from .grubhub_order_count_parser import GrubhubOrderCountParser
from .excel_autofiller import ExcelAutofiller
from openpyxl.utils import get_column_letter

from .config import (
    REPORTS_CASHSHEET_MAP,
    GRUBHUB_VENUE_MAP,
    FILL_COL_MAP,
    REPORTS_FOLDER,
    CASH_SHEET_FOLDER,
    VERBOSE_TRACE,
)
from ..utils import strip_accents


def _normalize_venue(name):
    """Casefold and collapse whitespace so sloppy report spellings match."""
    return " ".join(name.split()).casefold()


def _compact_venue(name):
    """Only casefolded letters/digits — spelling skeleton for fuzzy matching."""
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def _is_subsequence(short, long):
    """True if *short*'s characters appear in *long* in order."""
    it = iter(long)
    return all(ch in it for ch in short)


# Normalized views of GRUBHUB_VENUE_MAP, built once at import time, so venue
# lookups survive case, whitespace, and light misspellings in Grubhub's
# hand-typed names.
_GRUBHUB_VENUE_MAP_NORM = {
    _normalize_venue(k): v for k, v in GRUBHUB_VENUE_MAP.items()
}
_GRUBHUB_VENUE_MAP_COMPACT = {
    _compact_venue(k): v for k, v in GRUBHUB_VENUE_MAP.items()
}


def _fuzzy_venue_map_entry(venue):
    """
    Last-resort venue lookup for misspelled names like "QDBA" → "Qdoba".

    A venue matches a map key when one compact form is a subsequence of the
    other (letters in order, a few dropped — vowel-skipping abbreviations),
    they are close in length, and exactly one key matches. Anything looser
    would risk landing numbers on the wrong register row.
    """
    compact = _compact_venue(venue)
    if len(compact) < 3:
        return None
    matches = [
        entry for key, entry in _GRUBHUB_VENUE_MAP_COMPACT.items()
        if abs(len(key) - len(compact)) <= 2
        and (_is_subsequence(compact, key) or _is_subsequence(key, compact))
    ]
    return matches[0] if len(matches) == 1 else None


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

    def trace(self, msg):
        """
        One line of step-by-step arithmetic, indented under a detail line.

        Silent unless ``verbose_trace`` is on. Emitted as 'detail' so the UI
        needs no new tag — these lines are secondary context, not status.
        """
        if VERBOSE_TRACE:
            self._emit("detail", f"     {msg}")

    def warning(self, msg):
        """Standalone warning line (not tied to a specific success/failure)."""
        self._emit("warning", f"   ⚠ {msg}")

    def add_success(self, location, filename, warning=None):
        self.successful.append({"location": location, "filename": filename})
        # Name the workbook. A failure line already carries it; success did
        # not, so a row written into the wrong file read exactly like a
        # correct one and there was nothing in the log to check.
        target = os.path.basename(filename) if filename else ""
        self._emit("success",
                   f"   ✓ {location}" + (f"  →  {target}" if target else ""))
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
        print_totals=False,
    ):
        self.casheet_dir = casheet_dir
        self.reports_dir = reports_dir
        self.tracker = ProcessingTracker(on_event=on_event)
        self.casheet_files = []
        self.stop_event = stop_event
        self.auto_print = auto_print
        self.printer_name = printer_name
        self.print_settings = print_settings
        # When on, the auto-print batch also includes the weekly Totals
        # sheet of every cash-sheet workbook in the folder.
        self.print_totals = print_totals
        self.filled_days_by_file= {}  # Track which weekdays we filled for optional auto-printing at the end
        self.db_manager = TendersDBManager()
        self.printable_reports = set()   # ← ADD: report basenames with non-zero data
        # Ambiguous pattern→workbook matches already reported this run.
        self._casheet_match_warnings = set()


    # ═══════════════════════════════════════════════════════════════
    #  MAIN EXECUTE
    # ═══════════════════════════════════════════════════════════════

    def execute(self):
        """
        Process all reports in ``reports_dir`` and fill the matching cash sheets.

        File-type detection by name:
            ``Operations Report*.csv``        -> Infor (1 venue per file)
            ``TransactionDetailbyVenue*.csv`` -> Grubhub tender detail
            ``SalesataGlance*.csv``           -> Grubhub order counts
            ``*.xls``                         -> Tavlo  (1 venue per file)

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
        infor_files, tavlo_files = [], []
        grubhub_files, grubhub_order_count_files = [], []
        for name in all_report_files:
            if name.lower().endswith(".csv"):
                if name.startswith("Operations Report"):
                    infor_files.append(name)
                elif name.startswith("TransactionDetailbyVenue"):
                    grubhub_files.append(name)
                elif self._is_grubhub_order_count_file(name):
                    grubhub_order_count_files.append(name)
            elif name.lower().endswith(".xls"):
                tavlo_files.append(name)

        infor_files.sort()
        tavlo_files.sort()
        grubhub_files.sort()
        grubhub_order_count_files.sort()

        total = (
            len(infor_files) + len(tavlo_files) + len(grubhub_files)
            + len(grubhub_order_count_files)
        )
        if total == 0:
            self.tracker.log("No report files found.")
            return self.tracker

        # One concise inventory line — the UI doesn't need a banner.
        self.tracker.log(
            f"Found {total} file(s):  "
            f"{len(infor_files)} Infor · "
            f"{len(tavlo_files)} Tavlo · "
            f"{len(grubhub_files)} Grubhub tender · "
            f"{len(grubhub_order_count_files)} Grubhub count"
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

        grubhub_order_counts = self._load_grubhub_order_counts(
            grubhub_order_count_files)
        if grubhub_files and not grubhub_order_counts:
            self.tracker.warning(
                "No Sales-at-a-Glance order-count file found; "
                "Grubhub count cells will be left unchanged.")

        # Grubhub: one tender file contains many venues x many dates.
        for name in grubhub_files:
            if self._stopped("Grubhub"):
                return self.tracker
            path = os.path.join(self.reports_dir, name)
            self.process_grubhub(
                GrubhubParser(path, self.tracker), path, grubhub_order_counts)

        # ── 4. Final summary block ─────────────────────────────────────────
        self.tracker.print_summary()

        # Print reports then cash sheets if enabled. The Totals option can
        # print on its own even when nothing was filled this run.
        if self.auto_print and (self.filled_days_by_file or self.print_totals):
            from ..printer import ExcelPrinter
            printer = ExcelPrinter(
                self.printer_name,
                self.tracker,
                settings=self.print_settings,
            )
            printer.print_all(
                self.reports_dir,
                self.casheet_dir,
                self._build_print_map(),
                self.printable_reports,
            )
        elif self.auto_print:
            self.tracker.log("Auto-print skipped: no filled cash sheets.")

        return self.tracker

    # ═══════════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════════

    def _build_print_map(self):
        """
        Return {casheet_path: {sheet names}} for the auto-print batch.

        Normally only the weekday tabs filled this run are printed. When the
        "Totals pages" print option is on, the weekly Totals sheet of EVERY
        cash-sheet workbook in the folder is added to the same batch —
        including workbooks nothing was filled into. The workbooks were
        already saved during autofill, so the Totals formulas pick up the
        new figures when Excel opens each file to print.
        """
        print_map = {path: set(days)
                     for path, days in self.filled_days_by_file.items()}
        if self.print_totals:
            self.tracker.log(
                "Totals option is on — printing the Totals sheet "
                "for every location.")
            for f in self.casheet_files:
                if f.lower().endswith(".xlsx") and not f.startswith("~$"):
                    path = os.path.join(self.casheet_dir, f)
                    print_map.setdefault(path, set()).add("Totals")
        return print_map

    def _stopped(self, stage):
        """Return True (and emit one line) if the user pressed Stop."""
        if self.stop_event and self.stop_event.is_set():
            self.tracker.log(f"Stopped during {stage} processing.")
            return True
        return False

    @staticmethod
    def _is_grubhub_order_count_file(filename):
        normalized = "".join(ch for ch in filename.lower() if ch.isalnum())
        return normalized.startswith("salesataglance")

    def _load_grubhub_order_counts(self, filenames):
        """Parse and merge all Grubhub Sales-at-a-Glance count files."""
        merged = None
        for name in filenames:
            if self._stopped("Grubhub order-count"):
                return merged

            path = os.path.join(self.reports_dir, name)
            self.tracker.section(f"Grubhub order counts: {name}")
            parser = GrubhubOrderCountParser(path, self.tracker)
            if not parser.parse(self.stop_event):
                self.tracker.add_failure(
                    "Grubhub order counts", name, "Parse failed")
                continue
            self._trace_order_counts(parser)

            # Grubhub reports are autofill-only; they are never printed,
            # so they are not added to ``printable_reports``.
            if merged is None:
                merged = parser
            else:
                merged.merge_from(parser)

        if merged:
            unmapped = {
                v for v in merged.get_unmapped_venues()
                if not self._resolves_in_venue_map(v)
            }
            if unmapped:
                self.tracker.warning(
                    "Unmapped Grubhub order-count venues: "
                    f"{', '.join(sorted(unmapped))}")
        return merged

    def _trace_order_counts(self, parser):
        """
        Show what one Sales-at-a-Glance file contributes, venue by venue.

        Each line names the figure taken from the report and the cash-sheet
        column it will land in, so the log reads as "this number goes there":
        regular venues feed the count column, Swoop Swap siblings feed their
        order count to the Less-transfer column, and Choose Your Own
        Adventure siblings contribute their merchant sales to the 1M Meal
        column. Venues with no mapping (directly or through their base
        venue) are flagged inline.
        """
        if not VERBOSE_TRACE:
            return

        def col(key):
            idx = FILL_COL_MAP.get(key)
            return get_column_letter(idx) if idx else "?"

        t = self.tracker
        for date in parser.get_dates():
            venues = parser.get_venues(date)
            t.trace(f"┌ Sales-at-a-Glance · {date}  ({len(venues)} venue(s))")
            total = 0
            for venue in venues:
                count = parser.get_count(date, venue) or 0
                total += count
                swoop_base = self._swoop_base_venue(venue)
                cyoa_base = self._cyoa_base_venue(venue)
                if swoop_base:
                    value = f"{count:>10} order(s)"
                    dest = (f"→ Less transfer ({col('swoop_swap')}) "
                            f"on '{swoop_base}' row")
                elif cyoa_base:
                    sales = parser.get_sales(date, venue) or 0.0
                    value = f"${sales:>9.2f} sales"
                    dest = f"→ 1M Meal ({col('cyoa')}) on '{cyoa_base}' row"
                else:
                    value = f"{count:>10} order(s)"
                    dest = f"→ count ({col('count')})"
                mapped = self._venue_map_entry(
                    swoop_base or cyoa_base or venue) is not None
                note = "" if mapped else "   ⚠ no venue mapping"
                t.trace(f"│ {venue:<44} {value}  {dest}{note}")
            t.trace(f"└ {total} order(s) on {date}")

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
        if data.get("count") or 0:
            return True
        if data.get("swoop_swap") or 0:
            return True
        if data.get("cyoa") or 0:
            return True
        if any(data.get("tenders", {}).values()):
            return True
        return False

    def find_casheet_file(self, casheet_pattern):
        """
        Find the cash-sheet workbook that *casheet_pattern* names.

        A workbook is named "<venue> Master.xlsx", so the venue part is
        whatever precedes "Master". That and the configured name are both
        reduced to letters and digits — lower-cased, no spaces or punctuation,
        so "City's Edge" still matches "City_s Edge Master.xlsx" — and then
        compared outright.

        The test used to be "does the file name contain the pattern", which is
        what broke Shake Smart: "shakesmart" also sits inside "unionshakesmart",
        so two workbooks matched and whichever the directory listing yielded
        first won. On a drive that does not sort its entries that was the wrong
        one every run — the Student Life Center's numbers went into the Union's
        workbook and its own sheet stayed blank, while the log still read
        "succeeded". An exact comparison leaves nothing to tie-break, so
        directory order stops mattering.
        """
        target = _compact_venue(casheet_pattern)
        if not target:
            return None

        # Shortest name first, then alphabetical. Two files can still reduce
        # to the same venue key — "… Master copy.xlsx" — and the least
        # decorated one is the real workbook. "~$" files are Excel's lock file
        # for a workbook someone still has open.
        matches = sorted(
            (f for f in self.casheet_files
             if not f.startswith("~$")
             and self._casheet_venue_key(f) == target),
            key=lambda f: (len(f), f.casefold()),
        )
        if not matches:
            return None
        if len(matches) > 1:
            self._warn_casheet_match(
                f"'{casheet_pattern}' matches {len(matches)} cash sheets "
                f"({', '.join(matches)}) — using '{matches[0]}'")
        return matches[0]

    @staticmethod
    def _casheet_venue_key(filename):
        """
        The venue part of a cash-sheet file name, as letters and digits only.

        "Shake Smart Master.xlsx" -> "shakesmart". Everything from "Master"
        onward is dropped; a workbook that doesn't carry the word keeps its
        whole name, so a plain "Shake Smart.xlsx" still resolves.
        """
        stem = os.path.splitext(filename)[0]
        cut = stem.casefold().find("master")
        return _compact_venue(stem[:cut] if cut > 0 else stem)

    def _warn_casheet_match(self, msg):
        """Warn once per run — find_casheet_file runs per venue, per date."""
        if msg not in self._casheet_match_warnings:
            self._casheet_match_warnings.add(msg)
            self.tracker.warning(msg)

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

        self.tracker.add_success(label, casheet_path)
        if self._report_has_data(data_dict):
            self.filled_days_by_file.setdefault(casheet_path, set()).add(week_day)

        # Persist a record in the analytics DB. Failure here is logged but
        # never blocks the autofill — the cash sheet is already saved.
        saved = self.db_manager.insert_record(
            report_date=data_dict.get("date"),
            raw_location=raw_location,
            location=location_in_db,
            total_sales=data_dict.get("total_sales", 0.0),
            tax=data_dict.get("tax", 0.0),
            meal_count=data_dict.get("count") or 0,
            tenders=data_dict.get("tenders", {}),
            source=source,
        )
        if not saved:
            self.tracker.log("   ⚠ DB record was not saved")
        return True

    # ═══════════════════════════════════════════════════════════════
    #  PROCESS ONE INFOR / TAVLO REPORT  (one file = one venue)
    # ═══════════════════════════════════════════════════════════════

    def _trace_single_report(self, data):
        """
        Show an Infor/Tavlo record's figures before they're written.

        There is no aggregation, discount fold, or fee adjustment on this path —
        one file is one venue for one date — so the trace is just the parsed
        numbers plus the same tenders-vs-sales balance check Grubhub gets.
        """
        if not VERBOSE_TRACE:
            return

        t = self.tracker
        count = data.get("count")
        t.trace(f"┌ {data.get('location')} · {data.get('date')}  "
                "(single venue — no aggregation, no fee/discount adjustment)")
        t.trace(f"│ {'sales':<12}: ${data.get('total_sales', 0.0):.2f}   "
                f"tax ${data.get('tax', 0.0):.2f}   "
                f"count {count if count is not None else 'not filled'}")

        live = {k: v for k, v in data.get("tenders", {}).items() if v}
        t.trace(f"│ {'tenders':<12}: " + (" · ".join(
            f"{k} ${v:.2f}" for k, v in sorted(live.items())) or "none"))

        tender_sum = sum(data.get("tenders", {}).values())
        delta = tender_sum - data.get("total_sales", 0.0)
        mark = "✓ balances" if abs(delta) < 0.005 else f"✗ off by ${delta:+.2f}"
        t.trace(f"│ {'balance':<12}: tenders ${tender_sum:.2f} vs sales "
                f"${data.get('total_sales', 0.0):.2f}  {mark}")

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
        self._trace_single_report(data)

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
        to both ``total_sales`` and the ``visa`` tender column. Adding to a
        tender as well as the total is what keeps ``sum(tenders)`` equal to
        ``total_sales``, which is what the cash sheet's over/short formula
        checks.

        Returns ``(discount, before)`` where ``before`` is the
        ``(visa, total_sales)`` pair prior to the fold, or None if there was
        no discount to apply — the caller uses this to trace the change.
        """
        disc = data.get("discounts", 0.0)
        before = None
        if disc:
            data.setdefault("tenders", {})
            before = (data["tenders"].get("visa", 0.0),
                      data.get("total_sales", 0.0))
            data["tenders"]["visa"] = data["tenders"].get("visa", 0.0) + disc
            data["total_sales"] = data.get("total_sales", 0.0) + disc
        data.pop("discounts", None)
        # Returned so the caller can trace the fold without re-deriving it.
        return disc, before

    def _aggregate_data_dicts(self, data_list):
        """Sum multiple data dicts that target the same cash-sheet row."""
        # Sibling venues (Swoop Swap / Choose Your Own Adventure) never
        # contribute to the regular count cell, so a group with only siblings
        # leaves it None (untouched).
        has_normal = any(
            not d.get("is_swoop") and not d.get("is_cyoa") for d in data_list)
        merged = {
            "date": data_list[0]["date"],
            "count": 0 if has_normal else None,
            "swoop_swap": None,
            "cyoa": None,
            "total_sales": 0.0,
            "tax": 0.0,
            "tenders": {},
            "discounts": 0.0,
            "flex_count": 0,
        }
        for d in data_list:
            if d.get("is_swoop"):
                swoop = d.get("swoop_swap")
                if swoop is not None:
                    merged["swoop_swap"] = (
                        merged["swoop_swap"] or 0) + swoop
            elif d.get("is_cyoa"):
                cyoa = d.get("cyoa")
                if cyoa is not None:
                    merged["cyoa"] = (merged["cyoa"] or 0.0) + cyoa
            else:
                count = d.get("count")
                if count is None:
                    merged["count"] = None
                elif merged["count"] is not None:
                    merged["count"] += count
            # Sibling sales and tenders merge into the base row like any
            # other register — a Swoop Swap's $1.72 of Flex is still Flex.
            merged["total_sales"] += d.get("total_sales", 0.0)
            merged["tax"] += d.get("tax", 0.0)
            merged["discounts"] += d.get("discounts", 0.0)
            # A Swoop Swap's flex payment is still a flex payment — the count
            # follows the same merge rule its dollars do.
            merged["flex_count"] += d.get("flex_count") or 0
            for k, v in d.get("tenders", {}).items():
                merged["tenders"][k] = merged["tenders"].get(k, 0.0) + v
        return merged

    def process_grubhub(self, parser, grubhub_path, order_counts=None):
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
        # Grubhub reports are autofill-only; they are never printed.

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
                grub_date, venues, parser, grubhub_filename, order_counts)

            for (casheet_path, loc_in_casheet, loc_in_db), grp in date_groups.items():
                if self._stopped("Grubhub"):
                    return
                self._fill_grubhub_group(
                    grub_date, grp, casheet_path, loc_in_casheet, loc_in_db)

        # Surface anything we saw but couldn't map. These don't fail the run
        # but are useful hints for the user to update their config.
        # Sibling venues resolve through their base venue's map entry, so
        # only report venues that are unmapped even after that fallback.
        unmapped_v = {
            v for v in parser.get_unmapped_venues()
            if not self._resolves_in_venue_map(v)
        }
        unmapped_t = parser.get_unmapped_tenders()
        if unmapped_v:
            self.tracker.warning(f"Unmapped venues: {', '.join(unmapped_v)}")
        if unmapped_t:
            self.tracker.warning(f"Unmapped tenders: {', '.join(unmapped_t)}")

    def _group_grubhub_venues(self, grub_date, venues, parser,
                              grubhub_filename, order_counts=None):
        """
        Build a {(casheet_path, loc_in_casheet, loc_in_db): {venues, data_list}}
        map. Multiple Grubhub venues can land on the same cash sheet row — for
        example a base venue and its "Meal Transfer" sibling — so we aggregate.
        """
        date_groups = {}
        for venue in venues:
            # Sibling venues reuse the base venue's config entry and land on
            # the same cash-sheet row. Their sales/tenders merge into the row
            # like any register, and each also fills a dedicated column:
            #   "X - Swoop Swap Shop"            → at-a-glance order count
            #                                      → Less transfer (G)
            #   "X - Choose Your Own Adventure"  → at-a-glance sales
            #                                      → 1M Meal (H)
            swoop_base = self._swoop_base_venue(venue)
            cyoa_base = self._cyoa_base_venue(venue)
            map_name = swoop_base or cyoa_base or venue
            entry = self._venue_map_entry(map_name)
            if entry is None:
                self.tracker.add_failure(
                    venue, grubhub_filename,
                    "Venue not in GRUBHUB_VENUE_MAP")
                continue

            casheet_pattern, loc_in_casheet, loc_in_db = entry
            casheet_file = self.find_casheet_file(casheet_pattern)
            if casheet_file is None:
                self.tracker.add_failure(
                    venue, grubhub_filename,
                    f"No casheet file matching '{casheet_pattern}'")
                continue

            casheet_path = os.path.join(self.casheet_dir, casheet_file)
            data = parser.get_data_dict(grub_date, venue)
            data["date"] = grub_date
            data["is_swoop"] = swoop_base is not None
            data["is_cyoa"] = cyoa_base is not None
            data["count"] = None
            data["swoop_swap"] = None
            data["cyoa"] = None
            if data["is_swoop"]:
                value = (order_counts.get_count(grub_date, venue)
                         if order_counts else None)
                data["swoop_swap"] = value
                missing_bucket = "missing_swoop"
            elif data["is_cyoa"]:
                value = (order_counts.get_sales(grub_date, venue)
                         if order_counts else None)
                data["cyoa"] = value
                missing_bucket = "missing_cyoa"
            else:
                value = (order_counts.get_count(grub_date, venue)
                         if order_counts else None)
                data["count"] = value
                missing_bucket = "missing_counts"

            key = (casheet_path, loc_in_casheet, loc_in_db)
            grp = date_groups.setdefault(
                key,
                {"venues": [], "data_list": [], "missing_counts": [],
                 "missing_swoop": [], "missing_cyoa": []},
            )
            grp["venues"].append(venue)
            grp["data_list"].append(data)
            if value is None:
                grp[missing_bucket].append(venue)
        return date_groups

    @staticmethod
    def _sibling_base_venue(venue, marker):
        """
        Strip a sibling-venue *marker*; None if the venue doesn't carry it.

        Grubhub venue names are hand-typed, so the marker is not reliably the
        last thing on the line. Stray separators trail it ("QDBA - Swoop Swap
        Shop -"), and some venues append a campus qualifier after it ("Union
        Food Court - Swoop Swap - Utah"). Everything from the marker rightward
        is the sibling label either way, so the base venue is whatever comes
        before it — both of those yield "QDBA" and "Union Food Court".
        """
        clean = " ".join(venue.split())
        idx = clean.casefold().find(marker)
        if idx < 0:
            return None
        return clean[:idx].strip(" -–—").strip() or None

    @staticmethod
    def _venue_map_entry(venue):
        """GRUBHUB_VENUE_MAP lookup tolerant of case/whitespace differences."""
        entry = GRUBHUB_VENUE_MAP.get(venue)
        if entry is None:
            entry = _GRUBHUB_VENUE_MAP_NORM.get(_normalize_venue(venue))
        return entry

    def _resolves_in_venue_map(self, venue):
        """True if the venue, or its sibling base, has a map entry."""
        base = self._swoop_base_venue(venue) or self._cyoa_base_venue(venue)
        return self._venue_map_entry(base or venue) is not None

    # Grubhub types the Swoop Swap marker by hand and sometimes drops the
    # "Shop" — "Greek Kabob - Swoop Swap". Longest first, so the full marker
    # always wins and never leaves a stray "Shop" on the base venue name.
    _SWOOP_MARKERS = ("swoop swap shop", "swoop swap")

    @classmethod
    def _swoop_base_venue(cls, venue):
        """
        'City Edge - Swoop Swap Shop' -> 'City Edge'; else None.

        Also 'Union Food Court - Swoop Swap - Utah' -> 'Union Food Court' —
        the campus qualifier after the marker is part of the sibling label.
        """
        for marker in cls._SWOOP_MARKERS:
            base = cls._sibling_base_venue(venue, marker)
            if base:
                return base
        return None

    @classmethod
    def _cyoa_base_venue(cls, venue):
        """'Basecamp - Choose Your Own Adventure' -> 'Basecamp'; else None."""
        return cls._sibling_base_venue(venue, "choose your own adventure")

    def _trace_grubhub_group(self, grub_date, loc_in_casheet, loc_in_db,
                             venue_names, data_list, merged, disc, disc_before):
        """
        Show how several venues become one cash-sheet row.

        Every line is arithmetic the reader can check by hand: which venue
        contributed what, how the discount moved, and whether the tenders add
        up to the sales figure. The balance line is the same equality the cash
        sheet's over/short column computes, so a mismatch here predicts a
        non-zero over/short before the workbook is even opened.
        """
        if not VERBOSE_TRACE:
            return

        t = self.tracker
        t.trace(f"┌ row '{loc_in_casheet}' ({loc_in_db}) · {grub_date} ← "
                f"{' + '.join(venue_names)}")

        def sum_line(label, values, total, money=True):
            fmt = (lambda v: f"${v:.2f}") if money else (lambda v: f"{v}")
            if len(values) > 1:
                t.trace(f"│ {label:<12}: "
                        f"{' + '.join(fmt(v) for v in values)} = {fmt(total)}")
            else:
                t.trace(f"│ {label:<12}: {fmt(total)}")

        counts = [d.get("count") for d in data_list
                  if not d.get("is_swoop") and not d.get("is_cyoa")]
        if any(c is None for c in counts):
            t.trace(f"│ {'order count':<12}: missing for "
                    f"{sum(1 for c in counts if c is None)} venue(s) "
                    "— count cell will be left unchanged")
        elif counts:
            sum_line("order count", counts, sum(counts), money=False)
        t.trace("│               (order counts come from Sales-at-a-Glance, "
                "not the tender report)")

        swoops = [d.get("swoop_swap") for d in data_list
                  if d.get("swoop_swap") is not None]
        if swoops:
            sum_line("less transfer", swoops, sum(swoops), money=False)
            t.trace("│               (Swoop Swap order counts → column G)")

        cyoas = [d.get("cyoa") for d in data_list
                 if d.get("cyoa") is not None]
        if cyoas:
            sum_line("1M meal", cyoas, sum(cyoas))
            t.trace("│               (Choose Your Own Adventure sales "
                    "→ column H)")

        # total_sales already includes the discount at this point, so subtract
        # it back out to show the pre-fold contributions honestly.
        sales = [d.get("total_sales", 0.0) for d in data_list]
        sum_line("sales", sales, merged["total_sales"] - disc)
        sum_line("tax", [d.get("tax", 0.0) for d in data_list], merged["tax"])

        if disc and disc_before:
            visa_before, sales_before = disc_before
            t.trace(f"│ {'discounts':<12}: ${disc:.2f} added back → "
                    f"visa ${visa_before:.2f} → "
                    f"${merged['tenders']['visa']:.2f}, "
                    f"sales ${sales_before:.2f} → "
                    f"${merged['total_sales']:.2f}")
        else:
            t.trace(f"│ {'discounts':<12}: none")

        live = {k: v for k, v in merged.get("tenders", {}).items() if v}
        t.trace(f"│ {'tenders':<12}: " + (" · ".join(
            f"{k} ${v:.2f}" for k, v in sorted(live.items())) or "none"))

        flex_counts = [d.get("flex_count") or 0 for d in data_list]
        if any(flex_counts):
            sum_line("flex payments", flex_counts, merged.get("flex_count", 0),
                     money=False)
            t.trace("│               (rows tendered in Flex Dollars → "
                    "flex column, one row under TOTALS)")

        tender_sum = sum(merged.get("tenders", {}).values())
        delta = tender_sum - merged["total_sales"]
        mark = "✓ balances" if abs(delta) < 0.005 else f"✗ off by ${delta:+.2f}"
        t.trace(f"│ {'balance':<12}: tenders ${tender_sum:.2f} vs sales "
                f"${merged['total_sales']:.2f}  {mark}")

    def _fill_grubhub_group(self, grub_date, grp, casheet_path,
                            loc_in_casheet, loc_in_db):
        """Aggregate (if needed), fold discounts in, and fill one cash row."""
        venue_names = grp["venues"]
        data_list = grp["data_list"]
        missing_counts = grp.get("missing_counts", [])
        missing_swoop = grp.get("missing_swoop", [])
        missing_cyoa = grp.get("missing_cyoa", [])

        # Always aggregate — even a single-venue group goes through the same
        # sibling routing, so a Swoop sibling that shows up alone is still
        # handled correctly.
        merged_data = self._aggregate_data_dicts(data_list)
        if len(data_list) > 1:
            label = f"{grub_date} : {', '.join(venue_names)} (combined)"
            # Just the venue names, matching the single-venue branch below.
            # Provenance is already recorded by the DB's `source` column, and
            # the old "Grubhub" prefix was concatenated without a separator.
            raw_location = ", ".join(venue_names)
            venue_display = f"{venue_names[0]} +{len(venue_names) - 1} more"
        else:
            label = f"{grub_date} : {venue_names[0]}"
            raw_location = venue_names[0]
            venue_display = venue_names[0]

        disc, disc_before = self._add_discounts(merged_data)
        self._trace_grubhub_group(
            grub_date, loc_in_casheet, loc_in_db, venue_names, data_list,
            merged_data, disc, disc_before)

        if missing_counts:
            merged_data["count"] = None
            self.tracker.warning(
                "Missing Grubhub order count for "
                f"{', '.join(missing_counts)} on {grub_date}; "
                "count cell left unchanged.")
        if missing_swoop:
            merged_data["swoop_swap"] = None
            self.tracker.warning(
                "Missing Grubhub order count for "
                f"{', '.join(missing_swoop)} on {grub_date}; "
                "Less-transfer cell left unchanged.")
        if missing_cyoa:
            merged_data["cyoa"] = None
            self.tracker.warning(
                "Missing Grubhub merchant sales for "
                f"{', '.join(missing_cyoa)} on {grub_date}; "
                "1M Meal cell left unchanged.")

        # One compact summary line per cash row before we fill.
        sales = merged_data.get("total_sales", 0)
        tax = merged_data.get("tax", 0)
        count = merged_data.get("count", 0)
        count_text = count if count is not None else "not filled"
        line = (f"{venue_display:<40} ${sales:>9.2f}  tax ${tax:>6.2f}  "
                f"count {count_text}")
        if merged_data.get("swoop_swap") is not None:
            line += f"  swoop count {merged_data['swoop_swap']}"
        if merged_data.get("cyoa") is not None:
            line += f"  1M meal ${merged_data['cyoa']:.2f}"
        if merged_data.get("flex_count"):
            line += f"  flex payments {merged_data['flex_count']}"
        self.tracker.detail(line)

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
