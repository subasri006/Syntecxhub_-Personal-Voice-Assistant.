"""Main Window GUI for Personal Voice Assistant.

Modern CustomTkinter desktop interface featuring dark theme, live status badge,
circular microphone button, speech recognition monitor, scrollable chat history,
settings sidebar, quick command chips, and thread-safe background event polling.
"""

from __future__ import annotations

import logging
import queue
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from assistant.assistant_controller import AssistantController
from assistant.speech_recognition_service import (
    STATUS_CALIBRATING,
    STATUS_IDLE,
    STATUS_LISTENING,
    STATUS_RECOGNIZING,
    STATUS_SLEEPING,
    STATUS_SPEAKING,
)
from gui.components import DateTimeClock, MessageBubble, QuickCommandChip, StatusBadge

logger = logging.getLogger(__name__)


class MainWindow(ctk.CTk):
    """Main Application Window."""

    def __init__(self, controller: AssistantController):
        super().__init__()

        self.controller = controller
        self.gui_queue: queue.Queue = queue.Queue()

        # Appearance configuration
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Personal Voice Assistant")
        self.geometry("1100x740")
        self.minsize(920, 640)

        # Connect controller callbacks to thread-safe queue dispatch
        self._wire_controller()

        # Setup GUI layout
        self._create_header()
        self._create_main_layout()

        # Populate settings
        self._populate_voices()

        # Handle window close cleanly
        self.protocol("WM_DELETE_WINDOW", self.confirm_and_exit)

        # Start background event consumer
        self._process_gui_queue()

        # Add initial welcome message
        self._add_system_welcome()

        # Check microphone readiness on startup
        self._check_initial_microphone()

    def _wire_controller(self) -> None:
        """Register callbacks with the controller to enqueue GUI updates."""
        self.controller.on_status_changed = lambda status: self.gui_queue.put(
            ("status", status)
        )
        self.controller.on_user_speech = lambda text: self.gui_queue.put(
            ("user_speech", text)
        )
        self.controller.on_assistant_response = lambda text, action: self.gui_queue.put(
            ("assistant_response", (text, action))
        )
        self.controller.on_error = lambda err: self.gui_queue.put(("error", err))
        self.controller.on_control_action = lambda action: self.gui_queue.put(
            ("control", action)
        )

    def _process_gui_queue(self) -> None:
        """Drain background events on the main thread and update GUI elements."""
        try:
            while not self.gui_queue.empty():
                event_type, data = self.gui_queue.get_nowait()
                if event_type == "status":
                    self._on_status_update(data)
                elif event_type == "user_speech":
                    self._on_user_speech(data)
                elif event_type == "assistant_response":
                    text, action = data
                    self._on_assistant_response(text, action)
                elif event_type == "error":
                    self._on_error(data)
                elif event_type == "control":
                    if data == "exit":
                        self.confirm_and_exit()
                self.gui_queue.task_done()
        except queue.Empty:
            pass

        # Reschedule check every 50ms
        self.after(50, self._process_gui_queue)

    # --- UI Layout Construction ---

    def _create_header(self) -> None:
        """Build top navigation header with title, status, and live clock."""
        header = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=0, height=70)
        header.pack(fill="x", side="top", padx=0, pady=0)
        header.pack_propagate(False)

        # Left: Branding
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=20, pady=12)

        title_lbl = ctk.CTkLabel(
            brand_frame,
            text="🎙️ Personal Voice Assistant",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#f8fafc",
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ctk.CTkLabel(
            brand_frame,
            text="Offline TTS • Safe System Automation • Desktop Assistant",
            font=ctk.CTkFont(size=11),
            text_color="#64748b",
        )
        subtitle_lbl.pack(anchor="w")

        # Center: Live Status Badge
        self.status_badge = StatusBadge(header, initial_status=STATUS_IDLE)
        self.status_badge.pack(side="left", padx=30, pady=16)

        # Right: Live Date/Time Clock
        self.clock = DateTimeClock(header)
        self.clock.pack(side="right", padx=20, pady=12)

    def _create_main_layout(self) -> None:
        """Create two-column layout: Sidebar controls and Conversation canvas."""
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=16, pady=12)

        # Left Column: Sidebar Controls & Settings (Fixed width)
        self.sidebar = ctk.CTkScrollableFrame(
            container, width=320, fg_color="#1e293b", corner_radius=12
        )
        self.sidebar.pack(side="left", fill="y", padx=(0, 12), pady=0)

        # Right Column: Conversation, Current State, and Input
        self.main_content = ctk.CTkFrame(container, fg_color="transparent")
        self.main_content.pack(side="right", fill="both", expand=True)

        self._build_sidebar_controls()
        self._build_main_content()

    def _build_sidebar_controls(self) -> None:
        """Construct sidebar buttons, microphone indicator, switches, and sliders."""
        # Section 1: Microphone Action Center
        mic_card = ctk.CTkFrame(self.sidebar, fg_color="#0f172a", corner_radius=12)
        mic_card.pack(fill="x", padx=10, pady=(10, 14))

        mic_card_title = ctk.CTkLabel(
            mic_card,
            text="VOICE CONTROL",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8",
        )
        mic_card_title.pack(pady=(12, 6))

        # Circular Mic Button inside a centered frame to maintain perfect circle geometry
        mic_circle_box = ctk.CTkFrame(mic_card, fg_color="transparent")
        mic_circle_box.pack(pady=(6, 4))

        self.btn_mic_circle = ctk.CTkButton(
            mic_circle_box,
            text="🎙️",
            font=ctk.CTkFont(size=30),
            width=76,
            height=76,
            corner_radius=38,
            fg_color="#334155",
            hover_color="#475569",
            command=self._toggle_listening,
        )
        self.btn_mic_circle.pack()

        self.lbl_mic_hint = ctk.CTkLabel(
            mic_card,
            text="Click mic to start",
            font=ctk.CTkFont(size=11),
            text_color="#cbd5e1",
        )
        self.lbl_mic_hint.pack(pady=(0, 10))

        # Start / Stop Buttons
        btn_box = ctk.CTkFrame(mic_card, fg_color="transparent")
        btn_box.pack(fill="x", padx=12, pady=(0, 12))

        self.btn_start = ctk.CTkButton(
            btn_box,
            text="Start Listening",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            command=self._on_start_listening_clicked,
            width=130,
        )
        self.btn_start.pack(side="left", expand=True, padx=(0, 4))

        self.btn_stop = ctk.CTkButton(
            btn_box,
            text="Stop Listening",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._on_stop_listening_clicked,
            width=130,
        )
        self.btn_stop.pack(side="right", expand=True, padx=(4, 0))

        # Section 2: Listening Modes
        modes_card = ctk.CTkFrame(self.sidebar, fg_color="#0f172a", corner_radius=12)
        modes_card.pack(fill="x", padx=10, pady=(0, 14))

        ctk.CTkLabel(
            modes_card,
            text="ACTIVATION MODES",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8",
        ).pack(anchor="w", padx=12, pady=(10, 6))

        # Continuous listening switch
        self.switch_continuous = ctk.CTkSwitch(
            modes_card,
            text="Continuous Mode (Hands-free)",
            font=ctk.CTkFont(size=12),
            command=self._on_continuous_toggle,
        )
        self.switch_continuous.pack(anchor="w", padx=12, pady=6)

        # Wake word switch & input
        self.switch_wake_word = ctk.CTkSwitch(
            modes_card,
            text="Wake Word Activation",
            font=ctk.CTkFont(size=12),
            command=self._on_wake_word_toggle,
        )
        self.switch_wake_word.pack(anchor="w", padx=12, pady=6)

        self.entry_wake_word = ctk.CTkEntry(
            modes_card,
            placeholder_text="Wake word (e.g. hey assistant)",
            height=30,
            font=ctk.CTkFont(size=11),
        )
        self.entry_wake_word.insert(0, self.controller.wake_word)
        self.entry_wake_word.pack(fill="x", padx=12, pady=(0, 12))
        self.entry_wake_word.bind("<FocusOut>", lambda _: self._save_wake_word())
        self.entry_wake_word.bind("<Return>", lambda _: self._save_wake_word())

        # Section 3: Audio & Speech Settings
        settings_card = ctk.CTkFrame(
            self.sidebar, fg_color="#0f172a", corner_radius=12
        )
        settings_card.pack(fill="x", padx=10, pady=(0, 14))

        ctk.CTkLabel(
            settings_card,
            text="VOICE SETTINGS (OFFLINE)",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8",
        ).pack(anchor="w", padx=12, pady=(10, 6))

        # Speech Rate
        rate_frame = ctk.CTkFrame(settings_card, fg_color="transparent")
        rate_frame.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(
            rate_frame, text="Speech Rate:", font=ctk.CTkFont(size=11), text_color="#cbd5e1"
        ).pack(side="left")
        self.lbl_rate_val = ctk.CTkLabel(
            rate_frame, text="175 wpm", font=ctk.CTkFont(size=11), text_color="#38bdf8"
        )
        self.lbl_rate_val.pack(side="right")

        self.slider_rate = ctk.CTkSlider(
            settings_card,
            from_=100,
            to=280,
            number_of_steps=18,
            command=self._on_rate_slider,
        )
        self.slider_rate.set(175)
        self.slider_rate.pack(fill="x", padx=12, pady=(0, 8))

        # Speech Volume
        vol_frame = ctk.CTkFrame(settings_card, fg_color="transparent")
        vol_frame.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(
            vol_frame, text="Speech Volume:", font=ctk.CTkFont(size=11), text_color="#cbd5e1"
        ).pack(side="left")
        self.lbl_vol_val = ctk.CTkLabel(
            vol_frame, text="90%", font=ctk.CTkFont(size=11), text_color="#38bdf8"
        )
        self.lbl_vol_val.pack(side="right")

        self.slider_vol = ctk.CTkSlider(
            settings_card,
            from_=0.0,
            to=1.0,
            number_of_steps=20,
            command=self._on_vol_slider,
        )
        self.slider_vol.set(0.9)
        self.slider_vol.pack(fill="x", padx=12, pady=(0, 8))

        # Voice Selector
        ctk.CTkLabel(
            settings_card,
            text="Selected Voice:",
            font=ctk.CTkFont(size=11),
            text_color="#cbd5e1",
        ).pack(anchor="w", padx=12, pady=(4, 2))

        self.combo_voices = ctk.CTkComboBox(
            settings_card,
            values=["Default Voice"],
            command=self._on_voice_selected,
            height=30,
            font=ctk.CTkFont(size=11),
        )
        self.combo_voices.pack(fill="x", padx=12, pady=(0, 10))

        # Mic Calibration Button
        self.btn_calibrate = ctk.CTkButton(
            settings_card,
            text="Calibrate Ambient Noise",
            font=ctk.CTkFont(size=11),
            fg_color="#334155",
            hover_color="#475569",
            command=self._calibrate_mic,
        )
        self.btn_calibrate.pack(fill="x", padx=12, pady=(0, 12))

        # Section 4: Quick Action Chips
        chips_card = ctk.CTkFrame(self.sidebar, fg_color="#0f172a", corner_radius=12)
        chips_card.pack(fill="x", padx=10, pady=(0, 14))

        ctk.CTkLabel(
            chips_card,
            text="EXAMPLE COMMANDS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#94a3b8",
        ).pack(anchor="w", padx=12, pady=(10, 6))

        examples = [
            "What time is it?",
            "Tell me today's date",
            "Open Notepad",
            "Open Calculator",
            "Open Google",
            "Open YouTube",
            "Search for Python tutorials",
            "How much disk space is available?",
            "What is my computer name?",
            "Show available commands",
        ]
        for cmd in examples:
            chip = QuickCommandChip(
                chips_card, command_text=cmd, on_click=self._execute_typed_command
            )
            chip.pack(fill="x", padx=12, pady=3)

        # Section 5: Session Actions
        session_card = ctk.CTkFrame(
            self.sidebar, fg_color="transparent"
        )
        session_card.pack(fill="x", padx=10, pady=(4, 16))

        self.btn_clear = ctk.CTkButton(
            session_card,
            text="Clear Conversation",
            fg_color="#334155",
            hover_color="#475569",
            command=self._clear_conversation,
        )
        self.btn_clear.pack(fill="x", pady=4)

        self.btn_exit = ctk.CTkButton(
            session_card,
            text="Exit Assistant",
            fg_color="#7f1d1d",
            hover_color="#991b1b",
            command=self.confirm_and_exit,
        )
        self.btn_exit.pack(fill="x", pady=4)

    def _build_main_content(self) -> None:
        """Construct the live response banners, scrollable chat, and text input bar."""
        # Live Utterance Banner
        self.live_banner = ctk.CTkFrame(
            self.main_content, fg_color="#1e293b", corner_radius=12, height=110
        )
        self.live_banner.pack(fill="x", pady=(0, 10))
        self.live_banner.pack_propagate(False)

        # Recognized text display
        recog_row = ctk.CTkFrame(self.live_banner, fg_color="transparent")
        recog_row.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(
            recog_row,
            text="User Heard:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8",
            width=90,
            anchor="w",
        ).pack(side="left")
        self.lbl_live_heard = ctk.CTkLabel(
            recog_row,
            text="Ready. Say a command or click 'Start Listening'.",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="#e2e8f0",
            anchor="w",
        )
        self.lbl_live_heard.pack(side="left", fill="x", expand=True)

        # Assistant response display
        reply_row = ctk.CTkFrame(self.live_banner, fg_color="transparent")
        reply_row.pack(fill="x", padx=16, pady=(2, 10))
        ctk.CTkLabel(
            reply_row,
            text="Assistant Reply:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#c084fc",
            width=90,
            anchor="w",
        ).pack(side="left")
        self.lbl_live_reply = ctk.CTkLabel(
            reply_row,
            text="Awaiting command.",
            font=ctk.CTkFont(size=12),
            text_color="#e2e8f0",
            anchor="w",
        )
        self.lbl_live_reply.pack(side="left", fill="x", expand=True)

        # Scrollable Conversation History
        self.chat_container = ctk.CTkScrollableFrame(
            self.main_content, fg_color="#0f172a", corner_radius=12
        )
        self.chat_container.pack(fill="both", expand=True, pady=(0, 10))

        # Bottom Input Area
        input_bar = ctk.CTkFrame(
            self.main_content, fg_color="#1e293b", corner_radius=12, height=52
        )
        input_bar.pack(fill="x", pady=(0, 4))
        input_bar.pack_propagate(False)

        self.entry_command = ctk.CTkEntry(
            input_bar,
            placeholder_text="Type a voice command (e.g., 'What time is it?', 'Open Calculator', 'Search for Python')...",
            font=ctk.CTkFont(size=12),
            height=38,
            border_width=0,
            fg_color="#0f172a",
        )
        self.entry_command.pack(side="left", fill="x", expand=True, padx=(10, 8), pady=7)
        self.entry_command.bind("<Return>", lambda _: self._send_typed_command())

        self.btn_send = ctk.CTkButton(
            input_bar,
            text="Send ⏎",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=80,
            height=38,
            command=self._send_typed_command,
        )
        self.btn_send.pack(side="right", padx=(0, 10), pady=7)

        # Notification / Offline Warning Bar
        self.lbl_notification = ctk.CTkLabel(
            self.main_content,
            text="Offline TTS active • Google STT requires internet • Typed commands work 100% offline",
            font=ctk.CTkFont(size=10),
            text_color="#64748b",
        )
        self.lbl_notification.pack(side="bottom", anchor="w", padx=6)

    # --- Populating Data ---

    def _populate_voices(self) -> None:
        """Fetch available installed TTS voices and populate combobox."""
        voices = self.controller.get_available_voices()
        if voices:
            names = [v["name"] for v in voices]
            self.combo_voices.configure(values=names)
            self.combo_voices.set(names[0])
            self._voice_map = {v["name"]: v["id"] for v in voices}
        else:
            self._voice_map = {}

    def _check_initial_microphone(self) -> None:
        """Verify microphone accessibility on startup and update notification banner."""
        ok, msg = self.controller.stt.is_microphone_available()
        if ok:
            self.lbl_notification.configure(
                text="✅ Microphone connected and ready • Speak or type any command (e.g. 'what time', 'open calculator')",
                text_color="#10b981",
            )
        else:
            self.lbl_notification.configure(
                text=f"⚠️ {msg}",
                text_color="#f59e0b",
            )

    def _add_system_welcome(self) -> None:
        """Display helpful introduction in the conversation canvas."""
        welcome_text = "👋 Welcome to Personal Voice Assistant!"
        self._add_chat_bubble("assistant", welcome_text)

    # --- User Interaction Actions ---

    def _toggle_listening(self) -> None:
        """Toggle listening state via the big mic button."""
        if self.controller.stt.status in (STATUS_LISTENING, STATUS_RECOGNIZING):
            self._on_stop_listening_clicked()
        else:
            self._on_start_listening_clicked()

    def _on_start_listening_clicked(self) -> None:
        """Handle Start Listening request."""
        continuous = bool(self.switch_continuous.get())
        ok, msg = self.controller.stt.is_microphone_available()
        if not ok:
            self._on_error(msg)
            return

        self.lbl_live_heard.configure(text="Listening for voice... (Speak now)")
        self.lbl_notification.configure(
            text="🎤 Microphone active! Speak your command clearly into your microphone.",
            text_color="#10b981",
        )
        self.controller.start_listening(continuous=continuous)

    def _on_stop_listening_clicked(self) -> None:
        """Handle Stop Listening request."""
        self.controller.stop_listening()

    def _on_continuous_toggle(self) -> None:
        """Toggle continuous hands-free mode."""
        is_continuous = bool(self.switch_continuous.get())
        if is_continuous:
            self.lbl_notification.configure(
                text="Continuous mode enabled: Listening will restart automatically after each command.",
                text_color="#38bdf8",
            )
            # If already listening, restart with continuous=True
            if self.controller.stt.status == STATUS_LISTENING:
                self.controller.start_listening(continuous=True)
        else:
            self.lbl_notification.configure(
                text="One-shot listening mode active.",
                text_color="#64748b",
            )
            self.controller.is_continuous = False

    def _on_wake_word_toggle(self) -> None:
        """Toggle wake word requirement."""
        enabled = bool(self.switch_wake_word.get())
        phrase = self.entry_wake_word.get()
        self.controller.set_wake_word(enabled, phrase)
        if enabled:
            self.lbl_notification.configure(
                text=f"Wake word active: Only commands starting with '{self.controller.wake_word}' will execute.",
                text_color="#f59e0b",
            )
        else:
            self.lbl_notification.configure(
                text="Wake word disabled: All spoken input will be processed directly.",
                text_color="#64748b",
            )

    def _save_wake_word(self) -> None:
        """Save edited wake word phrase."""
        phrase = self.entry_wake_word.get().strip()
        if phrase:
            enabled = bool(self.switch_wake_word.get())
            self.controller.set_wake_word(enabled, phrase)

    def _on_rate_slider(self, value: float) -> None:
        """Handle speech rate adjustment."""
        rate = int(value)
        self.lbl_rate_val.configure(text=f"{rate} wpm")
        self.controller.set_tts_rate(rate)

    def _on_vol_slider(self, value: float) -> None:
        """Handle speech volume adjustment."""
        pct = int(value * 100)
        self.lbl_vol_val.configure(text=f"{pct}%")
        self.controller.set_tts_volume(value)

    def _on_voice_selected(self, choice: str) -> None:
        """Handle voice combobox change."""
        if hasattr(self, "_voice_map") and choice in self._voice_map:
            voice_id = self._voice_map[choice]
            self.controller.set_tts_voice(voice_id)

    def _calibrate_mic(self) -> None:
        """Trigger microphone ambient noise calibration."""
        self.lbl_notification.configure(
            text="Calibrating microphone for 1 second of room silence...",
            text_color="#f59e0b",
        )
        self.update_idletasks()
        success, msg = self.controller.calibrate_microphone()
        self.lbl_notification.configure(
            text=msg, text_color="#10b981" if success else "#ef4444"
        )

    def _send_typed_command(self) -> None:
        """Send command from the text entry bar."""
        text = self.entry_command.get().strip()
        if not text:
            return
        self.entry_command.delete(0, "end")
        self._execute_typed_command(text)

    def _execute_typed_command(self, text: str) -> None:
        """Execute command text."""
        self.lbl_live_heard.configure(text=text)
        self.controller.execute_command(text)

    def _clear_conversation(self) -> None:
        """Clear chat messages."""
        for widget in self.chat_container.winfo_children():
            widget.destroy()
        self.controller.clear_history()
        self._add_system_welcome()

    # --- Thread-Safe Event Handlers ---

    def _on_status_update(self, status: str) -> None:
        """Update GUI according to new assistant status."""
        self.status_badge.set_status(status)

        if status == STATUS_LISTENING:
            self.btn_mic_circle.configure(
                fg_color="#10b981", hover_color="#059669"
            )
            self.lbl_mic_hint.configure(text="Listening to voice...", text_color="#10b981")
            self.btn_start.configure(state="disabled")
            self.btn_stop.configure(state="normal")
        elif status == STATUS_RECOGNIZING:
            self.btn_mic_circle.configure(
                fg_color="#06b6d4", hover_color="#0891b2"
            )
            self.lbl_mic_hint.configure(text="Recognizing speech...", text_color="#06b6d4")
        elif status == STATUS_SPEAKING:
            self.btn_mic_circle.configure(
                fg_color="#8b5cf6", hover_color="#7c3aed"
            )
            self.lbl_mic_hint.configure(text="Speaking response...", text_color="#8b5cf6")
        elif status == STATUS_CALIBRATING:
            self.btn_mic_circle.configure(
                fg_color="#f59e0b", hover_color="#d97706"
            )
            self.lbl_mic_hint.configure(text="Calibrating...", text_color="#f59e0b")
        elif status == STATUS_SLEEPING:
            self.btn_mic_circle.configure(
                fg_color="#6366f1", hover_color="#4f46e5"
            )
            self.lbl_mic_hint.configure(text="Sleeping ('Wake up')", text_color="#6366f1")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="normal")
        else:  # Idle or Error
            self.btn_mic_circle.configure(
                fg_color="#334155", hover_color="#475569"
            )
            self.lbl_mic_hint.configure(text="Click mic to start", text_color="#cbd5e1")
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")

    def _on_user_speech(self, text: str) -> None:
        """Display captured speech in live banner and chat history."""
        self.lbl_live_heard.configure(text=text)
        self._add_chat_bubble("user", text)

    def _on_assistant_response(self, text: str, action_type: str) -> None:
        """Display assistant reply in live banner and chat history."""
        self.lbl_live_reply.configure(text=text)
        self._add_chat_bubble("assistant", text)

    def _on_error(self, message: str) -> None:
        """Display error notification."""
        self.lbl_notification.configure(text=f"⚠️ {message}", text_color="#f87171")

    def _add_chat_bubble(self, role: str, text: str) -> None:
        """Add a formatted message bubble to the chat container."""
        bubble = MessageBubble(self.chat_container, role=role, text=text)
        bubble.pack(fill="x", padx=10, pady=6)

        # Scroll to bottom smoothly
        self.after(50, self._scroll_chat_bottom)

    def _scroll_chat_bottom(self) -> None:
        """Scroll the chat view to the most recent message."""
        try:
            self.chat_container._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def confirm_and_exit(self) -> None:
        """Prompt confirmation before shutting down."""
        if messagebox.askyesno(
            "Exit Assistant",
            "Are you sure you want to close Personal Voice Assistant?",
            parent=self,
        ):
            self.controller.shutdown()
            self.destroy()
            sys.exit(0)
