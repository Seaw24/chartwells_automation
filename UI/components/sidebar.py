"""
Compact sidebar with hover-expand / collapse.
Accepts a ``nav_callbacks`` dict mapping logical names to callables.
"""

import customtkinter as ctk
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None  # graceful fallback – logo just won't show

_LOGO_PATH = Path(__file__).resolve().parent.parent.parent / \
    "logo" / "chartwells.jfif"


class SideBar(ctk.CTkFrame):
    """Purple sidebar with icon-only collapsed state and labelled expanded state."""

    COLLAPSED_W = 72
    EXPANDED_W = 220
    BG = "#6C5CE7"
    HOVER_BG = "#5B4CD6"
    ACTIVE_BG = "#8B7FEF"

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

        nav_callbacks = nav_callbacks or {}

        # ── logo ─────────────────────────────────────────────────────
        self._build_logo()

        # ── nav buttons ──────────────────────────────────────────────
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="nsew", pady=10)

        self._buttons: list[dict] = []
        items = [
            ("home",     "🏠", "Home",             nav_callbacks.get("home")),
            ("autofill", "🤖", "Auto-Fill Center", nav_callbacks.get("autofill")),
        ]
        for key, icon, text, cmd in items:
            self._add_button(nav_frame, key, icon, text, cmd)

        # ── bottom section ───────────────────────────────────────────
        bot_frame = ctk.CTkFrame(self, fg_color="transparent")
        bot_frame.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        self._bottom_buttons: list[dict] = []
        for key, icon, text, cmd in [
            ("support",  "🎧", "Support", lambda: None),
            ("settings", "⚙️", "Settings", lambda: None),
        ]:
            self._add_button(bot_frame, key, icon, text, cmd,
                             storage=self._bottom_buttons)

        # ── hover bindings ───────────────────────────────────────────
        self._bind_enter_recursive(self)

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
            row, text=icon, width=44, height=44, corner_radius=22,
            fg_color="transparent", hover_color=self.HOVER_BG,
            font=ctk.CTkFont(size=20), command=command, cursor="hand2",
        )
        btn.grid(row=0, column=0)

        lbl = ctk.CTkLabel(
            row, text=text, font=ctk.CTkFont(size=13), text_color="white",
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
                b["label"].configure(font=ctk.CTkFont(size=13, weight="bold"),
                                     text_color="#FFFFFF")
            else:
                b["button"].configure(fg_color="transparent")
                b["label"].configure(font=ctk.CTkFont(size=13),
                                     text_color="#DAD7FF")

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
