from BE.src.cash_sheet_filler.grubhub_parser import GrubhubParser
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    if len(sys.argv) < 2:
        print("Usage: python BE/test/see_lines.py <path-to-grubhub-csv>")
        return

    csv_path = sys.argv[1]
    parser = GrubhubParser(csv_path)
    ok = parser.parse()
    print(f"Parsed: {ok}")
    print(f"Dates found: {len(parser.get_dates())}")


if __name__ == "__main__":
    main()
