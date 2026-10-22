# Personal Voice Assistant 🎙️

A complete, modern, desktop-based Personal Voice Assistant application built from scratch with Python, CustomTkinter, SpeechRecognition, and offline pyttsx3.

Designed specifically for Windows 10 and Windows 11 with a modern dark theme, real-time audio visualization feedback, safe system automation, and strict whitelist validation against arbitrary command execution.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Key Features](#key-features)
3. [Architecture and Design](#architecture-and-design)
4. [Supported Voice & Text Commands](#supported-voice--text-commands)
5. [Online vs. Offline Capabilities](#online-vs-offline-capabilities)
6. [Security & Safety Architecture](#security--safety-architecture)
7. [System Requirements](#system-requirements)
8. [Setup and Installation Guide (Windows PowerShell)](#setup-and-installation-guide-windows-powershell)
9. [How to Launch the Application](#how-to-launch-the-application)
10. [Troubleshooting Guide (PyAudio, Microphone, Windows Permissions)](#troubleshooting-guide)
11. [Automated Testing](#automated-testing)
12. [Project Structure](#project-structure)

---

## Project Overview

**Personal Voice Assistant** is an offline-capable, privacy-respecting AI assistant for Windows desktops. It captures user voice input through the microphone, normalizes and routes commands using a modular rule-based engine, triggers safe desktop actions, and replies with natural, localized text-to-speech.

Unlike cloud assistants that charge fees or collect recordings, this assistant prioritizes free libraries, zero subscription requirements, offline speech synthesis, and local execution.

---

## Key Features

- **Modern Dark-Themed Desktop GUI**:
  - Built with `CustomTkinter` featuring rounded cards, status pills, and high-DPI scaling.
  - Large interactive microphone button with state-aware color feedback:
    - 🟢 **Green**: Actively listening to microphone audio.
    - 🔵 **Cyan**: Processing and recognizing speech.
    - 🟣 **Purple**: Speaking response via offline TTS.
    - 🟠 **Orange**: Calibrating ambient noise.
    - ⚪ **Gray**: Idle and awaiting input.
  - Live digital clock and system date banner.
  - Scrollable chat history with distinct message bubbles and timestamps for User and Assistant.
  - Instant one-click example command chips.
  - Fallback text input entry with Enter-key dispatch (works 100% offline).
- **Voice Activation Modes**:
  - **Push-to-Talk / One-Shot Mode**: Click Start Listening (or the microphone button) for single-command recognition.
  - **Hands-Free Continuous Mode**: Toggle continuous listening for ongoing hands-free interaction.
  - **Wake Word Activation**: Optional customizable wake word (default: `"Hey Assistant"` or `"Assistant"`).
  - **Sleep Mode**: Put the assistant to sleep (`"go to sleep"`) and reactivate at any time (`"wake up"`).
- **Offline Text-to-Speech (TTS)**:
  - Powered by `pyttsx3` using Windows SAPI5 offline voices (e.g. Microsoft David, Microsoft Zira).
  - Real-time sliders for speaking rate (100–280 wpm) and volume (0–100%).
  - Voice selection combobox populated with all installed system voices.
  - **Echo/Loop Prevention**: Automatically mutes speech recognition while the assistant speaks so it never recognizes its own voice.
- **Robust Speech Recognition**:
  - SpeechRecognition library with automatic background noise calibration (`adjust_for_ambient_noise`).
  - Configurable recognition timeout and phrase limits.
  - Clean error handling for unintelligible audio or missing internet connectivity without application crashes.
- **Strict Safety Sandbox**:
  - Whitelist-only application execution (Notepad, Calculator, Paint, File Explorer, Command Prompt, Task Manager, Control Panel).
  - Explicit URL scheme validation and sanitized search query URL encoding.
  - Zero execution of arbitrary shell strings (`shell=False` enforced across all subprocess invocations).

---

## Architecture and Design

The application follows an asynchronous, thread-safe, modular Model-View-Controller (MVC) architecture:

```
                            ┌─────────────────────────────────┐
                            │    User Voice / Text Input      │
                            └────────────────┬────────────────┘
                                             │
                                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 AssistantController                                    │
│   ┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐   │
│   │ SpeechRecognitionService│  │     CommandRouter      │  │  TextToSpeechService   │   │
│   │  (PyAudio + Google STT)│  │ (Rule-Based Normalizer)│  │ (Offline pyttsx3/SAPI5)│   │
│   └───────────┬────────────┘  └───────────┬────────────┘  └───────────┬────────────┘   │
└───────────────┼───────────────────────────┼───────────────────────────┼────────────────┘
                │                           │                           │
                ▼                           ▼                           ▼
        ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
        │  Microphone   │           │   Handlers:   │           │ Audio Speaker │
        │ (Listen Loop) │           │ - AppLauncher │           │ (TTS Thread)  │
        └───────────────┘           │ - Web/Search  │           └───────────────┘
                                    │ - System Info │
                                    │ - Controls    │
                                    └───────┬───────┘
                                            │
                                            ▼
                        ┌───────────────────────────────────────┐
                        │        Thread-Safe GUI Queue          │
                        └───────────────────┬───────────────────┘
                                            │
                                            ▼
                        ┌───────────────────────────────────────┐
                        │        MainWindow (CustomTkinter)     │
                        │ - Chat Bubbles  - Dynamic Status Pill │
                        │ - Mic Ring      - Controls & Settings │
                        └───────────────────────────────────────┘
```

1. **`assistant/speech_recognition_service.py`**: Runs a dedicated daemon worker thread for audio capture and recognition. Coordinates with TTS to avoid acoustic feedback loops.
2. **`assistant/text_to_speech.py`**: Runs a dedicated daemon worker thread with a FIFO queue for serialized Windows SAPI5 COM calls.
3. **`assistant/command_router.py`**: Normalizes input, strips trailing punctuation, isolates wake words, and matches regex patterns against registered intent rules.
4. **`assistant/command_handlers.py`**: Implements safe execution routines, returning structured `CommandResult` instances.
5. **`assistant/application_launcher.py`**: Enforces strict application whitelisting and invokes system tools via `subprocess.Popen([exe], shell=False)`.
6. **`assistant/system_info.py`**: Safe system queries using `platform`, `shutil`, and `psutil`.
7. **`gui/main_window.py`**: Thread-safe UI polling via `self.after()` and an internal queue, preventing Tkinter race conditions.

---

## Supported Voice & Text Commands

All commands can be spoken through the microphone or typed into the bottom text entry box:

### A. Greetings & Conversation
- `"Hello"` / `"Hi assistant"` / `"Hey"`
- `"Good morning"` / `"Good afternoon"` / `"Good evening"`
- `"How are you?"` / `"How are you doing?"`

### B. Date & Time
- `"What time is it?"` / `"Tell me the time"` / `"Current time"`
- `"Tell me today's date"` / `"What is the date?"` / `"What's today's date?"`
- `"What day is today?"` / `"What day of the week is it?"`

### C. Open Applications (Strict Whitelist)
- `"Open Notepad"` (or `"Launch Notepad"`)
- `"Open Calculator"` (or `"Open Calc"`)
- `"Open Paint"`
- `"Open File Explorer"` (or `"Open Explorer"`)
- `"Open Command Prompt"` (or `"Open CMD"`)
- `"Open Task Manager"`
- `"Open Control Panel"`

### D. Web Browser Shortcuts
- `"Open Google"`
- `"Open YouTube"`
- `"Open Gmail"`
- `"Open GitHub"`
- `"Open ChatGPT"`
- `"Open Wikipedia"`
- `"Open Reddit"`
- `"Open StackOverflow"`

### E. Web Search
- `"Search for Python tutorials"`
- `"Search Google for machine learning projects"`
- `"Find information about artificial intelligence"`
- `"Google quantum computing"`

### F. System Utilities
- `"What is my computer name?"` / `"Hostname"`
- `"Show my operating system"` / `"What OS am I running?"`
- `"How much disk space is available?"` / `"Check disk space"`
- `"System status"` / `"CPU usage"`

### G. Assistant Controls
- `"Stop listening"` / `"Pause listening"`
- `"Go to sleep"`
- `"Wake up"`
- `"Help"` / `"Show available commands"`
- `"Exit assistant"` / `"Quit assistant"`

### H. Unknown / Unsupported Commands
- If a command is not recognized, the assistant responds:
  *"Sorry, I didn't understand that command. You can say 'What time is it?', 'Open Calculator', 'Search for Python tutorials', or say 'Help' to see all available commands."*

---

## Online vs. Offline Capabilities

| Feature | Online Required? | Engine / Backend | Behavior If Offline |
| :--- | :---: | :---: | :--- |
| **Text-to-Speech (Voice Output)** | ❌ **No** | pyttsx3 (Windows SAPI5) | Works 100% offline with zero latency. |
| **Typed Commands** | ❌ **No** | Local Python Command Router | Works 100% offline. |
| **Application Launching** | ❌ **No** | Local Windows System32 | Works 100% offline. |
| **Date, Time & Day** | ❌ **No** | Local Python `datetime` | Works 100% offline. |
| **Disk Space & OS Info** | ❌ **No** | Local `platform`, `shutil`, `psutil` | Works 100% offline. |
| **Speech Recognition** | ⚠️ **Yes** | SpeechRecognition (Google API) | Requires an internet connection. If offline, notifies the user gracefully while typed commands remain functional. |
| **Web Browser Navigation** | ⚠️ **Yes** | System Web Browser | Requires internet to load external websites. |
| **Web Search** | ⚠️ **Yes** | Google Search in Browser | Requires internet to view search results. |

> [!NOTE]
> Speech recognition uses Google's free recognition service via SpeechRecognition, which requires an active internet connection. If your connection drops, the assistant remains fully usable via typed commands, offline TTS, and local system automation.

---

## Security & Safety Architecture

1. **No Arbitrary Shell Execution**: The application will **never** execute arbitrary user voice input in a shell. Commands are never passed to `eval()`, `exec()`, `os.system()`, or `subprocess.Popen(..., shell=True)`.
2. **Whitelist-Enforced App Launcher**: Only explicitly authorized desktop applications (`notepad.exe`, `calc.exe`, `mspaint.exe`, `explorer.exe`, `cmd.exe`, `taskmgr.exe`, `control.exe`) can be launched. Any unauthorized program (e.g. `open malicious.bat`) is rejected with a polite message.
3. **Shell Injection Sanitization**: Input strings containing command separators (`;`, `&`, `|`, `>`, `<`) are sanitized or treated as literal non-matching text.
4. **URL & Query Sanitization**: Web searches sanitize control characters, limit query length to 200 characters, and encode parameters with `urllib.parse.quote_plus`.
5. **Privacy Safeguard**: The application does not write audio recordings to disk. Microphone audio is kept in volatile memory for the duration of recognition and immediately discarded.
6. **Graceful Exit Confirmation**: Application exit requests require confirmation to prevent accidental shutdown.

---

## System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit recommended)
- **Python**: Python 3.11 or higher
- **Audio Hardware**: Working microphone (built-in or USB headset) and audio output device (speakers or headphones)
- **Network**: Internet connection for speech-to-text recognition and web searches

---

## Setup and Installation Guide (Windows PowerShell)

Open **PowerShell** in the project directory (`Personal Voice Assistant`) and run:

```powershell
# 1. Create a Python virtual environment
python -m venv .venv

# 2. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# If PowerShell displays an execution policy error, enable local script execution for the current session:
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

# 3. Upgrade pip to latest version
python -m pip install --upgrade pip

# 4. Install all dependencies
pip install -r requirements.txt
```

---

## How to Launch the Application

### 1. Launch the Modern Desktop GUI (Default)

```powershell
# With virtual environment activated:
python main.py
```

Optional CLI flags:
- `--rate <int>`: Set initial speech rate in words per minute (e.g., `python main.py --rate 180`).
- `--volume <float>`: Set initial speech volume from 0.0 to 1.0 (e.g., `python main.py --volume 0.85`).
- `--wake-word "<phrase>"`: Set initial wake word (e.g., `python main.py --wake-word "hey assistant"`).

### 2. Launch in Headless Command-Line Mode (CLI)

For environments without a graphical display or quick testing:

```powershell
python main.py --cli
```

---

## Troubleshooting Guide

### 1. PyAudio Installation on Windows

If `pip install pyaudio` fails with compilation or wheel errors:
- **Python 3.11**: Official prebuilt PyAudio wheels exist on PyPI (`pip install pyaudio` installs `PyAudio-0.2.14-cp311-win_amd64.whl` automatically).
- If using another Python version where compilation is attempted:
  ```powershell
  pip install pipwin
  pipwin install pyaudio
  ```
  Or download the matching `.whl` file from [Gohlke's Python Unofficial Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio) and run:
  ```powershell
  pip install <downloaded_wheel_file>.whl
  ```

### 2. Microphone Permissions on Windows 10 & 11

If the assistant fails to hear audio or indicates a microphone error:
1. Open Windows **Settings** (`Win + I`).
2. Navigate to **Privacy & Security** > **Microphone**.
3. Ensure **Microphone access** is turned **On**.
4. Ensure **Let desktop apps access your microphone** is turned **On**.
5. Verify in **Sound Settings** that your preferred microphone is set as the **Default input device**.

### 3. Ambient Noise Calibration

If speech is not being recognized properly in a noisy room:
1. Click the **"Calibrate Ambient Noise"** button in the sidebar.
2. Remain silent for 1 second while the microphone samples background noise levels.
3. The recognizer will automatically adjust its dynamic energy threshold.

### 4. Text-to-Speech (pyttsx3) Initialization

If TTS produces no audio:
- Verify that your speakers or headphones are not muted.
- Ensure the Windows **Windows Audio** service is running.
- In the assistant sidebar, test different voices using the **"Selected Voice"** combobox.

---

## Automated Testing

The project includes an automated test suite with 84 unit tests covering:
- Text normalization, casing, and punctuation stripping.
- Greeting intent classification and contextual responses.
- Local date, time, and day-of-week formatting.
- Safe application whitelist matching and rejection of unauthorized apps.
- Shell injection attack prevention.
- Web browser shortcuts and Google search query extraction.
- System information retrieval.
- Wake word extraction.
- Mocking of subprocesses, web browsers, and hardware drivers.

To run the automated tests:

```powershell
.\.venv\Scripts\pytest -v
```

Expected output:
```
============================= 84 passed in 5.73s ==============================
```

---

## Project Structure

```
Personal Voice Assistant/
├── .gitignore                      # Git ignore patterns for venv, pycache, OS files
├── requirements.txt                # Pinned production dependencies
├── README.md                       # Comprehensive documentation & user guide
├── main.py                         # Application entrypoint (GUI and CLI modes)
│
├── assistant/                      # Core Assistant Engine
│   ├── __init__.py                 # Assistant package definition
│   ├── speech_recognition_service.py # Audio capture, noise calibration & STT
│   ├── text_to_speech.py           # Thread-safe offline pyttsx3 SAPI5 engine
│   ├── command_router.py           # Modular rule-based intent router & normalizer
│   ├── command_handlers.py         # Handlers for greetings, time, apps, search, system
│   ├── application_launcher.py     # Whitelist-enforced desktop app launcher
│   ├── system_info.py              # Safe system diagnostics (OS, disk, CPU, RAM)
│   └── assistant_controller.py     # Central coordinator & state manager
│
├── gui/                            # Modern Desktop User Interface
│   ├── __init__.py                 # GUI package definition
│   ├── main_window.py              # CustomTkinter dark-theme window & layout
│   └── components.py               # Status badges, chat bubbles, clock & chips
│
└── tests/                          # Automated Unit Test Suite
    ├── __init__.py                 # Test package definition
    ├── test_command_router.py      # Tests for regex matching, normalization, security
    └── test_command_handlers.py    # Tests for handlers with subprocess/browser mocking
```

---

## License

This project is licensed under the MIT License — free for personal, educational, and commercial use.
