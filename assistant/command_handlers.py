"""Command Handlers Module.

Implements safe, specialized handler functions for all supported voice
assistant commands including greetings, time/date, application launching,
web navigation, search, system information, system actions (volume, screenshots,
safe folder creation, power safeguards), and AI conversational responses.
"""

from __future__ import annotations

import datetime
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from assistant import ai_service, application_launcher, system_actions, system_info

# Initialize shared AI service instance
_ai_engine = ai_service.AIService()


@dataclass
class CommandResult:
    """Represents the structured result of executing a command."""

    success: bool
    response_text: str
    action_type: str  # 'speak', 'launch', 'browse', 'control', 'info', 'error', 'ai'
    action_data: Optional[Dict[str, Any]] = None
    should_speak: bool = True
    spoken_text: Optional[str] = None  # Concise text for text-to-speech


# Whitelist of trusted web destinations
WEB_SHORTCUTS: Dict[str, str] = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://www.github.com",
    "chatgpt": "https://chatgpt.com",
    "wikipedia": "https://www.wikipedia.org",
    "reddit": "https://www.reddit.com",
    "stackoverflow": "https://stackoverflow.com",
    "music": "https://music.youtube.com",
    "spotify": "https://open.spotify.com",
}


# --- A. Greeting Handlers ---

def handle_greeting(match_group: Optional[str] = None) -> CommandResult:
    """Handle greeting phrases with friendly, time-sensitive responses."""
    now = datetime.datetime.now()
    hour = now.hour

    if hour < 12:
        period = "Good morning"
    elif hour < 17:
        period = "Good afternoon"
    else:
        period = "Good evening"

    msg = f"{period}! I am your Personal Voice Assistant. How can I help you today?"
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="speak",
        spoken_text=msg,
    )


def handle_how_are_you() -> CommandResult:
    """Handle inquiries about the assistant's state."""
    msg = "I'm operating smoothly and ready to assist you. What can I do for you?"
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="speak",
        spoken_text=msg,
    )


# --- B. Date & Time Handlers ---

def handle_time() -> CommandResult:
    """Return the current local time."""
    now = datetime.datetime.now()
    time_str = now.strftime("%I:%M %p").lstrip("0")
    msg = f"The current time is {time_str}."
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="speak",
        action_data={"timestamp": now.isoformat(), "time": time_str},
        spoken_text=msg,
    )


def handle_date() -> CommandResult:
    """Return today's full date."""
    now = datetime.datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    msg = f"Today is {date_str}."
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="speak",
        action_data={"timestamp": now.isoformat(), "date": date_str},
        spoken_text=msg,
    )


def handle_day_of_week() -> CommandResult:
    """Return today's day of the week."""
    now = datetime.datetime.now()
    day_name = now.strftime("%A")
    msg = f"Today is {day_name}."
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="speak",
        action_data={"day": day_name},
        spoken_text=msg,
    )


# --- C. Application Launch Handlers ---

def handle_open_application(app_name: str) -> CommandResult:
    """Safely launch an authorized desktop application from the whitelist."""
    clean_app = app_name.strip()
    success, msg = application_launcher.launch_application(clean_app)
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="launch",
        action_data={"application": clean_app, "success": success},
        spoken_text=msg,
    )


# --- D. Web Browser Handlers ---

def handle_open_website(site_name: str) -> CommandResult:
    """Open a predefined safe website in the default browser."""
    clean_name = site_name.strip().lower()
    url = WEB_SHORTCUTS.get(clean_name)

    if not url:
        parsed = urllib.parse.urlparse(site_name)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            url = site_name
        else:
            supported = ", ".join(k.title() for k in WEB_SHORTCUTS.keys())
            msg = f"Website '{site_name}' is not recognized. Available shortcuts: {supported}."
            return CommandResult(
                success=False,
                response_text=msg,
                action_type="browse",
                spoken_text=f"Website {site_name} is not recognized.",
            )

    try:
        webbrowser.open(url)
        msg = f"Opening {clean_name.title()} in your browser."
        return CommandResult(
            success=True,
            response_text=msg,
            action_type="browse",
            action_data={"url": url},
            spoken_text=msg,
        )
    except Exception as exc:
        return CommandResult(
            success=False,
            response_text=f"Could not open browser: {exc}",
            action_type="error",
            spoken_text="Could not open the browser.",
        )


# --- E. Web Search Handlers ---

def handle_web_search(query: str) -> CommandResult:
    """Sanitize and perform a Google web search in the default browser."""
    query = query.strip()
    if not query:
        return CommandResult(
            success=False,
            response_text="Please specify what you would like me to search for.",
            action_type="speak",
            spoken_text="Please specify what you would like me to search for.",
        )

    sanitized = "".join(ch for ch in query if ch.isprintable())[:200].strip()
    if not sanitized:
        return CommandResult(
            success=False,
            response_text="The search query was invalid.",
            action_type="error",
            spoken_text="The search query was invalid.",
        )

    encoded = urllib.parse.quote_plus(sanitized)
    search_url = f"https://www.google.com/search?q={encoded}"

    try:
        webbrowser.open(search_url)
        msg = f"Searching Google for '{sanitized}'."
        return CommandResult(
            success=True,
            response_text=msg,
            action_type="browse",
            action_data={"query": sanitized, "url": search_url},
            spoken_text=msg,
        )
    except Exception as exc:
        return CommandResult(
            success=False,
            response_text=f"Could not open search in browser: {exc}",
            action_type="error",
            spoken_text="Could not open the search.",
        )


# --- F. Desktop System Actions (Volume, Screenshots, Folders, Music) ---

def handle_volume(action: str) -> CommandResult:
    """Adjust system volume."""
    success, msg = system_actions.change_volume(action)
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="control",
        action_data={"volume_action": action},
        spoken_text=msg,
    )


def handle_screenshot() -> CommandResult:
    """Take a full desktop screenshot and save to Pictures."""
    success, msg, path = system_actions.take_screenshot()
    spoken = "Screenshot captured." if success else "Could not capture screenshot."
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="control",
        action_data={"screenshot_path": path},
        spoken_text=spoken,
    )


def handle_create_folder(folder_name: str) -> CommandResult:
    """Safely create a folder on the user's Desktop."""
    success, msg = system_actions.create_safe_folder(folder_name)
    spoken = f"Created folder {folder_name}." if success else msg
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="control",
        action_data={"folder_name": folder_name, "success": success},
        spoken_text=spoken,
    )


def handle_play_music(query: Optional[str] = None) -> CommandResult:
    """Stream music via default media services."""
    success, msg = system_actions.play_music(query)
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="browse",
        action_data={"music_query": query},
        spoken_text=msg,
    )


# --- G. System Power Safeguards (Shutdown & Restart) ---

def handle_shutdown_request() -> CommandResult:
    """Request confirmation before shutting down."""
    prompt = (
        "⚠️ Warning: Are you sure you want to shut down your computer?\n"
        "Please confirm by saying or typing 'yes confirm' (or 'cancel' to abort)."
    )
    spoken = "Are you sure you want to shut down your computer? Say yes confirm or cancel."
    return CommandResult(
        success=True,
        response_text=prompt,
        action_type="control",
        action_data={"pending_confirmation": "shutdown"},
        spoken_text=spoken,
    )


def handle_shutdown_confirm() -> CommandResult:
    """Execute confirmed shutdown with a safety grace countdown."""
    success, msg = system_actions.execute_shutdown(countdown_seconds=60)
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="control",
        action_data={"shutdown_confirmed": True},
        spoken_text="Shutting down the computer in sixty seconds. You can say cancel shutdown to abort.",
    )


def handle_shutdown_cancel() -> CommandResult:
    """Cancel pending shutdown."""
    success, msg = system_actions.cancel_shutdown()
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="control",
        action_data={"shutdown_cancelled": True},
        spoken_text="Shutdown has been cancelled.",
    )


def handle_restart_request() -> CommandResult:
    """Request confirmation before restarting."""
    prompt = (
        "⚠️ Warning: Are you sure you want to restart your computer?\n"
        "Please confirm by saying or typing 'yes confirm' (or 'cancel' to abort)."
    )
    spoken = "Are you sure you want to restart your computer? Say yes confirm or cancel."
    return CommandResult(
        success=True,
        response_text=prompt,
        action_type="control",
        action_data={"pending_confirmation": "restart"},
        spoken_text=spoken,
    )


def handle_restart_confirm() -> CommandResult:
    """Execute confirmed restart with a safety countdown."""
    success, msg = system_actions.execute_restart(countdown_seconds=60)
    return CommandResult(
        success=success,
        response_text=msg,
        action_type="control",
        action_data={"restart_confirmed": True},
        spoken_text="Restarting computer in sixty seconds. You can say cancel shutdown to abort.",
    )


# --- H. Conversational AI & General Question Answering ---

def handle_ai_question(question: str) -> CommandResult:
    """Dispatch general knowledge and conversational questions to the AI service."""
    full_text, spoken_summary = _ai_engine.answer_question(question)
    is_clarification = "I don't have this entry in my offline knowledge bank" in full_text
    return CommandResult(
        success=not is_clarification,
        response_text=full_text,
        action_type="ai",
        action_data={"question": question},
        spoken_text=spoken_summary,
    )


# --- I. System Utilities Handlers ---

def handle_computer_name() -> CommandResult:
    """Return the computer hostname."""
    msg = system_info.get_computer_name()
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="info",
        spoken_text=msg,
    )


def handle_operating_system() -> CommandResult:
    """Return OS information."""
    msg = system_info.get_os_info()
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="info",
        spoken_text=msg,
    )


def handle_disk_space() -> CommandResult:
    """Return disk space usage."""
    msg = system_info.get_disk_space()
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="info",
        spoken_text=msg,
    )


def handle_system_status() -> CommandResult:
    """Return overall CPU and memory metrics."""
    msg = system_info.get_system_health()
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="info",
        spoken_text=msg,
    )


# --- J. Assistant Controls Handlers ---

def handle_stop_listening() -> CommandResult:
    """Signal the assistant to stop active or continuous listening."""
    msg = "Listening stopped. Click Start Listening or type a command whenever you need me."
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="control",
        action_data={"control": "stop_listening"},
        spoken_text="Listening stopped.",
    )


def handle_go_to_sleep() -> CommandResult:
    """Put assistant into sleep mode."""
    msg = "Going to sleep. Say 'wake up' or click the microphone to resume."
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="control",
        action_data={"control": "sleep"},
        spoken_text="Going to sleep.",
    )


def handle_wake_up() -> CommandResult:
    """Wake assistant from sleep."""
    msg = "I am awake and listening. How can I help you?"
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="control",
        action_data={"control": "wake_up"},
        spoken_text=msg,
    )


def handle_help() -> CommandResult:
    """Show available commands and usage guide."""
    msg = (
        "Here are commands you can say or type:\n"
        "• Desktop Actions: 'Open Notepad', 'Open Calculator', 'Open VS Code', 'Take a screenshot'\n"
        "• Media & Audio: 'Play music', 'Play Bohemian Rhapsody', 'Increase volume', 'Decrease volume', 'Mute'\n"
        "• Websites: 'Open YouTube', 'Open Google', 'Open GitHub', 'Open ChatGPT'\n"
        "• Search: 'Search for Python tutorials', 'Google quantum computing'\n"
        "• Files & System: 'Create a folder named Projects', 'Check disk space', 'Show operating system'\n"
        "• Questions & AI: 'What is artificial intelligence?', 'Explain this code', 'What is 25 * 4?'\n"
        "• Power & Controls: 'Shutdown my computer', 'Cancel shutdown', 'Stop listening', 'Exit'"
    )
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="info",
        action_data={"control": "help"},
        spoken_text="Here is a summary of actions and questions you can ask me.",
    )


def handle_exit() -> CommandResult:
    """Request application exit."""
    msg = "Goodbye! Have a great day."
    return CommandResult(
        success=True,
        response_text=msg,
        action_type="control",
        action_data={"control": "exit"},
        spoken_text=msg,
    )


# --- K. Unknown / Fallback Handler ---

def handle_unknown_command(raw_input: str) -> CommandResult:
    """Fallback handler: routes conversational questions to AI service if appropriate."""
    clean = raw_input.strip()
    norm = clean.lower()

    # Only route to AI if it looks like a genuine question or conversational prompt
    question_starters = (
        "what", "why", "how", "who", "when", "where", "can you",
        "tell me", "explain", "define", "is it", "which", "calculate", "compute"
    )
    is_question = any(norm.startswith(q) for q in question_starters) or norm.endswith("?")

    if is_question:
        return handle_ai_question(clean)

    msg = (
        "Sorry, I didn't understand that command. "
        "You can say 'What is artificial intelligence?', 'Open VS Code', 'Take a screenshot', "
        "'Play music', or say 'Help' to see all available commands."
    )
    return CommandResult(
        success=False,
        response_text=msg,
        action_type="speak",
        action_data={"unrecognized_input": raw_input},
        spoken_text="Sorry, I didn't understand that command. Say help for examples.",
    )
