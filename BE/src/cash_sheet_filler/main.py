"""
Main Execution Module
Processes Infor (CSV), Tavlo (XLS/XML), and Grubhub (CSV) reports
and fills the corresponding cash sheet Excel workbooks.
"""

import os
import traceback
from datetime import date, timedelta
from dateutil.parser import parse as dateutil_parse
from openpyxl import load_workbook

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


# ═══════════════════════════════════════════════════════════════
#  PROCESSING TRACKER
# ═══════════════════════════════════════════════════════════════

class ProcessingTracker:
    """Tracks successes, failures, and warnings across all reports."""

    def __init__(self):
        self.successful = []
        self.failed = []
        self.warnings = []

    def add_success(self, location, filename, warning=None):
        self.successful.append({"location": location, "filename": filename})
        if warning:
            self.warnings.append(
                {"location": location, "filename": filename, "msg": warning})

    def add_failure(self, location, filename, message):
        self.failed.append(
            {"location": location, "filename": filename, "msg": message})

    def print_summary(self):
        total = len(self.successful) + len(self.failed)
        print("\n" + "=" * 70)
        print("PROCESSING SUMMARY")
        print(f"  Successful : {len(self.successful)}")
        print(f"  Failed     : {len(self.failed)}")
        print(f"  Warnings   : {len(self.warnings)}")
        print(f"  Total      : {total}")

        if self.warnings:
            print("\nWARNINGS:")
            for w in self.warnings:
                print(f"  - {w['location']}: {w['msg']}")

        if self.failed:
            print("\nFAILED:")
            for f in self.failed:
                loc = f["location"] or "Unknown"
                print(f"  - {loc} ({f['filename']}): {f['msg']}")

        print("=" * 70 + "\n")


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def get_weekday_name(report_date):
    """Convert a date string (e.g. MM/DD/YYYY) to its weekday name."""
    try:
        return dateutil_parse(report_date).strftime("%A")
    except (ValueError, TypeError):
        print(f"  Error: Could not parse date '{report_date}'.")
        print(f"  Please use MM/DD/YYYY or similar format.")
        return None


def find_casheet_file(casheet_pattern, casheet_files):
    """Find a cash-sheet file whose name contains *casheet_pattern*."""
    for f in casheet_files:
        if casheet_pattern.strip() in f.strip():
            return f
    return None


def fill_and_save(casheet_path, location_in_casheet, weekday, data_dict, tracker, label):
    """
    Open a cash-sheet workbook, fill one location row, save, and validate.

    Args:
        casheet_path:  Full path to the .xlsx file
        location_in_casheet:  Row label to search for in the sheet
        weekday:  Worksheet tab name (e.g. "Monday")
        data_dict:  Dict with keys date, count, total_sales, tax, tenders
        tracker:  ProcessingTracker
        label:  Human-readable label for log messages

    Returns:
        bool
    """
    filler = ExcelAutofiller(casheet_path, location_in_casheet, weekday)

    if not filler.open_workbook():
        tracker.add_failure(label, casheet_path, "Failed to open workbook")
        return False

    if not filler.filling(data_dict):
        tracker.add_failure(label, casheet_path, "Failed to fill data")
        filler.close()
        return False

    valid = filler.save()
    filler.close()

    if valid:
        tracker.add_success(label, casheet_path)
    else:
        tracker.add_success(label, casheet_path,
                            warning="Tender over/short != 0")

    return True


# ═══════════════════════════════════════════════════════════════
#  PROCESS ONE INFOR / TAVLO REPORT  (one file = one venue)
# ═══════════════════════════════════════════════════════════════

def process_single_report(report_parser, casheet_dir, weekday,
                          report_filename, tracker, casheet_files):
    """
    Parse an Infor or Tavlo report and fill the matching cash sheet.

    Args:
        report_parser:  An InforParser or TavloParser instance (already constructed).
        casheet_dir:    Folder containing cash-sheet Excel files.
        weekday:        Worksheet tab name.
        report_filename: Name of the source report file (for logging).
        tracker:        ProcessingTracker.
        casheet_files:  List of filenames in casheet_dir.
    """
    print(f"\n--- {report_filename} ---")

    # 1. Parse
    if not report_parser.parse():
        tracker.add_failure("Unknown", report_filename, "Parse failed")
        return

    data = report_parser.get_data_dict()
    location = data["location"]
    print(f"  Location: {location}")

    # 2. Look up cash-sheet mapping
    if location not in REPORTS_CASHSHEET_MAP:
        tracker.add_failure(location, report_filename,
                            "Location not in REPORTS_CASHSHEET_MAP")
        return

    casheet_pattern, location_in_casheet = REPORTS_CASHSHEET_MAP[location]

    # 3. Find the cash-sheet file
    casheet_file = find_casheet_file(casheet_pattern, casheet_files)
    if casheet_file is None:
        tracker.add_failure(location, report_filename,
                            f"No casheet file matching '{casheet_pattern}'")
        return

    # 4. Fill and save
    casheet_path = os.path.join(casheet_dir, casheet_file)
    fill_and_save(casheet_path, location_in_casheet, weekday,
                  data, tracker, f"{location} ({report_filename})")


# ═══════════════════════════════════════════════════════════════
#  PROCESS GRUBHUB REPORT  (one file = ALL venues × ALL dates)
# ═══════════════════════════════════════════════════════════════

def _aggregate_data_dicts(data_list):
    """
    Merge/sum multiple data dicts that target the same cash-sheet row.

    Args:
        data_list: List of dicts with keys date, count, total_sales, tax, tenders.

    Returns:
        A single merged dict with summed values.
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


def process_grubhub(grubhub_path, casheet_dir,
                    tracker, casheet_files):
    """
    Parse a Grubhub CSV and fill each venue's cash sheet for every date.

    Groups ALL data by cash-sheet file across ALL dates, so each workbook is
    opened only once (avoids corruption from repeated open/save cycles).
    Venues that share a row are aggregated (summed).

    Args:
        grubhub_path:     Full path to the Grubhub CSV.
        casheet_dir:      Folder containing cash-sheet Excel files.
        tracker:          ProcessingTracker.
        casheet_files:    List of filenames in casheet_dir.
    """
    grubhub_filename = os.path.basename(grubhub_path)
    print(f"\n--- Grubhub: {grubhub_filename} ---")

    parser = GrubhubParser(grubhub_path)
    if not parser.parse():
        tracker.add_failure("Grubhub", grubhub_filename, "Parse failed")
        return

    if not parser.get_dates():
        print(f"  No Grubhub data found in file.")
        return

    # ── Step 1: Collect ALL data grouped by casheet_path ──────────────
    # Structure: {casheet_path: [(weekday, location, merged_data, label), ...]}
    file_tasks = {}

    for date in parser.get_dates():
        weekday = get_weekday_name(date)
        if not weekday:
            continue
        venues = parser.get_venues(date)
        print(f"\n  Date: {date} ({weekday})  —  {len(venues)} venue(s)")

        # Group venues by (casheet_path, location) for this date
        date_groups = {}
        for venue in venues:
            if venue not in GRUBHUB_VENUE_MAP:
                tracker.add_failure(venue, grubhub_filename,
                                    "Venue not in GRUBHUB_VENUE_MAP")
                continue

            casheet_pattern, location_in_casheet = GRUBHUB_VENUE_MAP[venue]
            casheet_file = find_casheet_file(casheet_pattern, casheet_files)
            if casheet_file is None:
                tracker.add_failure(venue, grubhub_filename,
                                    f"No casheet file matching '{casheet_pattern}'")
                continue

            casheet_path = os.path.join(casheet_dir, casheet_file)
            data = parser.get_data_dict(date, venue)
            data["date"] = date

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
                merged_data = _aggregate_data_dicts(data_list)
                label = f"{date} : Grubhub → {', '.join(venue_names)} (combined)"
            else:
                merged_data = data_list[0]
                label = f"{date} : Grubhub → {venue_names[0]}"

            if casheet_path not in file_tasks:
                file_tasks[casheet_path] = []
            file_tasks[casheet_path].append(
                (weekday, location_in_casheet, merged_data, label))

    # ── Step 2: Open each workbook once, fill all dates, save once ────
    for casheet_path, tasks in file_tasks.items():
        wb = None
        try:
            wb = load_workbook(casheet_path)
        except Exception as e:
            for (_, _, _, label) in tasks:
                tracker.add_failure(label, casheet_path,
                                    f"Failed to open workbook: {e}")
            continue

        all_ok = True
        for (weekday, location_in_casheet, merged_data, label) in tasks:
            try:
                # Find sheet (case-insensitive)
                sheet_map = {s.lower(): s for s in wb.sheetnames}
                actual_sheet = sheet_map.get(weekday.lower())
                if actual_sheet is None:
                    tracker.add_failure(label, casheet_path,
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
                    tracker.add_failure(label, casheet_path,
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

                print(f"  ✓ {label} → row {target_row}")
                tracker.add_success(label, casheet_path)

            except Exception as e:
                tracker.add_failure(label, casheet_path, f"Fill error: {e}")
                all_ok = False

        # Save once for the entire workbook
        try:
            wb.save(casheet_path)
            print(f"  💾 Saved: {os.path.basename(casheet_path)}")
        except PermissionError:
            print(
                f"  ❌ Cannot save {os.path.basename(casheet_path)}: file is open")
        except Exception as e:
            print(f"  ❌ Save error for {os.path.basename(casheet_path)}: {e}")
        finally:
            wb.close()

    # Log any unmapped items
    unmapped_v = parser.get_unmapped_venues()
    unmapped_t = parser.get_unmapped_tenders()
    if unmapped_v:
        print(f"\n  Unmapped venues : {unmapped_v}")
    if unmapped_t:
        print(f"  Unmapped tenders: {unmapped_t}")


# ═══════════════════════════════════════════════════════════════
#  MAIN EXECUTE
# ═══════════════════════════════════════════════════════════════

def execute(reports_dir, casheet_dir, weekday, report_date):
    """
    Process all reports in *reports_dir* and fill cash sheets in *casheet_dir*.

    File-type detection:
        .csv starting with "Operations Report" → Infor
        .csv starting with "SalesbyVenue"       → Grubhub
        .xls                                    → Tavlo
    """
    tracker = ProcessingTracker()

    # ── Gather files ──────────────────────────────────────────────────
    try:
        all_report_files = os.listdir(reports_dir)
    except (FileNotFoundError, PermissionError) as e:
        print(f"  Cannot access reports folder: {e}")
        return

    try:
        casheet_files = os.listdir(casheet_dir)
    except (FileNotFoundError, PermissionError) as e:
        print(f"  Cannot access cash-sheets folder: {e}")
        return

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
        print("  No report files found.")
        return

    print(f"\nFound {len(infor_files)} Infor, {len(tavlo_files)} Tavlo, "
          f"{len(grubhub_files)} Grubhub file(s)")

    # ── Process Infor (CSV, one venue per file) ───────────────────────
    for name in infor_files:
        path = os.path.join(reports_dir, name)
        parser = InforParser(path, report_date)
        process_single_report(parser, casheet_dir, weekday,
                              name, tracker, casheet_files)

    # ── Process Tavlo (XLS/XML, one venue per file) ───────────────────
    for name in tavlo_files:
        path = os.path.join(reports_dir, name)
        parser = TavloParser(path, report_date)
        process_single_report(parser, casheet_dir, weekday,
                              name, tracker, casheet_files)

    # ── Process Grubhub (CSV, all venues in one file) ─────────────────
    # Convert report_date (MM/DD/YYYY) to YYYY-MM-DD for Grubhub lookup
    try:
        target_date = dateutil_parse(report_date).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        target_date = None

    if target_date:
        for name in grubhub_files:
            path = os.path.join(reports_dir, name)
            process_grubhub(path, casheet_dir,
                            tracker, casheet_files)

    # ── Summary ───────────────────────────────────────────────────────
    tracker.print_summary()


# ═══════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Resolve folder paths — use config values or prompt
    reports_dir = REPORTS_FOLDER
    casheet_dir = CASH_SHEET_FOLDER

    if not reports_dir:
        reports_dir = input("Path to reports folder: ").strip()
    if not casheet_dir:
        casheet_dir = input("Path to cash-sheets folder: ").strip()

    # Get report date
    weekday = None
    while not weekday:
        report_date = input(
            "Cash sheet date to fill (MM/DD/YYYY, blank=yesterday): ").strip()
        if report_date == "":
            yesterday = date.today() - timedelta(days=1)
            report_date = yesterday.strftime("%m/%d/%Y")
        weekday = get_weekday_name(report_date)
        if weekday:
            print(f"  {report_date} is a {weekday}")

    execute(reports_dir, casheet_dir, weekday=weekday, report_date=report_date)
