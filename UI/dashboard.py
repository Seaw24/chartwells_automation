import customtkinter as ctk
from components.sidebar import SideBar
from components.summaryPanel import SummaryPanel


class Dashboard(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="#F5F5F7")

        # Layout Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.side_bar = SideBar(
            self,
            show_dashboard=self.show_dashboard,
            show_cash_sheet_autofill=self.show_cash_sheet_autofill,
            show_tender_breakdown_autofill=self.show_tender_breakdown_autofill
        )
        self.side_bar.grid(row=0, column=0, sticky="nsew")

        # Content Pages
        self._create_dashboard_content()
        self._create_cash_sheet_content()
        self._create_tender_breakdown_content()

        # Show default page
        self.show_dashboard()

    def _create_dashboard_content(self):
        """Create the main dashboard page"""
        self.dashboard_content = ctk.CTkFrame(self, fg_color="#F5F5F7")

        # Header Section
        header_frame = ctk.CTkFrame(
            self.dashboard_content, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))

        # Main title
        title_label = ctk.CTkLabel(
            header_frame,
            text="Dashboard",
            font=ctk.CTkFont(size=32, weight="bold", family="Arial"),
            text_color="#1a1a1a",
            anchor="w"
        )
        title_label.pack(side="top", anchor="w")

        # Greeting subtitle
        greeting_label = ctk.CTkLabel(
            header_frame,
            text="Hi James, Good Morning!",
            font=ctk.CTkFont(size=16, family="Arial"),
            text_color="#9E9E9E",
            anchor="w"
        )
        greeting_label.pack(side="top", anchor="w", pady=(5, 0))

        # Summary Panel
        self.summary_panel = SummaryPanel(self.dashboard_content)
        self.summary_panel.pack(fill="x", padx=20, pady=(20, 10))

        # Update with sample data
        self.summary_panel.update_value(
            flex_sales=597,
            credit_cards=875,
            transfers=1380,
            total_revenue=1200
        )

        # Placeholder for Task Manager
        self.middle_section = ctk.CTkFrame(
            self.dashboard_content,
            fg_color="white",
            corner_radius=15
        )
        self.middle_section.pack(fill="both", expand=True, padx=20, pady=10)

        placeholder_label = ctk.CTkLabel(
            self.middle_section,
            text="(Task Manager will go here)",
            text_color="#9E9E9E",
            font=ctk.CTkFont(size=14)
        )
        placeholder_label.place(relx=0.5, rely=0.5, anchor="center")

    def _create_cash_sheet_content(self):
        """Create the cash sheet autofill page"""
        self.cash_sheet_content = ctk.CTkFrame(self, fg_color="#F5F5F7")

        label = ctk.CTkLabel(
            self.cash_sheet_content,
            text="Cash Sheet Autofill Content Goes Here",
            font=ctk.CTkFont(size=18, family="Arial"),
            text_color="#1a1a1a"
        )
        label.pack(pady=20, padx=20)

    def _create_tender_breakdown_content(self):
        """Create the tender breakdown autofill page"""
        self.tender_breakdown_content = ctk.CTkFrame(self, fg_color="#F5F5F7")

        label = ctk.CTkLabel(
            self.tender_breakdown_content,
            text="Tender Breakdown Autofill Content Goes Here",
            font=ctk.CTkFont(size=18, family="Arial"),
            text_color="#1a1a1a"
        )
        label.pack(pady=20, padx=20)

    def _hide_all_frames(self):
        """Hide all content frames"""
        self.dashboard_content.grid_forget()
        self.cash_sheet_content.grid_forget()
        self.tender_breakdown_content.grid_forget()

    def show_dashboard(self):
        """Show the dashboard page"""
        self._hide_all_frames()
        self.dashboard_content.grid(row=0, column=1, sticky="nsew")
        self.side_bar.active_function("Dashboard")

    def show_cash_sheet_autofill(self):
        """Show the cash sheet autofill page"""
        self._hide_all_frames()
        self.cash_sheet_content.grid(row=0, column=1, sticky="nsew")
        self.side_bar.active_function("Cash Sheet Autofill")

    def show_tender_breakdown_autofill(self):
        """Show the tender breakdown autofill page"""
        self._hide_all_frames()
        self.tender_breakdown_content.grid(row=0, column=1, sticky="nsew")
        self.side_bar.active_function("Tender Breakdown Autofill")


if __name__ == "__main__":
    # Create root window
    app = ctk.CTk()
    app.title("Chartwells Finance Dashboard")
    app.geometry("1200x800")

    # Set appearance
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    # Create and pack dashboard
    dashboard = Dashboard(app)
    dashboard.pack(fill="both", expand=True)

    app.mainloop()
