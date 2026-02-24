# BE/src/path_helper.py
"""
Resolves paths for both development and PyInstaller-frozen environments.

Dev mode:   paths resolve relative to the project root
Frozen mode: bundled files are in sys._MEIPASS, but EDITABLE configs
             live in a 'config/' folder next to the .exe
"""
import sys
import shutil
from pathlib import Path


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return getattr(sys, '_MEIPASS', None) is not None


def get_bundle_dir() -> Path:
    """Where PyInstaller extracted the bundled (read-only) files."""
    if is_frozen():
        return Path(sys._MEIPASS)
    # Dev mode: project root (two levels up from this file)
    return Path(__file__).resolve().parents[2]


def get_app_dir() -> Path:
    """
    The 'application directory' — where the .exe lives (frozen)
    or the project root (dev mode).
    This is where editable configs and user data folders should be.
    """
    if is_frozen():
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def get_config_dir() -> Path:
    """
    Returns the path to the editable config/ folder.
    On first run, copies bundled defaults into it.
    """
    config_dir = get_app_dir() / "config"
    config_dir.mkdir(exist_ok=True)

    # On first run (frozen mode), seed configs from the bundle
    if is_frozen():
        _seed_config(config_dir, "cash_sheet_config.json",
                     get_bundle_dir() / "config_defaults" / "cash_sheet_config.json")
        _seed_config(config_dir, "tender_config.json",
                     get_bundle_dir() / "config_defaults" / "tender_config.json")

    return config_dir


def _seed_config(config_dir: Path, filename: str, bundled_path: Path):
    """Copy a bundled config to the editable folder if it doesn't exist yet."""
    target = config_dir / filename
    if not target.exists() and bundled_path.exists():
        shutil.copy2(bundled_path, target)
