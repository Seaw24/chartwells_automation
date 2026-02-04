import customtkinter as ctk
from PIL import Image


class SideBar(ctk.CTkFrame):
    def __init__(self, parent, show_dashboard, show_cash_sheet_autofill, show_tender_breakdown_autofill):
        super().__init__(parent, width=200, corner_radius=0, fg_color="#6C63FF")

        # --- MAIN LAYOUT CONFIGURATION ---
        # Row 0: Top Frame (Logo + Nav) - Takes all extra space (weight=1)
        # Row 1: Bottom Frame (Settings) - Stays at bottom (weight=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # =========================================================================#
        # PART 1: TOP FRAME (Logo + Navigation)
        # =========================================================================#
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, sticky="nsew")

        # Layout inside Top Frame:
        # Row 0: Logo
        # Row 1: Spacer (Pushes Nav down)
        # Row 2: Nav Buttons
        self.top_frame.grid_rowconfigure(1, weight=1)
        self.top_frame.grid_columnconfigure(0, weight=1)

        # ----- Logo Section (Row 0) ----- #
        try:
            # We use a try/except block just in case the image file is missing
            self.logo_image = ctk.CTkImage(Image.open(
                "logo/chartwells.jfif"), size=(180, 50))
            self.logo_label = ctk.CTkLabel(
                self.top_frame, image=self.logo_image, text="", compound="top")
        except Exception:
            # Fallback if image not found
            self.logo_label = ctk.CTkLabel(
                self.top_frame, text="CHARTWELLS", font=("Arial", 20, "bold"))

        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 30))

        # ----- Button Frame (Row 2) ----- #
        self.button_frame = ctk.CTkFrame(
            self.top_frame, fg_color="transparent")
        self.button_frame.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Home Button
        self.home_image = ctk.CTkImage(Image.open(
            "logo\\home.png"), size=(30, 30))
        self.show_dashboard_button = self.create_nav_btn(
            self.button_frame, "", show_dashboard, self.home_image)
        self.show_dashboard_button.pack(pady=10,)

        self.show_cash_sheet_autofill_button = self.create_nav_btn(
            self.button_frame, "Cash Sheet Autofill", show_cash_sheet_autofill)
        self.show_cash_sheet_autofill_button.pack(pady=10, fill="x")

        self.show_tender_breakdown_autofill_button = self.create_nav_btn(
            self.button_frame, "Tender Breakdown", show_tender_breakdown_autofill)
        self.show_tender_breakdown_autofill_button.pack(pady=10, fill="x")

        # =========================================================================#
        # PART 2: BOTTOM FRAME (Settings + Support)
        # =========================================================================#
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=20)

        # 1. Separator (Inside bottom frame, at the top)
        self.separator = ctk.CTkFrame(
            self.bottom_frame, height=2, fg_color="gray50")
        self.separator.pack(fill="x", pady=(0, 15))

        # 2. Settings Buttons
        # Note: We pass strings directly, not 'text="Settings"'
        self.settings_button = self.create_nav_btn(
            self.bottom_frame, "Settings", self.open_settings)
        self.settings_button.pack(pady=5, fill="x")

        self.contact_support_button = self.create_nav_btn(
            self.bottom_frame, "Contact Support", self.contact_support)
        self.contact_support_button.pack(pady=5, fill="x")

        # 3. Footer
        self.lbl_version = ctk.CTkLabel(
            self.bottom_frame, text="v1.0.0", text_color="gray75", font=("Arial", 10))
        self.lbl_version.pack(pady=(10, 0))

    def create_nav_btn(self, parent, text, command, image=None):
        """ Helper to create styled buttons consistently """
        return ctk.CTkButton(parent, text=text, anchor="w",
                             fg_color="transparent",
                             image=image,
                             height=30,
                             width=30,
                             text_color="white",
                             hover_color="#55C2F8",
                             command=command)

    def active_function(self, tab_name):
        """ Highlight the active button in the sidebar """
        # Make all buttons transparent
        self.show_dashboard_button.configure(fg_color="transparent")
        self.show_cash_sheet_autofill_button.configure(fg_color="transparent")
        self.show_tender_breakdown_autofill_button.configure(
            fg_color="transparent")

        # Normalize the input string
        target = tab_name.strip().lower()

        # Highlight the active button
        if target == "dashboard":
            self.show_dashboard_button.configure(fg_color="#61C6F9")
        elif "cash sheet" in target:
            self.show_cash_sheet_autofill_button.configure(
                fg_color="#61C6F9")
        elif "tender breakdown" in target:
            self.show_tender_breakdown_autofill_button.configure(
                fg_color="#61C6F9")

    def open_settings(self):
        print("Settings button clicked")

    def contact_support(self):
        print("Contact Support button clicked")
