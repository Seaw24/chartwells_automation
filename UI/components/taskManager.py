import customtkinter as ctk
import json
from pathlib import Path
from datetime import datetime

TASK_FILE = str(Path(__file__).resolve().parents[2] / "tasks.json")

# --- Color Palette ---
PURPLE = "#6C5CE7"
PURPLE_HOVER = "#5B4CD6"
PURPLE_LIGHT = "#EDE9FF"
PURPLE_SUBTLE = "#F4F1FF"
BG_GRAY = "#F5F5F7"
BG_CARD_HOVER = "#EFEFEF"
TEXT_PRIMARY = "#1a1a1a"
TEXT_SECONDARY = "#8E8E93"
TEXT_MUTED = "#AEAEB2"
CARD_BG = "#FFFFFF"
BORDER_COLOR = "#E5E5EA"
SUCCESS = "#34C759"
SUCCESS_BG = "#E8F9EE"
DANGER = "#FF3B30"
DANGER_BG = "#FFE5E5"
WARNING = "#FF9500"
WARNING_BG = "#FFF4E5"
AVATAR_COLORS = ["#6C5CE7", "#00B894",
                 "#0984E3", "#E17055", "#FDCB6E", "#636E72"]


class TaskManager(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=16,
                         border_width=1, border_color=BORDER_COLOR)

        self.tasks = self.load_tasks()
        self.view_mode = "Active"
        self._popup = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._create_header()

        self.scroll_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent", label_text="",
            scrollbar_button_color="#D1D1D6", scrollbar_button_hover_color="#A1A1A6"
        )
        self.scroll_frame.grid(
            row=1, column=0, sticky="nsew", padx=12, pady=(5, 12))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.refresh_list()

    # ── Header ──────────────────────────────────────────────────
    def _create_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))

        # Left side - icon + title
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left")

        icon_box = ctk.CTkFrame(
            left, width=32, height=32, corner_radius=8, fg_color=PURPLE_LIGHT
        )
        icon_box.pack(side="left", padx=(0, 10))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="📋", font=ctk.CTkFont(size=14)).place(
            relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            left, text="Team Tasks",
            font=ctk.CTkFont(family="Arial", size=18, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="left")

        # Right side - custom toggle + add
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right")

        # ── Custom Toggle ──
        self._create_custom_toggle(right)

        ctk.CTkButton(
            right, text="＋  New Task", width=110, height=36,
            fg_color=PURPLE, hover_color=PURPLE_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=10,
            command=self.open_new_task_popup
        ).pack(side="left")

    def _create_custom_toggle(self, parent):
        """Custom pill toggle with counts"""
        self.toggle_frame = ctk.CTkFrame(
            parent, fg_color=BG_GRAY, corner_radius=10, height=36
        )
        self.toggle_frame.pack(side="left", padx=(0, 12))
        self.toggle_frame.pack_propagate(False)

        inner = ctk.CTkFrame(self.toggle_frame, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=3, pady=3)

        active_count = len([t for t in self.tasks if t["status"] == "Active"])
        completed_count = len(
            [t for t in self.tasks if t["status"] == "Completed"])

        self.btn_active = ctk.CTkButton(
            inner, text=f"Active  {active_count}",
            fg_color=PURPLE, hover_color=PURPLE_HOVER,
            text_color="white", corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30, width=95,
            command=lambda: self.switch_view("Active")
        )
        self.btn_active.pack(side="left", padx=(0, 2))

        self.btn_completed = ctk.CTkButton(
            inner, text=f"Completed  {completed_count}",
            fg_color="transparent", hover_color="#E5E5EA",
            text_color=TEXT_SECONDARY, corner_radius=8,
            font=ctk.CTkFont(size=12),
            height=30, width=110,
            command=lambda: self.switch_view("Completed")
        )
        self.btn_completed.pack(side="left")

    def _update_toggle(self):
        """Update toggle button appearance and counts"""
        active_count = len([t for t in self.tasks if t["status"] == "Active"])
        completed_count = len(
            [t for t in self.tasks if t["status"] == "Completed"])

        if self.view_mode == "Active":
            self.btn_active.configure(
                fg_color=PURPLE, hover_color=PURPLE_HOVER,
                text_color="white", text=f"Active  {active_count}",
                font=ctk.CTkFont(size=12, weight="bold")
            )
            self.btn_completed.configure(
                fg_color="transparent", hover_color="#E5E5EA",
                text_color=TEXT_SECONDARY, text=f"Completed  {completed_count}",
                font=ctk.CTkFont(size=12)
            )
        else:
            self.btn_active.configure(
                fg_color="transparent", hover_color="#E5E5EA",
                text_color=TEXT_SECONDARY, text=f"Active  {active_count}",
                font=ctk.CTkFont(size=12)
            )
            self.btn_completed.configure(
                fg_color=PURPLE, hover_color=PURPLE_HOVER,
                text_color="white", text=f"Completed  {completed_count}",
                font=ctk.CTkFont(size=12, weight="bold")
            )

    # ── Popup Dialog ────────────────────────────────────────────
    def open_new_task_popup(self):
        """Open a modal popup to create a new task"""
        if self._popup and self._popup.winfo_exists():
            self._popup.focus()
            return

        top = self.winfo_toplevel()

        # Dark overlay
        self._overlay = ctk.CTkFrame(top, fg_color="black", corner_radius=0)
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay.configure(fg_color=("gray20", "gray20"))
        self._overlay.bind("<Button-1>", lambda e: self._close_popup())
        self._overlay.lift()

        # Popup card
        self._popup = ctk.CTkFrame(
            top, fg_color=CARD_BG, corner_radius=16, width=460,
            border_width=1, border_color=BORDER_COLOR
        )
        self._popup.place(relx=0.5, rely=0.4, anchor="center")
        self._popup.lift()
        self._popup.grid_propagate(False)
        self._popup.configure(width=460, height=480)

        # ── Popup Header ──
        popup_header = ctk.CTkFrame(self._popup, fg_color="transparent")
        popup_header.pack(fill="x", padx=28, pady=(24, 0))

        # Icon + title
        title_row = ctk.CTkFrame(popup_header, fg_color="transparent")
        title_row.pack(side="left")

        icon_box = ctk.CTkFrame(
            title_row, width=36, height=36, corner_radius=10, fg_color=PURPLE_LIGHT
        )
        icon_box.pack(side="left", padx=(0, 10))
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="📝", font=ctk.CTkFont(size=16)).place(
            relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            title_row, text="Create New Task",
            font=ctk.CTkFont(family="Arial", size=20, weight="bold"),
            text_color=TEXT_PRIMARY
        ).pack(side="left")

        ctk.CTkButton(
            popup_header, text="✕", width=32, height=32,
            fg_color=BG_GRAY, hover_color="#E5E5EA", text_color=TEXT_SECONDARY,
            font=ctk.CTkFont(size=16), corner_radius=8,
            command=self._close_popup
        ).pack(side="right")

        # ── Divider ──
        ctk.CTkFrame(self._popup, fg_color=BORDER_COLOR, height=1).pack(
            fill="x", padx=28, pady=(16, 0))

        # ── Form Fields ──
        form = ctk.CTkFrame(self._popup, fg_color="transparent")
        form.pack(fill="x", padx=28, pady=(20, 0))

        # Project Name
        self._make_field_label(form, "Project Name")
        self.entry_name = ctk.CTkEntry(
            form, placeholder_text="e.g. Weekly Cash Report",
            height=40, corner_radius=10, border_color=BORDER_COLOR,
            border_width=1, fg_color=BG_GRAY, font=ctk.CTkFont(size=13)
        )
        self.entry_name.pack(fill="x", pady=(0, 14))

        # Description
        self._make_field_label(form, "Description")
        self.entry_desc = ctk.CTkTextbox(
            form, height=60, corner_radius=10, border_color=BORDER_COLOR,
            border_width=1, fg_color=BG_GRAY, font=ctk.CTkFont(size=13)
        )
        self.entry_desc.pack(fill="x", pady=(0, 14))

        # Row: Assignee + Deadline
        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        left_col = ctk.CTkFrame(row, fg_color="transparent")
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._make_field_label(left_col, "Assignee")
        self.entry_assignee = ctk.CTkEntry(
            left_col, placeholder_text="e.g. James",
            height=40, corner_radius=10, border_color=BORDER_COLOR,
            border_width=1, fg_color=BG_GRAY, font=ctk.CTkFont(size=13)
        )
        self.entry_assignee.pack(fill="x")

        right_col = ctk.CTkFrame(row, fg_color="transparent")
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self._make_field_label(right_col, "Deadline (dd/mm/yy)")
        self.entry_deadline = ctk.CTkEntry(
            right_col,
            placeholder_text="e.g. 25/02/26",
            height=40,
            corner_radius=10,
            border_color=BORDER_COLOR,
            border_width=1,
            fg_color=BG_GRAY,
            font=ctk.CTkFont(size=13),
        )
        self.entry_deadline.pack(fill="x")

        # ── Action Buttons ──
        btn_row = ctk.CTkFrame(self._popup, fg_color="transparent")
        btn_row.pack(fill="x", padx=28, pady=(22, 24), side="bottom")

        ctk.CTkButton(
            btn_row, text="Cancel", width=100, height=38,
            fg_color=BG_GRAY, hover_color="#E5E5EA", text_color=TEXT_PRIMARY,
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=10,
            command=self._close_popup
        ).pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            btn_row, text="Create Task", width=120, height=38,
            fg_color=PURPLE, hover_color=PURPLE_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=10,
            command=self._save_from_popup
        ).pack(side="right")

        self.entry_name.focus()

    def _make_field_label(self, parent, text):
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(family="Arial", size=12, weight="bold"),
            text_color=TEXT_SECONDARY, anchor="w"
        ).pack(anchor="w", pady=(0, 5))

    def _save_from_popup(self):
        name = self.entry_name.get().strip()
        desc = self.entry_desc.get("1.0", "end").strip()
        assignee = self.entry_assignee.get().strip()
        deadline = self.entry_deadline.get().strip()

        if not name:
            self.entry_name.configure(border_color=DANGER)
            return

        new_task = {
            "name": name,
            "description": desc if desc else "",
            "assignee": assignee if assignee else "Unassigned",
            "deadline": deadline if deadline else "—",
            "date": datetime.now().strftime("%d/%m/%y"),
            "completed_date": "",
            "status": "Active"
        }

        self.tasks.insert(0, new_task)
        self.save_tasks()
        self._close_popup()
        self.refresh_list()

    def _close_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        if hasattr(self, '_overlay') and self._overlay.winfo_exists():
            self._overlay.destroy()
        self._popup = None

    # ── Data ────────────────────────────────────────────────────
    def load_tasks(self):
        task_path = Path(TASK_FILE)
        if task_path.exists():
            try:
                with task_path.open('r', encoding='utf-8') as f:
                    loaded = json.load(f)
                if isinstance(loaded, list):
                    return loaded
            except (OSError, json.JSONDecodeError, TypeError):
                return []
        return []

    def save_tasks(self):
        with Path(TASK_FILE).open('w', encoding='utf-8') as f:
            json.dump(self.tasks, f, indent=4)

    def switch_view(self, value):
        self.view_mode = value
        self.refresh_list()

    def toggle_task_status(self, task):
        if task["status"] == "Active":
            task["status"] = "Completed"
            task["completed_date"] = datetime.now().strftime("%d/%m/%y %H:%M")
        else:
            task["status"] = "Active"
            task["completed_date"] = ""
        self.save_tasks()
        self.refresh_list()

    def delete_task(self, task):
        if task in self.tasks:
            self.tasks.remove(task)
            self.save_tasks()
            self.refresh_list()

    def _get_deadline_status(self, task):
        """Returns (color, bg_color, label) based on deadline proximity"""
        deadline_str = task.get('deadline', '—')
        if deadline_str == '—' or not deadline_str:
            return TEXT_MUTED, BG_GRAY, "No deadline"
        try:
            deadline = datetime.strptime(deadline_str, "%d/%m/%y")
            now = datetime.now()
            days_left = (deadline - now).days
            if days_left < 0:
                return DANGER, DANGER_BG, "Overdue"
            elif days_left <= 2:
                return WARNING, WARNING_BG, f"{days_left}d left"
            else:
                return SUCCESS, SUCCESS_BG, f"{days_left}d left"
        except ValueError:
            return TEXT_MUTED, BG_GRAY, deadline_str

    # ── List Rendering ──────────────────────────────────────────
    def refresh_list(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        filtered = [t for t in self.tasks if t["status"] == self.view_mode]
        self._update_toggle()

        if not filtered:
            empty = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
            empty.pack(fill="x", pady=40)
            if self.view_mode == "Active":
                ctk.CTkLabel(empty, text="🎉", font=ctk.CTkFont(size=40)).pack()
                ctk.CTkLabel(
                    empty, text="All caught up!",
                    font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT_PRIMARY
                ).pack(pady=(10, 4))
                ctk.CTkLabel(
                    empty, text="No active tasks. Click '+ New Task' to add one.",
                    font=ctk.CTkFont(size=13), text_color=TEXT_SECONDARY
                ).pack()
            else:
                ctk.CTkLabel(empty, text="📋", font=ctk.CTkFont(size=40)).pack()
                ctk.CTkLabel(
                    empty, text="No completed tasks yet",
                    font=ctk.CTkFont(size=16, weight="bold"), text_color=TEXT_PRIMARY
                ).pack(pady=(10, 4))
                ctk.CTkLabel(
                    empty, text="Tasks you finish will appear here.",
                    font=ctk.CTkFont(size=13), text_color=TEXT_SECONDARY
                ).pack()
            return

        for task in filtered:
            if self.view_mode == "Completed":
                self._create_completed_card(task)
            else:
                self._create_active_card(task)

    # ── Active Card ─────────────────────────────────────────────
    def _create_active_card(self, task):
        card = ctk.CTkFrame(
            self.scroll_frame, fg_color=BG_GRAY, corner_radius=12, height=78,
            border_width=1, border_color="#EAEAED"
        )
        card.pack(fill="x", pady=3, padx=4)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Avatar ──
        assignee = task.get('assignee', 'Unassigned')
        initial = assignee[0].upper() if assignee else "?"
        color_idx = sum(ord(c) for c in assignee) % len(AVATAR_COLORS)

        avatar = ctk.CTkFrame(
            inner, width=42, height=42, corner_radius=21,
            fg_color=AVATAR_COLORS[color_idx]
        )
        avatar.pack(side="left", padx=(0, 14))
        avatar.pack_propagate(False)
        ctk.CTkLabel(
            avatar, text=initial, text_color="white",
            font=ctk.CTkFont(size=15, weight="bold")
        ).place(relx=0.5, rely=0.5, anchor="center")

        # ── Info ──
        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        task_name = task.get('name', task.get('description', 'Untitled'))
        ctk.CTkLabel(
            info, text=task_name,
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color=TEXT_PRIMARY, anchor="w"
        ).pack(anchor="w")

        # Subtitle row with assignee + deadline badge
        sub_row = ctk.CTkFrame(info, fg_color="transparent")
        sub_row.pack(anchor="w", pady=(3, 0))

        ctk.CTkLabel(
            sub_row, text=f"{assignee}",
            font=ctk.CTkFont(family="Arial", size=12),
            text_color=TEXT_SECONDARY
        ).pack(side="left")

        # Deadline badge
        dl_color, dl_bg, dl_text = self._get_deadline_status(task)
        deadline_badge = ctk.CTkFrame(
            sub_row, fg_color=dl_bg, corner_radius=6, height=20
        )
        deadline_badge.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(
            deadline_badge, text=f"  📅 {dl_text}  ",
            font=ctk.CTkFont(size=11), text_color=dl_color
        ).pack(padx=2, pady=1)

        # ── Actions ──
        actions = ctk.CTkFrame(inner, fg_color="transparent")
        actions.pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            actions, text="✓  Done", width=80, height=30,
            fg_color="transparent", hover_color=SUCCESS_BG,
            text_color=SUCCESS, border_width=1, border_color=SUCCESS,
            corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda t=task: self.toggle_task_status(t)
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions, text="🗑", width=30, height=30,
            fg_color="transparent", hover_color=DANGER_BG,
            text_color=DANGER, corner_radius=8,
            font=ctk.CTkFont(size=14),
            command=lambda t=task: self.delete_task(t)
        ).pack(side="left")

    # ── Completed Card ──────────────────────────────────────────
    def _create_completed_card(self, task):
        card = ctk.CTkFrame(
            self.scroll_frame, fg_color=BG_GRAY, corner_radius=12, height=82,
            border_width=1, border_color="#EAEAED"
        )
        card.pack(fill="x", pady=3, padx=4)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16, pady=12)

        # ── Checkmark circle ──
        check = ctk.CTkFrame(
            inner, width=42, height=42, corner_radius=21, fg_color=SUCCESS_BG
        )
        check.pack(side="left", padx=(0, 14))
        check.pack_propagate(False)
        ctk.CTkLabel(
            check, text="✓", text_color=SUCCESS,
            font=ctk.CTkFont(size=18, weight="bold")
        ).place(relx=0.5, rely=0.5, anchor="center")

        # ── Info ──
        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        task_name = task.get('name', task.get('description', 'Untitled'))
        ctk.CTkLabel(
            info, text=task_name,
            font=ctk.CTkFont(family="Arial", size=14, weight="bold"),
            text_color=TEXT_MUTED, anchor="w"
        ).pack(anchor="w")

        # Subtitle with completed date
        sub_row = ctk.CTkFrame(info, fg_color="transparent")
        sub_row.pack(anchor="w", pady=(3, 0))

        assignee = task.get('assignee', 'Unassigned')
        ctk.CTkLabel(
            sub_row, text=f"{assignee}",
            font=ctk.CTkFont(family="Arial", size=12),
            text_color=TEXT_MUTED
        ).pack(side="left")

        completed_date = task.get('completed_date', '')
        if completed_date:
            completed_badge = ctk.CTkFrame(
                sub_row, fg_color=SUCCESS_BG, corner_radius=6, height=20
            )
            completed_badge.pack(side="left", padx=(10, 0))
            ctk.CTkLabel(
                completed_badge, text=f"  ✓ Done {completed_date}  ",
                font=ctk.CTkFont(size=11), text_color=SUCCESS
            ).pack(padx=2, pady=1)

        # ── Actions ──
        actions = ctk.CTkFrame(inner, fg_color="transparent")
        actions.pack(side="right", padx=(10, 0))

        ctk.CTkButton(
            actions, text="↩  Reopen", width=90, height=30,
            fg_color="transparent", hover_color=PURPLE_LIGHT,
            text_color=PURPLE, border_width=1, border_color=PURPLE,
            corner_radius=8, font=ctk.CTkFont(size=12),
            command=lambda t=task: self.toggle_task_status(t)
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions, text="🗑", width=30, height=30,
            fg_color="transparent", hover_color=DANGER_BG,
            text_color=DANGER, corner_radius=8,
            font=ctk.CTkFont(size=14),
            command=lambda t=task: self.delete_task(t)
        ).pack(side="left")
