import customtkinter as ctk
from PIL import Image


class SideBar(ctk.CTkFrame):
    def __init__(self, parent, show_dashboard, show_cash_sheet_autofill):
        super().__init__(parent, width=80, corner_radius=0, fg_color="#6C5CE7",
                         border_width=0)

        # Sidebar state
        self.is_expanded = False
        self.collapsed_width = 80
        self.expanded_width = 240
        self.animation_id = None
        self.current_width = self.collapsed_width
        self._poll_id = None  # For mouse-leave polling

        # Prevent sidebar from shrinking/growing automatically
        self.grid_propagate(False)

        # Main layout configuration
        self.grid_rowconfigure(0, weight=0)  # Logo
        self.grid_rowconfigure(1, weight=1)  # Nav
        self.grid_rowconfigure(2, weight=0)  # Bottom
        self.grid_columnconfigure(0, weight=1)

        # Store command references
        self.show_dashboard = show_dashboard
        self.show_cash_sheet_autofill = show_cash_sheet_autofill

        # Bind hover events to the FRAME
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)

        # Create sidebar sections
        self._create_logo_section()
        self._create_navigation_section()
        self._create_bottom_section()

        # Bind <Enter> to all children so hovering any widget expands
        self._bind_enter_recursive(self)

    def _bind_enter_recursive(self, widget):
        """Bind <Enter> to widget and all its children"""
        try:
            widget.bind("<Enter>", self.on_enter)
        except Exception:
            pass
        for child in widget.winfo_children():
            self._bind_enter_recursive(child)

    def _is_mouse_over_sidebar(self):
        """Check if mouse is within sidebar bounds"""
        try:
            x, y = self.winfo_pointerxy()
            sx = self.winfo_rootx()
            sy = self.winfo_rooty()
            sw = self.winfo_width()
            sh = self.winfo_height()
            return sx <= x < sx + sw and sy <= y < sy + sh
        except Exception:
            return False

    def on_enter(self, event):
        """Expand sidebar on hover"""
        if not self.is_expanded:
            self._expand()

    def _expand(self):
        """Expand the sidebar instantly"""
        if self.animation_id:
            self.after_cancel(self.animation_id)
            self.animation_id = None

        self.is_expanded = True
        # Snap width instantly - no animation
        self.current_width = self.expanded_width
        self.configure(width=self.expanded_width)
        self.update_idletasks()
        self._show_labels_and_align_left()
        self._start_polling()

    def on_leave(self, event):
        """Collapse sidebar when mouse leaves"""
        # Let the polling handle the collapse check
        pass

    def _start_polling(self):
        """Poll to check if mouse has left the sidebar"""
        if self._poll_id:
            self.after_cancel(self._poll_id)

        def poll():
            if not self.is_expanded:
                self._poll_id = None
                return

            if not self._is_mouse_over_sidebar():
                self.is_expanded = False
                self._hide_labels_and_center()
                # Snap width instantly - no animation
                self.current_width = self.collapsed_width
                self.configure(width=self.collapsed_width)
                self.update_idletasks()
                self._poll_id = None
                return

            self._poll_id = self.after(100, poll)

        self._poll_id = self.after(100, poll)

    def _animate_to(self, target_width, on_complete=None):
        """Smooth easing animation"""
        if self.animation_id:
            self.after_cancel(self.animation_id)
            self.animation_id = None

        start_width = self.current_width
        total_distance = target_width - start_width
        duration = 550  # milliseconds
        frame_time = 3  # ~66fps for smoother feel
        total_frames = max(1, duration // frame_time)
        frame = [0]

        def ease_out_quint(t):
            return 1 - (1 - t) ** 3

        def animate():
            frame[0] += 1
            progress = min(frame[0] / total_frames, 1.0)
            eased = ease_out_quint(progress)

            self.current_width = start_width + (total_distance * eased)
            self.configure(width=int(self.current_width))

            if progress < 1.0:
                self.animation_id = self.after(frame_time, animate)
            else:
                self.current_width = target_width
                self.configure(width=target_width)
                self.animation_id = None
                if on_complete:
                    on_complete()

        animate()

    def _show_labels_and_align_left(self):
        """Align icons left and show labels"""
        # Align logo left and show finance label
        self.logo_content_frame.pack_configure(padx=(15, 0), anchor="w")
        self.finance_label.grid(row=0, column=1, sticky="w", padx=(15, 0))

        # Align nav buttons left and show labels
        for btn_data in self.nav_buttons:
            btn_data['frame'].pack_configure(padx=(15, 0), anchor="w")
            btn_data['label'].grid(row=0, column=1, sticky="w", padx=(10, 10))

        # Align bottom buttons left and show labels
        for btn_data in self.bottom_buttons:
            btn_data['frame'].pack_configure(padx=(15, 0), anchor="w")
            btn_data['label'].grid(row=0, column=1, sticky="w", padx=(10, 10))

    def _hide_labels_and_center(self):
        """Hide labels and center icons"""
        # Hide finance label and center logo
        self.finance_label.grid_forget()
        self.logo_content_frame.pack_configure(padx=0, anchor="center")

        # Hide nav labels and center buttons
        for btn_data in self.nav_buttons:
            btn_data['label'].grid_forget()
            btn_data['frame'].pack_configure(padx=0, anchor="center")

        # Hide bottom labels and center buttons
        for btn_data in self.bottom_buttons:
            btn_data['label'].grid_forget()
            btn_data['frame'].pack_configure(padx=0, anchor="center")

    def _create_logo_section(self):
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.grid(row=0, column=0, pady=(20, 30), sticky="ew")

        img = ctk.CTkImage(light_image=Image.open(
            "logo/chartwells.jfif"), size=(40, 20))
        # Container for icon and text - centered by default
        self.logo_content_frame = ctk.CTkFrame(
            logo_frame, fg_color="transparent")
        self.logo_content_frame.pack(
            padx=0, anchor="center")  # Centered when collapsed

        # Icon circle
        icon_frame = ctk.CTkFrame(
            self.logo_content_frame, fg_color="white", width=50, height=50)
        icon_frame.grid(row=0, column=0)
        icon_frame.grid_propagate(False)

        ctk.CTkLabel(icon_frame, text="", image=img, font=ctk.CTkFont(
            size=24), text_color="#6C5CE7").place(relx=0.5, rely=0.5, anchor="center")

        # Finance text (initially hidden)
        self.finance_label = ctk.CTkLabel(self.logo_content_frame, text="Finance", font=ctk.CTkFont(
            size=16, weight="bold"), text_color="white")

    def _create_navigation_section(self):
        nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        nav_frame.grid(row=1, column=0, sticky="nsew", pady=20)

        self.nav_buttons = []

        nav_items = [
            ("🏠", "Home", self.show_dashboard, "dashboard"),
            ("🤖", "Auto Fill Center", self.show_cash_sheet_autofill, "cash sheet"),
        ]

        for icon, label, cmd, uid in nav_items:
            self._add_button(nav_frame, self.nav_buttons,
                             icon, label, cmd, uid)

        self.home_button = self.nav_buttons[0]['button']
        self.cash_sheet_button = self.nav_buttons[1]['button']

    def _create_bottom_section(self):
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20))

        self.bottom_buttons = []
        bottom_items = [
            ("🎧", "Support", self.contact_support, "Support"),
            ("⚙️", "Settings", self.open_settings, "Settings")
        ]

        for icon, label, cmd, uid in bottom_items:
            self._add_button(bottom_frame, self.bottom_buttons,
                             icon, label, cmd, uid)

    def _add_button(self, parent, storage_list, icon, label_text, command, identifier):
        """Helper to create nav buttons"""
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        # Centered when collapsed
        btn_frame.pack(pady=5, padx=0, anchor="center")

        # Button
        button = ctk.CTkButton(
            btn_frame, text=icon, width=50, height=50, corner_radius=25,
            fg_color="transparent", hover_color="#5B4CD6",
            font=ctk.CTkFont(size=24), command=command, cursor="hand2"
        )
        button.grid(row=0, column=0)

        # Label (hidden by default) - make it clickable
        label = ctk.CTkLabel(btn_frame, text=label_text, font=ctk.CTkFont(
            size=14), text_color="white", anchor="w", cursor="hand2")

        # Bind click event to label for navigation
        label.bind("<Button-1>", lambda e, cmd=command: cmd())

        storage_list.append(
            {'frame': btn_frame, 'button': button, 'label': label, 'identifier': identifier})

    def active_function(self, tab_name):
        # Reset all nav buttons and labels
        for btn in self.nav_buttons:
            btn['button'].configure(fg_color="transparent")
            btn['label'].configure(
                font=ctk.CTkFont(size=14),
                text_color="#DAD7FF"
            )

        target = tab_name.lower()
        if target == "dashboard":
            self.nav_buttons[0]['button'].configure(fg_color="#8B7FEF")
            self.nav_buttons[0]['label'].configure(
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#FFFFFF"
            )
        elif "cash sheet" in target:
            self.nav_buttons[1]['button'].configure(fg_color="#8B7FEF")
            self.nav_buttons[1]['label'].configure(
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#FFFFFF"
            )
        elif "tender" in target:
            self.nav_buttons[2]['button'].configure(fg_color="#8B7FEF")
            self.nav_buttons[2]['label'].configure(
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="#FFFFFF"
            )

    def open_settings(self): print("Settings clicked")
    def contact_support(self): print("Support clicked")
