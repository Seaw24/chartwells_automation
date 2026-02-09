import customtkinter as ctk
from datetime import datetime
from components.taskManager import TaskManager
from components.sidebar import SideBar
from components.summaryPanel import SummaryPanel
from components.resizablePane import ResizablePane
from components.cash_sheet_autofill_UI import CashSheetAutofillUI


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
        header_frame.pack(fill="x", padx=24, pady=(20, 6))

        # Top row: title + date
        top_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        top_row.pack(fill="x")

        # Main title
        ctk.CTkLabel(
            top_row,
            text="Dashboard",
            font=ctk.CTkFont(size=28, weight="bold", family="Arial"),
            text_color="#1a1a1a",
            anchor="w"
        ).pack(side="left")

        # Current date badge
        today = datetime.now().strftime("%A, %b %d")
        date_frame = ctk.CTkFrame(top_row, fg_color="#EDE9FF", corner_radius=8)
        date_frame.pack(side="right")
        ctk.CTkLabel(
            date_frame, text=f"  📅  {today}  ",
            font=ctk.CTkFont(size=12, family="Arial"),
            text_color="#6C5CE7"
        ).pack(padx=6, pady=4)

        # Greeting subtitle
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Good Morning"
        elif hour < 17:
            greeting = "Good Afternoon"
        else:
            greeting = "Good Evening"

        ctk.CTkLabel(
            header_frame,
            text=f"Hi Chartwells, {greeting}!",
            font=ctk.CTkFont(size=14, family="Arial"),
            text_color="#9E9E9E",
            anchor="w"
        ).pack(side="top", anchor="w", pady=(4, 0))

        # Resizable pane with Summary (top) and Task Manager (bottom)
        self.resizable_pane = ResizablePane(
            self.dashboard_content,
            top_widget_class=SummaryPanel,
            bottom_widget_class=TaskManager,
            initial_top_ratio=0.35,
            min_top=60,
            min_bottom=80
        )
        self.resizable_pane.pack(
            fill="both", expand=True, padx=20, pady=(8, 12))

        # Get references to the actual widgets
        self.summary_panel = self.resizable_pane.top_widget
        self.task_manager = self.resizable_pane.bottom_widget

        # Update with sample data
        self.summary_panel.update_value(
            transfer=1380,
            flex=597,
            ucash=250,
            dining=425,
            contract_card=320,
            creditcard=875,
            total=3847
        )

    def _create_cash_sheet_content(self):
        """Create the unified autofill page (tabbed: cash sheet / tender / config)"""
        self.cash_sheet_content = ctk.CTkFrame(self, fg_color="#F5F5F7")

        self.autofill_ui = CashSheetAutofillUI(self.cash_sheet_content)
        self.autofill_ui.pack(fill="both", expand=True, padx=20, pady=20)

    def _create_tender_breakdown_content(self):
        """Tender breakdown shares the same tabbed UI — just reuse it"""
        self.tender_breakdown_content = self.cash_sheet_content

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
        """Show the autofill page on the Cash Sheet tab"""
        self._hide_all_frames()
        self.cash_sheet_content.grid(row=0, column=1, sticky="nsew")
        self.autofill_ui._select_tab("cash_sheet")
        self.side_bar.active_function("Cash Sheet Autofill")

    def show_tender_breakdown_autofill(self):
        """Show the autofill page on the Tender Breakdown tab"""
        self._hide_all_frames()
        self.cash_sheet_content.grid(row=0, column=1, sticky="nsew")
        self.autofill_ui._select_tab("tender")
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
