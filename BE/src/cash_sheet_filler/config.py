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

# Per-workbook column differences, keyed by a fragment of the file name.
# Read with .get() for the same reason as VERBOSE_TRACE: configs written by
# an older build live next to the .exe and are never overwritten.
COL_MAP_OVERRIDES = _config.get("col_map_overrides", {})


def _compact_name(name):
    """Letters and digits only, lower-cased — 'City_s Edge' == "City's Edge"."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def col_maps_for(xl_path):
    """
    Return ``(fill_col_map, checking_col_map)`` for one cash-sheet workbook.

    Most venues share the standard layout, but a few sheets are built a
    column short — Kahlert Village has no "1M Meal" column, so everything
    from "Less coupons" rightward sits one to the left — and a filler using
    the standard map writes those venues' tenders into the wrong columns.
    ``col_map_overrides`` records the differences per workbook; an entry
    lists only the keys that move, and a key mapped to ``null`` means the
    sheet has no such column and nothing should be written there.
    """
    fill = dict(FILL_COL_MAP)
    checking = dict(CHECKING_COL_MAP)
    haystack = _compact_name(Path(xl_path).name) if xl_path else ""
    if not haystack:
        return fill, checking
    for fragment, override in COL_MAP_OVERRIDES.items():
        if _compact_name(fragment) not in haystack:
            continue
        fill.update(override.get("fill_col_map", {}))
        checking.update(override.get("checking_col_map", {}))
    return fill, checking
