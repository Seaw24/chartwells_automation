"""
Grubhub Parser Module
Parses the Grubhub "SalesbyVenuebyPaymentMethod" CSV report.
"""

import csv
from datetime import datetime
from .config import GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP, CASHEET_TENDERS
from .base_parser import BaseParser

from ..utils import strip_accents


class GrubhubParser(BaseParser):
    """
    Parser for the Grubhub sales-by-venue CSV export.
    """

    COL_DATE = 0
    COL_VENUE = 6
    COL_PAYMENT_METHOD = 8
    COL_TAX = 11
    COL_DISCOUNTS = 13
    COL_TOTAL_SALES = 25
    COL_MEAL_COUNT = 26
    MERGE_SUFFIX = " - Meal Transfer"

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

    def parse(self, stop_event=None):
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)  # Read header row

                # ── Validate/find columns by header name ──────────────
                # Check if preconfigured index matches expected name.
                # If not, search the whole header row for it.
                header_clean = [h.strip().lower() for h in header]

                col_map = {
                    "order date":             "COL_DATE",
                    "venue name":             "COL_VENUE",
                    "payment method":         "COL_PAYMENT_METHOD",
                    "tax":                    "COL_TAX",
                    "charged on tender":      "COL_TOTAL_SALES",
                    "meal count":             "COL_MEAL_COUNT",
                    "tapingo discount":       "COL_DISCOUNTS",
                }

                for name, attr in col_map.items():
                    expected_idx = getattr(self, attr)
                    # If preconfigured index is valid and matches, keep it
                    if expected_idx < len(header_clean) and header_clean[expected_idx] == name:
                        continue
                    # Otherwise search the whole header
                    found = False
                    for i, h in enumerate(header_clean):
                        if h == name:
                            setattr(self, attr, i)
                            self._log(
                                f"  ℹ Column '{name}' found at index {i} (was {expected_idx})")
                            found = True
                            break
                    if not found:
                        self._log_warning(
                            f"Column '{name}' not found in header")

                # ── Parse data rows ───────────────────────────────────
                for i, row in enumerate(reader):
                    if stop_event and stop_event.is_set():
                        self._log("🛑 Aborting Grubhub parsing...")
                        return False
                    if len(row) <= max(self.COL_DATE, self.COL_VENUE, self.COL_PAYMENT_METHOD,
                                       self.COL_TAX, self.COL_TOTAL_SALES, self.COL_MEAL_COUNT, self.COL_DISCOUNTS):
                        continue

                    date_str = row[self.COL_DATE].strip()

                    # Skip summary/total rows and empty rows
                    if not date_str or date_str.lower().startswith("total"):
                        continue

                    try:
                        date = self.normalize_date(date_str)
                    except ValueError:
                        continue

                    venue = row[self.COL_VENUE].strip()
                    payment_method = row[self.COL_PAYMENT_METHOD].strip()

                    # Skip rows with no venue (sub-total rows)
                    if not venue:
                        continue

                    try:
                        tax = self._parse_dollar(row[self.COL_TAX])
                        sale = self._parse_dollar(row[self.COL_TOTAL_SALES])
                        meal_count = self._parse_int(row[self.COL_MEAL_COUNT])
                        discounts = self._parse_dollar(row[self.COL_DISCOUNTS])
                    except (ValueError, IndexError):
                        self._log_warning(
                            f"Data parsing error in row {i}: {row[:3]}...")
                        continue

                    # Merge "- Meal Transfer" suffix venues into base venue
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
                            "total_discounts": 0.0,
                        }

                    entry = self.data[date][venue]
                    entry["total_count"] += meal_count
                    entry["total_sales"] += sale
                    entry["total_tax"] += tax
                    entry["total_discounts"] += discounts

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
            "discounts": raw["total_discounts"],
            "tenders": raw["tenders"].copy(),
        }

    def get_unmapped_venues(self): return self._unmapped_venues.copy()
    def get_unmapped_tenders(self): return self._unmapped_tenders.copy()
