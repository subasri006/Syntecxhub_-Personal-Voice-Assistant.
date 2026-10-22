"""Unit Tests for Specialized Command Handlers with Mocking.

Validates non-hardware dependent behaviors: application launching,
browser opening, URL construction, time/date formatting, and error handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from assistant import application_launcher, command_handlers


class TestApplicationLauncherHandlers:
    """Test safe application execution with mocking."""

    @patch("subprocess.Popen")
    def test_launch_allowed_application(self, mock_popen: MagicMock):
        success, msg = application_launcher.launch_application("notepad")
        assert success is True
        assert "Opening Notepad" in msg
        mock_popen.assert_called()
        # Ensure shell=False is enforced
        args, kwargs = mock_popen.call_args
        assert args[0] == ["notepad.exe"]
        assert kwargs.get("shell") is False

    @patch("subprocess.Popen")
    def test_launch_calculator(self, mock_popen: MagicMock):
        success, msg = application_launcher.launch_application("calculator")
        assert success is True
        assert "Opening Calculator" in msg
        mock_popen.assert_called()
        args, kwargs = mock_popen.call_args
        assert args[0] == ["calc.exe"]
        assert kwargs.get("shell") is False

    def test_launch_disallowed_application(self):
        success, msg = application_launcher.launch_application("cmd.exe /c del system32")
        assert success is False
        assert "not in my list of allowed applications" in msg

    @patch("subprocess.Popen", side_effect=FileNotFoundError("Executable not found"))
    def test_launch_missing_executable_handles_gracefully(self, mock_popen: MagicMock):
        success, msg = application_launcher.launch_application("notepad")
        assert success is False
        assert "Could not find the executable" in msg


class TestWebBrowserHandlers:
    """Test browser shortcut and search query handling."""

    @patch("webbrowser.open")
    def test_open_youtube_shortcut(self, mock_browser: MagicMock):
        result = command_handlers.handle_open_website("youtube")
        assert result.success is True
        assert result.action_type == "browse"
        mock_browser.assert_called_once_with("https://www.youtube.com")

    @patch("webbrowser.open")
    def test_open_google_shortcut(self, mock_browser: MagicMock):
        result = command_handlers.handle_open_website("google")
        assert result.success is True
        mock_browser.assert_called_once_with("https://www.google.com")

    def test_open_unrecognized_website(self):
        result = command_handlers.handle_open_website("unknown_fake_site")
        assert result.success is False
        assert "is not recognized" in result.response_text

    @patch("webbrowser.open")
    def test_web_search_query(self, mock_browser: MagicMock):
        result = command_handlers.handle_web_search("Python tutorials for beginners")
        assert result.success is True
        assert result.action_type == "browse"
        expected_url = (
            "https://www.google.com/search?q=Python+tutorials+for+beginners"
        )
        mock_browser.assert_called_once_with(expected_url)

    def test_web_search_empty_query(self):
        result = command_handlers.handle_web_search("")
        assert result.success is False
        assert "Please specify what you would like me to search for" in result.response_text


class TestDateTimeFormatting:
    """Test date, time, and day format strings."""

    def test_time_returns_clean_string(self):
        result = command_handlers.handle_time()
        assert result.success is True
        assert "The current time is" in result.response_text
        # Verifies format like "9:45 PM" or "11:30 AM"
        assert any(meridiem in result.response_text for meridiem in ("AM", "PM"))

    def test_date_returns_full_format(self):
        result = command_handlers.handle_date()
        assert result.success is True
        assert "Today is" in result.response_text
        assert result.action_data is not None
        assert "date" in result.action_data

    def test_day_returns_day_of_week(self):
        result = command_handlers.handle_day_of_week()
        assert result.success is True
        assert "Today is" in result.response_text
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        assert any(d in result.response_text for d in days)


class TestSystemInfoHandlers:
    """Test safe system information queries."""

    def test_computer_name_handler(self):
        result = command_handlers.handle_computer_name()
        assert result.success is True
        assert "Your computer name is" in result.response_text

    def test_operating_system_handler(self):
        result = command_handlers.handle_operating_system()
        assert result.success is True
        assert "You are running" in result.response_text

    def test_disk_space_handler(self):
        result = command_handlers.handle_disk_space()
        assert result.success is True
        assert "Disk status:" in result.response_text
        assert "GB free" in result.response_text
