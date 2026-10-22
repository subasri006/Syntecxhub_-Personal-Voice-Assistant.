"""Assistant Controller Module.

Acts as the central orchestrator connecting Speech Recognition,
Text-to-Speech, Command Routing, safety validations, and GUI callbacks.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Callable, Dict, List, Optional

from assistant.command_handlers import CommandResult
from assistant.command_router import CommandRouter
from assistant.speech_recognition_service import (
    STATUS_IDLE,
    STATUS_LISTENING,
    STATUS_SLEEPING,
    STATUS_SPEAKING,
    SpeechRecognitionService,
)
from assistant.text_to_speech import TextToSpeechService

logger = logging.getLogger(__name__)


class AssistantController:
    """Central Controller managing voice assistant lifecycle and interactions."""

    def __init__(
        self,
        wake_word: str = "hey assistant",
        wake_word_enabled: bool = False,
        tts_rate: int = 175,
        tts_volume: float = 0.9,
    ):
        self.wake_word = wake_word
        self.wake_word_enabled = wake_word_enabled
        self.is_sleeping = False
        self.is_continuous = False

        self.conversation_history: List[Dict[str, str]] = []

        # GUI Event Callbacks
        self.on_status_changed: Optional[Callable[[str], None]] = None
        self.on_user_speech: Optional[Callable[[str], None]] = None
        self.on_assistant_response: Optional[Callable[[str, str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_control_action: Optional[Callable[[str], None]] = None

        # Core subsystems
        self.router = CommandRouter()
        self.tts = TextToSpeechService(
            rate=tts_rate,
            volume=tts_volume,
            on_speech_started=self._handle_tts_started,
            on_speech_finished=self._handle_tts_finished,
            on_error=self._handle_error,
        )

        self.stt = SpeechRecognitionService(
            on_status_change=self._handle_stt_status,
            on_speech_recognized=self._handle_speech_recognized,
            on_error=self._handle_error,
            is_speaking_check=lambda: self.tts.is_speaking,
        )

    # --- Callback Handlers ---

    def _handle_tts_started(self, text: str) -> None:
        """Called when TTS begins speaking."""
        self._notify_status(STATUS_SPEAKING)

    def _handle_tts_finished(self, text: str) -> None:
        """Called when TTS completes speaking."""
        if self.is_sleeping:
            self._notify_status(STATUS_SLEEPING)
        elif self.is_continuous:
            self._notify_status(STATUS_LISTENING)
        else:
            self._notify_status(STATUS_IDLE)

    def _handle_stt_status(self, status: str) -> None:
        """Propagate STT status updates to GUI."""
        if not self.tts.is_speaking:
            if self.is_sleeping:
                self._notify_status(STATUS_SLEEPING)
            else:
                self._notify_status(status)

    def _notify_status(self, status_text: str) -> None:
        """Notify GUI of status change."""
        if self.on_status_changed:
            try:
                self.on_status_changed(status_text)
            except Exception as exc:
                logger.error("Error in status changed callback: %s", exc)

    def _handle_error(self, message: str) -> None:
        """Handle errors from STT or TTS."""
        logger.warning("Assistant error: %s", message)
        if self.on_error:
            try:
                self.on_error(message)
            except Exception as exc:
                logger.error("Error in error callback: %s", exc)

    def _append_history(self, role: str, text: str) -> None:
        """Append an entry to conversation history."""
        timestamp = datetime.datetime.now().strftime("%I:%M %p")
        self.conversation_history.append(
            {"role": role, "text": text, "timestamp": timestamp}
        )

    # --- Speech Recognition Flow ---

    def _handle_speech_recognized(self, text: str) -> None:
        """Process incoming speech captured by the microphone."""
        if not text.strip():
            return

        # If sleeping, only wake up commands can reactivate
        if self.is_sleeping:
            norm = CommandRouter.normalize_text(text)
            if "wake up" in norm or "wake" in norm:
                self.is_sleeping = False
                res = CommandResult(
                    success=True,
                    response_text="I am awake and listening. How can I help you?",
                    action_type="control",
                    action_data={"control": "wake_up"},
                )
                self._dispatch_command_result(text, res)
            return

        # Check Wake Word if enabled
        command_to_process = text
        if self.wake_word_enabled:
            detected, remainder = CommandRouter.extract_wake_word(
                text, self.wake_word
            )
            if not detected:
                # Wake word not heard; ignore background conversation
                return
            if not remainder:
                # User only said the wake word (e.g. "Hey assistant")
                self._append_history("user", text)
                if self.on_user_speech:
                    self.on_user_speech(text)
                reply = "I'm listening, how can I help you?"
                self._append_history("assistant", reply)
                if self.on_assistant_response:
                    self.on_assistant_response(reply, "speak")
                self.tts.speak(reply)
                return
            command_to_process = remainder

        # Process the recognized voice command
        self.execute_command(command_to_process, source_text=text)

    # --- Command Execution ---

    def execute_command(self, command_text: str, source_text: Optional[str] = None) -> CommandResult:
        """Route and execute a command from voice or text input."""
        display_user_text = source_text or command_text
        self._append_history("user", display_user_text)

        if self.on_user_speech:
            try:
                self.on_user_speech(display_user_text)
            except Exception as exc:
                logger.error("Error in on_user_speech callback: %s", exc)

        # Route the command
        result = self.router.route(command_text)
        self._dispatch_command_result(display_user_text, result)
        return result

    def _dispatch_command_result(self, input_text: str, result: CommandResult) -> None:
        """Dispatch command result to TTS, history, and GUI."""
        self._append_history("assistant", result.response_text)

        # Handle control directives
        if result.action_type == "control" and result.action_data:
            control_code = result.action_data.get("control")
            if control_code == "stop_listening":
                self.stop_listening()
            elif control_code == "sleep":
                self.is_sleeping = True
                self._notify_status(STATUS_SLEEPING)
            elif control_code == "wake_up":
                self.is_sleeping = False
                self._notify_status(
                    STATUS_LISTENING if self.is_continuous else STATUS_IDLE
                )
            elif control_code == "exit":
                if self.on_control_action:
                    self.on_control_action("exit")

        # Notify GUI of assistant response
        if self.on_assistant_response:
            try:
                self.on_assistant_response(result.response_text, result.action_type)
            except Exception as exc:
                logger.error("Error in on_assistant_response callback: %s", exc)

        # Speak response if requested (using concise spoken_text if available)
        if result.should_speak:
            text_to_speak = result.spoken_text or result.response_text
            if text_to_speak:
                self.tts.speak(text_to_speak)

    # --- Public Control Methods ---

    def start_listening(self, continuous: bool = False) -> None:
        """Begin speech recognition."""
        self.is_continuous = continuous
        self.is_sleeping = False
        self.stt.start_listening(continuous=continuous)

    def stop_listening(self) -> None:
        """Halt speech recognition."""
        self.is_continuous = False
        self.stt.stop_listening()
        self._notify_status(STATUS_IDLE)

    def calibrate_microphone(self) -> Tuple[bool, str]:
        """Calibrate microphone for room noise."""
        return self.stt.calibrate_ambient_noise()

    def set_wake_word(self, enabled: bool, phrase: str = "hey assistant") -> None:
        """Configure wake word detection."""
        self.wake_word_enabled = enabled
        if phrase.strip():
            self.wake_word = phrase.strip()

    def set_tts_rate(self, rate: int) -> None:
        """Adjust TTS speech rate."""
        self.tts.set_rate(rate)

    def set_tts_volume(self, volume: float) -> None:
        """Adjust TTS volume level (0.0 to 1.0)."""
        self.tts.set_volume(volume)

    def set_tts_voice(self, voice_id: str) -> None:
        """Select TTS voice."""
        self.tts.set_voice(voice_id)

    def get_available_voices(self) -> List[Dict[str, str]]:
        """Retrieve available TTS voices."""
        return self.tts.get_available_voices()

    def clear_history(self) -> None:
        """Clear the current session conversation history."""
        self.conversation_history.clear()

    def shutdown(self) -> None:
        """Gracefully release microphone and TTS threads."""
        self.stop_listening()
        self.tts.stop()
