# CodeBlind

> When I say nocode, I really mean it.

CodeBlind is a voice-first local coding harness. Speak a repo task aloud; the app captures your voice, inspects the workspace, plans or answers the request, and reads the result back to you via text-to-speech. Mutating actions are confirmation-gated, so the harness can explore freely but will ask before editing files or running risky commands.

## How It Works

```
Microphone → VoiceParser → Session Orchestrator → Repo Ops / ClaudeAPI → TTSBridge
```

1. **VoiceParser** – captures audio from your microphone and transcribes it to text.
2. **Session Orchestrator** – keeps turn history, classifies intent, and decides whether to answer immediately or stage a proposed repo action.
3. **Repo Ops / ClaudeAPI** – either inspects the repo and answers questions, runs verification, or drafts a code change proposal that waits for spoken approval.
4. **TTSBridge** – pipes the response to the Swift TTS executable for spoken output (macOS only; optional on other platforms).

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

### Session mode (default)

```bash
python main.py
python main.py --voice handy
python main.py --once
```

Speak repo-aware requests such as:
- “git status”
- “search for `TestingGuardrails`”
- “run tests”
- “update `main.py` to use the session controller”

For mutating requests, CodeBlind will propose an action and wait for a spoken confirmation like “approve” or “cancel”.

### Direct mode (legacy)

```bash
python main.py --direct
python main.py --direct --once
```

This preserves the earlier voice → Claude → TTS path without conversational state or confirmation gating.

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
│   ├── harness_types.py       # ProposedAction and TurnResult models
│   ├── orchestrator.py        # Pipeline orchestration and TTSBridge
│   ├── repo_ops.py            # Repo inspection, test runs, and approved mutations
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
