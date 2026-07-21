import customtkinter as ctk

# Unified design system — see theme.py. Names kept (PURPLE, ORANGE…) so the
# many existing references don't need touching; values now point at the
# single Deep-Teal palette shared across every screen.
try:
    from .theme import (
        PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, PRIMARY_SUBTLE,
        BG, TEXT, TEXT_SEC, TEXT_MUTED, CARD, BORDER,
        GREEN, GREEN_BG, RED, RED_BG, AMBER, AMBER_BG, FONT,
    )
except ImportError:  # flat import fallback
    from theme import (
        PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, PRIMARY_SUBTLE,
        BG, TEXT, TEXT_SEC, TEXT_MUTED, CARD, BORDER,
        GREEN, GREEN_BG, RED, RED_BG, AMBER, AMBER_BG, FONT,
    )

PURPLE = PRIMARY
PURPLE_DARK = PRIMARY_DARK
PURPLE_LIGHT = PRIMARY_LIGHT
PURPLE_SUBTLE = PRIMARY_SUBTLE
ORANGE = AMBER
ORANGE_BG = AMBER_BG


class Card(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=CARD, corner_radius=8,
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
        parent, text="+ Add", width=60, height=26, corner_radius=6,
        fg_color=GREEN_BG, text_color=GREEN, hover_color="#D4F5DD",
        font=ctk.CTkFont(family=FONT, size=11, weight="bold"),
        command=add_cb, cursor="hand2").pack(side="right")


def card_header(parent, title, subtitle=None, add_cb=None):
    """
    Standard header block for a config card: bold title, optional muted
    count label ("(5 entries)"), an optional "+ Add" button on the right,
    and an optional one-line description underneath.

    Returns the count label so callers can update it on refresh.
    """
    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    wrap.pack(fill="x", pady=(0, 8))
    row = ctk.CTkFrame(wrap, fg_color="transparent")
    row.pack(fill="x")
    ctk.CTkLabel(row, text=title,
                 font=ctk.CTkFont(family=FONT, size=14, weight="bold"),
                 text_color=TEXT).pack(side="left")
    count_label = ctk.CTkLabel(row, text="",
                               font=ctk.CTkFont(family=FONT, size=11),
                               text_color=TEXT_MUTED)
    count_label.pack(side="left", padx=(8, 0))
    if add_cb is not None:
        add_button(row, add_cb)
    if subtitle:
        ctk.CTkLabel(wrap, text=subtitle,
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=TEXT_SEC, justify="left", anchor="w",
                     wraplength=620).pack(anchor="w", pady=(2, 0))
    return count_label


def show_input_dialog(parent, title, fields, defaults=None,
                      helpers=None, required=None, numeric=None):
    """
    Modal form dialog.

    fields:   ordered list of field labels; one entry box per field.
    defaults: {label: prefill value}.
    helpers:  {label: small grey hint shown under the entry}.
    required: labels that must be non-empty before Save is accepted.
    numeric:  labels that must parse as whole numbers.

    Returns {label: stripped text} or None if cancelled. Enter saves,
    Escape cancels. Invalid input shows an inline error instead of
    silently discarding what the user typed.
    """
    helpers = helpers or {}
    required = set(required or [])
    numeric = set(numeric or [])

    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.configure(fg_color=BG)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()

    ctk.CTkLabel(dialog, text=title,
                 font=ctk.CTkFont(family=FONT, size=15, weight="bold"),
                 text_color=TEXT).pack(anchor="w", padx=16, pady=(14, 2))

    entries = {}
    for field_name in fields:
        req_mark = " *" if field_name in required else ""
        ctk.CTkLabel(dialog, text=field_name + req_mark,
                     font=ctk.CTkFont(family=FONT, size=12, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(8, 0))
        entry = ctk.CTkEntry(dialog, height=30, width=380, border_color=BORDER,
                             font=ctk.CTkFont(family=FONT, size=12))
        entry.pack(fill="x", padx=16, pady=(2, 0))
        if defaults and field_name in defaults:
            entry.insert(0, str(defaults[field_name]))
        if field_name in helpers:
            ctk.CTkLabel(dialog, text=helpers[field_name],
                         font=ctk.CTkFont(family=FONT, size=10),
                         text_color=TEXT_MUTED, justify="left", anchor="w",
                         wraplength=380).pack(anchor="w", padx=16)
        entries[field_name] = entry

    error_label = ctk.CTkLabel(dialog, text="",
                               font=ctk.CTkFont(family=FONT, size=11),
                               text_color=RED, justify="left", anchor="w",
                               wraplength=380)
    error_label.pack(anchor="w", padx=16, pady=(6, 0))

    result = {}
    cancelled = [True]

    def save(_event=None):
        values = {name: entry.get().strip()
                  for name, entry in entries.items()}
        for name in fields:
            if name in required and not values[name]:
                error_label.configure(text=f"{name} is required.")
                entries[name].focus_set()
                return
            if name in numeric and values[name]:
                try:
                    int(values[name])
                except ValueError:
                    error_label.configure(
                        text=f"{name} must be a whole number, like 3 or 21.")
                    entries[name].focus_set()
                    return
        result.update(values)
        cancelled[0] = False
        dialog.destroy()

    def cancel(_event=None):
        dialog.destroy()

    button_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    button_frame.pack(fill="x", padx=16, pady=(8, 12))

    ctk.CTkButton(
        button_frame, text="Cancel", width=80, height=32,
        fg_color=BG, text_color=TEXT_SEC, hover_color=BORDER,
        border_width=1, border_color=BORDER, corner_radius=8,
        command=cancel,
    ).pack(side="right", padx=(6, 0))

    ctk.CTkButton(
        button_frame, text="Save", width=80, height=32,
        fg_color=PURPLE, hover_color=PURPLE_DARK,
        corner_radius=8, command=save,
    ).pack(side="right")

    dialog.bind("<Return>", save)
    dialog.bind("<Escape>", cancel)

    # Size to content, then center over the app window.
    dialog.update_idletasks()
    top = parent.winfo_toplevel()
    w = max(dialog.winfo_reqwidth(), 412)
    h = dialog.winfo_reqheight()
    x = top.winfo_rootx() + (top.winfo_width() - w) // 2
    y = top.winfo_rooty() + (top.winfo_height() - h) // 2
    dialog.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

    if fields:
        entries[fields[0]].focus_set()
    dialog.wait_window()
    return result if not cancelled[0] else None
