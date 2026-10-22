"""System Information Utility Module.

Provides safe, platform-aware methods to retrieve system status,
operating system details, disk space, and hardware usage without
executing arbitrary shell commands or revealing sensitive data.
"""

from __future__ import annotations

import os
import platform
import shutil
from typing import Dict, Any


def get_computer_name() -> str:
    """Return the hostname or computer name."""
    try:
        name = platform.node() or os.environ.get("COMPUTERNAME", "Unknown Device")
        return f"Your computer name is {name}."
    except Exception as exc:
        return f"Could not determine computer name: {exc}"


def get_os_info() -> str:
    """Return operating system name, release, and architecture."""
    try:
        os_name = platform.system()
        release = platform.release()
        version = platform.version()
        arch = platform.machine()
        return (
            f"You are running {os_name} {release} (Version: {version}, Architecture: {arch})."
        )
    except Exception as exc:
        return f"Could not determine operating system details: {exc}"


def get_disk_space(path: str = ".") -> str:
    """Return disk space usage (total, used, free) for the current drive."""
    try:
        usage = shutil.disk_usage(path)
        total_gb = usage.total / (1024**3)
        free_gb = usage.free / (1024**3)
        used_gb = usage.used / (1024**3)
        percent_free = (usage.free / usage.total) * 100 if usage.total > 0 else 0

        return (
            f"Disk status: {free_gb:.1f} GB free out of {total_gb:.1f} GB "
            f"({percent_free:.0f}% free, {used_gb:.1f} GB used)."
        )
    except Exception as exc:
        return f"Could not retrieve disk space information: {exc}"


def get_system_health() -> str:
    """Return CPU and Memory metrics if psutil is installed, otherwise basic info."""
    try:
        import psutil  # type: ignore

        cpu_pct = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory()
        ram_pct = ram.percent
        ram_avail_gb = ram.available / (1024**3)

        return (
            f"Current CPU usage is {cpu_pct}%. "
            f"Memory usage is {ram_pct}% ({ram_avail_gb:.1f} GB available)."
        )
    except ImportError:
        # Fallback if psutil is not available
        return get_disk_space()
    except Exception as exc:
        return f"Could not retrieve system metrics: {exc}"


def get_full_system_summary() -> Dict[str, Any]:
    """Return a dictionary of system summary info."""
    return {
        "computer_name": platform.node(),
        "os": f"{platform.system()} {platform.release()}",
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }
