"""
Compact sidebar with hover-expand / collapse.
Accepts a ``nav_callbacks`` dict mapping logical names to callables.
"""

import customtkinter as ctk
from pathlib import Path

try:
    from .theme import (
        PRIMARY, PRIMARY_DARK, ACCENT, CARD, BORDER, BG as THEME_BG,
        PRIMARY_LIGHT, TEXT, TEXT_SEC, FONT,
    )
    from .icons import get_icon
except ImportError:  # flat import fallback
    from theme import (
        PRIMARY, PRIMARY_DARK, ACCENT, CARD, BORDER, BG as THEME_BG,
        PRIMARY_LIGHT, TEXT, TEXT_SEC, FONT,
    )
    from icons import get_icon

try:
    from PIL import Image
    from BE.src.path_helper import get_bundle_dir
    _LOGO_PATH = get_bundle_dir() / "logo" / "chartwells.jfif"
except ImportError:
    Image = None  # graceful fallback – logo just won't show
    _LOGO_PATH = Path(__file__).resolve(
    ).parent.parent.parent / "logo" / "chartwells.jfif"

# Icon tints on the teal sidebar
_ICON_ON = "#FFFFFF"

_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / \
    "logo" / "chartwells.jfif"

# ── Support Contact Info (edit these) ────────────────────────────────
SUPPORT_NAME = "Duc Nam Nguyen"
SUPPORT_PHONE = "(360) 223 - 9663"
SUPPORT_EMAIL = "ducnam883@gmail.com"


class SideBar(ctk.CTkFrame):
    """Purple sidebar with icon-only collapsed state and labelled expanded state."""

    COLLAPSED_W = 72
    EXPANDED_W = 220
    BG = PRIMARY
    HOVER_BG = PRIMARY_DARK
    ACTIVE_BG = ACCENT

    def __init__(self, parent, nav_callbacks: dict[str, callable] | None = None):
        super().__init__(parent, width=self.COLLAPSED_W, corner_radius=0,
                         fg_color=self.BG, border_width=0)

        self.grid_propagate(False)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._expanded = False
        self._current_width = self.COLLAPSED_W
        self._poll_id = None
        self._active_key: str | None = None
        self._support_popup = None

        nav_callbacks = nav_callbacks or {}

        # ── logo ─────────────────────────────────────────────────────
        self._build_logo()

        # ── nav buttons ──────────────────────────────────────────────
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="nsew", pady=10)

        self._buttons: list[dict] = []
        items = [
            ("home",      "home",      "Home",             nav_callbacks.get("home")),
            ("analytics", "analytics", "Analytics",        nav_callbacks.get("analytics")),
            ("autofill",  "autofill",  "Auto-Fill Center", nav_callbacks.get("autofill")),
        ]
        for key, icon, text, cmd in items:
            self._add_button(nav_frame, key, icon, text, cmd)

        # ── bottom section ───────────────────────────────────────────
        bot_frame = ctk.CTkFrame(self, fg_color="transparent")
        bot_frame.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self._bottom_buttons: list[dict] = []
        for key, icon, text, cmd in [
            ("support",  "support",  "Support", self._show_support_popup),
            ("settings", "settings", "Settings", lambda: None),
        ]:
            self._add_button(bot_frame, key, icon, text, cmd,
                             storage=self._bottom_buttons)

        # ── hover bindings ───────────────────────────────────────────
        self._bind_enter_recursive(self)

    # ── Support Popup ────────────────────────────────────────────────
    def _show_support_popup(self):
        """Show a small popup with developer contact info."""
        if self._support_popup and self._support_popup.winfo_exists():
            self._support_popup.focus()
            return

        popup = ctk.CTkToplevel(self)
        popup.title("Support")
        popup.geometry("340x260")
        popup.resizable(False, False)
        popup.configure(fg_color=THEME_BG)
        popup.grab_set()
        self._support_popup = popup

        # ── Header ──
        hdr = ctk.CTkFrame(popup, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(20, 0))

        icon_box = ctk.CTkFrame(hdr, width=40, height=40, corner_radius=10,
                                fg_color=PRIMARY_LIGHT)
        icon_box.pack(side="left", padx=(0, 12))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="", image=get_icon("support", 20, PRIMARY)).place(
            relx=0.5, rely=0.5, anchor="center")

        title_frame = ctk.CTkFrame(hdr, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text="Need Help?",
                     font=ctk.CTkFont(family=FONT, size=18, weight="bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="Reach out to the developer",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC).pack(anchor="w")

        # ── Divider ──
        ctk.CTkFrame(popup, fg_color=BORDER, height=1).pack(
            fill="x", padx=24, pady=(16, 0))

        # ── Contact Card ──
        card = ctk.CTkFrame(popup, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", padx=24, pady=(16, 0))

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(fill="x", padx=16, pady=14)

        contact_items = [
            ("Name", SUPPORT_NAME),
            ("Phone", SUPPORT_PHONE),
            ("Email", SUPPORT_EMAIL),
        ]
        for i, (label, value) in enumerate(contact_items):
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", pady=(0 if i == 0 else 6, 0))

            ctk.CTkLabel(row, text=f"{label}",
                         font=ctk.CTkFont(family=FONT, size=12),
                         text_color=TEXT_SEC, width=52,
                         anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value,
                         font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                         text_color=TEXT).pack(side="left", padx=(6, 0))

        # ── Close button ──
        ctk.CTkButton(popup, text="Close", width=100, height=32,
                      corner_radius=8, fg_color=self.BG,
                      hover_color=self.HOVER_BG,
                      font=ctk.CTkFont(family=FONT, size=12),
                      command=popup.destroy).pack(pady=(14, 16))

    # ── logo ─────────────────────────────────────────────────────────
    def _build_logo(self):
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.grid(row=0, column=0, pady=(16, 10), sticky="ew")

        self._logo_inner = ctk.CTkFrame(wrapper, fg_color="transparent")
        self._logo_inner.pack(anchor="center")

        icon_box = ctk.CTkFrame(self._logo_inner, fg_color="white",
                                width=44, height=44, corner_radius=10)
        icon_box.grid(row=0, column=0)
        icon_box.grid_propagate(False)

        if Image and _LOGO_PATH.exists():
            img = ctk.CTkImage(light_image=Image.open(
                _LOGO_PATH), size=(36, 18))
            ctk.CTkLabel(icon_box, text="", image=img).place(
                relx=0.5, rely=0.5, anchor="center")
        else:
            ctk.CTkLabel(icon_box, text="C", font=ctk.CTkFont(size=20, weight="bold"),
                         text_color=self.BG).place(relx=0.5, rely=0.5, anchor="center")

        self._title_label = ctk.CTkLabel(
            self._logo_inner, text="Chartwells",
            font=ctk.CTkFont(size=15, weight="bold"), text_color="white")

    # ── button builder ───────────────────────────────────────────────
    def _add_button(self, parent, key, icon, text, command,
                    storage: list | None = None):
        storage = storage if storage is not None else self._buttons

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(pady=3, anchor="center")

        btn = ctk.CTkButton(
            row, text="", image=get_icon(icon, 22, _ICON_ON),
            width=44, height=44, corner_radius=12,
            fg_color="transparent", hover_color=self.HOVER_BG,
            command=command, cursor="hand2",
        )
        btn.grid(row=0, column=0)

        lbl = ctk.CTkLabel(
            row, text=text,
            font=ctk.CTkFont(family=FONT, size=13), text_color="white",
            anchor="w", cursor="hand2",
        )
        if command:
            lbl.bind("<Button-1>", lambda _e, c=command: c())

        storage.append({"key": key, "frame": row, "button": btn, "label": lbl})

    # ── active highlight ─────────────────────────────────────────────
    def set_active(self, key: str):
        """Highlight the button matching *key* and dim the rest."""
        self._active_key = key
        for b in self._buttons:
            if b["key"] == key:
                b["button"].configure(fg_color=self.ACTIVE_BG)
                b["label"].configure(
                    font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                    text_color="#FFFFFF")
            else:
                b["button"].configure(fg_color="transparent")
                b["label"].configure(
                    font=ctk.CTkFont(family=FONT, size=13),
                    text_color="#CFE6EC")

    # ── expand / collapse ────────────────────────────────────────────
    def _bind_enter_recursive(self, widget):
        try:
            widget.bind("<Enter>", self._on_enter)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_enter_recursive(child)

    def _on_enter(self, _event=None):
        if not self._expanded:
            self._expand()

    def _expand(self):
        self._expanded = True
        self._current_width = self.EXPANDED_W
        self.configure(width=self.EXPANDED_W)
        self.update_idletasks()
        self._show_labels()
        self._start_poll()

    def _collapse(self):
        self._expanded = False
        self._current_width = self.COLLAPSED_W
        self.configure(width=self.COLLAPSED_W)
        self.update_idletasks()
        self._hide_labels()

    def _show_labels(self):
        self._logo_inner.pack_configure(padx=(12, 0), anchor="w")
        self._title_label.grid(row=0, column=1, sticky="w", padx=(12, 0))
        for b in self._buttons + self._bottom_buttons:
            b["frame"].pack_configure(padx=(12, 0), anchor="w")
            b["label"].grid(row=0, column=1, sticky="w", padx=(8, 8))

    def _hide_labels(self):
        self._title_label.grid_forget()
        self._logo_inner.pack_configure(padx=0, anchor="center")
        for b in self._buttons + self._bottom_buttons:
            b["label"].grid_forget()
            b["frame"].pack_configure(padx=0, anchor="center")

    # ── mouse-leave polling ──────────────────────────────────────────
    def _start_poll(self):
        if self._poll_id:
            self.after_cancel(self._poll_id)

        def _check():
            if not self._expanded:
                self._poll_id = None
                return
            if not self._mouse_inside():
                self._collapse()
                self._poll_id = None
                return
            self._poll_id = self.after(120, _check)

        self._poll_id = self.after(120, _check)

    def _mouse_inside(self) -> bool:
        try:
            mx, my = self.winfo_pointerxy()
            sx, sy = self.winfo_rootx(), self.winfo_rooty()
            return sx <= mx < sx + self.winfo_width() and sy <= my < sy + self.winfo_height()
        except Exception:
            return False
