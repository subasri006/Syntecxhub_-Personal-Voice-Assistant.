"""Speech Recognition Service Module.

Captures microphone audio, calibrates ambient noise, handles timeouts,
and interfaces with SpeechRecognition engines (Google Speech API by default)
with clean fallbacks and thread-safe callbacks.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)

# State constants
STATUS_IDLE = "Idle"
STATUS_CALIBRATING = "Calibrating Microphone..."
STATUS_LISTENING = "Listening..."
STATUS_RECOGNIZING = "Recognizing Speech..."
STATUS_SPEAKING = "Assistant Speaking..."
STATUS_SLEEPING = "Sleeping (Say 'Wake up')"
STATUS_ERROR = "Error"


class SpeechRecognitionService:
    """Thread-safe Speech Recognition Service.

    Manages microphone input, ambient noise adjustment, and speech-to-text
    recognition with graceful error handling and non-blocking background workers.
    """

    def __init__(
        self,
        language: str = "en-US",
        timeout: float = 10.0,
        phrase_time_limit: float = 12.0,
        energy_threshold: int = 250,
        dynamic_energy_threshold: bool = True,
        on_status_change: Optional[Callable[[str], None]] = None,
        on_speech_recognized: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        is_speaking_check: Optional[Callable[[], bool]] = None,
    ):
        self.language = language
        self.timeout = timeout
        self.phrase_time_limit = phrase_time_limit
        self.energy_threshold = energy_threshold
        self.dynamic_energy_threshold = dynamic_energy_threshold

        self.on_status_change = on_status_change
        self.on_speech_recognized = on_speech_recognized
        self.on_error = on_error
        self.is_speaking_check = is_speaking_check

        self._recognizer = None
        self._microphone = None
        self._is_continuous = False
        self._stop_requested = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._status = STATUS_IDLE

        self._init_speech_recognition()

    @property
    def status(self) -> str:
        """Return the current recognition status."""
        return self._status

    def _set_status(self, new_status: str) -> None:
        """Update internal status and notify listeners."""
        self._status = new_status
        if self.on_status_change:
            try:
                self.on_status_change(new_status)
            except Exception as exc:
                logger.error("Error in on_status_change callback: %s", exc)

    def _init_speech_recognition(self) -> None:
        """Initialize the underlying speech_recognition objects."""
        try:
            import speech_recognition as sr

            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = self.energy_threshold
            self._recognizer.dynamic_energy_threshold = self.dynamic_energy_threshold
            self._recognizer.pause_threshold = 0.8
        except ImportError:
            self._recognizer = None
            logger.warning("speech_recognition library not available.")

    def is_microphone_available(self) -> Tuple[bool, str]:
        """Verify whether a working microphone and PyAudio backend exist."""
        try:
            import speech_recognition as sr

            try:
                # Test creating a Microphone object
                mic = sr.Microphone()
                # Test opening the audio stream briefly
                with mic as source:
                    pass
                return True, "Microphone is connected and ready."
            except (AttributeError, ImportError, OSError) as exc:
                return (
                    False,
                    f"Microphone or PyAudio driver unavailable: {exc}. "
                    "Ensure a microphone is plugged in and PyAudio is installed.",
                )
        except Exception as exc:
            return False, f"Audio subsystem error: {exc}"

    def calibrate_ambient_noise(self, duration: float = 1.0) -> Tuple[bool, str]:
        """Calibrate the microphone for background noise."""
        if not self._recognizer:
            return False, "Speech recognizer is not initialized."

        try:
            import speech_recognition as sr

            self._set_status(STATUS_CALIBRATING)
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=duration)
            self._set_status(STATUS_IDLE)
            return (
                True,
                f"Calibrated for background noise (Threshold: {int(self._recognizer.energy_threshold)}).",
            )
        except Exception as exc:
            self._set_status(STATUS_ERROR)
            msg = f"Microphone calibration failed: {exc}"
            logger.error(msg)
            if self.on_error:
                self.on_error(msg)
            return False, msg

    def start_listening(self, continuous: bool = False) -> None:
        """Start listening asynchronously in a background thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            # Already active
            return

        self._is_continuous = continuous
        self._stop_requested.clear()
        self._worker_thread = threading.Thread(
            target=self._listening_loop,
            daemon=True,
            name="SpeechRecognition-Worker",
        )
        self._worker_thread.start()

    def stop_listening(self) -> None:
        """Signal the background listening worker to stop."""
        self._is_continuous = False
        self._stop_requested.set()
        self._set_status(STATUS_IDLE)

    def _listening_loop(self) -> None:
        """Background thread execution loop for speech capture and recognition."""
        try:
            import speech_recognition as sr
        except ImportError:
            self._set_status(STATUS_ERROR)
            if self.on_error:
                self.on_error("speech_recognition library is not installed.")
            return

        while not self._stop_requested.is_set():
            # If the assistant is actively speaking, avoid picking up own voice
            if self.is_speaking_check and self.is_speaking_check():
                time.sleep(0.3)
                continue

            try:
                mic = sr.Microphone()
            except Exception as mic_err:
                self._set_status(STATUS_ERROR)
                if self.on_error:
                    self.on_error(f"Cannot access microphone: {mic_err}")
                break

            self._set_status(STATUS_LISTENING)
            audio = None

            try:
                with mic as source:
                    # Listen for audio phrase
                    audio = self._recognizer.listen(
                        source,
                        timeout=self.timeout,
                        phrase_time_limit=self.phrase_time_limit,
                    )
            except sr.WaitTimeoutError:
                # Normal silence timeout in continuous mode; keep listening
                if not self._is_continuous:
                    self._set_status(STATUS_IDLE)
                    if self.on_error:
                        self.on_error(
                            "Listening timed out (no speech heard). Click 'Start Listening' to speak or enable 'Continuous Mode'."
                        )
                    break
                continue
            except Exception as listen_err:
                if self._stop_requested.is_set():
                    break
                logger.warning("Error listening to microphone: %s", listen_err)
                if not self._is_continuous:
                    self._set_status(STATUS_ERROR)
                    if self.on_error:
                        self.on_error(f"Microphone listening error: {listen_err}")
                    break
                time.sleep(0.5)
                continue

            if self._stop_requested.is_set():
                break

            # If assistant started speaking while recording, discard audio
            if self.is_speaking_check and self.is_speaking_check():
                continue

            # Convert captured speech to text
            if audio is not None:
                self._set_status(STATUS_RECOGNIZING)
                try:
                    text = self._recognizer.recognize_google(
                        audio, language=self.language
                    )
                    logger.info("Recognized speech: %s", text)
                    if self.on_speech_recognized:
                        self.on_speech_recognized(text)
                except sr.UnknownValueError:
                    # Speech was unintelligible
                    logger.debug("Speech unintelligible.")
                    if not self._is_continuous and self.on_error:
                        self.on_error(
                            "Could not understand the audio. Please speak clearly."
                        )
                except sr.RequestError as req_err:
                    msg = (
                        f"Speech recognition service request failed: {req_err}. "
                        "Check your internet connection."
                    )
                    logger.warning(msg)
                    if self.on_error:
                        self.on_error(msg)
                except Exception as rec_err:
                    logger.error("Recognition exception: %s", rec_err)
                    if self.on_error:
                        self.on_error(f"Recognition error: {rec_err}")

            if not self._is_continuous:
                break

        self._set_status(STATUS_IDLE)
