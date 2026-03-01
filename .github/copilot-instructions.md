# Copilot Instructions for codeblind

## Project Overview

**codeblind** is a voice-driven coding assistant that lets developers write code hands-free. The pipeline is:

1. **VoiceParser** — captures microphone audio and transcribes it to text via Google Speech Recognition (`SpeechRecognition` library).
2. **ClaudeAPI** — sends the transcribed command to Anthropic's Claude API and returns generated code.
3. **TestingGuardrails** — writes the generated code to a temp directory and validates it with `pytest`, returning a conversational summary.
4. **TTSBridge** — speaks the summary aloud via a compiled Swift TTS command-line binary (`swift_tts/.build/release/swift_tts`).
5. **Orchestrator** — wires all four components together into a single `run_once()` cycle.
6. **VSCodeIntegration** — optional helper to open generated files in VS Code.

## Repository Layout

```
src/                  # Python source modules
  claude_api.py       # ClaudeAPI class (Anthropic client wrapper)
  orchestrator.py     # Orchestrator + TTSBridge classes
  testing_guardrails.py # TestingGuardrails class (pytest runner)
  voice_parser.py     # VoiceParser class (SpeechRecognition wrapper)
  vscode_integration.py # VSCodeIntegration helper
swift_tts/            # Swift package for TTS (spoken output)
tests/                # pytest test suite mirroring src/
  conftest.py         # adds src/ to sys.path
requirements.txt      # Python dependencies: pytest, SpeechRecognition, anthropic
.github/workflows/ci.yml  # CI: installs deps, runs pytest tests/ src/
```

## How to Run Tests

```bash
pip install -r requirements.txt
pytest tests/ src/
```

The CI workflow (`.github/workflows/ci.yml`) runs the same command on every push and pull request.

## Coding Conventions

- **Python 3.11+**; follow PEP 8.
- Each module defines one primary class and a matching `*Error` exception (e.g., `ClaudeAPIError`, `VoiceParserError`).
- Use `logging` (not `print`) for all runtime output. Get a module-level logger with `logging.getLogger(__name__)`.
- Dependency imports that may be absent at test time (e.g., `speech_recognition`, `anthropic`) are done inside `__init__` with a try/except so the class can be instantiated with mock objects in tests.
- Constructors accept optional collaborator arguments (e.g., `client=`, `recognizer=`) to support dependency injection in tests.
- Keep methods small and focused; new public methods should have a one-line docstring.

## Adding New Features

1. Add the implementation in the appropriate `src/` module (or create a new one following the same pattern).
2. Add corresponding tests in `tests/test_<module>.py`.
3. If a new external library is needed, add it to `requirements.txt`.
4. Ensure `pytest tests/ src/` passes before opening a PR.

## Architecture Notes

- The Swift TTS binary must be compiled before `TTSBridge` can speak (`swift build -c release` inside `swift_tts/`). Tests that exercise `TTSBridge.speak()` mock `subprocess.run` to avoid requiring the binary.
- `TestingGuardrails.validate_code()` writes generated code to a `tempfile.TemporaryDirectory`, so it never pollutes the working tree.
- `ClaudeAPI` retries API calls up to `MAX_RETRIES` (3) times with a `RETRY_DELAY` (2 s) between attempts.
