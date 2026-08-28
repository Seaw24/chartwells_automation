# config.py
import sys
import json
import shutil
from pathlib import Path

try:
    from BE.src.path_helper import sync_config_with_defaults as _sync_config_with_defaults
except ImportError:
    try:
        from ..path_helper import sync_config_with_defaults as _sync_config_with_defaults
    except ImportError:
        def _sync_config_with_defaults(editable, bundled):
            return []


def _get_config_path():
    filename = "tender_config.json"

    if getattr(sys, 'frozen', False):
        editable = Path(sys.executable).parent / "config" / filename
        bundled = Path(sys._MEIPASS) / "BE" / "src" / "tender_break" / filename
        if not editable.exists():
            editable.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled, editable)
        else:
            # Top up a config seeded by an older build with the keys this
            # build's default has gained — additions only, nothing replaced.
            _sync_config_with_defaults(editable, bundled)
        return editable

    return Path(__file__).parent / filename


CONFIG_FILE = _get_config_path()


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
