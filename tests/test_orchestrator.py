import pytest
from unittest.mock import MagicMock, patch

from harness_types import ProposedAction
from orchestrator import Orchestrator, TTSBridge, TTSError


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


class TestLegacyOrchestratorBehavior:
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

    def test_run_once_calls_testing_guardrails_with_code(self):
        orchestrator, _, _, testing_guardrails, _ = self._make_orchestrator(
            code="def foo(): return 1"
        )
        orchestrator.run_once()
        testing_guardrails.validate_code.assert_called_once_with("def foo(): return 1")

    def test_run_pipeline_returns_expected_keys(self):
        orchestrator, _, _, _, _ = self._make_orchestrator()
        result = orchestrator.run_pipeline()
        assert set(result.keys()) == {"command", "response"}


class TestSessionOrchestrator:
    def _make_session_orchestrator(self):
        voice_parser = MagicMock()

        claude_api = MagicMock()
        claude_api.answer_question.return_value = "The working tree has two modified files."
        claude_api.summarize_execution.return_value = "Updated main.py and ran the tests."
        claude_api.plan_code_change.return_value = {
            "action_type": "edit_file",
            "target_paths": ["main.py"],
            "content": "print('updated')\n",
            "summary": "update main.py",
            "rollback_note": "Restore the previous version from git diff.",
            "verification_command": ["python", "-m", "pytest", "tests/test_orchestrator.py"],
        }

        testing_guardrails = MagicMock()

        repo_operations = MagicMock()
        repo_operations.git_status.return_value = " M main.py"
        repo_operations.describe_workspace.return_value = "Repo root: /tmp/repo"
        repo_operations.read_file.return_value = "print('hello')"
        repo_operations.search_files.return_value = "main.py:10:def main():"
        repo_operations.summarize_tests.return_value = "Your code passed all 5 tests."

        def apply_action(action):
            if action.action_type == "edit_file":
                return ["Updated main.py."]
            if action.action_type == "run_command":
                return ["Ran python -m pytest tests/test_orchestrator.py.", "1 passed in 0.01s"]
            raise AssertionError(f"Unexpected action type {action.action_type}")

        repo_operations.apply_action.side_effect = apply_action

        tts_bridge = MagicMock()
        orchestrator = Orchestrator(
            voice_parser=voice_parser,
            claude_api=claude_api,
            testing_guardrails=testing_guardrails,
            tts_bridge=tts_bridge,
            repo_operations=repo_operations,
        )
        return orchestrator, claude_api, repo_operations, tts_bridge

    def test_start_session_speaks_greeting(self):
        orchestrator, _, _, tts_bridge = self._make_session_orchestrator()
        greeting = orchestrator.start_session()
        assert "CodeBlind session ready" in greeting
        tts_bridge.speak.assert_called_once()

    def test_exploration_request_runs_immediately(self):
        orchestrator, claude_api, repo_operations, _ = self._make_session_orchestrator()
        result = orchestrator.handle_turn("git status")
        assert result.intent == "explore"
        assert result.pending_approval_request is None
        assert result.actions_taken == [" M main.py"]
        repo_operations.git_status.assert_called_once()
        claude_api.answer_question.assert_called_once()

    def test_code_change_request_requires_approval(self):
        orchestrator, claude_api, repo_operations, _ = self._make_session_orchestrator()
        result = orchestrator.handle_turn("update main.py to start a session")
        assert result.intent == "code_change"
        assert isinstance(result.pending_approval_request, ProposedAction)
        assert result.pending_approval_request.target_paths == ["main.py"]
        repo_operations.apply_action.assert_not_called()
        claude_api.plan_code_change.assert_called_once()

    def test_approve_runs_pending_action_and_verification(self):
        orchestrator, _, repo_operations, _ = self._make_session_orchestrator()
        orchestrator.handle_turn("update main.py to start a session")
        result = orchestrator.handle_turn("approve")
        assert result.intent == "approval"
        assert "Updated main.py." in result.actions_taken
        assert result.verification_summary is not None
        assert repo_operations.apply_action.call_count == 2

    def test_cancel_clears_pending_action(self):
        orchestrator, _, repo_operations, _ = self._make_session_orchestrator()
        orchestrator.handle_turn("update main.py to start a session")
        result = orchestrator.handle_turn("cancel")
        assert result.intent == "cancel"
        assert "Canceled the pending action" in result.spoken_response
        repo_operations.apply_action.assert_not_called()

    def test_explain_uses_latest_task_state(self):
        orchestrator, _, _, _ = self._make_session_orchestrator()
        orchestrator.handle_turn("update main.py to start a session")
        orchestrator.handle_turn("approve")
        result = orchestrator.handle_turn("explain what changed")
        assert result.intent == "explain"
        assert "Updated main.py" in result.spoken_response or "updated" in result.spoken_response.lower()

    def test_run_tests_request_returns_verification_summary(self):
        orchestrator, _, repo_operations, _ = self._make_session_orchestrator()
        result = orchestrator.handle_turn("run tests")
        assert result.intent == "test"
        assert result.verification_summary == "Your code passed all 5 tests."
        repo_operations.summarize_tests.assert_called_once()
