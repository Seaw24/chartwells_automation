"""
Grubhub Parser Module
Parses the Grubhub "SalesbyVenuebyPaymentMethod" CSV report.
"""

import csv
from datetime import datetime
try:
    from .config import GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP, CASHEET_TENDERS
    from .base_parser import BaseParser
except ImportError:
    from config import GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP, CASHEET_TENDERS
    from base_parser import BaseParser

from ..utils import strip_accents


class GrubhubParser(BaseParser):
    """
    Parser for the Grubhub sales-by-venue CSV export.
    """

    MERGE_SUFFIX = " - Meal Transfer"
    COL_DATE = 0
    COL_VENUE = 3
    COL_PAYMENT_METHOD = 5
    COL_TAX = 8
    COL_TOTAL_SALES = 9
    COL_MEAL_COUNT = 16

    def __init__(self, file_path, tracker=None):
        super().__init__(tracker)  # Initialize BaseParser
        self.file_path = file_path
        self.data = {}
        self._unmapped_venues = set()
        self._unmapped_tenders = set()

    @staticmethod
    def _parse_dollar(value):
        clean_val = value.strip().replace("$", "").replace(",", "")
        if clean_val.startswith("(") and clean_val.endswith(")"):
            clean_val = "-" + clean_val[1:-1]
        return float(clean_val)

    @staticmethod
    def _parse_int(value):
        return int(value.strip().replace(",", ""))

    def normalize_date(self, date_str):
        for fmt in ("%m-%d-%y", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%m/%d/%Y")
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {date_str}")

    def parse(self):
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
                        self._log_warning(f"Data parsing error in row: {row}")
                        continue

                    if venue.endswith(self.MERGE_SUFFIX):
                        venue = venue[: -len(self.MERGE_SUFFIX)].strip()

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

                    if payment_method in GRUBHUB_TENDERS:
                        casheet_key = GRUBHUB_TENDERS[payment_method]
                        entry["tenders"][casheet_key] += sale
                    else:
                        self._unmapped_tenders.add(payment_method)

                    if venue not in GRUBHUB_VENUE_MAP:
                        self._unmapped_venues.add(venue)

            self._log(f"  ✓ Grubhub parsed: {len(self.data)} date(s)")
            return True

        except FileNotFoundError:
            self._log_error(f"Grubhub file not found: {self.file_path}")
            return False

    def get_dates(self): return list(self.data.keys())
    def get_venues(self, date): return list(self.data.get(date, {}).keys())

    def get_data_dict(self, date, venue):
        raw = self.data.get(date, {}).get(venue)
        if raw is None:
            return None
        return {
            "location": strip_accents(venue),
            "date": date,
            "count": raw["total_count"],
            "total_sales": raw["total_sales"],
            "tax": raw["total_tax"],
            "tenders": raw["tenders"].copy(),
        }

    def get_unmapped_venues(self): return self._unmapped_venues.copy()
    def get_unmapped_tenders(self): return self._unmapped_tenders.copy()
