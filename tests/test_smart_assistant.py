"""Unit tests for upgraded Smart Assistant capabilities.

Tests:
- Volume adjustment (up, down, mute)
- Screenshot capture
- Safe folder creation and path security
- Music playback commands
- Shutdown and restart confirmation safeguards
- Offline AI knowledge base and safe math calculation
- Code explanation
- Extended application resolution (VS Code, Chrome, Edge)
"""

from __future__ import annotations

import pathlib
import pytest
from unittest.mock import MagicMock, patch

from assistant import ai_service, application_launcher, system_actions
from assistant.command_router import CommandRouter


@pytest.fixture
def router() -> CommandRouter:
    return CommandRouter()


class TestVolumeControl:
    """Test system volume intent routing and execution."""

    @patch("assistant.system_actions._send_virtual_key")
    def test_volume_up_command(self, mock_key: MagicMock, router: CommandRouter):
        result = router.route("increase volume")
        assert result.success is True
        assert "Volume increased" in result.response_text
        mock_key.assert_called_once_with(system_actions.VK_VOLUME_UP, times=5)

    @patch("assistant.system_actions._send_virtual_key")
    def test_volume_down_command(self, mock_key: MagicMock, router: CommandRouter):
        result = router.route("turn down volume")
        assert result.success is True
        assert "Volume decreased" in result.response_text
        mock_key.assert_called_once_with(system_actions.VK_VOLUME_DOWN, times=5)

    @patch("assistant.system_actions._send_virtual_key")
    def test_volume_mute_command(self, mock_key: MagicMock, router: CommandRouter):
        result = router.route("mute volume")
        assert result.success is True
        assert "mute toggled" in result.response_text
        mock_key.assert_called_once_with(system_actions.VK_VOLUME_MUTE, times=1)


class TestScreenshotAction:
    """Test screenshot capture intent routing and execution."""

    @patch("PIL.ImageGrab.grab")
    def test_take_screenshot(self, mock_grab: MagicMock, router: CommandRouter, tmp_path: pathlib.Path):
        fake_img = MagicMock()
        mock_grab.return_value = fake_img

        with patch("assistant.system_actions.get_screenshots_dir", return_value=tmp_path):
            result = router.route("take a screenshot")
            assert result.success is True
            assert "Screenshot captured and saved" in result.response_text
            assert result.spoken_text == "Screenshot captured."
            fake_img.save.assert_called_once()


class TestSafeFolderCreation:
    """Test folder creation with path validation and security."""

    def test_create_valid_folder(self, router: CommandRouter, tmp_path: pathlib.Path):
        with patch("assistant.system_actions.get_desktop_dir", return_value=tmp_path):
            result = router.route("create a folder named TestProject")
            assert result.success is True
            assert "successfully created folder 'testproject'" in result.response_text.lower()
            assert (tmp_path / "testproject").is_dir()

    def test_create_duplicate_folder_fails_safely(self, router: CommandRouter, tmp_path: pathlib.Path):
        existing = tmp_path / "existingfolder"
        existing.mkdir()
        with patch("assistant.system_actions.get_desktop_dir", return_value=tmp_path):
            result = router.route("create folder named existingfolder")
            assert result.success is False
            assert "already exists" in result.response_text

    def test_create_folder_with_illegal_characters_rejected(self, router: CommandRouter):
        result = router.route("create a folder named Invalid:Folder*Name?")
        assert result.success is False
        assert "illegal characters" in result.response_text

    def test_create_folder_with_traversal_rejected(self, router: CommandRouter):
        result = router.route("create a folder named ../../Escape")
        assert result.success is False
        assert "illegal characters" in result.response_text or "traversal" in result.response_text


class TestMusicPlayback:
    """Test music streaming requests."""

    @patch("webbrowser.open")
    def test_play_music_generic(self, mock_browser: MagicMock, router: CommandRouter):
        result = router.route("play music")
        assert result.success is True
        assert "Opening YouTube Music" in result.response_text
        mock_browser.assert_called_once_with("https://music.youtube.com")

    @patch("webbrowser.open")
    def test_play_music_specific_song(self, mock_browser: MagicMock, router: CommandRouter):
        result = router.route("play Bohemian Rhapsody")
        assert result.success is True
        assert "playing 'bohemian rhapsody'" in result.response_text.lower()
        mock_browser.assert_called_once()
        args, _ = mock_browser.call_args
        assert "bohemian+rhapsody" in args[0].lower()


class TestPowerSafeguards:
    """Test shutdown and restart confirmation requirements."""

    def test_shutdown_requires_confirmation(self, router: CommandRouter):
        # 1. User asks to shut down
        result1 = router.route("shutdown my computer")
        assert result1.success is True
        assert "Are you sure you want to shut down your computer" in result1.response_text
        assert router.pending_confirmation == "shutdown"

        # 2. User confirms
        with patch("assistant.system_actions.execute_shutdown", return_value=(True, "Countdown started")):
            result2 = router.route("yes confirm")
            assert result2.success is True
            assert router.pending_confirmation is None

    def test_shutdown_cancel(self, router: CommandRouter):
        router.route("shutdown my computer")
        assert router.pending_confirmation == "shutdown"

        result = router.route("cancel")
        assert result.success is True
        assert "cancelled" in result.response_text.lower()
        assert router.pending_confirmation is None

    def test_restart_requires_confirmation(self, router: CommandRouter):
        result1 = router.route("restart my computer")
        assert result1.success is True
        assert "Are you sure you want to restart" in result1.response_text
        assert router.pending_confirmation == "restart"

        with patch("assistant.system_actions.execute_restart", return_value=(True, "Restarting")):
            result2 = router.route("yes")
            assert result2.success is True
            assert router.pending_confirmation is None


class TestAIQuestionAnswering:
    """Test offline and local AI conversational responses."""

    def test_ai_definition_question(self, router: CommandRouter):
        result = router.route("what is artificial intelligence?")
        assert result.success is True
        assert result.action_type == "ai"
        assert "simulation of human intelligence" in result.response_text.lower()
        assert len(result.spoken_text) > 0
        assert len(result.spoken_text) < len(result.response_text)

    def test_math_calculation(self, router: CommandRouter):
        result = router.route("what is 25 * 4?")
        assert result.success is True
        assert "100" in result.response_text

    def test_code_explanation(self, router: CommandRouter):
        sample_code = "explain this code: def add(a, b): return a + b"
        result = router.route(sample_code)
        assert result.success is True
        assert "Function definitions: add" in result.response_text

    def test_conversational_chit_chat(self, router: CommandRouter):
        result = router.route("who created you?")
        assert result.success is True
        assert "Personal Voice Assistant" in result.response_text


class TestExtendedApplications:
    """Test discovery and resolution of extended apps (VS Code, Chrome, Edge)."""

    def test_vscode_launch_resolution(self):
        # On this machine VS Code is installed, so resolve_executable should succeed
        resolved = application_launcher.resolve_executable("vs code")
        assert resolved is not None
        display, cmd_args = resolved
        assert display == "VS Code"

    @patch("subprocess.Popen")
    def test_open_vscode_command(self, mock_popen: MagicMock, router: CommandRouter):
        with patch("assistant.application_launcher.resolve_executable", return_value=("VS Code", ["code.cmd"])):
            result = router.route("open vs code")
            assert result.success is True
            assert "Opening VS Code" in result.response_text
            mock_popen.assert_called_once()
