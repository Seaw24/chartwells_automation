# config.py
import json
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
#  LOAD CONFIGURATION FROM JSON
# ═══════════════════════════════════════════════════════════════

CONFIG_FILE = Path(__file__).parent / "cash_sheet_config.json"


def load_config():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_FILE}")
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Error decoding JSON from configuration file: {e}")

    return config


def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Error saving configuration to file: {e}")


_config = load_config()

# ═══════════════════════════════════════════════════════════════
#  EXPORT CONFIG VARIABLES
# ═══════════════════════════════════════════════════════════════

REPORTS_CASHSHEET_MAP = _config["reports_cashsheet_map"]
FILL_COL_MAP = _config["fill_col_map"]
CHECKING_COL_MAP = _config["checking_col_map"]
INFOR_TENDERS = _config["infor_tenders"]
TAVLO_TENDERS = _config["tavlo_tenders"]
CASHEET_TENDERS = _config["casheet_tenders"]
GRUBHUB_TENDERS = _config["grubhub_tenders"]
GRUBHUB_VENUE_MAP = _config["grubhub_venue_map"]
REPORTS_FOLDER = _config["reports_folder"]
CASH_SHEET_FOLDER = _config["cash_sheets_folder"]
