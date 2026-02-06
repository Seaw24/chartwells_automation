import customtkinter as ctk

# --- Color Palette ---
PURPLE = "#6C5CE7"
BG_GRAY = "#F5F5F7"
BORDER_COLOR = "#E5E5EA"
HANDLE_COLOR = "#D1D1D6"
HANDLE_HOVER = "#8E8E93"
HANDLE_ACTIVE = "#6C5CE7"


class ResizablePane(ctk.CTkFrame):
    """A container with two vertically stacked panes separated by a draggable divider."""

    def __init__(self, parent, top_widget_class, bottom_widget_class,
                 initial_top_ratio=0.3, min_top=60, min_bottom=80):
        super().__init__(parent, fg_color="transparent")

        self.min_top = min_top
        self.min_bottom = min_bottom
        self._dragging = False
        self._top_ratio = initial_top_ratio

        # Use pack-based layout for pixel-perfect control
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        # Top pane — fixed height, updated on drag & window resize
        self.top_widget = top_widget_class(self)
        self.top_widget.grid(row=0, column=0, sticky="nsew")
        self.top_widget.grid_propagate(False)

        # Drag handle
        self.handle = ctk.CTkFrame(
            self, fg_color="transparent", height=14, cursor="sb_v_double_arrow"
        )
        self.handle.grid(row=1, column=0, sticky="ew")
        self.handle.grid_propagate(False)

        # Visual grip — three subtle dots
        self._grip_container = ctk.CTkFrame(
            self.handle, fg_color="transparent")
        self._grip_container.place(relx=0.5, rely=0.5, anchor="center")

        self._dots = []
        for i in range(3):
            dot = ctk.CTkFrame(
                self._grip_container, width=5, height=5,
                corner_radius=3, fg_color=HANDLE_COLOR
            )
            dot.pack(side="left", padx=2)
            self._dots.append(dot)

        # Bind drag events on handle, container, and dots
        for w in [self.handle, self._grip_container] + self._dots:
            w.bind("<Enter>", self._on_handle_enter)
            w.bind("<Leave>", self._on_handle_leave)
            w.bind("<Button-1>", self._on_drag_start)
            w.bind("<B1-Motion>", self._on_drag_motion)
            w.bind("<ButtonRelease-1>", self._on_drag_end)

        # Bottom pane — takes remaining space
        self.bottom_widget = bottom_widget_class(self)
        self.bottom_widget.grid(row=2, column=0, sticky="nsew")
        self.bottom_widget.grid_propagate(False)

        # Recalculate on window resize
        self.bind("<Configure>", self._on_configure)
        self._last_height = 0

    # ── Handle hover states ─────────────────────────────────────
    def _on_handle_enter(self, event):
        if not self._dragging:
            for dot in self._dots:
                dot.configure(fg_color=HANDLE_HOVER)

    def _on_handle_leave(self, event):
        if not self._dragging:
            for dot in self._dots:
                dot.configure(fg_color=HANDLE_COLOR)

    # ── Drag logic ──────────────────────────────────────────────
    def _on_drag_start(self, event):
        self._dragging = True
        self._drag_start_y = event.y_root
        self._top_height_start = self.top_widget.winfo_height()
        for dot in self._dots:
            dot.configure(fg_color=HANDLE_ACTIVE)

    def _on_drag_motion(self, event):
        if not self._dragging:
            return

        total = self.winfo_height() - self.handle.winfo_height()
        if total <= 0:
            return

        dy = event.y_root - self._drag_start_y
        new_top = self._top_height_start + dy

        # Clamp to minimums
        new_top = max(self.min_top, min(new_top, total - self.min_bottom))

        # Store ratio and apply
        self._top_ratio = new_top / total
        self._apply_sizes(total)

    def _on_drag_end(self, event):
        self._dragging = False
        for dot in self._dots:
            dot.configure(fg_color=HANDLE_COLOR)

    # ── Resize on window change ─────────────────────────────────
    def _on_configure(self, event):
        h = self.winfo_height()
        if h == self._last_height or h < 50:
            return
        self._last_height = h
        total = h - self.handle.winfo_height()
        if total > 0:
            self._apply_sizes(total)

    def _apply_sizes(self, total):
        """Set top pane height from ratio; bottom gets the rest via weight."""
        top_h = max(self.min_top, min(
            int(total * self._top_ratio), total - self.min_bottom))
        self.grid_rowconfigure(0, weight=0, minsize=top_h)
        # Bottom row keeps weight=1 so it fills the rest
        self.grid_rowconfigure(2, weight=1, minsize=self.min_bottom)
