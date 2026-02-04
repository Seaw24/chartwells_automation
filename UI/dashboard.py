import customtkinter as ctk
# Ensure components/sidebar.py exists
from components.sidebar import SideBar


class Dashboard(ctk.CTkFrame):
    def __init__(self, parent):
        # 1. FIX: Accept 'parent' and pass it to super()
        super().__init__(parent)

        # 2. FIX: Remove self.title/geometry. Frames don't have these.
        # We handle geometry in the main execution block below.

        # --- Layout Configuration ---
        # Col 0 = Sidebar (fixed), Col 1 = Main Content (expandable)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---------------- Sidebar Integration ---------------- #
        self.side_bar = SideBar(
            self,
            show_dashboard=self.show_dashboard,
            show_cash_sheet_autofill=self.show_cash_sheet_autofill,
            show_tender_breakdown_autofill=self.show_tender_breakdown_autofill
        )
        self.side_bar.grid(row=0, column=0, sticky="nsew")

        # ---------------- Page Content Area ---------------- #

        # 1. Dashboard Content Frame
        self.dashboard_content = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.dashboard_content, text="Dashboard Content Goes Here",
                     font=ctk.CTkFont(size=16),
                     # Changed to white for dark mode visibility
                     text_color="white").pack(pady=20)

        # 2. Cash Sheet Autofill Content Frame
        self.cashet_sheet_content = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.cashet_sheet_content, text="Cash Sheet Autofill Content Goes Here",
                     font=ctk.CTkFont(size=16)).pack(pady=20)

        # 3. Tender Breakdown Autofill Content Frame
        self.tender_breakdown_content = ctk.CTkFrame(
            self, fg_color="transparent")
        ctk.CTkLabel(self.tender_breakdown_content, text="Tender Breakdown Autofill Content Goes Here",
                     font=ctk.CTkFont(size=16)).pack(pady=20)

        # Show default page
        self.show_dashboard()

    def _hide_all_frames(self):
        """ Hide all content frames using grid_forget (matches .grid) """
        self.dashboard_content.grid_forget()
        self.cashet_sheet_content.grid_forget()
        self.tender_breakdown_content.grid_forget()

    def show_dashboard(self):
        self._hide_all_frames()
        self.dashboard_content.grid(row=0, column=1, sticky="nsew")
        # Ensure string matches Sidebar logic exactly
        self.side_bar.active_function("Dashboard")

    def show_cash_sheet_autofill(self):
        self._hide_all_frames()
        self.cashet_sheet_content.grid(row=0, column=1, sticky="nsew")
        # Ensure string matches Sidebar logic exactly
        self.side_bar.active_function("Cash Sheet Autofill")

    def show_tender_breakdown_autofill(self):
        self._hide_all_frames()
        self.tender_breakdown_content.grid(row=0, column=1, sticky="nsew")
        # Ensure string matches Sidebar logic exactly
        self.side_bar.active_function("Tender Breakdown Autofill")


if __name__ == "__main__":
    # 3. FIX: Create the ROOT window here
    app = ctk.CTk()

    # Configure the Window settings here (not in the Frame class)
    app.title("Chartwells Finance Dashboard")
    app.geometry("1000x700")
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("dark-blue")

    # Create the Dashboard Frame inside the Root Window
    dashboard = Dashboard(app)
    dashboard.pack(fill="both", expand=True)

    app.mainloop()
