"""
Grubhub Parser Module
─────────────────────
Parses the Grubhub "TransactionDetailbyVenuebyPaymentMethod" CSV export.

A single CSV contains many venues across many dates. The parser groups rows
into ``data[date][venue]`` and reconciles a few quirks of the Grubhub format:

* Some venues have a "- Meal Transfer" sibling row whose totals must be
  merged into the base venue.
* For Credit Card rows, Grubhub's "Charged on Tender" figure still includes
  the service fee it collected. That fee is not venue revenue, so we subtract
  it back out before the amount reaches the cash sheet.
* Discounts are reconciled later (in ``main._add_discounts``).
* Meal count is tracked only for diagnostics. Cash-sheet order count now comes
  from the separate Sales-at-a-Glance report.

Logging has two levels. By default the class reports only aggregates so the
UI stays calm. With ``verbose_trace`` on in the config it also prints each
row's arithmetic — charged amount, fee subtracted, resulting tender — grouped
under the venue it belongs to, so a cash-sheet figure can be traced back to
the CSV rows that produced it.
"""

import csv
from datetime import datetime
from .config import (GRUBHUB_TENDERS, GRUBHUB_VENUE_MAP, CASHEET_TENDERS,
                     VERBOSE_TRACE)
from .base_parser import BaseParser

from ..utils import strip_accents


class GrubhubParser(BaseParser):
    """Parser for the Grubhub sales-by-venue CSV export."""

    # Default column indices — re-validated at parse time against the header
    # row. If the export ever shifts a column we re-resolve by name.
    COL_DATE = 0
    COL_VENUE = 6
    COL_PAYMENT_METHOD = 8
    COL_TAX = 11
    COL_DISCOUNTS = 13
    COL_SERVICE_FEE = 18
    COL_TOTAL_SALES = 25
    COL_MEAL_COUNT = 26
    MERGE_SUFFIX = " - Meal Transfer"

    def __init__(self, file_path, tracker=None):
        super().__init__(tracker)
        self.file_path = file_path
        self.data = {}
        self._unmapped_venues = set()
        self._unmapped_tenders = set()
        # Aggregate counters — surfaced once at the end of parse() instead
        # of one log line per row.
        self._service_fee_count = 0
        self._service_fee_total = 0.0
        # {(date, venue): [row trace line, ...]} — built during the row loop
        # and emitted grouped by venue at the end, so the log reads
        # venue-by-venue instead of following the CSV's row order.
        self._trace_rows = {}

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
        """
        Read and aggregate the CSV. Honors a ``stop_event`` so the user can
        cancel a long parse mid-stream.

        Returns True on success, False if the file is missing or the user
        canceled.
        """
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader)
                self._resolve_columns(header)

                # ── Parse data rows ───────────────────────────────────
                for i, row in enumerate(reader):
                    if stop_event and stop_event.is_set():
                        self._log("Stopped during Grubhub parsing.")
                        return False
                    self._process_row(i, row)

        except FileNotFoundError:
            self._log_error(f"Grubhub file not found: {self.file_path}")
            return False

        # One concise summary line covers the whole parse — including the
        # service fees we deducted, which would otherwise spam the log.
        msg = f"Grubhub parsed: {len(self.data)} date(s)"
        if self._service_fee_count:
            msg += (f" · removed ${self._service_fee_total:.2f} in service "
                    f"fees from {self._service_fee_count} Credit Card row(s)")
        self._log(f"   {msg}")
        self._emit_row_traces()
        return True

    # ── helpers ──────────────────────────────────────────────────────
    def _resolve_columns(self, header):
        """
        Validate and (if needed) re-bind column indices using the header row.

        Grubhub occasionally adds/removes columns. We trust the configured
        indices first and fall back to a name lookup. We only log the
        unresolved case — re-bound columns are silent.
        """
        header_clean = [h.strip().lower() for h in header]
        col_map = {
            "order date":           "COL_DATE",
            "venue name":           "COL_VENUE",
            "payment method":       "COL_PAYMENT_METHOD",
            "tax":                  "COL_TAX",
            "charged on tender":    "COL_TOTAL_SALES",
            "meal count":           "COL_MEAL_COUNT",
            "tapingo discount":     "COL_DISCOUNTS",
            "tapingo service fee":  "COL_SERVICE_FEE",
        }
        for name, attr in col_map.items():
            expected_idx = getattr(self, attr)
            if (expected_idx < len(header_clean)
                    and header_clean[expected_idx] == name):
                continue  # already correct — no need to re-bind or log
            for i, h in enumerate(header_clean):
                if h == name:
                    setattr(self, attr, i)
                    break
            else:
                self._log_warning(f"Column '{name}' not found in header")

    def _process_row(self, i, row):
        """Process one data row, accumulating into ``self.data``."""
        # Skip rows that are too short to read every column we care about.
        max_idx = max(self.COL_DATE, self.COL_VENUE, self.COL_PAYMENT_METHOD,
                      self.COL_TAX, self.COL_TOTAL_SALES, self.COL_MEAL_COUNT,
                      self.COL_DISCOUNTS)
        if len(row) <= max_idx:
            return

        date_str = row[self.COL_DATE].strip()
        # Skip summary/total/empty rows.
        if not date_str or date_str.lower().startswith("total"):
            return
        try:
            date = self.normalize_date(date_str)
        except ValueError:
            return

        venue = row[self.COL_VENUE].strip()
        payment_method = row[self.COL_PAYMENT_METHOD].strip()
        if not venue:
            return  # sub-total rows have no venue

        try:
            tax = self._parse_dollar(row[self.COL_TAX])
            sale = self._parse_dollar(row[self.COL_TOTAL_SALES])
            meal_count = self._parse_int(row[self.COL_MEAL_COUNT])
            discounts = self._parse_dollar(row[self.COL_DISCOUNTS])
        except (ValueError, IndexError):
            self._log_warning(f"Data parsing error in row {i}: {row[:3]}...")
            return

        # Merge "- Meal Transfer" suffix venues into the base venue.
        merged_from_transfer = venue.endswith(self.MERGE_SUFFIX)
        if merged_from_transfer:
            venue = venue[: -len(self.MERGE_SUFFIX)].strip()

        # Keep the pre-adjustment figure so the trace can show the subtraction.
        charged = sale
        service_fee = 0.0

        # Credit Card rows arrive with Grubhub's service fee still baked into
        # the tendered amount. Subtract it so only venue revenue is recorded.
        if payment_method == "Credit Card":
            try:
                service_fee = self._parse_dollar(row[self.COL_SERVICE_FEE])
                sale -= service_fee
                self._service_fee_total += service_fee
                self._service_fee_count += 1
            except (ValueError, IndexError):
                self._log_warning(f"Could not parse service fee in row {i}")
                service_fee = 0.0

        entry = self.data.setdefault(date, {}).setdefault(
            venue,
            {
                "total_count": 0,
                "total_sales": 0.0,
                "total_tax": 0.0,
                "tenders": CASHEET_TENDERS.copy(),
                "total_discounts": 0.0,
            },
        )
        entry["total_count"] += meal_count
        entry["total_sales"] += sale
        entry["total_tax"] += tax
        entry["total_discounts"] += discounts

        # Map the payment method to a cash-sheet tender column. Unmapped
        # methods are remembered and surfaced once at the end of the run.
        if payment_method in GRUBHUB_TENDERS:
            casheet_key = GRUBHUB_TENDERS[payment_method]
            entry["tenders"][casheet_key] += sale
        else:
            casheet_key = None
            self._unmapped_tenders.add(payment_method)

        if venue not in GRUBHUB_VENUE_MAP:
            self._unmapped_venues.add(venue)

        self._record_row_trace(
            date, venue, payment_method, casheet_key, charged, service_fee,
            sale, tax, discounts, meal_count, merged_from_transfer)

    def _record_row_trace(self, date, venue, payment_method, casheet_key,
                          charged, service_fee, sale, tax, discounts,
                          meal_count, merged_from_transfer):
        """
        Remember one row's arithmetic for the verbose trace.

        Built as a string here rather than logged immediately so ``parse`` can
        group the lines under their venue — the CSV interleaves venues, and a
        log that jumps between them is unreadable.
        """
        if not VERBOSE_TRACE:
            return

        # Fixed-width segments so the numbers line up into readable columns
        # even when a row has no fee to subtract.
        fee_part = f"  − fee ${service_fee:>7.2f}" if service_fee else " " * 16
        line = (f"{payment_method:<16} charged ${charged:>9.2f}{fee_part}"
                f"  = ${sale:>9.2f}  → "
                f"{casheet_key or 'UNMAPPED TENDER':<16}")

        notes = [f"tax ${tax:>7.2f}", f"meals {meal_count:>3}"]
        if discounts:
            notes.append(f"discount ${discounts:.2f} held")
        if merged_from_transfer:
            notes.append(f'merged from "{self.MERGE_SUFFIX.strip()}"')
        line += " · " + " · ".join(notes)

        self._trace_rows.setdefault((date, venue), []).append(line)

    def _emit_row_traces(self):
        """Print the collected row arithmetic, grouped venue by venue."""
        for (date, venue), lines in self._trace_rows.items():
            entry = self.data.get(date, {}).get(venue)
            if entry is None:
                continue
            self._trace(f"┌ {venue} · {date}  ({len(lines)} row(s))")
            for line in lines:
                self._trace(f"│ {line}")
            self._trace(
                f"└ venue total: sales ${entry['total_sales']:.2f} · "
                f"tax ${entry['total_tax']:.2f} · "
                f"discounts held ${entry['total_discounts']:.2f} · "
                f"meals {entry['total_count']}")

    def get_dates(self): return list(self.data.keys())
    def get_venues(self, date): return list(self.data.get(date, {}).keys())

    def get_data_dict(self, date, venue):
        raw = self.data.get(date, {}).get(venue)
        if raw is None:
            return None
        return {
            "location": strip_accents(venue),
            "date": date,
            "count": None,
            "transaction_meal_count": raw["total_count"],
            "total_sales": raw["total_sales"],
            "tax": raw["total_tax"],
            "discounts": raw["total_discounts"],
            "tenders": raw["tenders"].copy(),
        }

    def get_unmapped_venues(self): return self._unmapped_venues.copy()
    def get_unmapped_tenders(self): return self._unmapped_tenders.copy()
