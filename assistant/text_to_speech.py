"""Text-to-Speech Engine Module.

Provides offline, thread-safe speech synthesis using pyttsx3.
Uses a dedicated background worker thread to prevent GUI lockups,
handles Windows COM initialization, supports rate/volume adjustments,
voice selection, and prevents the microphone from recognizing its own output.
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TextToSpeechService:
    """Thread-safe offline Text-to-Speech service using pyttsx3."""

    def __init__(
        self,
        rate: int = 175,
        volume: float = 0.9,
        on_speech_started: Optional[Callable[[str], None]] = None,
        on_speech_finished: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self.rate = rate
        self.volume = max(0.0, min(1.0, volume))
        self.selected_voice_id: Optional[str] = None
        self.on_speech_started = on_speech_started
        self.on_speech_finished = on_speech_finished
        self.on_error = on_error

        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._is_speaking = False
        self._is_running = True
        self._worker_thread: Optional[threading.Thread] = None

        self._available_voices: List[Dict[str, str]] = []
        self._init_worker()

    @property
    def is_speaking(self) -> bool:
        """Return True if speech synthesis is currently playing."""
        return self._is_speaking

    def _init_worker(self) -> None:
        """Start the background TTS thread."""
        self._worker_thread = threading.Thread(
            target=self._tts_worker_loop, daemon=True, name="TTS-Worker"
        )
        self._worker_thread.start()

    def _tts_worker_loop(self) -> None:
        """Worker thread loop managing the pyttsx3 engine."""
        # Initialize COM on Windows for this worker thread
        if sys.platform == "win32":
            try:
                import pythoncom  # type: ignore

                pythoncom.CoInitialize()
            except Exception:
                pass

        engine = None
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)

            # Discover installed voices
            voices = engine.getProperty("voices")
            if voices:
                self._available_voices = [
                    {
                        "id": v.id,
                        "name": getattr(v, "name", f"Voice {idx}"),
                        "languages": getattr(v, "languages", []),
                    }
                    for idx, v in enumerate(voices)
                ]
                if not self.selected_voice_id and voices:
                    self.selected_voice_id = voices[0].id
                    engine.setProperty("voice", self.selected_voice_id)

        except Exception as exc:
            logger.error("Failed to initialize pyttsx3 engine: %s", exc)
            if self.on_error:
                self.on_error(f"TTS initialization failed: {exc}")
            engine = None

        while self._is_running:
            try:
                text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if text is None:  # Shutdown signal
                break

            if not text.strip():
                self._queue.task_done()
                continue

            self._is_speaking = True
            if self.on_speech_started:
                try:
                    self.on_speech_started(text)
                except Exception as cb_exc:
                    logger.error("Error in on_speech_started callback: %s", cb_exc)

            if engine is not None:
                try:
                    # Apply updated properties before speaking
                    engine.setProperty("rate", self.rate)
                    engine.setProperty("volume", self.volume)
                    if self.selected_voice_id:
                        engine.setProperty("voice", self.selected_voice_id)

                    engine.say(text)
                    engine.runAndWait()
                except Exception as speak_exc:
                    logger.error("TTS playback error: %s", speak_exc)
                    if self.on_error:
                        self.on_error(f"Speech playback error: {speak_exc}")
            else:
                # Mock speech duration if engine failed
                time.sleep(0.5)

            self._is_speaking = False
            if self.on_speech_finished:
                try:
                    self.on_speech_finished(text)
                except Exception as cb_exc:
                    logger.error("Error in on_speech_finished callback: %s", cb_exc)

            self._queue.task_done()

        # Clean up
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass

        if sys.platform == "win32":
            try:
                import pythoncom  # type: ignore

                pythoncom.CoUninitialize()
            except Exception:
                pass

    def speak(self, text: str) -> None:
        """Enqueue speech text for asynchronous spoken playback."""
        if not self._is_running:
            return
        self._queue.put(text)

    def set_rate(self, rate: int) -> None:
        """Set speaking rate in words per minute (typically 100 - 300)."""
        self.rate = max(80, min(350, int(rate)))

    def set_volume(self, volume: float) -> None:
        """Set volume level between 0.0 and 1.0."""
        self.volume = max(0.0, min(1.0, float(volume)))

    def set_voice(self, voice_id: str) -> None:
        """Select an installed voice by ID."""
        self.selected_voice_id = voice_id

    def get_available_voices(self) -> List[Dict[str, str]]:
        """Return the list of discovered TTS voices."""
        return list(self._available_voices)

    def stop(self) -> None:
        """Stop current speech synthesis and terminate worker thread."""
        self._is_running = False
        # Clear any pending items
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except (queue.Empty, ValueError):
                break
        self._queue.put(None)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
