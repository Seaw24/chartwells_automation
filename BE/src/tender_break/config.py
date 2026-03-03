# config.py
import sys
import json
from pathlib import Path


def _get_config_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "BE" / "src" / "tender_break"
    return Path(__file__).parent


CONFIG_FILE = _get_config_dir() / "tender_config.json"


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

FILENAME_TO_MASTER_NAME = _config["filename_to_master_name"]
LOCATION_START_COL = _config["location_start_col"]
DIRECTORY_PATHS = _config["directory_paths"]
IMPORTANT_CASHEET_DATA_COL = _config["important_casheet_data_col"]
FIRST_DATE_ROW = _config.get("first_date_row", 3)
DATE_COL = _config.get("date_col", 21)
