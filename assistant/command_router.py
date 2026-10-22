"""Modular Rule-Based & AI-Augmented Command Router.

Parses, normalizes, and dispatches voice and text inputs to appropriate
handlers using pattern matching, regex, intent classifiers, desktop automation,
and generative AI fallbacks. Guarantees safe execution without shell injection.
"""

from __future__ import annotations

import re
import string
from typing import Callable, List, Optional, Pattern, Tuple

from assistant.command_handlers import (
    CommandResult,
    handle_ai_question,
    handle_computer_name,
    handle_create_folder,
    handle_date,
    handle_day_of_week,
    handle_disk_space,
    handle_exit,
    handle_go_to_sleep,
    handle_greeting,
    handle_help,
    handle_how_are_you,
    handle_open_application,
    handle_open_website,
    handle_operating_system,
    handle_play_music,
    handle_restart_confirm,
    handle_restart_request,
    handle_screenshot,
    handle_shutdown_cancel,
    handle_shutdown_confirm,
    handle_shutdown_request,
    handle_stop_listening,
    handle_system_status,
    handle_time,
    handle_unknown_command,
    handle_volume,
    handle_wake_up,
    handle_web_search,
)


class CommandRule:
    """Represents a rule associating regex patterns with a handler function."""

    def __init__(
        self,
        patterns: List[str],
        handler: Callable[..., CommandResult],
        name: str,
        extract_groups: bool = False,
    ):
        self.patterns: List[Pattern[str]] = [
            re.compile(p, re.IGNORECASE) for p in patterns
        ]
        self.handler = handler
        self.name = name
        self.extract_groups = extract_groups

    def match(self, text: str) -> Optional[Tuple[Callable[..., CommandResult], Tuple[str, ...]]]:
        """Test text against all patterns in this rule."""
        for pattern in self.patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups() if self.extract_groups else ()
                return self.handler, groups
        return None


class CommandRouter:
    """Dispatches normalized user commands to safe execution handlers or AI engine."""

    def __init__(self):
        self.rules: List[CommandRule] = []
        self.pending_confirmation: Optional[str] = None
        self._register_default_rules()

    @staticmethod
    def normalize_text(text: str) -> str:
        """Clean and normalize raw speech or typed input.

        Converts to lowercase, removes excessive whitespace and terminal punctuation.
        """
        if not text:
            return ""

        cleaned = " ".join(text.strip().split())
        cleaned = cleaned.lower()
        cleaned = cleaned.strip("\"'.,?!;:~")
        return cleaned

    @staticmethod
    def extract_wake_word(
        raw_text: str, wake_word: str = "hey assistant"
    ) -> Tuple[bool, str]:
        """Check if the text starts with or contains the wake word.

        Returns (wake_word_detected, remaining_command).
        """
        normalized_input = CommandRouter.normalize_text(raw_text)
        normalized_wake = CommandRouter.normalize_text(wake_word)

        if not normalized_wake:
            return True, normalized_input

        wake_variants = [normalized_wake]
        if " " in normalized_wake:
            parts = normalized_wake.split()
            wake_variants.append(parts[-1])

        for variant in wake_variants:
            if normalized_input == variant:
                return True, ""
            pattern = rf"^{re.escape(variant)}\b[\s,:]*(.*)$"
            match = re.match(pattern, normalized_input, re.IGNORECASE)
            if match:
                return True, match.group(1).strip()

        return False, normalized_input

    def _register_default_rules(self) -> None:
        """Register built-in command patterns and handlers."""

        # 1. Greetings
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(hello|hi|hey|good morning|good afternoon|good evening|howdy|sup)( assistant)?$",
                    r"^(greetings|welcome assistant)$",
                ],
                handler=handle_greeting,
                name="greeting",
            )
        )

        # 2. How are you
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(how are you( doing)?|how('s|s) it going|what('s|s) up)( assistant)?$",
                ],
                handler=handle_how_are_you,
                name="how_are_you",
            )
        )

        # 3. Date & Time
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(what time is it|what('s|s) the time|tell me (the |what )?time( it is)?|current time|time please|do you have the time)$",
                    r"^(what time|tell time|time now|the time|clock|^time$)$",
                    r"^what is the time$",
                ],
                handler=handle_time,
                name="time",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(tell me today('s|s) date|what('s|s| is) (today('s|s)|the) date|today('s|s) date|current date|what date is it)$",
                    r"^(what date|what is the date|date today|tell date|^date$)$",
                ],
                handler=handle_date,
                name="date",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(what day is today|what day is it|what day of the week is it|which day is today)$",
                    r"^(what day|day of week|day today|^day$)$",
                ],
                handler=handle_day_of_week,
                name="day_of_week",
            )
        )

        # 4. System Actions: Volume Control
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:increase volume|raise volume|volume up|turn up (?:the )?volume|louder|boost volume)$",
                ],
                handler=lambda: handle_volume("up"),
                name="volume_up",
            )
        )
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:decrease volume|lower volume|volume down|turn down (?:the )?volume|softer|reduce volume)$",
                ],
                handler=lambda: handle_volume("down"),
                name="volume_down",
            )
        )
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:mute volume|mute sound|mute audio|^mute$|^unmute$|toggle mute)$",
                ],
                handler=lambda: handle_volume("mute"),
                name="volume_mute",
            )
        )

        # 5. System Actions: Screenshot
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:take (?:a )?screenshot|capture (?:the )?screen|capture screenshot|^screenshot$)$",
                ],
                handler=handle_screenshot,
                name="screenshot",
            )
        )

        # 6. System Actions: Safe Folder Creation
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:create|make)(?: a)? folder (?:named|called)\s+(.+)$",
                    r"^(?:create|make)(?: a)? (?:new )?folder\s+(.+)$",
                    r"^(?:create|make)(?: a)? directory (?:named|called)?\s+(.+)$",
                ],
                handler=handle_create_folder,
                name="create_folder",
                extract_groups=True,
            )
        )

        # 7. Media: Music Playback
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:play (?:some )?music|play (?:a )?song|play songs|start music)$",
                ],
                handler=lambda: handle_play_music(None),
                name="play_music_generic",
            )
        )
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^play\s+(.+)$",
                ],
                handler=handle_play_music,
                name="play_music_query",
                extract_groups=True,
            )
        )

        # 8. System Actions: Shutdown & Restart Safeguards
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:shutdown (?:my )?computer|turn off (?:my )?computer|turn off (?:my )?pc|shutdown (?:my )?pc|shut down)$",
                ],
                handler=self._trigger_shutdown_request,
                name="shutdown_request",
            )
        )
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:restart (?:my )?computer|reboot (?:my )?computer|restart (?:my )?pc|reboot)$",
                ],
                handler=self._trigger_restart_request,
                name="restart_request",
            )
        )
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:cancel shutdown|abort shutdown|stop shutdown|cancel restart)$",
                ],
                handler=self._trigger_shutdown_cancel,
                name="shutdown_cancel",
            )
        )

        # 9. Web Browser Shortcuts (e.g., "open youtube", "open google")
        known_sites = "google|youtube|gmail|github|chatgpt|wikipedia|reddit|stackoverflow|music|spotify"
        self.rules.append(
            CommandRule(
                patterns=[
                    rf"^(?:open|go to|launch|visit)\s+({known_sites})(?:\.com|\.org)?$",
                    rf"^({known_sites})(?:\.com|\.org)?$",
                ],
                handler=handle_open_website,
                name="open_website",
                extract_groups=True,
            )
        )

        # 10. Direct application shortcuts without 'open' (e.g., "calculator", "notepad", "vs code")
        direct_apps = (
            "notepad|calculator|calc|paint|file explorer|explorer|command prompt|cmd|"
            "task manager|control panel|vs code|vscode|code|chrome|edge|spotify"
        )
        self.rules.append(
            CommandRule(
                patterns=[
                    rf"^({direct_apps})$",
                ],
                handler=handle_open_application,
                name="direct_open_application",
                extract_groups=True,
            )
        )

        # 11. General Application Launchers (e.g., "open notepad", "open calculator", "open vs code")
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:open|launch|start|run)\s+(?:the\s+)?([a-zA-Z0-9\s._\-]{2,50})$",
                ],
                handler=handle_open_application,
                name="open_application",
                extract_groups=True,
            )
        )

        # 12. Web Searches
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:search google for|search for|google search for|find information about|find info about|look up for)\s+(.+)$",
                    r"^(?:search|google|find|look up)\s+(.+)$",
                ],
                handler=handle_web_search,
                name="web_search",
                extract_groups=True,
            )
        )

        # 13. System Utilities
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:what('s|s| is) (?:my )?computer name|show (?:my )?computer name|computer name|pc name|my pc|hostname|^computer$)$",
                ],
                handler=handle_computer_name,
                name="computer_name",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:show (?:my )?operating system|what('s|s| is) (?:my )?operating system|what('s|s| is) my os|operating system|show os|what os am i running|os version|windows version|^os$)$",
                ],
                handler=handle_operating_system,
                name="operating_system",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:how much (?:disk )?space is available|check disk space|disk space|storage available|available disk space|how much storage do i have|storage space|disk usage|free space|^disk$|^storage$)$",
                ],
                handler=handle_disk_space,
                name="disk_space",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:system status|system health|cpu usage|memory usage|ram usage|how is the system doing|cpu|ram|system info)$",
                ],
                handler=handle_system_status,
                name="system_status",
            )
        )

        # 14. Assistant Controls
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:stop listening|stop voice|mute microphone|stop recording|pause listening|^stop$)$",
                ],
                handler=handle_stop_listening,
                name="stop_listening",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:go to sleep|sleep mode|sleep assistant|^sleep$)$",
                ],
                handler=handle_go_to_sleep,
                name="go_to_sleep",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:wake up|wake assistant|^wake$)$",
                ],
                handler=handle_wake_up,
                name="wake_up",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:help|show available commands|what can you do|commands|show help|list commands|options|menu)$",
                ],
                handler=handle_help,
                name="help",
            )
        )

        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:exit assistant|quit assistant|close assistant|exit|quit|goodbye|bye|shutdown assistant)$",
                ],
                handler=handle_exit,
                name="exit",
            )
        )

        # 15. Explicit AI Code Explanation & Questions
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:explain this code|explain code|explain the code)(?::|\s+)?([\s\S]*)$",
                ],
                handler=handle_ai_question,
                name="explain_code",
                extract_groups=True,
            )
        )
        self.rules.append(
            CommandRule(
                patterns=[
                    r"^(?:what is|what are|explain|who is|who are|tell me about|how does|why is|calculate|compute)\s+(.+)$",
                ],
                handler=handle_ai_question,
                name="general_ai_question",
                extract_groups=True,
            )
        )

    def _trigger_shutdown_request(self) -> CommandResult:
        """Trigger shutdown confirmation state."""
        self.pending_confirmation = "shutdown"
        return handle_shutdown_request()

    def _trigger_restart_request(self) -> CommandResult:
        """Trigger restart confirmation state."""
        self.pending_confirmation = "restart"
        return handle_restart_request()

    def _trigger_shutdown_cancel(self) -> CommandResult:
        """Cancel any pending shutdown or restart."""
        self.pending_confirmation = None
        return handle_shutdown_cancel()

    def _handle_pasted_terminal_command(self, raw_input: str) -> Optional[CommandResult]:
        r"""Detect and execute user commands when someone accidentally pastes terminal syntax.

        E.g.: '"hello`nwhat time is it`nhow much disk space..." | .\.venv\Scripts\python.exe main.py --cli'
        """
        if "`n" in raw_input or "\\n" in raw_input or "main.py" in raw_input or "|" in raw_input:
            quote_match = re.search(r'"([^"]+)"', raw_input)
            payload = quote_match.group(1) if quote_match else raw_input

            payload = re.split(r"\|\s*\.?\\?\.venv", payload, flags=re.IGNORECASE)[0]
            payload = re.split(r"\|\s*python", payload, flags=re.IGNORECASE)[0]

            raw_cmds = re.split(r"`n|\\n|\n|;", payload)
            valid_cmds = [c.strip() for c in raw_cmds if c.strip() and not c.strip().startswith("-")]

            if valid_cmds:
                results_text = []
                for cmd in valid_cmds[:4]:
                    res = self._route_single(cmd)
                    if res and res.success:
                        results_text.append(f"• '{cmd}': {res.response_text}")

                if results_text:
                    combined = (
                        "I noticed you pasted a terminal command! Here are the results for the commands inside:\n"
                        + "\n".join(results_text)
                        + "\n\nTip: You don't need to type terminal commands! You can simply speak or type normal commands directly like 'what time', 'open calculator', or 'hello'!"
                    )
                    return CommandResult(
                        success=True,
                        response_text=combined,
                        action_type="speak",
                        spoken_text="I executed the commands inside your pasted snippet.",
                    )
        return None

    def _route_single(self, text: str) -> CommandResult:
        """Internal helper to match a single normalized command."""
        normalized = self.normalize_text(text)
        if not normalized:
            return CommandResult(
                success=False,
                response_text="I didn't hear anything. Please try speaking again or type your command.",
                action_type="speak",
                should_speak=False,
            )

        # Check pending power confirmations
        if self.pending_confirmation:
            if normalized in ("yes confirm", "yes", "confirm", "proceed", "do it"):
                action = self.pending_confirmation
                self.pending_confirmation = None
                if action == "shutdown":
                    return handle_shutdown_confirm()
                elif action == "restart":
                    return handle_restart_confirm()
            elif normalized in ("no", "cancel", "abort", "don't", "stop"):
                self.pending_confirmation = None
                return handle_shutdown_cancel()

        for rule in self.rules:
            matched = rule.match(normalized)
            if matched:
                handler, groups = matched
                if groups:
                    return handler(*groups)
                return handler()

        # No direct rule matched -> route through unknown/AI fallback
        return handle_unknown_command(text)

    def route(self, raw_input: str) -> CommandResult:
        """Route user voice or text input to the matching command handler.

        Returns a CommandResult instance.
        """
        pasted_res = self._handle_pasted_terminal_command(raw_input)
        if pasted_res:
            return pasted_res

        return self._route_single(raw_input)
