import customtkinter as ctk


class SummaryPanel(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")

        # Layout Configuration - 4 equal columns
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create summary cards with colors matching the reference image
        self.flex_widgets = self.create_card(
            0, "Flex Sales", "💳", "$0.00", "#7B68EE"
        )
        self.credit_widgets = self.create_card(
            1, "Credit Cards", "🏦", "$0.00", "#7B68EE"
        )
        self.transfer_widgets = self.create_card(
            2, "Transfers", "⇆", "$0.00", "#7B68EE"
        )
        self.total_widgets = self.create_card(
            3, "Total Revenue", "💰", "$0.00", "#7B68EE"
        )

    def create_card(self, column_idx, title, icon, value, color):
        """Create a single summary card"""
        card = ctk.CTkFrame(
            self,
            fg_color="white",
            corner_radius=15,
            border_width=0
        )
        card.grid(row=0, column=column_idx, padx=10, pady=10, sticky="nsew")

        # Configure card layout
        card.grid_rowconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=0)
        card.grid_rowconfigure(2, weight=0)
        card.grid_columnconfigure(0, weight=1)

        # Value label (top, large, bold, black)
        lbl_value = ctk.CTkLabel(
            card,
            text=value,
            font=ctk.CTkFont(size=36, weight="bold", family="Arial"),
            text_color="#1a1a1a"
        )
        lbl_value.grid(row=0, column=0, pady=(20, 5), sticky="s")

        # Icon (middle, colored)
        lbl_icon = ctk.CTkLabel(
            card,
            text=icon,
            font=ctk.CTkFont(size=48),
            text_color=color
        )
        lbl_icon.grid(row=1, column=0, pady=(5, 5))

        # Title label (bottom, gray)
        lbl_title = ctk.CTkLabel(
            card,
            text=title,
            font=ctk.CTkFont(size=13, family="Arial"),
            text_color="#9E9E9E"
        )
        lbl_title.grid(row=2, column=0, pady=(5, 20), sticky="n")

        return lbl_value

    def update_value(self, flex_sales, credit_cards, transfers, total_revenue):
        """Update all card values"""
        self.flex_widgets.configure(text=f"${flex_sales:,.0f}")
        self.credit_widgets.configure(text=f"${credit_cards:,.0f}")
        self.transfer_widgets.configure(text=f"${transfers:,.0f}")
        self.total_widgets.configure(text=f"${total_revenue:,.0f}")
