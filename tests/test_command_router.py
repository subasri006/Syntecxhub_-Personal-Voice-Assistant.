"""Unit Tests for Command Router and Intent Parsing.

Validates normalization, regex pattern matching, aliases, search query extraction,
whitespace/case handling, and security protections against arbitrary commands.
"""

from __future__ import annotations

import pytest

from assistant.command_router import CommandRouter


@pytest.fixture
def router() -> CommandRouter:
    """Fixture providing an initialized CommandRouter instance."""
    return CommandRouter()


class TestTextNormalization:
    """Test text cleaning and normalization routines."""

    def test_empty_and_whitespace(self, router: CommandRouter):
        assert router.normalize_text("") == ""
        assert router.normalize_text("   ") == ""
        assert router.normalize_text("\n\t  ") == ""

    def test_case_insensitivity(self, router: CommandRouter):
        assert router.normalize_text("HELLO World") == "hello world"
        assert router.normalize_text("wHaT TiMe Is It") == "what time is it"

    def test_strip_punctuation(self, router: CommandRouter):
        assert router.normalize_text("what time is it???") == "what time is it"
        assert router.normalize_text('"open notepad!"') == "open notepad"
        assert router.normalize_text("hello assistant.") == "hello assistant"

    def test_collapses_consecutive_spaces(self, router: CommandRouter):
        assert router.normalize_text("  open     calculator   ") == "open calculator"


class TestGreetingCommands:
    """Test recognition of greeting intents."""

    @pytest.mark.parametrize(
        "phrase",
        [
            "hello",
            "HELLO",
            "  hi  ",
            "hi assistant",
            "hey",
            "good morning",
            "good afternoon",
            "good evening",
            "welcome assistant",
            "how are you?",
            "HOW ARE YOU",
            "how's it going assistant",
        ],
    )
    def test_greetings_matched(self, router: CommandRouter, phrase: str):
        result = router.route(phrase)
        assert result.success is True
        assert result.action_type == "speak"
        assert len(result.response_text) > 0


class TestDateTimeCommands:
    """Test matching date and time commands."""

    @pytest.mark.parametrize(
        "phrase",
        [
            "what time is it?",
            "what's the time",
            "whats the time",
            "tell me the time",
            "current time",
            "time please",
            "what time",
            "time",
            "tell time",
        ],
    )
    def test_time_command(self, router: CommandRouter, phrase: str):
        result = router.route(phrase)
        assert result.success is True
        assert "The current time is" in result.response_text
        assert "time" in result.action_data

    @pytest.mark.parametrize(
        "phrase",
        [
            "tell me today's date",
            "what is today's date?",
            "what's the date",
            "today's date",
            "current date",
            "what date",
            "date",
        ],
    )
    def test_date_command(self, router: CommandRouter, phrase: str):
        result = router.route(phrase)
        assert result.success is True
        assert "Today is" in result.response_text
        assert "date" in result.action_data

    @pytest.mark.parametrize(
        "phrase",
        [
            "what day is today?",
            "what day is it",
            "what day of the week is it",
            "what day",
            "day",
        ],
    )
    def test_day_command(self, router: CommandRouter, phrase: str):
        result = router.route(phrase)
        assert result.success is True
        assert "Today is" in result.response_text
        assert "day" in result.action_data


class TestWebSearchExtraction:
    """Test search query extraction from various voice phrasing patterns."""

    @pytest.mark.parametrize(
        "input_phrase, expected_query",
        [
            ("search google for Python tutorials", "Python tutorials"),
            ("search for machine learning projects", "machine learning projects"),
            ("find information about artificial intelligence", "artificial intelligence"),
            ("google search for deep learning", "deep learning"),
            ("search quantum computing", "quantum computing"),
            ("find nearest coffee shop", "nearest coffee shop"),
        ],
    )
    def test_search_query_extracted(
        self, router: CommandRouter, input_phrase: str, expected_query: str
    ):
        result = router.route(input_phrase)
        assert result.success is True
        assert result.action_type == "browse"
        assert result.action_data is not None
        assert result.action_data["query"].lower() == expected_query.lower()
        assert "https://www.google.com/search?q=" in result.action_data["url"]


class TestBrowserNavigation:
    """Test direct web shortcut commands."""

    @pytest.mark.parametrize(
        "phrase, expected_domain",
        [
            ("open google", "google.com"),
            ("open youtube", "youtube.com"),
            ("open gmail", "mail.google.com"),
            ("open github", "github.com"),
            ("open chatgpt", "chatgpt.com"),
            ("go to wikipedia", "wikipedia.org"),
        ],
    )
    def test_website_shortcuts(
        self, router: CommandRouter, phrase: str, expected_domain: str
    ):
        result = router.route(phrase)
        assert result.success is True
        assert result.action_type == "browse"
        assert expected_domain in result.action_data["url"]


class TestApplicationWhitelistAndSecurity:
    """Test application launch patterns and security whitelist enforcement."""

    @pytest.mark.parametrize(
        "phrase, canonical_app",
        [
            ("open notepad", "notepad"),
            ("launch calculator", "calculator"),
            ("open paint", "paint"),
            ("start file explorer", "file explorer"),
            ("open command prompt", "command prompt"),
            ("open task manager", "task manager"),
            ("open control panel", "control panel"),
        ],
    )
    def test_supported_applications_matched(
        self, router: CommandRouter, phrase: str, canonical_app: str
    ):
        result = router.route(phrase)
        assert result.action_type == "launch"
        assert result.action_data["application"].lower() == canonical_app

    @pytest.mark.parametrize(
        "unsupported_phrase",
        [
            "open malicious_trojan",
            "open random_unknown_software",
            "open games.exe",
        ],
    )
    def test_unsupported_applications_rejected(
        self, router: CommandRouter, unsupported_phrase: str
    ):
        result = router.route(unsupported_phrase)
        assert result.action_type == "launch"
        assert result.success is False
        assert "not in my list of allowed applications" in result.response_text

    @pytest.mark.parametrize(
        "malicious_injection",
        [
            "open notepad & calc.exe",
            "open notepad; rm -rf /",
            "open notepad && whoami",
            "open notepad | powershell",
            "open notepad > file.txt",
        ],
    )
    def test_shell_injection_safely_neutralized(
        self, router: CommandRouter, malicious_injection: str
    ):
        # Router should either treat as unknown or pass as literal string to application launcher
        # which rejects non-whitelisted strings without shell=True
        result = router.route(malicious_injection)
        # If it reached launcher, it must NOT succeed
        if result.action_type == "launch":
            assert result.success is False
            assert "not in my list of allowed applications" in result.response_text
        else:
            # Or router handled as unknown command
            assert "didn't understand" in result.response_text.lower()


class TestSystemUtilities:
    """Test system query commands."""

    def test_computer_name(self, router: CommandRouter):
        result = router.route("what is my computer name?")
        assert result.success is True
        assert result.action_type == "info"
        assert "computer name is" in result.response_text

    def test_operating_system(self, router: CommandRouter):
        result = router.route("show my operating system")
        assert result.success is True
        assert result.action_type == "info"
        assert "running" in result.response_text

    def test_disk_space(self, router: CommandRouter):
        result = router.route("how much disk space is available?")
        assert result.success is True
        assert result.action_type == "info"
        assert "Disk status:" in result.response_text


class TestAssistantControls:
    """Test assistant control commands."""

    def test_stop_listening(self, router: CommandRouter):
        result = router.route("stop listening")
        assert result.action_type == "control"
        assert result.action_data["control"] == "stop_listening"

    def test_go_to_sleep(self, router: CommandRouter):
        result = router.route("go to sleep")
        assert result.action_type == "control"
        assert result.action_data["control"] == "sleep"

    def test_wake_up(self, router: CommandRouter):
        result = router.route("wake up")
        assert result.action_type == "control"
        assert result.action_data["control"] == "wake_up"

    def test_help(self, router: CommandRouter):
        result = router.route("help")
        assert result.action_type == "info"
        assert "Here are commands you can say or type" in result.response_text

    def test_exit(self, router: CommandRouter):
        result = router.route("exit assistant")
        assert result.action_type == "control"
        assert result.action_data["control"] == "exit"


class TestUnknownAndEdgeCases:
    """Test empty input and unknown command fallback."""

    def test_empty_string(self, router: CommandRouter):
        result = router.route("")
        assert result.success is False
        assert "didn't hear anything" in result.response_text

    def test_gibberish_unknown(self, router: CommandRouter):
        result = router.route("abracadabra flim flam 12345")
        assert result.success is False
        assert "didn't understand that command" in result.response_text
        assert "unrecognized_input" in result.action_data


class TestWakeWordExtraction:
    """Test wake word detection and parsing."""

    def test_wake_word_only(self):
        detected, remainder = CommandRouter.extract_wake_word("hey assistant", "hey assistant")
        assert detected is True
        assert remainder == ""

    def test_wake_word_with_command(self):
        detected, remainder = CommandRouter.extract_wake_word(
            "hey assistant what time is it?", "hey assistant"
        )
        assert detected is True
        assert remainder == "what time is it"

    def test_wake_word_not_present(self):
        detected, remainder = CommandRouter.extract_wake_word(
            "what time is it?", "hey assistant"
        )
        assert detected is False


class TestPastedTerminalCommandHandling:
    """Test forgiving extraction of commands from accidentally pasted CLI snippets."""

    def test_pasted_powershell_pipe_snippet(self, router: CommandRouter):
        pasted = '"hello`nwhat time is it`nhow much disk space is available`nwhat is my computer name`nexit" | .\\.venv\\Scripts\\python.exe main.py --cli'
        result = router.route(pasted)
        assert result.success is True
        assert "I noticed you pasted a terminal command" in result.response_text
        assert "The current time is" in result.response_text
        assert "Tip:" in result.response_text
