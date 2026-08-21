"""
Grubhub Sales-at-a-Glance parser.

This report is the source of truth for Grubhub order counts. The older
TransactionDetailbyVenuebyPaymentMethod report still supplies sales, tax,
discounts, and tender breakdown values, but its meal-count column is not used
for the cash-sheet order-count cell.

Total Merchant Sales is also collected per venue — "... - Choose Your Own
Adventure" sibling venues contribute that figure to the cash sheet's
"1,2,3" column instead of an order count.
"""

import csv
from datetime import datetime

from .base_parser import BaseParser
from .config import GRUBHUB_VENUE_MAP


class GrubhubOrderCountParser(BaseParser):
    """Parser for the Grubhub Sales-at-a-Glance CSV export."""

    COL_DATE = 0
    COL_VENUE = 3
    COL_TOTAL_SALES = 7
    COL_ORDER_COUNT = 8
    MERGE_SUFFIX = " - Meal Transfer"

    def __init__(self, file_path, tracker=None):
        super().__init__(tracker)
        self.file_path = file_path
        self.data = {}
        self.sales = {}
        self._unmapped_venues = set()
        self._order_total = 0
        self._row_count = 0

    @staticmethod
    def _parse_int(value):
        clean_val = str(value).strip().replace(",", "")
        if not clean_val:
            return 0
        return int(float(clean_val))

    @staticmethod
    def _parse_dollar(value):
        clean_val = str(value).strip().replace("$", "").replace(",", "")
        if not clean_val:
            return 0.0
        if clean_val.startswith("(") and clean_val.endswith(")"):
            clean_val = "-" + clean_val[1:-1]
        return float(clean_val)

    def normalize_date(self, date_str):
        for fmt in ("%m-%d-%y", "%m/%d/%Y", "%m-%d-%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%m/%d/%Y")
            except ValueError:
                continue
        raise ValueError(f"Invalid date format: {date_str}")

    def parse(self, stop_event=None):
        try:
            with open(self.file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
                self._resolve_columns(header)

                for i, row in enumerate(reader):
                    if stop_event and stop_event.is_set():
                        self._log("Stopped during Grubhub order-count parsing.")
                        return False
                    self._process_row(i, row)
        except FileNotFoundError:
            self._log_error(f"Grubhub order-count file not found: {self.file_path}")
            return False
        except StopIteration:
            self._log_error(f"Grubhub order-count file is empty: {self.file_path}")
            return False

        self._log(
            "   Grubhub order counts parsed: "
            f"{len(self.data)} date(s), {self._row_count} venue row(s), "
            f"{self._order_total} order(s)"
        )
        return True

    def _resolve_columns(self, header):
        header_clean = [h.strip().lower() for h in header]
        col_map = {
            "order date": "COL_DATE",
            "venue": "COL_VENUE",
            "total merchant sales": "COL_TOTAL_SALES",
            "order count": "COL_ORDER_COUNT",
        }
        for name, attr in col_map.items():
            expected_idx = getattr(self, attr)
            if (
                expected_idx < len(header_clean)
                and header_clean[expected_idx] == name
            ):
                continue
            for i, h in enumerate(header_clean):
                if h == name:
                    setattr(self, attr, i)
                    break
            else:
                self._log_warning(f"Column '{name}' not found in header")

    def _process_row(self, i, row):
        max_idx = max(self.COL_DATE, self.COL_VENUE, self.COL_TOTAL_SALES,
                      self.COL_ORDER_COUNT)
        if len(row) <= max_idx:
            return

        date_str = row[self.COL_DATE].strip()
        if not date_str or date_str.lower().startswith("total"):
            return

        try:
            date = self.normalize_date(date_str)
            count = self._parse_int(row[self.COL_ORDER_COUNT])
            sale = self._parse_dollar(row[self.COL_TOTAL_SALES])
        except ValueError:
            self._log_warning(f"Order-count parsing error in row {i}: {row[:4]}...")
            return

        venue = row[self.COL_VENUE].strip()
        if not venue:
            return

        if venue.endswith(self.MERGE_SUFFIX):
            venue = venue[: -len(self.MERGE_SUFFIX)].strip()

        self.data.setdefault(date, {})
        self.data[date][venue] = self.data[date].get(venue, 0) + count
        self.sales.setdefault(date, {})
        self.sales[date][venue] = self.sales[date].get(venue, 0.0) + sale
        self._order_total += count
        self._row_count += 1

        if venue not in GRUBHUB_VENUE_MAP:
            self._unmapped_venues.add(venue)

    def merge_from(self, other):
        for date, venues in other.data.items():
            target = self.data.setdefault(date, {})
            for venue, count in venues.items():
                target[venue] = target.get(venue, 0) + count
        for date, venues in other.sales.items():
            target = self.sales.setdefault(date, {})
            for venue, sale in venues.items():
                target[venue] = target.get(venue, 0.0) + sale
        self._unmapped_venues.update(other.get_unmapped_venues())
        self._order_total += other._order_total
        self._row_count += other._row_count

    def has_data(self):
        return any(
            count
            for venues in self.data.values()
            for count in venues.values()
        )

    @staticmethod
    def _normalize_venue(name):
        """
        Casefold, collapse whitespace, and drop stray edge separators, so
        hand-typed names match across reports ("Qdoba - Swoop Swap Shop -"
        vs "Qdoba - Swoop Swap Shop").
        """
        return " ".join(name.split()).casefold().strip(" -–—")

    def _lookup(self, source, date, venue):
        venues = source.get(date, {})
        if venue in venues:
            return venues[venue]
        norm = self._normalize_venue(venue)
        for name, value in venues.items():
            if self._normalize_venue(name) == norm:
                return value
        return None

    def get_count(self, date, venue):
        return self._lookup(self.data, date, venue)

    def get_sales(self, date, venue):
        return self._lookup(self.sales, date, venue)

    def get_dates(self):
        return list(self.data.keys())

    def get_venues(self, date):
        return list(self.data.get(date, {}).keys())

    def get_unmapped_venues(self):
        return self._unmapped_venues.copy()
