import customtkinter as ctk

PURPLE = "#6C5CE7"
PURPLE_DARK = "#5B4CD6"
PURPLE_LIGHT = "#EDE9FF"
PURPLE_SUBTLE = "#F4F1FF"
BG = "#F5F5F7"
TEXT = "#1a1a1a"
TEXT_SEC = "#8E8E93"
TEXT_MUTED = "#AEAEB2"
CARD = "#FFFFFF"
BORDER = "#E5E5EA"
GREEN = "#34C759"
GREEN_BG = "#E8F9EE"
RED = "#FF3B30"
RED_BG = "#FFE5E3"
ORANGE = "#FF9500"
ORANGE_BG = "#FFF3E0"
FONT = "Arial"


class Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=CARD, corner_radius=12,
                         border_width=1, border_color=BORDER, **kw)


def section_label(parent, text, grid_pos=None):
    label = ctk.CTkLabel(parent, text=text,
                         font=ctk.CTkFont(family=FONT, size=13, weight="bold"),
                         text_color=TEXT)
    if grid_pos:
        row, col, span = grid_pos
        label.grid(row=row, column=col, columnspan=span,
                   sticky="w", pady=(0, 8))
    else:
        label.pack(anchor="w", pady=(0, 6))


def add_button(parent, add_cb):
    ctk.CTkButton(
        parent, text="＋ Add", width=60, height=26, corner_radius=6,
        fg_color=GREEN_BG, text_color=GREEN, hover_color="#D4F5DD",
        font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
        command=add_cb, cursor="hand2").pack(side="right")


def show_input_dialog(parent, title, fields, defaults=None):
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry(f"400x{50 + len(fields) * 52 + 55}")
    dialog.resizable(False, False)
    dialog.grab_set()
    dialog.configure(fg_color=BG)

    entries = {}
    for i, field_name in enumerate(fields):
        ctk.CTkLabel(dialog, text=field_name,
                     font=ctk.CTkFont(family=FONT, size=12),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(10 if i == 0 else 3, 0))
        entry = ctk.CTkEntry(dialog, height=30, border_color=BORDER,
                             font=ctk.CTkFont(family=FONT, size=12))
        entry.pack(fill="x", padx=16, pady=(2, 0))
        if defaults and field_name in defaults:
            entry.insert(0, str(defaults[field_name]))
        entries[field_name] = entry

    result = {}
    cancelled = [True]

    def save():
        for field_name, entry in entries.items():
            result[field_name] = entry.get().strip()
        cancelled[0] = False
        dialog.destroy()

    button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    button_frame.pack(fill="x", padx=16, pady=(12, 10))

    ctk.CTkButton(
        button_frame, text="Cancel", width=80, height=32,
        fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
        border_width=1, border_color=BORDER, corner_radius=8,
        command=dialog.destroy,
    ).pack(side="left", padx=(0, 6))

    ctk.CTkButton(
        button_frame, text="Save", width=80, height=32,
        fg_color=PURPLE, hover_color=PURPLE_DARK,
        corner_radius=8, command=save,
    ).pack(side="left")

    dialog.wait_window()
    return result if not cancelled[0] else None
