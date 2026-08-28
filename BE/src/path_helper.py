# BE/src/path_helper.py
"""
Resolves paths for both development and PyInstaller-frozen environments.

Dev mode:   paths resolve relative to the project root
Frozen mode: bundled files are in sys._MEIPASS, but EDITABLE configs
             live in a 'config/' folder next to the .exe
"""
import sys
import copy
import json
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
    else:
        sync_config_with_defaults(target, bundled_path)


# ═══════════════════════════════════════════════════════════════
#  KEEPING AN INSTALLED CONFIG IN STEP WITH THE BUNDLED DEFAULTS
# ═══════════════════════════════════════════════════════════════

def _merge_missing(base: dict, user: dict, prefix: str = "") -> list[str]:
    """
    Copy across every key the bundled config has and the user's does not.

    Additions only: a key the user already has keeps their value, and a key
    only they have is left untouched. Nested dictionaries recurse, so a new
    location inside ``reports_cashsheet_map`` arrives without disturbing the
    locations already mapped. Lists and scalars are taken whole — the user's
    list wins wherever they have one, because entries like
    ``important_casheet_data_col`` are positional and merging them element by
    element would silently shift columns.

    Returns the dotted paths that were added, for logging.
    """
    added = []
    for key, base_value in base.items():
        path = f"{prefix}{key}"
        if key not in user:
            user[key] = copy.deepcopy(base_value)
            added.append(path)
        elif isinstance(base_value, dict) and isinstance(user[key], dict):
            added.extend(_merge_missing(base_value, user[key], f"{path}."))
    return added


def sync_config_with_defaults(editable: Path, bundled: Path) -> list[str]:
    """
    Add anything new in the bundled default config to the installed one.

    The editable config lives next to the .exe and is only ever seeded on the
    very first run, so a location added to the bundled default afterwards
    would never reach a user who has been running the app for a while. This
    folds those additions in on startup while leaving every value they have
    — including their own locations and folder paths — exactly as it is.

    Nothing is ever removed or overwritten; the file is rewritten only when
    there is something to add. Any failure is logged and ignored, since a
    stale-but-working config beats a crash on launch.
    """
    editable, bundled = Path(editable), Path(bundled)
    if not editable.exists() or not bundled.exists():
        return []
    # Dev mode points both paths at the same file — nothing to merge.
    if editable.resolve() == bundled.resolve():
        return []

    try:
        with open(editable, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        with open(bundled, "r", encoding="utf-8") as f:
            base_config = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[Config] Could not read defaults for {editable.name}: {exc}")
        return []

    if not isinstance(user_config, dict) or not isinstance(base_config, dict):
        return []

    added = _merge_missing(base_config, user_config)
    if not added:
        return []

    try:
        with open(editable, "w", encoding="utf-8") as f:
            json.dump(user_config, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        print(f"[Config] Could not write merged {editable.name}: {exc}")
        return []

    preview = ", ".join(added[:10]) + (" …" if len(added) > 10 else "")
    print(f"[Config] {editable.name}: added {len(added)} new default(s) "
          f"from this build — {preview}")
    return added
