import json
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
#  LOAD CONFIGURATION FROM JSON
# ═══════════════════════════════════════════════════════════════

CONFIG_FILE = Path(__file__).parent / "tender_config.json"


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
