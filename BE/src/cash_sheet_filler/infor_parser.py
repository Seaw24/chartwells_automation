"""
Infor Parser Module
Parses Infor point-of-sale system CSV reports and extracts financial data including
sales, taxes, guest counts, and tender breakdowns.
"""

import traceback
try:
    from .config import INFOR_TENDERS, CASHEET_TENDERS
except ImportError:
    from config import INFOR_TENDERS, CASHEET_TENDERS


class InforParser:
    """
    Parser for Infor point-of-sale system CSV export files.

    Extracts sales data from CSV files exported from the Infor POS system,
    including location, date, sales figures, taxes, guest counts, and tender breakdowns.

    Attributes:
        file_path (str): Path to the CSV report file
        data (dict): Parsed data including date, sales, tax, count, tenders, and location
        index (dict): Line indices for key sections in the report
        content (str): Raw file content
        lines (list): File content split into lines
    """

    # Section identifiers in CSV reports
    SECTION_MARKERS = {
        'summary': 'SUMMARY',
        'tax': 'TAX COLLECTED',
        'tenders': 'TENDERS',
        'count': 'SERVICE',
    }

    def __init__(self, file_path, report_date=None):
        """
        Initialize the Infor CSV parser.

        Args:
            file_path (str): Path to the CSV report file
            report_date (str, optional): Report date in MM/DD/YYYY format
        """
        self.file_path = file_path
        self.data = {
            'date': report_date,
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
        """
        Read the CSV file and build an index of section locations.

        Returns:
            bool: True if file read successfully, False otherwise
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                self.content = f.read()
                self.lines = self.content.split('\n')

                if not self.lines:
                    raise ValueError("The file is empty")

                # Build index of section markers
                for i, line in enumerate(self.lines):
                    line_stripped = line.strip()
                    for section_key, marker in self.SECTION_MARKERS.items():
                        if marker in line_stripped:
                            self.index[section_key] = i

                return True

        except FileNotFoundError:
            print(f"  ❌ File not found: {self.file_path}")
            return False

        except UnicodeDecodeError:
            print(f"  ❌ File encoding error - unable to read as UTF-8")
            return False

        except Exception as e:
            print(f"  ❌ Error reading file: {e}")
            traceback.print_exc()
            return False

    def parse_location(self):
        """
        Extract location name from the first line of the CSV.

        The first line typically contains: "Operations Report-Location Name-(Date)"

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.lines:
                raise ValueError("No lines available to parse")

            # Remove commas and split, then take everything after first 3 words
            parts = self.lines[0].strip().replace(',', '').split()[3:]
            self.data['location'] = ' '.join(parts)

            if not self.data['location']:
                raise ValueError("Location name is empty after parsing")

            return True

        except Exception as e:
            print(f"  ❌ Error parsing location: {e}")
            return False

    def parse_summary(self):
        """
        Extract total sales from the SUMMARY section.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if 'summary' not in self.index:
                print("  ❌ SUMMARY section not found in report")
                return False

            start_index = self.index['summary'] + 1
            end_index = self.index.get('tax', start_index + 10) - 1

            # Search for Total Sales line
            for line in self.lines[start_index:end_index]:
                if 'Total Sales' in line.strip():
                    try:
                        # Parse: "Total Sales,12345.67"
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            self.data['total_sales'] = float(parts[1].strip())
                            print(
                                f"  ✓ Total Sales: ${self.data['total_sales']:.2f}")
                            return True
                    except (ValueError, IndexError) as e:
                        print(f"  ❌ Cannot parse Total Sales value: {e}")
                        return False

            print(f"  ⚠️  Total Sales not found - report may have no data")
            return False

        except Exception as e:
            print(f"  ❌ Error parsing summary section: {e}")
            traceback.print_exc()
            return False

    def parse_tax(self):
        """
        Extract tax amount from the TAX COLLECTED section.

        Returns:
            bool: True if successful or tax not found (non-fatal), False on error
        """
        try:
            if 'tax' not in self.index:
                print("  ❌ TAX COLLECTED section not found in report")
                return False

            start_index = self.index['tax'] + 1
            end_index = self.index.get('tenders', start_index + 10) - 1

            # Search for Total Taxes line
            for line in self.lines[start_index:end_index]:
                line_stripped = line.strip()
                if 'Total Taxes:' in line_stripped or 'Total Taxes' in line_stripped:
                    try:
                        # Parse: "Total Taxes:,123.45" or "Total Taxes,123.45"
                        parts = line_stripped.split(',')
                        if len(parts) >= 2:
                            self.data['tax'] = float(parts[1].strip())
                            print(f"  ✓ Tax: ${self.data['tax']:.2f}")
                            return True
                    except (ValueError, IndexError) as e:
                        print(f"  ❌ Cannot parse tax value: {e}")
                        return False

            # Tax not found is not always fatal (some locations may not have tax)
            print(f"  ⚠️  Tax not found in report")
            return True

        except Exception as e:
            print(f"  ❌ Error parsing tax section: {e}")
            traceback.print_exc()
            return False

    def parse_tenders(self):
        """
        Parse the TENDERS section and extract all tender amounts.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if 'tenders' not in self.index:
                print("  ❌ TENDERS section not found in report")
                return False

            start_index = self.index['tenders'] + 1
            end_index = self.index.get('count', start_index + 20) - 1

            total_tender = 0.0
            recognized_count = 0
            unrecognized_tenders = []

            for line in self.lines[start_index:end_index]:
                # Skip header and summary rows
                if 'Name,Amount' in line or '% of Total Tender' in line:
                    continue

                # Stop at total line

                # Parse tender line: "TenderName,Amount"
                if ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        tender_name = parts[0].strip()

                        # Skip empty lines
                        if not tender_name:
                            continue

                        try:
                            tender_amount = float(parts[1].strip())
                            # Cal the balance
                            if tender_name == 'Total Tender:':
                                self.data["balance"] = tender_amount - \
                                    self.data["total_sales"]
                                break

                            # Check if tender is recognized
                            if tender_name not in INFOR_TENDERS:
                                unrecognized_tenders.append(tender_name)
                                continue

                            # Map to casheet tender name and store
                            casheet_tender_name = INFOR_TENDERS[tender_name]
                            self.data['tenders'][casheet_tender_name] = tender_amount
                            total_tender += tender_amount
                            recognized_count += 1

                        except ValueError:
                            print(
                                f"  ⚠️  Invalid amount for tender '{tender_name}'")
                            continue

            # Report unrecognized tenders
            if unrecognized_tenders:
                print(
                    f"  ⚠️  Unrecognized tenders: {', '.join(unrecognized_tenders)}")

            print(
                f"  ✓ Tenders: {recognized_count} types, ${total_tender:.2f} total")
            return True

        except Exception as e:
            print(f"  ❌ Error parsing tenders section: {e}")
            traceback.print_exc()
            return False

    def parse_count(self):
        """
        Extract guest count from the SERVICE section.

        Returns:
            bool: True if successful or count not found (non-fatal), False on error
        """
        try:
            if 'count' not in self.index:
                print("  ❌ SERVICE section not found in report")
                return False

            start_index = self.index['count'] + 1

            # Search for Guests line
            for line in self.lines[start_index:]:
                if 'Guests' in line.strip():
                    try:
                        # Parse: "Guests,123" or "Guests,123.0"
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            # Convert to int (handle potential float representation)
                            self.data['count'] = int(float(parts[1].strip()))
                            print(f"  ✓ Guests: {self.data['count']}")
                            return True
                    except (ValueError, IndexError) as e:
                        print(f"  ❌ Cannot parse guest count: {e}")
                        return False

            # Guest count not found - may indicate no data for the day
            print(f"  ⚠️  Guest count not found - report may have no data")
            return True

        except Exception as e:
            print(f"  ❌ Error parsing guest count: {e}")
            traceback.print_exc()
            return False

    def parse(self):
        """
        Main parsing method - orchestrates parsing of all sections.

        Returns:
            bool: True if all sections parsed successfully, False otherwise
        """
        # Step 1: Read the CSV file
        if not self.read_report():
            return False

        # Step 2: Parse location (must be done before printing header)
        if not self.parse_location():
            return False

        # Print parsing header
        print(f"\n{'=' * 70}")
        print(f"Parsing: {self.file_path}")
        print(f"Location: {self.data['location']}")
        print(f"Date: {self.data['date']}")
        print(f"{'=' * 70}")

        # Step 3: Parse all data sections
        sections_ok = (
            self.parse_summary() and
            self.parse_tax() and
            self.parse_tenders() and
            self.parse_count()
        )

        # Print result
        print(f"{'=' * 70}")
        if sections_ok:
            print("✅ Parsing successful!")
        else:
            print("❌ Parsing failed on one or more sections")
        print(f"{'=' * 70}\n")

        return sections_ok

    # ==================== PROPERTY ACCESSORS ====================

    @property
    def date_value(self):
        """Get the report date."""
        return self.data['date']

    @property
    def total_sales(self):
        """Get total sales including tax."""
        return self.data.get('total_sales', 0.0)

    @property
    def tax(self):
        """Get tax amount."""
        return self.data.get('tax', 0.0)

    @property
    def count(self):
        """Get number of guests."""
        return self.data.get('count', 0)

    @property
    def location(self):
        """Get location name."""
        return self.data.get('location', '')

    @property
    def net_sales(self):
        """Calculate net sales (total - tax)."""
        return self.total_sales - self.tax

    @property
    def all_tenders(self):
        """Get a copy of all tenders dictionary."""
        return self.data['tenders'].copy()

    # ==================== PUBLIC METHODS ====================

    def get_tender_amount(self, tender_name):
        """
        Get amount for a specific tender type.

        Args:
            tender_name (str): Name of tender type

        Returns:
            float: Amount or 0.0 if not found
        """
        return self.data['tenders'].get(tender_name, 0.0)

    def has_tender(self, tender_name):
        """
        Check if a tender type exists in the data.

        Args:
            tender_name (str): Name of tender type

        Returns:
            bool: True if tender exists, False otherwise
        """
        return tender_name in self.data['tenders']

    def get_data_dict(self):
        """
        Get all parsed data as a dictionary.

        Returns:
            dict: Complete data dictionary with location, date, sales, tax, count, and tenders
        """
        return {
            'location': self.location,
            'date': self.date_value,
            'total_sales': self.total_sales,
            'tax': self.tax,
            'count': self.count,
            'net_sales': self.net_sales,
            'tenders': self.all_tenders
        }

    def __repr__(self):
        """String representation of the parser."""
        return (f"InforParser(location='{self.location}', "
                f"date='{self.date_value}', "
                f"total_sales=${self.total_sales:.2f})")
