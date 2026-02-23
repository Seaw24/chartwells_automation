class BaseParser:
    """
    Parent class providing common logging methods for all parsers.
    Inherit from this to get _log, _log_error, and _log_warning automatically.
    """

    def __init__(self, tracker=None):
        self.tracker = tracker

    def _log(self, msg):
        """Standard info logging."""
        if self.tracker:
            self.tracker.log(msg)
        else:
            print(msg)

    def _log_error(self, msg):
        """Log parsing errors with a visual indicator."""
        self._log(f"  ❌ {msg}")

    def _log_warning(self, msg):
        """Log parsing warnings with a visual indicator."""
        self._log(f"  ⚠️  {msg}")
