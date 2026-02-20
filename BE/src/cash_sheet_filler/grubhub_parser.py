"""
Grubhub Parser Module
Parses the Grubhub "SalesbyVenuebyPaymentMethod" CSV report.

One CSV file covers ALL venues across ALL dates.
Each row has dollar amounts per payment method.
"""

import csv
from datetime import datetime
try:
    from .config import GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP, CASHEET_TENDERS
except ImportError:
    from config import GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP, CASHEET_TENDERS


class GrubhubParser:
    """
    Parser for the Grubhub sales-by-venue CSV export.

    CSV columns:
        [0]  Order Date
        [3]  Venue
        [5]  Payment Method
        [8]  Tax
        [9]  Total Merchant Sales  (subtotal + tax)
        [16] Meal Count

    After parsing, self.data is:
        {date_str: {venue_name: {total_count, total_sales, total_tax, tenders}}}
    """

    MERGE_SUFFIX = " - Meal Transfer"

    # Column indices in the CSV
    COL_DATE = 0
    COL_VENUE = 3
    COL_PAYMENT_METHOD = 5
    COL_TAX = 8
    COL_TOTAL_SALES = 9
    COL_MEAL_COUNT = 16

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = {}
        self._unmapped_venues = set()
        self._unmapped_tenders = set()

    # ─── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_dollar(value):
        """Strip '$' and ',' from a dollar string and return float."""
        return float(value.strip().replace("$", "").replace(",", ""))

    @staticmethod
    def _parse_int(value):
        """Strip whitespace and commas from an integer string."""
        return int(value.strip().replace(",", ""))

    @staticmethod
    def normalize_date(date_str):
        """Convert Grubhub date (MM-DD-YY etc.) to YYYY-MM-DD."""
        for fmt in ("%m-%d-%y", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {date_str}")

    # ─── Core Parsing ────────────────────────────────────────────────────

    def parse(self):
        """
        Parse the Grubhub CSV and populate self.data.

        Returns:
            bool: True if parsed successfully, False on file error.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header

                for row in reader:
                    if len(row) < 17 or row[self.COL_DATE].strip() in ("Total", ""):
                        continue

                    try:
                        date = self.normalize_date(row[self.COL_DATE])
                    except ValueError:
                        continue

                    venue = row[self.COL_VENUE].strip()
                    payment_method = row[self.COL_PAYMENT_METHOD].strip()

                    try:
                        tax = self._parse_dollar(row[self.COL_TAX])
                        sale = self._parse_dollar(row[self.COL_TOTAL_SALES])
                        meal_count = self._parse_int(row[self.COL_MEAL_COUNT])
                    except (ValueError, IndexError):
                        continue

                    # Merge " - Meal Transfer" venues into the base venue
                    if venue.endswith(self.MERGE_SUFFIX):
                        venue = venue[: -len(self.MERGE_SUFFIX)].strip()

                    # Init date / venue entry if new
                    if date not in self.data:
                        self.data[date] = {}
                    if venue not in self.data[date]:
                        self.data[date][venue] = {
                            "total_count": 0,
                            "total_sales": 0.0,
                            "total_tax": 0.0,
                            "tenders": CASHEET_TENDERS.copy(),
                        }

                    entry = self.data[date][venue]
                    entry["total_count"] += meal_count
                    entry["total_sales"] += sale
                    entry["total_tax"] += tax

                    # Map payment method to casheet tender key
                    if payment_method in GRUBHUB_TENDERS:
                        casheet_key = GRUBHUB_TENDERS[payment_method]
                        entry["tenders"][casheet_key] += sale
                    else:
                        self._unmapped_tenders.add(payment_method)

                    if venue not in GRUBHUB_VENUE_MAP:
                        self._unmapped_venues.add(venue)

            print(f"  ✓ Grubhub parsed: {len(self.data)} date(s)")
            return True

        except FileNotFoundError:
            print(f"  ❌ File not found: {self.file_path}")
            return False

    # ─── Public Accessors ────────────────────────────────────────────────

    def get_dates(self):
        """Get all dates with data."""
        return list(self.data.keys())

    def get_venues(self, date):
        """Get all venue names for a specific date."""
        return list(self.data.get(date, {}).keys())

    def get_venue_data(self, date, venue):
        """
        Get raw data for a specific venue on a date.

        Returns:
            dict or None: {total_count, total_sales, total_tax, tenders}
        """
        return self.data.get(date, {}).get(venue)

    def get_data_dict(self, date, venue):
        """
        Get data for one venue formatted like InforParser / TavloParser output.

        Returns:
            dict or None: {location, date, count, total_sales, tax, tenders}
        """
        raw = self.get_venue_data(date, venue)
        if raw is None:
            return None
        return {
            "location": venue,
            "date": date,
            "count": raw["total_count"],
            "total_sales": raw["total_sales"],
            "tax": raw["total_tax"],
            "tenders": raw["tenders"].copy(),
        }

    def get_unmapped_venues(self):
        return self._unmapped_venues.copy()

    def get_unmapped_tenders(self):
        return self._unmapped_tenders.copy()

    def __repr__(self):
        return (
            f"GrubhubParser(file='{self.file_path}', "
            f"dates={len(self.data)}, "
            f"venues={sum(len(v) for v in self.data.values())})"
        )
