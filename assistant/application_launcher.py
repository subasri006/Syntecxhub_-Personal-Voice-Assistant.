"""Safe Application Launcher Module.

Enforces strict whitelisting to safely open authorized desktop utilities
and popular applications without shell execution or arbitrary command injection risks.
Checks for executable existence before launching and provides graceful fallbacks.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

CURRENT_SYSTEM = platform.system()

# Strict whitelist mapping canonical name -> executable name or command list
WINDOWS_APP_WHITELIST: Dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "command prompt": "cmd.exe",
    "cmd": "cmd.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
}

# Third-party applications to probe on Windows
THIRD_PARTY_CANDIDATES: Dict[str, List[str]] = {
    "vs code": [
        "code.cmd",
        "code",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft VS Code\Code.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft VS Code\Code.exe"),
    ],
    "chrome": [
        "chrome.exe",
        "chrome",
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "edge": [
        "msedge.exe",
        "msedge",
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
    ],
    "spotify": [
        "spotify.exe",
        "spotify",
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    ],
}

GENERIC_APP_FALLBACKS: Dict[str, Dict[str, str]] = {
    "Linux": {
        "calculator": "gnome-calculator",
        "notepad": "gedit",
        "paint": "gimp",
        "file explorer": "nautilus",
        "command prompt": "x-terminal-emulator",
        "vs code": "code",
        "chrome": "google-chrome",
    },
    "Darwin": {
        "calculator": "Calculator",
        "notepad": "TextEdit",
        "paint": "Preview",
        "file explorer": "Finder",
        "command prompt": "Terminal",
        "vs code": "Visual Studio Code",
        "chrome": "Google Chrome",
    },
}


def get_supported_applications() -> List[str]:
    """Return a list of canonical supported application display names."""
    return [
        "Notepad",
        "Calculator",
        "Paint",
        "File Explorer",
        "Command Prompt",
        "Task Manager",
        "Control Panel",
        "VS Code",
        "Google Chrome",
        "Microsoft Edge",
        "Spotify",
    ]


def normalize_app_key(name: str) -> str:
    """Normalize input application name."""
    cleaned = name.strip().lower()
    # Normalize aliases
    if cleaned in ("calc", "calculator app"):
        return "calculator"
    if cleaned in ("explorer", "my computer", "files", "file manager"):
        return "file explorer"
    if cleaned in ("cmd", "terminal", "console", "cmd prompt"):
        return "command prompt"
    if cleaned in ("mspaint", "ms paint"):
        return "paint"
    if cleaned in ("taskmgr", "task manager"):
        return "task manager"
    if cleaned in ("code", "vscode", "visual studio code", "vs code"):
        return "vs code"
    if cleaned in ("google chrome", "chrome browser", "chrome"):
        return "chrome"
    if cleaned in ("microsoft edge", "ms edge", "edge browser", "edge"):
        return "edge"
    if cleaned in ("spotify music", "spotify app"):
        return "spotify"
    return cleaned


def find_windows_binary(candidate_list: List[str]) -> Optional[str]:
    """Locate the first available executable in PATH or standard directory paths."""
    for cand in candidate_list:
        if os.path.isabs(cand) and os.path.exists(cand):
            return cand
        resolved = shutil.which(cand)
        if resolved:
            return resolved
    return None


def resolve_executable(app_key: str) -> Optional[Tuple[str, Optional[List[str]]]]:
    """Resolve an application key to (display_name, command_args).

    If the application is supported but not found, command_args is None.
    If the application is completely unknown/unsupported, returns None.
    """
    system = CURRENT_SYSTEM
    norm_key = normalize_app_key(app_key)

    if system == "Windows":
        # Check standard Windows system tools
        if norm_key in WINDOWS_APP_WHITELIST:
            exe_name = WINDOWS_APP_WHITELIST[norm_key]
            return (norm_key.title(), [exe_name])

        # Check supported third-party applications
        if norm_key in THIRD_PARTY_CANDIDATES:
            binary = find_windows_binary(THIRD_PARTY_CANDIDATES[norm_key])
            display = "VS Code" if norm_key == "vs code" else norm_key.title()
            if binary:
                return (display, [binary])
            else:
                return (display, None)

        return None

    # Non-Windows fallback
    fallbacks = GENERIC_APP_FALLBACKS.get(system, {})
    cmd_name = fallbacks.get(norm_key)
    if not cmd_name:
        return None

    if system == "Darwin":
        return (norm_key.title(), ["open", "-a", cmd_name])
    return (norm_key.title(), [cmd_name])


def launch_application(app_name: str) -> Tuple[bool, str]:
    """Safely launch an authorized application from the whitelist.

    Returns:
        (success: bool, message: str)
    """
    resolved = resolve_executable(app_name)
    if not resolved:
        supported = ", ".join(get_supported_applications())
        return (
            False,
            f"'{app_name}' is not in my list of allowed applications. "
            f"Supported applications are: {supported}.",
        )

    display_name, cmd_args = resolved

    if cmd_args is None:
        return (
            False,
            f"{display_name} is not installed or could not be found on your computer.",
        )

    try:
        kwargs = {}
        if CURRENT_SYSTEM == "Windows":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            )

        subprocess.Popen(cmd_args, shell=False, **kwargs)
        return True, f"Opening {display_name}."

    except FileNotFoundError:
        return (
            False,
            f"Could not find the executable for {display_name} on your system.",
        )
    except PermissionError:
        return (
            False,
            f"Permission was denied when attempting to launch {display_name}.",
        )
    except Exception as exc:
        return (
            False,
            f"An error occurred while launching {display_name}: {exc}",
        )
