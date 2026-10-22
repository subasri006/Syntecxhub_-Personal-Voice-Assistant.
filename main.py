"""Personal Voice Assistant - Main Application Entrypoint.

Initializes the assistant controller, launches the modern desktop GUI,
and coordinates speech recognition, offline text-to-speech, and system automation.
"""

from __future__ import annotations

import argparse
import logging
import sys

# Configure UTF-8 for console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from assistant.assistant_controller import AssistantController
from gui.main_window import MainWindow

# Setup structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("VoiceAssistant")


def run_cli_mode(controller: AssistantController) -> None:
    """Run interactive terminal mode without GUI."""
    print("=" * 60)
    print("Personal Voice Assistant — CLI Interactive Mode")
    print("Type your commands below. Type 'exit' or press Ctrl+C to quit.")
    print("=" * 60)

    # Wire console callbacks
    controller.on_status_changed = lambda s: print(f"[*] Status: {s}")
    controller.on_assistant_response = lambda text, action: print(f"[Assistant]: {text}")
    controller.on_error = lambda err: print(f"[!] Error: {err}")

    try:
        while True:
            try:
                cmd = input("\n[You]> ").strip()
            except EOFError:
                break
            if not cmd:
                continue
            if cmd.lower() in ("exit", "quit"):
                controller.execute_command(cmd)
                break
            controller.execute_command(cmd)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        controller.shutdown()


def main() -> None:
    """Application main entrypoint."""
    parser = argparse.ArgumentParser(
        description="Personal Voice Assistant - Desktop AI Companion"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in headless command-line interactive mode instead of GUI",
    )
    parser.add_argument(
        "--wake-word",
        type=str,
        default="hey assistant",
        help="Initial wake word phrase (default: 'hey assistant')",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=175,
        help="Text-to-speech rate in words per minute (default: 175)",
    )
    parser.add_argument(
        "--volume",
        type=float,
        default=0.9,
        help="Text-to-speech volume between 0.0 and 1.0 (default: 0.9)",
    )

    args = parser.parse_args()

    logger.info("Initializing Assistant Controller...")
    controller = AssistantController(
        wake_word=args.wake_word,
        tts_rate=args.rate,
        tts_volume=args.volume,
    )

    if args.cli:
        run_cli_mode(controller)
    else:
        logger.info("Launching Desktop GUI...")
        try:
            app = MainWindow(controller=controller)
            app.mainloop()
        except KeyboardInterrupt:
            logger.info("Shutdown requested.")
            controller.shutdown()
        except Exception as exc:
            logger.critical("Fatal error encountered in GUI: %s", exc, exc_info=True)
            controller.shutdown()
            sys.exit(1)


if __name__ == "__main__":
    main()
