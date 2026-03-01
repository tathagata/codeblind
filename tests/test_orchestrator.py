import os
import pytest
from unittest.mock import MagicMock, patch

from orchestrator import Orchestrator, OrchestratorError, TTSBridge, TTSError


class TestTTSBridgeSpeak:
    def test_speak_raises_on_empty_text(self, tmp_path):
        bridge = TTSBridge(tts_executable=str(tmp_path / "tts"))
        with pytest.raises(TTSError, match="empty"):
            bridge.speak("")

    def test_speak_raises_on_whitespace_text(self, tmp_path):
        bridge = TTSBridge(tts_executable=str(tmp_path / "tts"))
        with pytest.raises(TTSError, match="empty"):
            bridge.speak("   ")

    def test_speak_raises_when_executable_missing(self, tmp_path):
        bridge = TTSBridge(tts_executable=str(tmp_path / "nonexistent_tts"))
        with pytest.raises(TTSError, match="not found"):
            bridge.speak("Hello")

    def test_speak_calls_subprocess_with_text(self, tmp_path):
        # Create a fake executable file so the path check passes
        fake_exe = tmp_path / "tts"
        fake_exe.write_text("#!/bin/sh\nexit 0\n")
        fake_exe.chmod(0o755)

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            bridge = TTSBridge(tts_executable=str(fake_exe))
            result = bridge.speak("Hello, world!")

        assert result is True
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["input"] == "Hello, world!"

    def test_speak_raises_on_subprocess_error(self, tmp_path):
        import subprocess

        fake_exe = tmp_path / "tts"
        fake_exe.write_text("#!/bin/sh\nexit 0\n")
        fake_exe.chmod(0o755)

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "tts", stderr="fail")
            bridge = TTSBridge(tts_executable=str(fake_exe))
            with pytest.raises(TTSError, match="subprocess failed"):
                bridge.speak("Hello")

    def test_default_executable_path_is_set(self):
        bridge = TTSBridge()
        assert "swift_tts" in bridge._executable


class TestOrchestrator:
    def _make_orchestrator(self, command="write a sort function", code="def sort(): pass",
                           summary="passed all 1 tests"):
        voice_parser = MagicMock()
        voice_parser.speech_to_text.return_value = command

        claude_api = MagicMock()
        claude_api.generate_code.return_value = code

        testing_guardrails = MagicMock()
        testing_guardrails.validate_code.return_value = summary

        tts_bridge = MagicMock()
        tts_bridge.speak.return_value = True

        orchestrator = Orchestrator(voice_parser, claude_api, testing_guardrails, tts_bridge)
        return orchestrator, voice_parser, claude_api, testing_guardrails, tts_bridge

    def test_run_once_returns_expected_keys(self):
        orchestrator, _, _, _, _ = self._make_orchestrator()
        result = orchestrator.run_once()
        assert set(result.keys()) == {"command", "code", "summary"}

    def test_run_once_returns_correct_values(self):
        orchestrator, _, _, _, _ = self._make_orchestrator(
            command="create a sort function",
            code="def sort(): pass",
            summary="passed all 1 tests",
        )
        result = orchestrator.run_once()
        assert result["command"] == "create a sort function"
        assert result["code"] == "def sort(): pass"
        assert result["summary"] == "passed all 1 tests"

    def test_run_once_calls_voice_parser(self):
        orchestrator, voice_parser, _, _, _ = self._make_orchestrator()
        orchestrator.run_once()
        voice_parser.speech_to_text.assert_called_once()

    def test_run_once_calls_claude_api_with_command(self):
        orchestrator, _, claude_api, _, _ = self._make_orchestrator(command="my command")
        orchestrator.run_once()
        claude_api.generate_code.assert_called_once_with("my command")

    def test_run_once_calls_testing_guardrails_with_code(self):
        orchestrator, _, _, testing_guardrails, _ = self._make_orchestrator(
            code="def foo(): return 1"
        )
        orchestrator.run_once()
        testing_guardrails.validate_code.assert_called_once_with("def foo(): return 1")

    def test_run_once_calls_tts_bridge_with_summary(self):
        orchestrator, _, _, _, tts_bridge = self._make_orchestrator(
            summary="Your code passed all 3 tests."
        )
        orchestrator.run_once()
        tts_bridge.speak.assert_called_once_with("Your code passed all 3 tests.")

    def test_run_once_propagates_voice_parser_error(self):
        from voice_parser import VoiceParserError

        orchestrator, voice_parser, _, _, _ = self._make_orchestrator()
        voice_parser.speech_to_text.side_effect = VoiceParserError("mic error")
        with pytest.raises(VoiceParserError, match="mic error"):
            orchestrator.run_once()

    def test_run_once_propagates_claude_api_error(self):
        from claude_api import ClaudeAPIError

        orchestrator, _, claude_api, _, _ = self._make_orchestrator()
        claude_api.generate_code.side_effect = ClaudeAPIError("API down")
        with pytest.raises(ClaudeAPIError, match="API down"):
            orchestrator.run_once()
