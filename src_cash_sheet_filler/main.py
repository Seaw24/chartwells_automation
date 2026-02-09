"""
Main Execution Module with Enhanced Error Tracking
Processes Infor and Tavlo reports and tracks errors by location.
"""

from calendar import weekday
import os
from infor_parser import InforParser
from tavlo_parser import TavloParser
from excel_autofiller import ExcelAutofiller
from datetime import date, timedelta
from dateutil.parser import parse
from config import REPORTS_CASHSHEET_MAP, REPORTS_FOLDER, CASH_SHEET_FOLDER


class ProcessingTracker:
    """
    Tracks processing results for all reports including success, failures, and validation warnings.
    """

    def __init__(self):
        self.successful = []
        self.failed = []
        self.validation_warnings = []  # Stores locations with over/short discrepancies
        self.unmapped_locations = []   # Locations not in REPORTS_CASHSHEET_MAP

    def add_success(self, location, filename, has_warning=False):
        """Add a successful processing result."""
        self.successful.append({
            'location': location,
            'filename': filename,
            'has_warning': has_warning
        })

    def add_failure(self, location, filename, error_type, error_message):
        """Add a failed processing result."""
        self.failed.append({
            'location': location,
            'filename': filename,
            'error_type': error_type,
            'error_message': error_message
        })

    def add_validation_warning(self, location, filename, discrepancy_amount=None):
        """Add a validation warning (tender discrepancy)."""
        self.validation_warnings.append({
            'location': location,
            'filename': filename,
            'discrepancy': discrepancy_amount
        })

    def add_unmapped_location(self, location, filename):
        """Add an unmapped location."""
        self.unmapped_locations.append({
            'location': location,
            'filename': filename
        })

    def print_summary(self):
        """Print a comprehensive summary of all processing results."""
        total = len(self.successful) + len(self.failed)

        print("\n" + "=" * 80)
        print("=" * 80)
        print("📊 PROCESSING SUMMARY")

        # Overall stats
        print(f"\n📈 Overall Statistics:")
        print(f"   ✅ Successful: {len(self.successful)}")
        print(f"   ❌ Failed: {len(self.failed)}")
        print(f"   ⚠️  Validation Warnings: {len(self.validation_warnings)}")
        print(f"   📁 Total Processed: {total}")

        # Validation warnings (over/short issues)
        if self.validation_warnings:
            print(f"\n⚠️  LOCATIONS WITH TENDER DISCREPANCIES:")
            print(f"   {'Location':<30} {'File':<40} {'Issue'}")
            print(f"   {'-' * 78}")
            for warning in self.validation_warnings:
                location = warning['location'][:28]
                filename = warning['filename'][:38]
                issue = f"Over/Short ≠ 0" if warning['discrepancy'] is None else f"${warning['discrepancy']:.2f}"
                print(f"   {location:<30} {filename:<40} {issue}")
            print(f"\n   💡 Tip: Check these locations' tender entries for accuracy")

        # Unmapped locations
        if self.unmapped_locations:
            print(f"\n🗺️  UNMAPPED LOCATIONS (Not in REPORTS_CASHSHEET_MAP):")
            print(f"   {'Location':<30} {'File':<40}")
            print(f"   {'-' * 72}")
            for item in self.unmapped_locations:
                location = item['location'][:28]
                filename = item['filename'][:38]
                print(f"   {location:<30} {filename:<40}")
            print(
                f"\n   💡 Tip: Add these locations to REPORTS_CASHSHEET_MAP in config.py")

        # Failed reports
        if self.failed:
            print(f"\n❌ FAILED REPORTS:")
            print(f"   {'Location':<30} {'Error Type':<20} {'Details'}")
            print(f"   {'-' * 78}")
            for failure in self.failed:
                location = failure['location'][:28] if failure['location'] else 'Unknown'
                error_type = failure['error_type'][:18]
                error_msg = failure['error_message'][:25]
                print(f"   {location:<30} {error_type:<20} {error_msg}")

        # Successful with warnings
        successful_with_warnings = [
            s for s in self.successful if s['has_warning']]
        if successful_with_warnings:
            print(
                f"\n✅ Successful (with warnings): {len(successful_with_warnings)}")
            for item in successful_with_warnings:
                print(f"   - {item['location']}")

        print("\n" + "=" * 80 + "\n")


def get_weekday_name(report_date):
    """
    Convert date string to weekday name.

    Args:
        report_date (str): Date in MM/DD/YYYY format

    Returns:
        str: Weekday name (e.g., 'Monday')
    """
    try:
        date_object = parse(report_date)
        weekday_name = date_object.strftime("%A")
        print(f"The date {report_date} is a {weekday_name}")
        return weekday_name
    except (ValueError, TypeError):
        print(f"✗ Error: Could not understand the enter date '{report_date}'.")
        print(f"  Please use a standard format like MM/DD/YYYY or 10-22-25.")
        # Return an empty string or raise an error to stop the program
        return None


def find_casheet(location, casheet_files):
    casheet_name = REPORTS_CASHSHEET_MAP[location][0]
    for casheet_file in casheet_files:
        if casheet_name.strip() in casheet_file.strip():
            return casheet_file
    return None


def process_report(report_parser, casheet_dir, weekday, report_filename, tracker, casheet_files):
    """
    Generic function to process both Infor and Tavlo reports with error tracking.

    Args:
        report_parser: InforParser or TavloParser instance
        casheet_dir (str): Directory containing cash sheet files
        weekday (str): Day of week for worksheet selection
        report_filename (str): Name of the report file being processed
        tracker (ProcessingTracker): Tracker instance for recording results

    Returns:
        bool: True if successful, False otherwise
    """
    print("\n" + "-" * 100)
    print("-" * 100)
    print(f"📄 PROCESSING REPORT: {report_filename}")

    location = None

    try:
        # Step 1: Parse the report
        if not report_parser.parse():
            tracker.add_failure(
                location='Unknown',
                filename=report_filename,
                error_type='Parse Error',
                error_message='Failed to parse report file'
            )
            print(f"❌ Failed to parse report: {report_filename}")
            return False

        parser = report_parser.get_data_dict()
        location = parser['location']

        # Step 2: Check if location exists in mapping
        if location not in REPORTS_CASHSHEET_MAP:
            tracker.add_unmapped_location(location, report_filename)
            print(
                f"⚠️  Cannot find the matched casheet with this report location: {location}")
            tracker.add_validation_warning(location, report_filename)
            return False

        # Print tenders if available (for Tavlo reports)
        if hasattr(report_parser, 'all_tenders'):
            print(f"💳 Tenders: {report_parser.all_tenders}\n")

        # Find information for casheet
        location_in_casheet = REPORTS_CASHSHEET_MAP[location][1]
        casheet_file = find_casheet(location, casheet_files)
        if casheet_file is None:
            expected_name = REPORTS_CASHSHEET_MAP[location][0]
            error_msg = f"Casheet file not found in directory. Expected a file containing: {expected_name}"

            print(f"❌ {error_msg}")
            tracker.add_failure(
                location=location,
                filename=report_filename,
                error_type='File Not Found',
                error_message=error_msg
            )
            return False
        casheet_path = os.path.join(casheet_dir, casheet_file)

        # Step 3: Open casheet
        try:
            casheet = ExcelAutofiller(
                casheet_path, location_in_casheet, weekday)
        except FileNotFoundError:
            tracker.add_failure(
                location=location,
                filename=report_filename,
                error_type='File Not Found',
                error_message=f'Casheet not found: {casheet_file}'
            )
            print(f"❌ Cannot find casheet: {casheet_path}")
            return False

        # Step 4: Open workbook
        if not casheet.open_workbook():
            tracker.add_failure(
                location=location,
                filename=report_filename,
                error_type='Workbook Error',
                error_message=f'Failed to open: {casheet_file}'
            )
            print(f"❌ Failed to open workbook: {casheet_file}")
            return False

        # Step 5: Fill data
        if not casheet.filling(parser):
            tracker.add_failure(
                location=location,
                filename=report_filename,
                error_type='Fill Error',
                error_message=f'Failed to fill: {casheet_file}'
            )
            print(f"❌ Failed to fill the casheet: {casheet_file}")
            return False

        # Step 6: Save and validate
        validation_passed = casheet.save()

        if validation_passed:
            tracker.add_success(location, report_filename, has_warning=False)
            print(f"✅ Successfully saved: {casheet_file}")
            return True
        else:
            # Save succeeded but validation found discrepancy
            tracker.add_success(location, report_filename, has_warning=True)
            tracker.add_validation_warning(location, report_filename)
            print(f"⚠️  Saved but validation warning: {casheet_file}")
            return True  # Still count as success since data was saved

    except Exception as e:
        tracker.add_failure(
            location=location or 'Unknown',
            filename=report_filename,
            error_type='Unexpected Error',
            error_message=str(e)[:50]
        )
        print(f"❌ Unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return False


def execute(reports_dir, casheet_dir, weekday, report_date):
    """
    Main execution function that processes all reports and generates summary.

    Args:
        reports_dir (str): Directory containing report files
        casheet_dir (str): Directory containing cash sheet files
        report_date (str): Report date in MM/DD/YYYY format (empty string for yesterday)
    """

    # Initialize tracking
    tracker = ProcessingTracker()

    # Get all the reports
    csv_files = []
    xls_files = []
    try:
        for report_file_path in os.listdir(reports_dir):
            if report_file_path.endswith(".csv"):
                csv_files.append(report_file_path)
            elif report_file_path.endswith(".xls"):
                xls_files.append(report_file_path)
    except FileNotFoundError:
        print(f"❌ Reports directory not found: {reports_dir}")
        return
    except PermissionError:
        print(f"❌ Permission denied accessing: {reports_dir}")
        return

    # Get all the casheets
    try:
        casheet_files = [
            casheet_file for casheet_file in os.listdir(casheet_dir)]
    except FileNotFoundError:
        print(f"❌ Reports directory not found: {reports_dir}")
        return
    except PermissionError:
        print(f"❌ Permission denied accessing: {reports_dir}")
        return

    # Check if no files found
    if (not csv_files and not xls_files) or not casheet_files:
        print("⚠️  No valid report files found")
        return

    print(
        f"\n🔍 Found {len(csv_files)} CSV file(s) and {len(xls_files)} XLS file(s)")

    # Process Infor (CSV) reports
    for csv_file in csv_files:
        csv_path = os.path.join(reports_dir, csv_file)
        csv_report = InforParser(csv_path, report_date)
        process_report(csv_report, casheet_dir, weekday,
                       csv_file, tracker, casheet_files)

    # Process Tavlo (XLS) reports
    for xls_file in xls_files:
        xls_path = os.path.join(reports_dir, xls_file)
        xls_report = TavloParser(xls_path, report_date)
        process_report(xls_report, casheet_dir, weekday,
                       xls_file, tracker, casheet_files)

    # Print comprehensive summary
    tracker.print_summary()


if __name__ == "__main__":
    # Run the processor
    weekday = None
    while not weekday:
        report_date = input("What cash sheet day that you trynna fill in? ")
        # Default is yesterday
        if report_date == "":
            yesterday = date.today() - timedelta(days=1)
            report_date = yesterday.strftime("%m/%d/%Y")
        weekday = get_weekday_name(report_date)

    execute(REPORTS_FOLDER, CASH_SHEET_FOLDER,
            weekday=weekday, report_date=report_date)
