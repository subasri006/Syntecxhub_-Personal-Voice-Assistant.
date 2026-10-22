"""Reusable Modern GUI Components for Personal Voice Assistant.

Includes custom styled widgets, status badges, message bubbles,
and microphone controls using CustomTkinter.
"""

from __future__ import annotations

import datetime
from typing import Callable, Optional
import customtkinter as ctk


class StatusBadge(ctk.CTkFrame):
    """Visual status pill badge showing status text and colored indicator."""

    STATUS_COLORS = {
        "Idle": "#6b7280",
        "Listening...": "#10b981",
        "Recognizing Speech...": "#06b6d4",
        "Assistant Speaking...": "#8b5cf6",
        "Calibrating Microphone...": "#f59e0b",
        "Sleeping (Say 'Wake up')": "#6366f1",
        "Error": "#ef4444",
    }

    def __init__(self, master, initial_status: str = "Idle", **kwargs):
        super().__init__(master, corner_radius=16, fg_color="#1e293b", **kwargs)

        self.indicator = ctk.CTkLabel(
            self,
            text="●",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=self.STATUS_COLORS.get(initial_status, "#6b7280"),
            width=20,
        )
        self.indicator.pack(side="left", padx=(10, 4), pady=4)

        self.label = ctk.CTkLabel(
            self,
            text=initial_status,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f8fafc",
        )
        self.label.pack(side="left", padx=(0, 12), pady=4)

    def set_status(self, status: str) -> None:
        """Update badge text and dot color."""
        self.label.configure(text=status)
        color = self.STATUS_COLORS.get(status, "#38bdf8")
        self.indicator.configure(text_color=color)


class MessageBubble(ctk.CTkFrame):
    """Modern chat bubble representing a single conversation utterance."""

    def __init__(
        self,
        master,
        role: str,
        text: str,
        timestamp: Optional[str] = None,
        **kwargs,
    ):
        is_user = role.lower() == "user"
        bg_color = "#1e3a8a" if is_user else "#1e293b"
        border_color = "#3b82f6" if is_user else "#334155"

        super().__init__(
            master,
            corner_radius=14,
            fg_color=bg_color,
            border_width=1,
            border_color=border_color,
            **kwargs,
        )

        time_str = timestamp or datetime.datetime.now().strftime("%I:%M %p")
        sender_title = "You" if is_user else "Assistant"
        header_color = "#93c5fd" if is_user else "#a78bfa"

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=12, pady=(8, 2))

        sender_lbl = ctk.CTkLabel(
            header_frame,
            text=sender_title,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=header_color,
        )
        sender_lbl.pack(side="left")

        time_lbl = ctk.CTkLabel(
            header_frame,
            text=time_str,
            font=ctk.CTkFont(size=10),
            text_color="#94a3b8",
        )
        time_lbl.pack(side="right")

        content_lbl = ctk.CTkLabel(
            self,
            text=text,
            font=ctk.CTkFont(size=13),
            text_color="#f8fafc",
            wraplength=480,
            justify="left",
            anchor="w",
        )
        content_lbl.pack(fill="x", padx=12, pady=(0, 10))


class QuickCommandChip(ctk.CTkButton):
    """Clickable chip button for executing sample voice commands with one tap."""

    def __init__(
        self,
        master,
        command_text: str,
        on_click: Callable[[str], None],
        **kwargs,
    ):
        super().__init__(
            master,
            text=command_text,
            command=lambda: on_click(command_text),
            corner_radius=12,
            height=28,
            font=ctk.CTkFont(size=11, weight="normal"),
            fg_color="#334155",
            hover_color="#475569",
            text_color="#e2e8f0",
            **kwargs,
        )


class DateTimeClock(ctk.CTkFrame):
    """Live clock widget showing local date and time."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.time_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38bdf8",
        )
        self.time_label.pack(anchor="e")

        self.date_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        self.date_label.pack(anchor="e")

        self._update_clock()

    def _update_clock(self) -> None:
        """Refresh current time and schedule next tick."""
        now = datetime.datetime.now()
        self.time_label.configure(text=now.strftime("%I:%M:%S %p"))
        self.date_label.configure(text=now.strftime("%A, %b %d, %Y"))
        self.after(1000, self._update_clock)
