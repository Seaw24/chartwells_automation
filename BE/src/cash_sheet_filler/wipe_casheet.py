import os
from openpyxl import load_workbook

# Import your configuration
from config import CASH_SHEET_FOLDER, FILL_COL_MAP


def clear_all_cash_sheets():
    print(f"Looking for Cash Sheets in: {CASH_SHEET_FOLDER}\n")

    # Exclude 'location' so we keep names, and 'date' so we don't wipe column 21 in the lower rows
    cols_to_clear = set(
        col for key, col in FILL_COL_MAP.items()
        if key not in ["location", "date"]
    )

    weekdays = ["Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday", "Saturday", "Sunday"]

    # Loop through every file in the folder
    for filename in os.listdir(CASH_SHEET_FOLDER):
        if not filename.endswith(".xlsx") or filename.startswith("~"):
            continue

        filepath = os.path.join(CASH_SHEET_FOLDER, filename)
        print(f"Wiping {filename}...")

        try:
            wb = load_workbook(filepath)
            changed = False

            # Check every sheet tab in the workbook
            for sheet_name in wb.sheetnames:
                # If the tab is a day of the week, wipe its data
                if sheet_name.strip().title() in weekdays:
                    ws = wb[sheet_name]

                    # 1. Clear the date at the top (Row 1)
                    date_col = FILL_COL_MAP.get("date")
                    if date_col:
                        ws.cell(row=1, column=date_col).value = None

                    # 2. Clear all the data rows (Row 4 down to the bottom)
                    # This naturally protects Rows 1, 2, and 3 (headers)
                    for row in range(5, ws.max_row + 1):
                        for col in cols_to_clear:
                            ws.cell(row=row, column=col).value = None

                    changed = True

            if changed:
                wb.save(filepath)
                print(f"  ✓ Wiped clean!")
            else:
                print(f"  ℹ️ No weekday tabs found.")

            wb.close()

        except PermissionError:
            print(f"  ❌ File is open in Excel! Please close it first.")
        except Exception as e:
            print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    clear_all_cash_sheets()
    print("\n✅ All cash sheets are now blank and ready for the AutoFill engine!")
