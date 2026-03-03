"""
Infor Parser Module
Parses Infor point-of-sale system CSV reports.
"""

import traceback
from .config import INFOR_TENDERS, CASHEET_TENDERS
from .base_parser import BaseParser
from dateutil.parser import parse

from ..utils import strip_accents


class InforParser(BaseParser):
    """
    Parser for Infor point-of-sale system CSV export files.
    """

    # Section identifiers in CSV reports
    SECTION_MARKERS = {
        'summary': 'SUMMARY',
        'tax': 'TAX COLLECTED',
        'tenders': 'TENDERS',
        'count': 'SERVICE',
    }

    def __init__(self, file_path, tracker=None):
        super().__init__(tracker)  # Initialize BaseParser with tracker
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
        self.content = None
        self.lines = []

    def read_report(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
                self.lines = self.content.split('\n')

                if not self.lines:
                    raise ValueError("The file is empty")

                for i, line in enumerate(self.lines):
                    line_stripped = line.strip()
                    for section_key, marker in self.SECTION_MARKERS.items():
                        if marker in line_stripped:
                            self.index[section_key] = i
                return True

        except FileNotFoundError:
            self._log_error(f"File not found: {self.file_path}")
            return False
        except UnicodeDecodeError:
            self._log_error(
                f"Cannot decode file (not UTF-8): {self.file_path}")
            return False
        except Exception as e:
            self._log_error(f"Error reading file: {e}")
            traceback.print_exc()
            return False

    def parse_date(self):
        try:
            if len(self.lines) < 3:
                raise ValueError("Not enough lines to parse date")

            # The date is on the 3rd line (index 2)
            date_line = self.lines[2].strip()

            if "Date(s):" in date_line:
                # Split by colon, grab the right side, and remove the CSV commas
                raw_date = date_line.split(":")[1].replace(',', '').strip()
                # Format to MM/DD/YYYY
                self.data['date'] = parse(
                    raw_date).strftime("%m/%d/%Y")
                self._log(f"  ✓ Date: {self.data['date']}")
                return True

            self._log_warning("Date not found on expected line")
            return False
        except Exception as e:
            self._log_error(f"Error parsing date from report: {e}")
            return False

    def parse_location(self):
        try:
            if not self.lines:
                raise ValueError("No lines available to parse")
            parts = self.lines[0].strip().replace(',', '').split()[3:]
            self.data['location'] = ' '.join(parts)
            self.data['location'] = strip_accents(self.data['location'])

            if not self.data['location']:
                raise ValueError("Location name is empty after parsing")
            return True
        except Exception as e:
            self._log_error(f"Error parsing location from first line: {e}")
            return False

    def parse_summary(self):
        try:
            if 'summary' not in self.index:
                self._log_error("SUMMARY section not found in report")
                return False

            start_index = self.index['summary'] + 1
            end_index = self.index.get('tax', start_index + 10) - 1

            for line in self.lines[start_index:end_index]:
                if 'Total Sales' in line.strip():
                    try:
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            self.data['total_sales'] = float(parts[1].strip())
                            self._log(
                                f"  ✓ Total Sales: ${self.data['total_sales']:.2f}")
                            return True
                    except (ValueError, IndexError) as e:
                        self._log_error(f"Cannot parse Total Sales value: {e}")
                        return False

            self._log_warning(
                "Total Sales not found - report may have no data")
            return False
        except Exception as e:
            self._log_error(f"Error parsing summary section: {e}")
            traceback.print_exc()
            return False

    def parse_tax(self):
        try:
            if 'tax' not in self.index:
                self._log_error("TAX COLLECTED section not found in report")
                return False

            start_index = self.index['tax'] + 1
            end_index = self.index.get('tenders', start_index + 10) - 1

            for line in self.lines[start_index:end_index]:
                line_stripped = line.strip()
                if 'Total Taxes:' in line_stripped or 'Total Taxes' in line_stripped:
                    try:
                        parts = line_stripped.split(',')
                        if len(parts) >= 2:
                            self.data['tax'] = float(parts[1].strip())
                            self._log(f"  ✓ Tax: ${self.data['tax']:.2f}")
                            return True
                    except (ValueError, IndexError) as e:
                        self._log_error(f"Cannot parse Tax value: {e}")
                        return False
            self._log_warning("Tax not found in report")
            return True
        except Exception as e:
            self._log_error(f"Error parsing tax section: {e}")
            return False

    def parse_tenders(self):
        try:
            if 'tenders' not in self.index:
                self._log_error("TENDERS section not found in report")
                return False

            start_index = self.index['tenders'] + 1
            end_index = self.index.get('count', start_index + 20) - 1

            total_tender = 0.0
            recognized_count = 0
            unrecognized_tenders = []

            for line in self.lines[start_index:end_index]:
                if 'Name,Amount' in line or '% of Total Tender' in line:
                    continue
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        tender_name = parts[0].strip()
                        if not tender_name:
                            continue
                        try:
                            tender_amount = float(parts[1].strip())
                            if tender_name == 'Total Tender:':
                                self.data["balance"] = tender_amount - \
                                    self.data["total_sales"]
                                break
                            if tender_name not in INFOR_TENDERS:
                                unrecognized_tenders.append(tender_name)
                                continue
                            casheet_tender_name = INFOR_TENDERS[tender_name]
                            self.data['tenders'][casheet_tender_name] += tender_amount
                            total_tender += tender_amount
                            recognized_count += 1
                            self._log(
                                f"   ✓ Recognized tender: '{tender_name}' mapped to '{casheet_tender_name}' with amount ${tender_amount:.2f} make  it to be {self.data['tenders'][casheet_tender_name]:.2f}")
                        except ValueError:
                            self._log_warning(
                                f"Invalid amount for tender '{tender_name}'")
                            continue

            if unrecognized_tenders:
                self._log_warning(
                    f"Unrecognized tenders: {', '.join(unrecognized_tenders)}")

            self._log(
                f"  ✓ Tenders: {recognized_count} types, ${total_tender:.2f} total")
            return True
        except Exception as e:
            self._log_error(f"Error parsing tenders section: {e}")
            traceback.print_exc()
            return False

    def parse_count(self):
        try:
            if 'count' not in self.index:
                self._log_error("SERVICE section not found in report")
                return False

            start_index = self.index['count'] + 1
            for line in self.lines[start_index:]:
                if 'Guests' in line.strip():
                    try:
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            self.data['count'] = int(float(parts[1].strip()))
                            self._log(f"  ✓ Guests: {self.data['count']}")
                            return True
                    except (ValueError, IndexError) as e:
                        self._log_error(f"Cannot parse guest count: {e}")
                        return False
            self._log_warning(
                "Guest count not found - report may have no data")
            return True
        except Exception as e:
            self._log_error(f"Error parsing guest count section: {e}")
            return False

    def parse(self):

        if not self.read_report():
            self._log(f"{'=' * 70}")
            return False
        if not self.parse_location():
            self._log(f"{'=' * 70}")

            return False
        if not self.parse_date():
            self._log(f"{'=' * 70}")
            return False

        sections_ok = (
            self.parse_summary() and
            self.parse_tax() and
            self.parse_tenders() and
            self.parse_count()
        )

        if sections_ok:
            self._log("  ✅ Parsing successful!")
        else:
            self._log_error("Parsing failed on one or more sections")
        self._log(f"{'=' * 70}\n")
        return sections_ok

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
