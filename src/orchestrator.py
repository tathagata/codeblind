import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class TTSError(Exception):
    """Raised when TTS output fails."""


class TTSBridge:
    """Pipes text to the Swift TTS command-line tool for spoken output."""

    DEFAULT_TTS_EXECUTABLE = os.path.join(
        os.path.dirname(__file__), "..", "swift_tts", ".build", "release", "swift_tts"
    )

    def __init__(self, tts_executable=None):
        self._executable = tts_executable or self.DEFAULT_TTS_EXECUTABLE

    def speak(self, text):
        """Send text to the Swift TTS tool via stdin."""
        if not text or not text.strip():
            raise TTSError("Cannot speak empty text.")
        executable = os.path.abspath(self._executable)
        if not os.path.isfile(executable):
            raise TTSError(f"Swift TTS executable not found: {executable}")
        logger.info("Speaking: %s...", text[:60])
        try:
            subprocess.run(
                [executable],
                input=text,
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            raise TTSError(f"TTS subprocess failed: {e.stderr}") from e


class OrchestratorError(Exception):
    """Raised when the orchestration pipeline encounters a fatal error."""


class Orchestrator:
    """Orchestrates VoiceParser → ClaudeAPI → TestingGuardrails → TTS output."""

    def __init__(self, voice_parser, claude_api, testing_guardrails, tts_bridge):
        self._voice_parser = voice_parser
        self._claude_api = claude_api
        self._testing_guardrails = testing_guardrails
        self._tts_bridge = tts_bridge

    def run_once(self):
        """
        Run one full cycle:
        1. Capture voice input
        2. Generate code via Claude API
        3. Validate generated code with pytest
        4. Speak results via TTS
        Returns a dict with keys: command, code, summary.
        """
        logger.info("Step 1: Listening for voice command...")
        command = self._voice_parser.speech_to_text()
        logger.info("Command received: %s", command)

        logger.info("Step 2: Generating code for command: %s", command)
        code = self._claude_api.generate_code(command)
        logger.info("Code generated.")

        logger.info("Step 3: Validating generated code...")
        summary = self._testing_guardrails.validate_code(code)
        logger.info("Validation complete: %s", summary)

        logger.info("Step 4: Speaking results...")
        self._tts_bridge.speak(summary)

        return {"command": command, "code": code, "summary": summary}
