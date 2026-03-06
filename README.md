# Chartwells Automation

Desktop automation app for:

- Cash Sheet autofill from Infor, Tavlo, and Grubhub reports
- Tender Breakdown autofill from cash sheets

## Quick Start (Windows)

1. Create/activate virtual environment
   - `python -m venv myenv`
   - `myenv\Scripts\Activate.ps1`
2. Install dependencies
   - `pip install -r requirements.txt`
3. Run app
   - `python UI/dashboard.py`

## Build EXE (PyInstaller)

- `pyinstaller chartwells.spec`
- Output executable is generated under `build/` / `dist/` per PyInstaller settings.

## Project Structure

- `UI/` desktop interface (CustomTkinter)
- `BE/src/cash_sheet_filler/` report parsers + cash sheet autofill engine
- `BE/src/tender_break/` tender breakdown engine
- `BE/src/db/` SQLite logging for autofill records
- `reports/` source reports folder
- `cash sheets/` source cash-sheet workbooks
- `DB/` SQLite database storage

## Notes

- Configuration is loaded from JSON config files in backend modules.
- In frozen mode, editable config files are created next to the executable in `config/`.
