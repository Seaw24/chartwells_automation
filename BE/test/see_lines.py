# run_parser.py (at your project root)
import os
import sys

# Allow running this file directly by adding the project root to sys.path.
PROJECT_ROOT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
    from BE.src.cash_sheet_filler.grubhub_parser import Grubhub_parser


parser = Grubhub_parser(
    r"C:\Users\admin\Downloads\SalesbyVenuebyPaymentMethod_2026-02-02-2026-02-16.csv")
parser.parse()
