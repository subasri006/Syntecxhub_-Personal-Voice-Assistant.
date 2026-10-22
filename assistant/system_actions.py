"""Windows System Actions Module.

Provides safe, platform-aware implementations for desktop automation:
- System volume control (up, down, mute)
- Screenshot capture via Pillow
- Safe folder creation with path validation
- System power actions with confirmation safeguards
- Music playback via default media services
"""

from __future__ import annotations

import ctypes
import datetime
import logging
import os
import pathlib
import re
import subprocess
import urllib.parse
import webbrowser
from typing import Optional, Tuple

from PIL import ImageGrab

logger = logging.getLogger(__name__)

# Virtual key codes for multimedia volume on Windows
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
KEYEVENTF_KEYUP = 0x0002


def _send_virtual_key(vk_code: int, times: int = 1) -> None:
    """Send a virtual keyboard key press on Windows."""
    if os.name != "nt":
        return
    try:
        user32 = ctypes.windll.user32
        for _ in range(times):
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
    except Exception as exc:
        logger.error("Failed to send virtual key 0x%X: %s", vk_code, exc)
        raise


def change_volume(action: str) -> Tuple[bool, str]:
    """Adjust system volume (up, down, mute)."""
    action = action.lower().strip()
    try:
        if action in ("up", "increase", "raise", "louder"):
            _send_virtual_key(VK_VOLUME_UP, times=5)
            return True, "Volume increased."
        elif action in ("down", "decrease", "lower", "softer"):
            _send_virtual_key(VK_VOLUME_DOWN, times=5)
            return True, "Volume decreased."
        elif action in ("mute", "unmute", "toggle_mute", "silence"):
            _send_virtual_key(VK_VOLUME_MUTE, times=1)
            return True, "Volume mute toggled."
        else:
            return False, f"Unknown volume action: '{action}'."
    except Exception as exc:
        return False, f"Could not adjust system volume: {exc}"


def get_desktop_dir() -> pathlib.Path:
    """Resolve the user's active Desktop directory, accounting for OneDrive."""
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive:
        onedrive_desktop = pathlib.Path(onedrive) / "Desktop"
        if onedrive_desktop.exists():
            return onedrive_desktop

    user_desktop = pathlib.Path.home() / "Desktop"
    if user_desktop.exists():
        return user_desktop

    # Fallback to user home
    return pathlib.Path.home()


def get_screenshots_dir() -> pathlib.Path:
    """Resolve or create the Screenshots directory."""
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive and (pathlib.Path(onedrive) / "Pictures").exists():
        base = pathlib.Path(onedrive) / "Pictures"
    else:
        base = pathlib.Path.home() / "Pictures"

    shots_dir = base / "Screenshots"
    try:
        shots_dir.mkdir(parents=True, exist_ok=True)
        return shots_dir
    except Exception:
        return base


def take_screenshot() -> Tuple[bool, str, Optional[str]]:
    """Capture the full screen and save as a timestamped PNG file."""
    try:
        shots_dir = get_screenshots_dir()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Screenshot_{timestamp}.png"
        filepath = shots_dir / filename

        image = ImageGrab.grab()
        image.save(str(filepath), "PNG")

        return True, f"Screenshot captured and saved to {filepath.name}.", str(filepath)
    except Exception as exc:
        logger.error("Failed to capture screenshot: %s", exc)
        return False, f"Could not capture screenshot: {exc}", None


def create_safe_folder(folder_name: str, target_dir: Optional[pathlib.Path] = None) -> Tuple[bool, str]:
    """Validate and safely create a new directory inside the user's Desktop or specified directory."""
    raw_name = folder_name.strip().strip("\"'")
    if not raw_name:
        return False, "Please specify a folder name to create."

    # Validate against illegal characters and directory traversal
    if re.search(r'[<>:"/\\|?*]', raw_name):
        return False, f"Folder name '{raw_name}' contains illegal characters (< > : \" / \\ | ? *)."

    if ".." in raw_name or raw_name.startswith("."):
        return False, "Folder name cannot contain path traversal elements."

    # Reserved Windows device names
    reserved = {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
                "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4",
                "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}
    if raw_name.upper() in reserved:
        return False, f"'{raw_name}' is a reserved Windows system name and cannot be used."

    base_dir = target_dir if target_dir is not None else get_desktop_dir()
    destination = base_dir / raw_name

    try:
        if destination.exists():
            return False, f"A folder named '{raw_name}' already exists at {destination}."

        destination.mkdir(parents=True, exist_ok=False)
        return True, f"Successfully created folder '{raw_name}' on your Desktop ({destination})."
    except PermissionError:
        return False, f"Permission denied when creating folder at {destination}."
    except Exception as exc:
        return False, f"Error creating folder: {exc}"


def play_music(query: Optional[str] = None) -> Tuple[bool, str]:
    """Play music via YouTube Music or standard media services."""
    try:
        if query and query.strip():
            clean_query = query.strip()
            encoded = urllib.parse.quote_plus(clean_query)
            url = f"https://music.youtube.com/search?q={encoded}"
            webbrowser.open(url)
            return True, f"Playing '{clean_query}' on YouTube Music."
        else:
            url = "https://music.youtube.com"
            webbrowser.open(url)
            return True, "Opening YouTube Music."
    except Exception as exc:
        return False, f"Could not launch music service: {exc}"


def execute_shutdown(countdown_seconds: int = 60) -> Tuple[bool, str]:
    """Initiate a Windows system shutdown with a safety grace countdown."""
    if os.name != "nt":
        return False, "Shutdown command is only supported on Windows."
    try:
        subprocess.run(
            ["shutdown", "/s", "/t", str(countdown_seconds)],
            check=True,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return (
            True,
            f"Computer shutdown initiated with a {countdown_seconds}-second countdown. "
            "Say or type 'cancel shutdown' to abort.",
        )
    except Exception as exc:
        return False, f"Failed to execute shutdown: {exc}"


def cancel_shutdown() -> Tuple[bool, str]:
    """Abort a pending Windows shutdown."""
    if os.name != "nt":
        return False, "Shutdown abort is only supported on Windows."
    try:
        res = subprocess.run(
            ["shutdown", "/a"],
            capture_output=True,
            text=True,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        if res.returncode == 0 or "1116" in str(res.stderr) or "unable to abort" in str(res.stderr).lower():
            return True, "System shutdown has been successfully cancelled."
        return True, "System shutdown has been cancelled."
    except Exception as exc:
        return False, f"Could not cancel shutdown: {exc}"


def execute_restart(countdown_seconds: int = 60) -> Tuple[bool, str]:
    """Initiate a Windows system restart with a safety grace countdown."""
    if os.name != "nt":
        return False, "Restart command is only supported on Windows."
    try:
        subprocess.run(
            ["shutdown", "/r", "/t", str(countdown_seconds)],
            check=True,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        return (
            True,
            f"Computer restart initiated with a {countdown_seconds}-second countdown. "
            "Say or type 'cancel shutdown' to abort.",
        )
    except Exception as exc:
        return False, f"Failed to execute restart: {exc}"
