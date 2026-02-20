"""
Tavlo Parser Module
Parses Tavlo sales reports (XML format) and extracts financial data including
sales, taxes, guest counts, and tender breakdowns.
"""

import xml.etree.ElementTree as ET
import traceback
try:
    from .config import TAVLO_TENDERS, CASHEET_TENDERS
except ImportError:
    from config import TAVLO_TENDERS, CASHEET_TENDERS


class TavloParser:
    """
    Parser for Tavlo point-of-sale system XML export files.

    Extracts sales data from XML files exported from the Tavlo POS system,
    including location, date, sales figures, taxes, guest counts, and tender breakdowns.

    Attributes:
        xl_path (str): Path to the XML report file
        data (dict): Parsed data including date, sales, tax, count, tenders, and location
        index (dict): Row indices for key sections in the report
        lines (list): Raw data as list of (key, value) tuples
    """

    # XML namespace for Excel SpreadsheetML format
    NAMESPACES = {'ss': 'urn:schemas-microsoft-com:office:spreadsheet'}

    # Section identifiers in the report
    SECTION_MARKERS = {
        'count': "Num Closed/Finished Orders",
        'tax': "Sales Taxes",
        'cc': "Credit Card",
        'coupons': "Coupon/Voucher",
        'custom_tenders': "Custom Tender"
    }

    def __init__(self, xl_path, report_date=None):
        """
        Initialize the Tavlo parser.

        Args:
            xl_path (str): Path to the Tavlo XML report file
            report_date (str, optional): Report date in MM/DD/YYYY format
        """
        self.xl_path = xl_path
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
        self.lines = []  # Stores (key, value) pairs from XML

    def read_report(self):
        """
        Read and parse the XML report file into structured data.

        Extracts all rows from the 'Financials' worksheet and builds an index
        of key section locations for later parsing.

        Returns:
            bool: True if file read successfully, False otherwise
        """
        try:
            # Parse the XML file
            tree = ET.parse(self.xl_path)
            root = tree.getroot()

            # Find the "Financials" worksheet
            financials_ws = self._find_financials_worksheet(root)
            if financials_ws is None:
                print("  ❌ Could not find 'Financials' sheet in the XML file")
                return False

            # Find the table within the worksheet
            table = financials_ws.find('ss:Table', self.NAMESPACES)
            if table is None:
                print("  ❌ Could not find Table in 'Financials' sheet")
                return False

            # Process all rows and build line index
            self._process_table_rows(table)
            return True

        except FileNotFoundError:
            print(f"  ❌ File not found: {self.xl_path}")
            return False

        except ET.ParseError as e:
            print(f"  ❌ XML parse error: {e}")
            return False

        except Exception as e:
            print(f"  ❌ Error reading report: {e}")
            traceback.print_exc()
            return False

    def _find_financials_worksheet(self, root):
        """
        Locate the 'Financials' worksheet in the XML document.

        Args:
            root: XML root element

        Returns:
            Element or None: The Financials worksheet element if found
        """
        for ws in root.findall('ss:Worksheet', self.NAMESPACES):
            ws_name = ws.get(f"{{{self.NAMESPACES['ss']}}}Name")
            if ws_name == 'Financials':
                return ws
        return None

    def _process_table_rows(self, table):
        """
        Process all rows in the table and build the lines list and section index.

        Args:
            table: XML table element containing the data
        """
        line_index = 0

        for row in table.findall('ss:Row', self.NAMESPACES):
            # Handle rows with Index attribute (indicates skipped rows in XML)
            line_index = self._handle_row_index(row, line_index)

            # Extract cell data
            cells = row.findall('ss:Cell', self.NAMESPACES)
            key_val, val_val = self._extract_cell_data(cells)

            # Store the line
            self.lines.append((key_val, val_val))

            # Update section index if this is a section marker
            self._update_section_index(key_val, line_index)

            line_index += 1

    def _handle_row_index(self, row, current_index):
        """
        Handle XML rows with Index attribute that indicate skipped rows.

        Args:
            row: XML row element
            current_index: Current line index

        Returns:
            int: Updated line index
        """
        row_index_attr = row.get(f"{{{self.NAMESPACES['ss']}}}Index")
        if row_index_attr:
            target_index = int(row_index_attr) - 1  # Convert to 0-based
            # Fill in empty rows that were skipped
            while current_index < target_index:
                self.lines.append(("", None))
                current_index += 1
        return current_index

    def _extract_cell_data(self, cells):
        """
        Extract key and value from the first two cells in a row.

        Args:
            cells: List of cell elements

        Returns:
            tuple: (key_string, value) where value is float if numeric, string otherwise
        """
        key_val = ""
        val_val = None

        # Extract key (first column)
        if len(cells) > 0:
            key_data = cells[0].find('ss:Data', self.NAMESPACES)
            if key_data is not None and key_data.text:
                key_val = str(key_data.text).strip()

        # Extract value (second column)
        if len(cells) > 1:
            val_data = cells[1].find('ss:Data', self.NAMESPACES)
            if val_data is not None and val_data.text:
                try:
                    val_val = float(val_data.text)
                except (ValueError, TypeError):
                    val_val = str(val_data.text).strip()

        return key_val, val_val

    def _update_section_index(self, key, line_index):
        """
        Update the section index if the key matches a known section marker.

        Args:
            key: Cell key/label
            line_index: Current line index
        """
        for section_name, marker in self.SECTION_MARKERS.items():
            if key == marker:
                self.index[section_name] = line_index
                break

    def parse_location(self):
        """
        Extract location name from the first line of the report.

        The location is typically in the format: "Location Name Sales on YYYY-MM-DD"

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.lines:
                raise ValueError("No data lines available")

            location_string = self.lines[0][0]
            # Split on "Sales" and take the part before it
            self.data['location'] = location_string.split("Sales")[0].strip()

            if not self.data['location']:
                raise ValueError("Location name is empty after parsing")

            return True

        except Exception as e:
            print(f"  ❌ Error parsing location: {e}")
            return False

    def parse_count(self):
        """
        Extract total guest count from the report.

        Sums all order counts in the guest count section.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if "count" not in self.index:
                print("  ❌ Guest count section not found in report")
                return False

            index = self.index["count"] + 1
            total_count = 0

            # Sum all counts until we hit an empty key
            while index < len(self.lines) and self.lines[index][0]:
                if self.lines[index][1] is not None:
                    total_count += int(self.lines[index][1])
                index += 1

            self.data["count"] = total_count
            print(f"  ✓ Guests: {self.data['count']}")
            return True

        except (ValueError, TypeError) as e:
            print(f"  ❌ Error parsing guest count (invalid number): {e}")
            return False

        except Exception as e:
            print(f"  ❌ Error parsing guest count: {e}")
            return False

    def parse_tax(self):
        """
        Extract tax and total sales from the taxes section.

        Looks for 'Net Tax' and 'Total incl. Taxes' entries.

        Returns:
            bool: True if both values found successfully, False otherwise
        """
        try:
            if "tax" not in self.index:
                print("  ❌ Tax section not found in report")
                return False

            index = self.index["tax"] + 1
            found_tax = False
            found_total = False

            # Search for both Net Tax and Total incl. Taxes
            while index < len(self.lines) and self.lines[index][0]:
                key = self.lines[index][0]
                value = self.lines[index][1]

                if value is not None:
                    if 'Net Tax' in key:
                        self.data["tax"] = float(value)
                        print(f"  ✓ Tax: ${self.data['tax']:.2f}")
                        found_tax = True

                    elif 'Total incl. Taxes' in key:
                        self.data["total_sales"] = float(value)
                        print(
                            f"  ✓ Total Sales: ${self.data['total_sales']:.2f}")
                        found_total = True

                index += 1

                # Stop once we have both values
                if found_tax and found_total:
                    break

            if not found_tax:
                print("  ❌ Net Tax not found in tax section")
            if not found_total:
                print("  ❌ Total incl. Taxes not found in tax section")

            return found_tax and found_total

        except (ValueError, TypeError) as e:
            print(f"  ❌ Error parsing tax (invalid number): {e}")
            return False

        except Exception as e:
            print(f"  ❌ Error parsing tax section: {e}")
            return False

    def _parse_tender_section(self, section_name):
        """
        Generic helper to parse tender sections (credit cards and custom tenders).

        Args:
            section_name (str): Name of the section in self.index

        Returns:
            bool: True if successful or section doesn't exist, False on error
        """
        try:
            if section_name not in self.index:
                print(f"  ℹ️  Section '{section_name}' not found. Skipping.")
                return True  # Not an error, section just doesn't exist

            index = self.index[section_name] + 1
            unrecognized_tenders = []

            # Process all tender entries until empty key
            while index < len(self.lines) and self.lines[index][0]:
                tender_name = self.lines[index][0].strip()
                tender_value = self.lines[index][1]

                # Skip empty or summary rows
                if (not tender_name or
                    tender_value is None or
                        tender_name in ["Credit Card Payments", "Credit Card Tips"]):
                    index += 1
                    continue

                # Map tender to casheet name and add amount
                if tender_name in TAVLO_TENDERS:
                    casheet_tender_name = TAVLO_TENDERS[tender_name]
                    self.data["tenders"][casheet_tender_name] += float(
                        tender_value)
                else:
                    unrecognized_tenders.append(tender_name)

                index += 1

            # Report unrecognized tenders
            if unrecognized_tenders:
                print(
                    f"  ⚠️  Unrecognized tenders in {section_name}: {', '.join(unrecognized_tenders)}")

            return True

        except (ValueError, TypeError) as e:
            print(f"  ❌ Error in {section_name} (invalid number): {e}")
            return False

        except Exception as e:
            print(f"  ❌ Error parsing {section_name}: {e}")
            traceback.print_exc()
            return False

    def parse_cc(self):
        """
        Parse credit card tender section.

        Returns:
            bool: True if successful, False otherwise
        """
        return self._parse_tender_section("cc")

    def parse_custom_tender(self):
        """
        Parse custom tender section (e.g., Flex, Dining Dollars, etc.).

        Returns:
            bool: True if successful, False otherwise
        """
        return self._parse_tender_section("custom_tenders")

    def parse_coupon(self):
        """
        Extract coupon/voucher total from the report.

        Returns:
            bool: True if successful or section doesn't exist, False on error
        """
        try:
            if "coupons" not in self.index:
                print("  ℹ️  No 'Coupon/Voucher' section found. Skipping.")
                return True  # Not an error, just no coupons

            index = self.index["coupons"] + 1

            # Navigate to the end of the coupon section (last non-empty row)
            while index < len(self.lines) and self.lines[index][0]:
                index += 1

            # The total should be on the last row before empty
            if index > self.index["coupons"] + 1:
                coupon_key = self.lines[index - 1][0]
                coupon_value = self.lines[index - 1][1]

                if coupon_value is not None and "Total" in coupon_key:
                    converted_coupons_name = TAVLO_TENDERS["Coupons"]
                    self.data["tenders"][converted_coupons_name] = float(
                        coupon_value)
                    print(
                        f"  ✓ Coupons: ${self.data['tenders'][converted_coupons_name]:.2f}")
                    return True

            print("  ⚠️  Could not find coupon total line")
            return True  # Not fatal, continue processing

        except (ValueError, TypeError) as e:
            print(f"  ❌ Error parsing coupons (invalid number): {e}")
            return False

        except Exception as e:
            print(f"  ❌ Error parsing coupons: {e}")
            return False

    def parse(self):
        """
        Main parsing method - orchestrates parsing of all sections.

        Returns:
            bool: True if all sections parsed successfully, False otherwise
        """
        # Step 1: Read the XML file
        if not self.read_report():
            return False

        # Step 2: Parse location name
        if not self.parse_location():
            return False

        # Print parsing header
        print(f"\n{'=' * 70}")
        print(f"Parsing: {self.xl_path}")
        print(f"Location: {self.data['location']}")
        print(f"Date: {self.data['date']}")
        print(f"{'=' * 70}")

        # Step 3: Parse all data sections
        ok_count = self.parse_count()
        ok_tax = self.parse_tax()
        ok_cc = self.parse_cc()
        ok_custom = self.parse_custom_tender()
        ok_coupon = self.parse_coupon()

        # Check if all sections parsed successfully
        if not all([ok_count, ok_tax, ok_cc, ok_custom, ok_coupon]):
            print(f"{'=' * 70}")
            print("❌ Parsing failed on one or more sections")
            print(f"{'=' * 70}\n")
            return False

        print(f"{'=' * 70}")
        print("✅ Parsing successful!")
        print(f"{'=' * 70}")
        return True

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
        return (f"TavloParser(location='{self.location}', "
                f"date='{self.date_value}', "
                f"total_sales=${self.total_sales:.2f})")
