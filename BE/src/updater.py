"""
Auto-Updater for Chartwells Automation
───────────────────────────────────────
Checks GitHub Releases for a newer version on startup.
If found, prompts the user and downloads the Windows release asset.

Usage in dashboard.py:
    from BE.src.updater import check_for_updates
    # In App.__init__, after window setup:
    self.after(1000, lambda: check_for_updates(self, CURRENT_VERSION))

Release tagging convention:
    Tag your GitHub releases as "v1.0.0", "v1.1.0", etc.
    The tag must start with 'v' followed by semver.

Setup:
    1. Create a GitHub repo (can be private — use a personal access token)
    2. Create a Release with a tag like "v1.0.0"
    3. Upload the built .zip and .exe as release assets
    4. Set GITHUB_REPO below to "your-username/your-repo"
    5. If private repo, set GITHUB_TOKEN in your .env
"""

import os
import sys
import json
import shutil
import tempfile
import threading
import subprocess
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import ssl
try:
    import certifi
    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None
try:
    from dotenv import load_dotenv
    try:
        from BE.src.path_helper import get_app_dir, get_bundle_dir
    except ImportError:
        try:
            from .path_helper import get_app_dir, get_bundle_dir
        except ImportError:
            get_app_dir = None
            get_bundle_dir = None

    if get_app_dir and (get_app_dir() / ".env").exists():
        load_dotenv(get_app_dir() / ".env")
    elif get_bundle_dir and (get_bundle_dir() / ".env").exists():
        load_dotenv(get_bundle_dir() / ".env")
    else:
        load_dotenv()
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════
#  CONFIGURATION — Change these for your project
# ═══════════════════════════════════════════════════════════════

GITHUB_REPO = "Seaw24/chartwells_automation"
# optional, for private repos
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "") or os.environ.get("UPDATER_TOKEN", "")

# Current version — bump this each time you build a new release
CURRENT_VERSION = "1.0.9"


# ═══════════════════════════════════════════════════════════════
#  VERSION PARSING
# ═══════════════════════════════════════════════════════════════

def _parse_version(tag: str) -> tuple[int, ...]:
    """Convert 'v1.2.3' or '1.2.3' to (1, 2, 3) for comparison."""
    clean = tag.strip().lstrip("v")
    try:
        return tuple(int(x) for x in clean.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _is_newer(remote_tag: str, local_version: str) -> bool:
    """True if the remote tag represents a newer version."""
    return _parse_version(remote_tag) > _parse_version(local_version)


# ═══════════════════════════════════════════════════════════════
#  GITHUB API
# ═══════════════════════════════════════════════════════════════

def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _fetch_latest_release() -> dict | None:
    """
    Fetch the latest release from GitHub API.
    Returns dict with keys: tag_name, name, body, assets[]
    """
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    req = Request(url, headers=_github_headers())

    try:
        with urlopen(req, timeout=10, context=_SSL_CONTEXT) as resp:            return json.loads(resp.read().decode())
    except (URLError, HTTPError, json.JSONDecodeError) as e:
        print(f"[Updater] Could not check for updates: {e}")
        return None


def _find_update_asset(assets: list[dict]) -> dict | None:
    """Find the best Windows update asset from the release assets list."""
    for asset in assets:
        name = asset.get("name", "").lower()
        if name == "chartwellsautomation-windows.zip":
            return asset
    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith(".zip") and "windows" in name:
            return asset
    for asset in assets:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            return asset
    return None


# ═══════════════════════════════════════════════════════════════
#  DOWNLOAD
# ═══════════════════════════════════════════════════════════════

def _download_asset(asset: dict, dest_path: Path, progress_callback=None) -> bool:
    """
    Download a release asset to dest_path.
    progress_callback(downloaded_bytes, total_bytes) is called periodically.
    """
    # For private repos, browser_download_url returns 404 without auth.
    # Always use the API URL with token if we have a token.
    if GITHUB_TOKEN and asset.get("url"):
        url = asset["url"]
    else:
        url = asset.get("browser_download_url", "") or asset.get("url", "")

    if not url:
        print("[Updater] No download URL found in asset")
        return False

    headers = _github_headers()
    # API URL needs octet-stream accept header to get the binary
    if "api.github.com" in url:
        headers["Accept"] = "application/octet-stream"

    req = Request(url, headers=headers)

    try:
        with urlopen(req, timeout=60, context=_SSL_CONTEXT) as resp:           
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024  # 64KB chunks

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

        return True
    except (URLError, HTTPError, OSError) as e:
        print(f"[Updater] Download failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  INSTALL (replace current .exe and restart)
# ═══════════════════════════════════════════════════════════════

def _get_current_exe() -> Path:
    """Get the path to the currently running executable."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    # Dev mode — return a dummy path (won't actually replace)
    return Path(__file__).resolve()


def _install_and_restart(new_exe_path: Path):
    """
    Replace the running .exe with the downloaded one and restart.

    Strategy: We can't overwrite a running .exe on Windows, so we:
    1. Rename the current .exe to .exe.old
    2. Copy the new .exe to the original location
    3. Launch the new .exe
    4. Exit the current process
    The .old file gets cleaned up on next launch.
    """
    current_exe = _get_current_exe()

    if not getattr(sys, "frozen", False):
        print("[Updater] Dev mode — skipping install. New exe at:", new_exe_path)
        return

    old_exe = current_exe.with_suffix(".exe.old")

    try:
        # Clean up any previous .old file
        if old_exe.exists():
            old_exe.unlink()

        # Rename current → .old
        current_exe.rename(old_exe)

        # Copy new → current location
        shutil.copy2(new_exe_path, current_exe)

        # Launch the new version
        subprocess.Popen([str(current_exe)])

        # Exit current process
        sys.exit(0)

    except OSError as e:
        print(f"[Updater] Install failed: {e}")
        # Try to restore the old exe
        if old_exe.exists() and not current_exe.exists():
            old_exe.rename(current_exe)


def _install_zip_and_restart(zip_path: Path):
    """
    Install a one-folder PyInstaller update from a downloaded zip and restart.

    The copy happens from a helper batch file after this process exits, because
    Windows locks the running executable and several loaded DLLs.
    """
    current_exe = _get_current_exe()

    if not getattr(sys, "frozen", False):
        print("[Updater] Dev mode — skipping install. New zip at:", zip_path)
        return

    app_dir = current_exe.parent
    work_dir = Path(tempfile.mkdtemp(prefix="chartwells_update_extract_"))
    extract_dir = work_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(extract_dir)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"[Updater] Could not extract update zip: {exc}")
        return

    nested_dir = extract_dir / "ChartwellsAutomation"
    if (nested_dir / current_exe.name).exists():
        source_dir = nested_dir
    elif (extract_dir / current_exe.name).exists():
        source_dir = extract_dir
    else:
        print("[Updater] Update zip did not contain ChartwellsAutomation.exe")
        return

    script_path = work_dir / "apply_update.bat"
    script_path.write_text(
        "\n".join([
            "@echo off",
            "timeout /t 2 /nobreak >nul",
            f'robocopy "{source_dir}" "{app_dir}" /E /R:5 /W:1',
            "if %ERRORLEVEL% GEQ 8 exit /b %ERRORLEVEL%",
            f'start "" "{current_exe}"',
            f'rmdir /s /q "{work_dir}"',
        ]),
        encoding="utf-8",
    )

    try:
        subprocess.Popen(
            ["cmd", "/c", str(script_path)],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        sys.exit(0)
    except OSError as exc:
        print(f"[Updater] Could not launch update installer: {exc}")


def _install_asset_and_restart(asset_path: Path):
    if asset_path.suffix.lower() == ".zip":
        _install_zip_and_restart(asset_path)
    else:
        _install_and_restart(asset_path)


def _cleanup_old_exe():
    """Remove .exe.old from a previous update (call on startup)."""
    if not getattr(sys, "frozen", False):
        return
    old_exe = _get_current_exe().with_suffix(".exe.old")
    try:
        if old_exe.exists():
            old_exe.unlink()
    except OSError:
        pass  # File might still be locked briefly after startup


# ═══════════════════════════════════════════════════════════════
#  UI INTEGRATION (CustomTkinter)
# ═══════════════════════════════════════════════════════════════

def check_for_updates(app_window, current_version: str = CURRENT_VERSION):
    """
    Called from App.__init__ via self.after().
    Checks GitHub in a background thread, shows a prompt if update found.

    Args:
        app_window: The CTk root window (for dialogs and .after() scheduling)
        current_version: The version string of the running app
    """
    # Clean up .old file from previous update
    _cleanup_old_exe()

    def _check():
        release = _fetch_latest_release()
        if release is None:
            return

        remote_tag = release.get("tag_name", "")
        if not _is_newer(remote_tag, current_version):
            print(f"[Updater] Up to date (v{current_version})")
            return

        update_asset = _find_update_asset(release.get("assets", []))
        if update_asset is None:
            print(
                f"[Updater] New version {remote_tag} found but no Windows update asset")
            return

        release_notes = release.get("body", "")[:300]  # Truncate long notes
        asset_size_mb = update_asset.get("size", 0) / (1024 * 1024)

        # Schedule UI prompt on main thread
        app_window.after(0, lambda: _show_update_prompt(
            app_window,
            remote_tag,
            release_notes,
            asset_size_mb,
            update_asset,
        ))

    thread = threading.Thread(target=_check, daemon=True)
    thread.start()


def _show_update_prompt(app_window, version_tag, release_notes, size_mb, asset):
    """Show a CustomTkinter dialog asking the user to update."""
    import customtkinter as ctk
    from tkinter import messagebox

    message = (
        f"A new version ({version_tag}) is available!\n"
        f"Size: {size_mb:.1f} MB\n\n"
    )
    if release_notes:
        message += f"What's new:\n{release_notes}\n\n"
    message += "Would you like to update now?"

    result = messagebox.askyesno(
        "Update Available",
        message,
        parent=app_window,
    )

    if result:
        _start_download(app_window, asset, version_tag)


def _start_download(app_window, asset, version_tag):
    """Show a progress window and download in background."""
    import customtkinter as ctk

    # ── Progress window ──────────────────────────────────────────
    progress_win = ctk.CTkToplevel(app_window)
    progress_win.title("Downloading Update")
    progress_win.geometry("400x150")
    progress_win.resizable(False, False)
    progress_win.transient(app_window)
    progress_win.grab_set()

    # Center on parent
    progress_win.update_idletasks()
    x = app_window.winfo_x() + (app_window.winfo_width() - 400) // 2
    y = app_window.winfo_y() + (app_window.winfo_height() - 150) // 2
    progress_win.geometry(f"+{x}+{y}")

    label = ctk.CTkLabel(
        progress_win,
        text=f"Downloading {version_tag}...",
        font=ctk.CTkFont(size=14),
    )
    label.pack(pady=(20, 10))

    progress_bar = ctk.CTkProgressBar(progress_win, width=350)
    progress_bar.pack(pady=5)
    progress_bar.set(0)

    status_label = ctk.CTkLabel(
        progress_win,
        text="Starting download...",
        font=ctk.CTkFont(size=11),
        text_color="#8E8E93",
    )
    status_label.pack(pady=5)

    # ── Background download ──────────────────────────────────────
    tmp_dir = Path(tempfile.mkdtemp(prefix="chartwells_update_"))
    tmp_asset = tmp_dir / asset.get("name", "ChartwellsAutomation-windows.zip")

    def _on_progress(downloaded, total):
        if total > 0:
            pct = downloaded / total
            dl_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            app_window.after(0, lambda: progress_bar.set(pct))
            app_window.after(0, lambda: status_label.configure(
                text=f"{dl_mb:.1f} / {total_mb:.1f} MB ({pct*100:.0f}%)"
            ))

    def _do_download():
        success = _download_asset(
            asset, tmp_asset, progress_callback=_on_progress)

        def _finish():
            progress_win.destroy()
            if success:
                from tkinter import messagebox
                messagebox.showinfo(
                    "Update Ready",
                    "Download complete! The app will now restart.",
                    parent=app_window,
                )
                _install_asset_and_restart(tmp_asset)
            else:
                from tkinter import messagebox
                messagebox.showerror(
                    "Update Failed",
                    "Download failed. Please try again later.",
                    parent=app_window,
                )

        app_window.after(0, _finish)

    thread = threading.Thread(target=_do_download, daemon=True)
    thread.start()
