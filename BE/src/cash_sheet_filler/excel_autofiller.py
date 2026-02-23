"""
Excel Autofiller Module
Handles automated filling of cash sheet Excel workbooks with parsed sales data.
"""

from openpyxl import load_workbook
import traceback
try:
    from .config import FILL_COL_MAP, CHECKING_COL_MAP
except ImportError:
    from config import FILL_COL_MAP, CHECKING_COL_MAP
from ..utils import strip_accents


class ExcelAutofiller:
    """
    Automates the process of filling cash sheet Excel files with sales data.

    Attributes:
        xl_path (str): Path to the Excel workbook file
        location (str): Location name to find and fill in the worksheet
        week_day (str): Name of the worksheet tab (day of week)
        start_row (int): Starting row for location search (default: 4)
        row (int): Current row being processed
        wb: Openpyxl workbook object
        ws: Openpyxl worksheet object
    """

    def __init__(self, xl_path, location, week_day, tracker=None):
        """
        Initialize the ExcelAutofiller.

        Args:
            xl_path (str): Full path to the Excel workbook
            location (str): Location name to search for in the workbook
            week_day (str): Worksheet name (e.g., 'Monday', 'Tuesday')
        """
        self.xl_path = xl_path
        self.location = location
        self.week_day = week_day
        self.start_row = 4  # Data starts at row 4 (after headers)
        self.row = 0
        self.wb = None
        self.ws = None
        self.tracker = tracker

    # ─── Logging Helpers ─────────────────────────────────────────────────

    def _log(self, msg):
        """Standard info logging."""
        if self.tracker:
            self.tracker.log(msg)
        else:
            print(msg)

    def _log_error(self, msg):
        """Log filling errors with a visual indicator."""
        self._log(f"  ❌ {msg}")

    def _log_warning(self, msg):
        """Log filling warnings with a visual indicator."""
        self._log(f"  ⚠️  {msg}")

    # ─── Core Methods ────────────────────────────────────────────────────

    def open_workbook(self):
        """
        Open and load the Excel workbook and specified worksheet.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.wb = load_workbook(self.xl_path)

            # Check if the worksheet exists (case-insensitive)
            sheet_map = {s.lower(): s for s in self.wb.sheetnames}
            actual_name = sheet_map.get(self.week_day.lower())
            if actual_name is None:
                self._log_error(
                    f"Worksheet '{self.week_day}' not found in workbook")
                return False

            self.ws = self.wb[actual_name]
            return True

        except FileNotFoundError:
            self._log_error(f"Workbook file not found: {self.xl_path}")
            return False

        except PermissionError:
            self._log_error(
                f"Permission denied: {self.xl_path}. Please close the file if it's currently open.")
            return False

        except Exception as e:
            self._log_error(f"Error opening workbook: {e}")
            traceback.print_exc()
            return False

    def find_row(self):
        """
        Search for the location name in the worksheet and set the current row.

        Returns:
            bool: True if location found, False otherwise
        """
        location_col = FILL_COL_MAP.get("location")

        if location_col is None:
            self._log_error("'location' column not defined in FILL_COL_MAP")
            return False

        # Search through rows starting from start_row
        for r in range(self.start_row, self.ws.max_row + 1):
            cell_value = self.ws.cell(r, location_col).value

            # Check if cell has value and matches location (case-insensitive, stripped)
            if cell_value and strip_accents(cell_value.strip().lower()) == strip_accents(self.location.lower()):
                self.row = r
                self._log(
                    f"  ✓ Found location '{self.location}' at row {self.row}")
                return True

        # Location not found
        self._log_error(
            f"Location '{self.location}' not found in column {location_col}")
        return False

    def checking_tenders(self):
        """
        Verify that tender calculations are correct by checking the 'over/short' column.

        Returns:
            bool: True if tenders balance correctly (over/short is 0 or None), False otherwise
        """
        over_col = CHECKING_COL_MAP.get("over")

        if over_col is None:
            self._log_warning(
                "'over' column not defined in CHECKING_COL_MAP - skipping validation")
            return True

        over_value = self.ws.cell(self.row, over_col).value

        # Check if there's a discrepancy
        if over_value is not None:
            try:
                over_amount = float(over_value)
                if over_amount != 0:
                    self._log_warning(
                        f"Tender validation failed: 'over/short' is {over_amount}")
                    return False
            except (ValueError, TypeError):
                self._log_error(
                    f"Invalid value in 'over/short' column: {over_value}")
                return False

        return True

    def filling(self, parser):
        """
        Fill the worksheet with data from the parser dictionary.
        """
        try:
            # Step 1: Find the correct row for this location
            if not self.find_row():
                return False

            # Tax is typically on the row below the main data row
            tax_row = self.row + 1

            # Step 2: Fill basic performance metrics
            date_col = FILL_COL_MAP.get("date")
            if date_col:
                self.ws.cell(1, date_col).value = parser.get("date")

            count_col = FILL_COL_MAP.get("count")
            if count_col:
                self.ws.cell(self.row, count_col).value = parser.get("count")

            total_sales_col = FILL_COL_MAP.get("total_sales")
            if total_sales_col:
                self.ws.cell(self.row, total_sales_col).value = parser.get(
                    "total_sales")

            tax_col = FILL_COL_MAP.get("tax")
            if tax_col:
                self.ws.cell(tax_row, tax_col).value = parser.get("tax")

            # Step 3: Fill tender amounts
            tenders = parser.get("tenders", {})
            unmatched_tenders = []

            for tender_name, amount in tenders.items():
                if tender_name not in FILL_COL_MAP:
                    unmatched_tenders.append(tender_name)
                    continue

                col = FILL_COL_MAP[tender_name]

                # Write all non-zero amounts (including negatives); clear zeros
                if amount != 0:
                    self.ws.cell(self.row, col).value = amount
                else:
                    self.ws.cell(self.row, col).value = None

            # Report any unmatched tenders
            if unmatched_tenders:
                self._log_warning(
                    f"Unmatched tenders not filled: {', '.join(unmatched_tenders)}")

            self._log(f"  ✓ {self.location} filled successfully")
            return True

        except KeyError as e:
            self._log_error(f"Missing expected data key: {e}")
            return False

        except Exception as e:
            self._log_error(f"Error during filling: {e}")
            traceback.print_exc()
            return False

    def save(self):
        """
        Save the workbook and validate the filled data.

        Returns:
            bool: True if save successful and data validates correctly, False otherwise
        """
        try:
            # Step 1: Save the workbook
            self.wb.save(self.xl_path)
            self._log(f"  💾 Saved: {self.location} casheet")

            # Step 2: Reload workbook with calculated formulas (data_only=True)
            self.wb = load_workbook(self.xl_path, data_only=True)
            sheet_map = {s.lower(): s for s in self.wb.sheetnames}
            actual_name = sheet_map.get(self.week_day.lower(), self.week_day)
            self.ws = self.wb[actual_name]

            # Step 3: Validate tender calculations
            is_correct = self.checking_tenders()

            if is_correct:
                self._log(
                    f"  ✓ {self.location} casheet validated successfully")
            else:
                self._log_warning(
                    f"{self.location} validation warning - check over/short column")

            return is_correct

        except PermissionError:
            self._log_error(
                f"Permission denied when saving: {self.xl_path}. Please close the file if it's currently open.")
            return False

        except Exception as e:
            self._log_error(f"Error saving workbook: {e}")
            traceback.print_exc()
            return False

    def close(self):
        """
        Properly close the workbook to free resources.
        """
        if self.wb:
            self.wb.close()
            self.wb = None
            self.ws = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures workbook is closed."""
        self.close()
