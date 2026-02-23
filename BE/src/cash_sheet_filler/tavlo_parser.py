"""
Tavlo Parser Module
Parses Tavlo sales reports (XML format).
"""

import xml.etree.ElementTree as ET
import traceback
try:
    from .config import TAVLO_TENDERS, CASHEET_TENDERS
    from .base_parser import BaseParser
except ImportError:
    from config import TAVLO_TENDERS, CASHEET_TENDERS
    from base_parser import BaseParser

from dateutil.parser import parse
from ..utils import strip_accents


class TavloParser(BaseParser):
    """
    Parser for Tavlo point-of-sale system XML export files.
    """

    NAMESPACES = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

    SECTION_MARKERS = {
        'count': "Num Closed/Finished Orders",
        'tax': "Sales Taxes",
        'cc': "Credit Card",
        'coupons': "Coupon/Voucher",
        'custom_tenders': "Custom Tender"
    }

    def __init__(self, file_path, tracker=None):
        super().__init__(tracker)  # Initialize BaseParser
        self.file_path = file_path
        self.data = {
            'date': "",
            'total_sales': 0.0,
            'tax': 0.0,
            'count': 0,
            'tenders': CASHEET_TENDERS.copy(),
            'location': "",
            'balance': 0.0
        }
        self.index = {}
        self.lines = []

    def read_report(self):
        try:
            tree = ET.parse(self.file_path)
            root = tree.getroot()

            financials_ws = self._find_financials_worksheet(root)
            if financials_ws is None:
                self._log_error("Could not find 'Financials' worksheet in XML")
                return False

            table = financials_ws.find('ss:Table', self.NAMESPACES)
            if table is None:
                self._log_error("Could not find Table in 'Financials' sheet")
                return False

            self._process_table_rows(table)
            return True

        except FileNotFoundError:
            self._log_error(f"File not found: {self.file_path}")
            return False
        except ET.ParseError as e:
            self._log_error(f"XML parse error: {e}")
            return False
        except Exception as e:
            self._log_error(f"Error reading report: {e}")
            traceback.print_exc()
            return False

    def _find_financials_worksheet(self, root):
        for ws in root.findall('ss:Worksheet', self.NAMESPACES):
            ws_name = ws.get(f"{{{self.NAMESPACES['ss']}}}Name")
            if ws_name == 'Financials':
                return ws
        return None

    def _process_table_rows(self, table):
        line_index = 0
        for row in table.findall('ss:Row', self.NAMESPACES):
            line_index = self._handle_row_index(row, line_index)
            cells = row.findall('ss:Cell', self.NAMESPACES)
            key_val, val_val = self._extract_cell_data(cells)
            self.lines.append((key_val, val_val))
            self._update_section_index(key_val, line_index)
            line_index += 1

    def _handle_row_index(self, row, current_index):
        row_index_attr = row.get(f"{{{self.NAMESPACES['ss']}}}Index")
        if row_index_attr:
            target_index = int(row_index_attr) - 1
            while current_index < target_index:
                self.lines.append(("", None))
                current_index += 1
        return current_index

    def _extract_cell_data(self, cells):
        key_val = ""
        val_val = None
        if len(cells) > 0:
            key_data = cells[0].find('ss:Data', self.NAMESPACES)
            if key_data is not None and key_data.text:
                key_val = str(key_data.text).strip()
        if len(cells) > 1:
            val_data = cells[1].find('ss:Data', self.NAMESPACES)
            if val_data is not None and val_data.text:
                try:
                    val_val = float(val_data.text)
                except (ValueError, TypeError):
                    val_val = str(val_data.text).strip()
        return key_val, val_val

    def _update_section_index(self, key, line_index):
        for section_name, marker in self.SECTION_MARKERS.items():
            if key == marker:
                self.index[section_name] = line_index
                break

    def parse_date(self):
        try:
            if not self.lines:
                raise ValueError("No data lines available")

            # Grab the text from the first cell
            location_string = str(self.lines[0][0])

            if "Sales on" in location_string:
                raw_date = location_string.split("Sales on")[-1].strip()
                # Format it to MM/DD/YYYY so the Excel autofiller understands it
                self.data['date'] = parse(raw_date).strftime("%m/%d/%Y")
                self._log(f"  ✓ Date: {self.data['date']}")
                return True

            self._log_warning("Date not found in report header")
            return False
        except Exception as e:
            self._log_error(f"Error parsing date: {e}")
            return False

    def parse_location(self):
        try:
            if not self.lines:
                raise ValueError("No data lines available")
            location_string = self.lines[0][0]
            self.data['location'] = location_string.split("Sales")[0].strip()
            self.data['location'] = strip_accents(self.data['location'])
            if not self.data['location']:
                raise ValueError("Location name is empty after parsing")
            return True
        except Exception as e:
            self._log_error(f"Error parsing location: {e}")
            return False

    def parse_count(self):
        try:
            if "count" not in self.index:
                self._log_error("Guest count section not found in report")
                return False
            index = self.index["count"] + 1
            total_count = 0
            while index < len(self.lines) and self.lines[index][0]:
                if self.lines[index][1] is not None:
                    total_count += int(self.lines[index][1])
                index += 1
            self.data["count"] = total_count
            self._log(f"  ✓ Guests: {self.data['count']}")
            return True
        except (ValueError, TypeError) as e:
            self._log_error(f"Error parsing guest count (invalid number): {e}")
            return False
        except Exception as e:
            self._log_error(f"Error parsing guest count: {e}")
            return False

    def parse_tax(self):
        try:
            if "tax" not in self.index:
                self._log_error("Tax section not found in report")
                return False
            index = self.index["tax"] + 1
            found_tax = False
            found_total = False
            while index < len(self.lines) and self.lines[index][0]:
                key = self.lines[index][0]
                value = self.lines[index][1]
                if value is not None:
                    if 'Net Tax' in key:
                        self.data["tax"] = float(value)
                        self._log(f"  ✓ Tax: ${self.data['tax']:.2f}")
                        found_tax = True
                    elif 'Total incl. Taxes' in key:
                        self.data["total_sales"] = float(value)
                        self._log(
                            f"  ✓ Total Sales: ${self.data['total_sales']:.2f}")
                        found_total = True
                index += 1
                if found_tax and found_total:
                    break
            if not found_tax:
                self._log_error("Net Tax not found in tax section")
            if not found_total:
                self._log_error("Total incl. Taxes not found in tax section")
            return found_tax and found_total
        except Exception as e:
            self._log_error(f"Error parsing tax section: {e}")
            return False

    def _parse_tender_section(self, section_name):
        try:
            if section_name not in self.index:
                self._log(
                    f"  ℹ️  Section '{section_name}' not found. Skipping.")
                return True
            index = self.index[section_name] + 1
            unrecognized_tenders = []
            while index < len(self.lines) and self.lines[index][0]:
                tender_name = self.lines[index][0].strip()
                tender_value = self.lines[index][1]
                if (not tender_name or tender_value is None or
                        tender_name in ["Credit Card Payments", "Credit Card Tips"]):
                    index += 1
                    continue
                if tender_name in TAVLO_TENDERS:
                    casheet_tender_name = TAVLO_TENDERS[tender_name]
                    self.data["tenders"][casheet_tender_name] += float(
                        tender_value)
                else:
                    unrecognized_tenders.append(tender_name)
                index += 1
            if unrecognized_tenders:
                self._log_warning(
                    f"Unrecognized tenders in {section_name}: {', '.join(unrecognized_tenders)}")
            return True
        except Exception as e:
            self._log_error(f"Error parsing {section_name}: {e}")
            traceback.print_exc()
            return False

    def parse_cc(self): return self._parse_tender_section("cc")

    def parse_custom_tender(
        self): return self._parse_tender_section("custom_tenders")

    def parse_coupon(self):
        try:
            if "coupons" not in self.index:
                self._log("  ℹ️  No 'Coupon/Voucher' section found. Skipping.")
                return True
            index = self.index["coupons"] + 1
            while index < len(self.lines) and self.lines[index][0]:
                index += 1
            if index > self.index["coupons"] + 1:
                coupon_key = self.lines[index - 1][0]
                coupon_value = self.lines[index - 1][1]
                if coupon_value is not None and "Total" in coupon_key:
                    converted_coupons_name = TAVLO_TENDERS["Coupons"]
                    self.data["tenders"][converted_coupons_name] = float(
                        coupon_value)
                    self._log(
                        f"  ✓ Coupons: ${self.data['tenders'][converted_coupons_name]:.2f}")
                    return True
            self._log_warning("Could not find coupon total line")
            return True
        except Exception as e:
            self._log_error(f"Error parsing coupons: {e}")
            return False

    def parse(self):
     # 0. print section separators  and report info for context

        if not self.read_report():
            self._log(f"\n{'=' * 70}")

            return False
        if not self.parse_location():
            self._log(f"\n{'=' * 70}")
            return False
        if not self.parse_date():
            self._log(f"\n{'=' * 70}")
            return False

        if not all([self.parse_count(), self.parse_tax(), self.parse_cc(), self.parse_custom_tender(), self.parse_coupon()]):
            self._log_error("Parsing failed on one or more sections")
            return False

        self._log("  ✅ Parsing successful!")
        return True

    def get_data_dict(self):
        return {
            'location': self.data['location'],
            'date': self.data['date'],
            'total_sales': self.data.get('total_sales', 0.0),
            'tax': self.data.get('tax', 0.0),
            'count': self.data.get('count', 0),
            'net_sales': self.data.get('total_sales', 0.0) - self.data.get('tax', 0.0),
            'tenders': self.data['tenders'].copy()
        }

    def get_unmapped_venues(self): return []
    def get_unmapped_tenders(self): return []
