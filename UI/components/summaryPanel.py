import customtkinter as ctk

# --- Color Palette (matching TaskManager) ---
PURPLE = "#6C5CE7"
PURPLE_LIGHT = "#EDE9FF"
PURPLE_SUBTLE = "#F4F1FF"
BG_GRAY = "#F5F5F7"
TEXT_PRIMARY = "#1a1a1a"
TEXT_SECONDARY = "#8E8E93"
TEXT_MUTED = "#AEAEB2"
CARD_BG = "#FFFFFF"
BORDER_COLOR = "#E5E5EA"
ACCENT_GREEN = "#34C759"
ACCENT_GREEN_BG = "#E8F9EE"


class SummaryPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=16,
                         border_width=1, border_color=BORDER_COLOR)

        # Layout Configuration
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Table
        self.grid_columnconfigure(0, weight=1)

        # Create header
        self._create_header()

        # Create scrollable table
        self._create_table()

    def _create_header(self):
        """Create header matching TaskManager style"""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))

        # Left: icon + title
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")

        icon_box = ctk.CTkFrame(
            left, width=32, height=32, corner_radius=8, fg_color=PURPLE_LIGHT
        )
        icon_box.pack(side="left", padx=(0, 10))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="📊", font=ctk.CTkFont(size=14)).place(
            relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            left, text="Sales Summary",
            font=ctk.CTkFont(family="Arial", size=18, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="left")

    def _create_table(self):
        """Create scrollable table with rows for each category"""
        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", label_text="",
            scrollbar_button_color="#D1D1D6", scrollbar_button_hover_color="#A1A1A6"
        )
        self.scroll_frame.grid(
            row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Column header row
        col_header = ctk.CTkFrame(
            self.scroll_frame, fg_color="transparent", height=24)
        col_header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        col_header.grid_columnconfigure(1, weight=1)
        col_header.grid_propagate(False)

        ctk.CTkLabel(
            col_header, text="Category",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color=TEXT_MUTED, anchor="w"
        ).grid(row=0, column=0, padx=(14, 0), sticky="w")

        ctk.CTkLabel(
            col_header, text="Amount",
            font=ctk.CTkFont(family="Arial", size=11, weight="bold"),
            text_color=TEXT_MUTED, anchor="e"
        ).grid(row=0, column=2, padx=(0, 14), sticky="e")

        # Define table rows: (key, label, icon)
        self.row_definitions = [
            ("transfer", "Total Transfer", "⇆"),
            ("flex", "Total Flex", "💳"),
            ("ucash", "Total UCash", "🪙"),
            ("dining", "Total Dining", "🍽️"),
            ("contract_card", "Total Contract Card", "📄"),
            ("creditcard", "Total Credit Card", "🏦"),
            ("total", "Grand Total", "💰"),
            ("total_average", "Total Average", "📈"),
            ("meal_count", "Meal Count", "🍱"),
        ]

        self.value_labels = {}

        for idx, (key, label, icon) in enumerate(self.row_definitions):
            self._create_table_row(idx + 1, key, label, icon)

    def _create_table_row(self, row_idx, key, label, icon):
        """Create a single table row"""
        is_total = key == "total"

        # Row container
        row_frame = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=PURPLE_SUBTLE if is_total else (
                BG_GRAY if row_idx % 2 == 0 else CARD_BG),
            corner_radius=8,
            height=40
        )
        row_frame.grid(row=row_idx, column=0, sticky="ew", pady=1, padx=2)
        row_frame.grid_columnconfigure(1, weight=1)
        row_frame.grid_propagate(False)

        # Icon
        ctk.CTkLabel(
            row_frame, text=icon,
            font=ctk.CTkFont(size=15),
            text_color=PURPLE, width=30
        ).grid(row=0, column=0, padx=(12, 4), pady=8, sticky="w")

        # Label
        ctk.CTkLabel(
            row_frame, text=label,
            font=ctk.CTkFont(family="Arial", size=13,
                             weight="bold" if is_total else "normal"),
            text_color=PURPLE if is_total else TEXT_PRIMARY,
            anchor="w"
        ).grid(row=0, column=1, padx=4, pady=8, sticky="w")

        # Value
        value_label = ctk.CTkLabel(
            row_frame, text="$0.00",
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color=PURPLE if is_total else TEXT_PRIMARY,
            anchor="e"
        )
        value_label.grid(row=0, column=2, padx=(4, 14), pady=8, sticky="e")

        self.value_labels[key] = value_label

    def update_value(self, transfer=0, flex=0, ucash=0, dining=0, contract_card=0, creditcard=0, total=0, total_average=0, meal_count=0):
        """Update all table values"""
        values = {
            "transfer": transfer,
            "flex": flex,
            "ucash": ucash,
            "dining": dining,
            "contract_card": contract_card,
            "creditcard": creditcard,
            "total": total,
            "total_average": total_average,
            "meal_count": meal_count
        }
        for key, value in values.items():
            if key in self.value_labels:
                self.value_labels[key].configure(text=f"${value:,.2f}")
