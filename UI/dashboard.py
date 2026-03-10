"""
Chartwells Automation – Main Application Window
Compact, lightweight UI built with customtkinter.
"""

import customtkinter as ctk
from pathlib import Path
import sys

# ── ensure we can import components & BE packages ────────────────────
_UI_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _UI_DIR.parent
for _p in (_UI_DIR, _ROOT_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from BE.src.db.tendersdb_manager import TendersDBManager
    from BE.src.updater import check_for_updates, CURRENT_VERSION
    from components.sidebar import SideBar
    from components.autofill_center import AutoFillCenter
    from components.taskManager import TaskManager
    from components.analyticsPage import AnalyticsPage
except ModuleNotFoundError:
    from UI.components.sidebar import SideBar
    from UI.components.autofill_center import AutoFillCenter
    from UI.components.taskManager import TaskManager
    from UI.components.analyticsPage import AnalyticsPage


class App(ctk.CTk):
    """Single-window application with a sidebar + swappable content area."""

    WIDTH = 960
    HEIGHT = 620

    def __init__(self):
        TendersDBManager()  # Ensure DB is initialized before any UI interaction
        super().__init__()

        # ── window setup ─────────────────────────────────────────────
        self.title("Chartwells Automation")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.minsize(760, 480)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        # ── layout: sidebar (left) + content (right) ────────────────
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = SideBar(
            self,
            nav_callbacks={
                "home": self._show_home,
                "autofill": self._show_autofill,
                "analytics": self._show_analytics,
            },
        )
        self.sidebar.grid(row=0, column=0, sticky="ns")

        # Content frame (right side)
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._content.grid_columnconfigure(0, weight=1)
        self._content.grid_rowconfigure(0, weight=1)

        # Cache pages so they are only built once
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._current_page: str | None = None

        # Start on auto-fill (the primary feature)
        self._show_analytics()
        self.after(1000, lambda: check_for_updates(self, CURRENT_VERSION))

    # ── page switching ───────────────────────────────────────────────

    def _clear_content(self):
        for w in self._content.winfo_children():
            w.grid_forget()

    def _show_page(self, name: str, factory):
        """Show *name* page, building it on first access via *factory*."""
        if name == self._current_page:
            return
        self._clear_content()
        if name not in self._pages:
            self._pages[name] = factory()
        page = self._pages[name]
        page.grid(row=0, column=0, sticky="nsew")
        self._current_page = name
        self.sidebar.set_active(name)

        # Let the page refresh its data when it becomes visible
        if hasattr(page, "on_show"):
            page.on_show()

    # ── individual pages ─────────────────────────────────────────────
    def _show_home(self):
        self._show_page("home", self._build_home)

    def _show_autofill(self):
        self._show_page("autofill", self._build_autofill)

    def _show_analytics(self):
        self._show_page("analytics", self._build_analytics)

    # ── page builders ────────────────────────────────────────────────
    def _build_home(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._content, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)

        # Home page: just the TaskManager (full height)
        task_mgr = TaskManager(frame)
        task_mgr.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        return frame

    def _build_autofill(self) -> ctk.CTkFrame:
        return AutoFillCenter(self._content)

    def _build_analytics(self) -> ctk.CTkFrame:
        return AnalyticsPage(self._content)


# ── entry point ──────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
