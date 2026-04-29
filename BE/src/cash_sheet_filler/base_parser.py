"""
Common logging helpers for every parser.

Each parser inherits from ``BaseParser`` so it can call:

    self._log(msg)         — neutral info line
    self._log_warning(msg) — warning (orange in the UI)
    self._log_error(msg)   — error   (red in the UI)

When a ``ProcessingTracker`` is attached, log calls are routed through its
structured emitters so the UI can color them. Without a tracker we fall
back to ``print`` so parsers stay usable from the CLI.
"""


class BaseParser:
    """Parent class providing the shared parser logging helpers."""

    def __init__(self, tracker=None):
        self.tracker = tracker

    def _log(self, msg):
        """Neutral info line."""
        if self.tracker:
            self.tracker.log(msg)
        else:
            print(msg)

    def _log_warning(self, msg):
        """Non-fatal issue. Routed through the tracker's warning emitter."""
        if self.tracker and hasattr(self.tracker, "warning"):
            self.tracker.warning(msg)
        else:
            self._log(f"   ⚠  {msg}")

    def _log_error(self, msg):
        """Parser-level error. The caller is responsible for failing the run."""
        # We deliberately use the public log channel and a clear marker
        # rather than mutating tracker counters here — counts are owned by
        # ``add_failure`` in the engine so the UI badges stay consistent.
        self._log(f"   ✗ {msg}")
