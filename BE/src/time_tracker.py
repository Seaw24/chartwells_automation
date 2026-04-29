# BE/src/time_tracker.py
"""
Time Tracker — standalone module for tracking time saved by automation.

Usage:
    from BE.src.time_tracker import TimeTracker

    tracker = TimeTracker()
    tracker.record_run("cash_sheet")   # adds 60 min
    tracker.record_run("tender")       # adds 300 min
    data = tracker.get_data()          # returns full dict
    tracker.is_enabled()               # check if tracking is active
    tracker.toggle_tracking()          # pause/resume

Both cash_sheet_filler and tender_break can import this independently.
The JSON file lives next to this module at BE/src/time_saved.json.
"""

import sys
import json
from pathlib import Path
from datetime import datetime


def _get_data_file():
    filename = "time_saved.json"
    if getattr(sys, 'frozen', False):
        editable = Path(sys.executable).parent / "config" / filename
        if not editable.exists():
            editable.parent.mkdir(parents=True, exist_ok=True)
            # In frozen mode there's no bundled seed file — that's fine.
            # _load() will fall back to _DEFAULTS when the file doesn't exist,
            # and _save() will create it on the first record_run() call.
        return editable
    return Path(__file__).parent / filename


_DATA_FILE = _get_data_file()

_DEFAULTS = {
    "cash_sheet_runs": 0,
    "tender_runs": 0,
    "cash_sheet_minutes_per_run": 60,
    "tender_minutes_per_run": 300,
    "total_minutes_saved": 0,
    "last_run": None,
    "tracking_enabled": True,
}


class TimeTracker:
    """Lightweight tracker that persists time-saved stats to a JSON file."""

    def __init__(self):
        self._data = self._load()

    # ── persistence ──────────────────────────────────────────────

    def _load(self) -> dict:
        """Load data from JSON, creating defaults if missing."""
        if _DATA_FILE.exists():
            try:
                with open(_DATA_FILE, "r") as f:
                    saved = json.load(f)
                # Merge with defaults so new keys are always present
                merged = {**_DEFAULTS, **saved}
                return merged
            except (json.JSONDecodeError, Exception):
                pass
        return dict(_DEFAULTS)

    def _save(self):
        """Persist current data to JSON."""
        try:
            with open(_DATA_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"[TimeTracker] Warning: could not save data: {e}")

    # ── public API ───────────────────────────────────────────────

    def get_data(self) -> dict:
        """Return a copy of the current tracking data."""
        return dict(self._data)

    def record_run(self, run_type: str):
        """
        Record a completed autofill run.

        Args:
            run_type: "cash_sheet" or "tender"
        """
        now_str = datetime.now().strftime("%m/%d/%Y %I:%M %p")

        if not self._data.get("tracking_enabled", True):
            # Paused — update timestamp only, don't accumulate
            self._data["last_run"] = now_str
            self._save()
            return

        if run_type == "cash_sheet":
            self._data["cash_sheet_runs"] += 1
            minutes = self._data.get("cash_sheet_minutes_per_run", 60)
        elif run_type == "tender":
            self._data["tender_runs"] += 1
            minutes = self._data.get("tender_minutes_per_run", 300)
        else:
            return

        self._data["total_minutes_saved"] += minutes
        self._data["last_run"] = now_str
        self._save()

    def is_enabled(self) -> bool:
        return self._data.get("tracking_enabled", True)

    def toggle_tracking(self) -> bool:
        """Toggle tracking on/off. Returns new state."""
        self._data["tracking_enabled"] = not self._data.get(
            "tracking_enabled", True)
        self._save()
        return self._data["tracking_enabled"]

    def get_total_minutes(self) -> int:
        return self._data.get("total_minutes_saved", 0)

    def get_last_run(self) -> str | None:
        return self._data.get("last_run")

    def get_run_counts(self) -> dict:
        return {
            "cash_sheet": self._data.get("cash_sheet_runs", 0),
            "tender": self._data.get("tender_runs", 0),
        }

    @staticmethod
    def format_time(total_minutes: int) -> str:
        """Format minutes into a human-readable string."""
        if total_minutes < 60:
            return f"{total_minutes}m"
        hours = total_minutes / 60
        if hours == int(hours):
            return f"{int(hours)}h"
        return f"{hours:.1f}h"
