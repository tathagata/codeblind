# CodeBlind

> When I say nocode, I really mean it.

CodeBlind is a voice-driven code generation tool. Speak a programming task aloud; the app captures your voice, sends it to the Claude API to generate code, validates the result with pytest, and reads the outcome back to you via text-to-speech.

## How It Works

```
Microphone → VoiceParser → ClaudeAPI → TestingGuardrails → TTSBridge (spoken output)
```

1. **VoiceParser** – captures audio from your microphone and transcribes it to text.
2. **ClaudeAPI** – sends the transcribed text to the Claude API (default model: Claude 3.5 Sonnet, configurable) and returns generated code.
3. **TestingGuardrails** – runs `pytest` against the generated code and summarises the results.
4. **TTSBridge** – pipes the summary to the Swift TTS executable for spoken output (macOS only; optional on other platforms).

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11 or later | [python.org](https://www.python.org/downloads/) |
| pip | bundled with Python | upgrade with `pip install --upgrade pip` |
| Swift toolchain | 5.5 or later | macOS only – required for the TTS module |
| Xcode Command Line Tools | latest | macOS only – install with `xcode-select --install` |
| Working microphone | — | required for voice input |
| Internet connection | — | required for Google Speech Recognition and Claude API |

> **macOS note:** Swift and AVFoundation are built-in on macOS 12+. The Swift TTS module is optional; you can still use CodeBlind without spoken output on Linux or Windows.

---

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/tathagata/codeblind.git
cd codeblind
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- `anthropic` – Claude API client
- `SpeechRecognition` – microphone capture and Google Speech Recognition
- `pyperclip` – clipboard access (used by the Handy voice-input alternative)
- `pytest` – test runner used by the testing guardrails

### 4. Set the Anthropic API key

CodeBlind uses the [Claude API](https://console.anthropic.com/) to generate code. Export your key as an environment variable:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

You can add this line to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.) so it persists across sessions.

### 5. Build the Swift TTS module (macOS only)

```bash
cd swift_tts
swift build --configuration release
cd ..
```

The compiled binary will be placed at `swift_tts/.build/release/swift_tts`. The `TTSBridge` class looks for it there automatically.

> **Skip this step** if you are on Linux or Windows, or if you do not need spoken output. You can still run the Python pipeline; just omit the `TTSBridge` from your `Orchestrator` setup or mock it in tests.

---

## Running the Application

### Quick start (interactive loop)

```python
# run_codeblind.py  (create this file in the project root, or run in a Python REPL)
import os
from src.claude_api import ClaudeAPI
from src.voice_parser import VoiceParser
from src.testing_guardrails import TestingGuardrails
from src.orchestrator import Orchestrator, TTSBridge

voice   = VoiceParser()
claude  = ClaudeAPI(api_key=os.environ["ANTHROPIC_API_KEY"])
guards  = TestingGuardrails()
tts     = TTSBridge()          # remove / mock on non-macOS systems

orchestrator = Orchestrator(voice, claude, guards, tts)

result = orchestrator.run_once()
print("Command :", result["command"])
print("Summary :", result["summary"])
```

Run it with:

```bash
python run_codeblind.py
```

Speak your programming task when prompted (e.g. *"write a function that reverses a string"*). The tool will generate the code, run tests, and read the outcome aloud.

### Alternative: Handy (offline voice input, macOS)

[Handy](https://github.com/cjpais/Handy) is a free, offline speech-to-text desktop app. Install and start it, then replace `VoiceParser` with `HandyVoiceParser`:

```python
from src.voice_parser import HandyVoiceParser

voice = HandyVoiceParser()   # everything else stays the same
```

---

## Running Tests

```bash
pytest tests/ src/
```

All tests use mocks for external dependencies (microphone, Claude API, TTS), so no API key or microphone is needed to run them.

---

## Project Structure

```
codeblind/
├── src/
│   ├── claude_api.py          # Claude API integration
│   ├── orchestrator.py        # Pipeline orchestration and TTSBridge
│   ├── testing_guardrails.py  # pytest-based code validation
│   ├── voice_parser.py        # VoiceParser and HandyVoiceParser
│   └── vscode_integration.py  # Open generated files in VS Code
├── swift_tts/
│   ├── Package.swift          # Swift package manifest
│   └── Sources/main.swift     # AVFoundation TTS executable
├── tests/                     # pytest test suite
├── requirements.txt           # Python dependencies
└── .github/workflows/ci.yml   # CI pipeline (Python 3.11, ubuntu-latest)
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `ClaudeAPIError: anthropic library is not installed` | Run `pip install anthropic` |
| `VoiceParserError: speech_recognition library is not installed` | Run `pip install SpeechRecognition` |
| `TTSError: Swift TTS executable not found` | Run `swift build --configuration release` inside `swift_tts/` |
| `OSError: [Errno -9996] Invalid input device` | Check that a microphone is connected and has OS permission |
| `ANTHROPIC_API_KEY` not set | Export the variable: `export ANTHROPIC_API_KEY="sk-ant-..."` |
