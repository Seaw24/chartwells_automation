# config.py
import sys
import json
import shutil
from pathlib import Path

# Initialize the database manager


def _get_config_path():
    """
    Editable config lives next to the .exe (or in dev, next to this file).
    On first run, copy the bundled default to the editable location.
    """
    filename = "cash_sheet_config.json"

    if getattr(sys, 'frozen', False):
        # Editable: same folder as the .exe
        editable = Path(sys.executable).parent / "config" / filename
        # Bundled default (read-only, inside _MEIPASS)
        bundled = Path(sys._MEIPASS) / "BE" / "src" / \
            "cash_sheet_filler" / filename
        if not editable.exists():
            editable.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled, editable)
        return editable
    else:
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
        try:
            from ..db.tendersdb_manager import TendersDBManager
        except ImportError:
            from BE.src.db.tendersdb_manager import TendersDBManager
        # Re-sync DB schema with updated tender config
        TendersDBManager().reload_tender_keys()
    except Exception as e:
        raise IOError(f"Error saving configuration to file: {e}")


_config = load_config()

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

# When true, parsers and the filler emit a step-by-step arithmetic trace
# (service fee subtraction, discount fold, aggregation, cell writes) instead
# of aggregate-only lines. Read with .get() so configs written by an older
# build — which live next to the .exe and are never overwritten — still load.
VERBOSE_TRACE = _config.get("verbose_trace", True)
