import logging
import os
import re
import subprocess

from harness_types import ProposedAction, TurnResult

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
    """Stateful voice-first coding harness with confirmation gating."""

    APPROVAL_WORDS = {"approve", "approved", "go ahead", "do it", "yes", "confirm"}
    CANCEL_WORDS = {"cancel", "stop", "never mind", "no", "reject"}

    def __init__(
        self,
        voice_parser,
        claude_api,
        testing_guardrails=None,
        tts_bridge=None,
        repo_operations=None,
    ):
        self._voice_parser = voice_parser
        self._claude_api = claude_api
        self._testing_guardrails = testing_guardrails
        self._tts_bridge = tts_bridge
        self._repo_operations = repo_operations
        self._history = []
        self._pending_action = None
        self._latest_task_state = {}

    def start_session(self):
        """Initialize session state and return a spoken-ready greeting."""
        self._history = []
        self._pending_action = None
        self._latest_task_state = {}
        greeting = (
            "CodeBlind session ready. Ask me to inspect the repo, plan a change, run tests, "
            "or explain the latest work."
        )
        self._speak_response(greeting)
        return greeting

    def handle_turn(self, transcript):
        """Handle one transcribed user turn and return a structured result."""
        cleaned = self._sanitize_transcript(transcript)
        intent = self._classify_intent(cleaned)
        logger.info("Handling session turn with intent '%s': %s", intent, cleaned)

        if intent in {"approval", "cancel"}:
            result = self._handle_confirmation(cleaned, intent)
        elif intent == "test":
            result = self._handle_test_request(cleaned)
        elif intent == "explore":
            result = self._handle_explore_request(cleaned)
        elif intent == "explain":
            result = self._handle_explain_request(cleaned)
        else:
            result = self._handle_code_change_request(cleaned)

        self._history.append({"transcript": cleaned, "intent": result.intent})
        self._latest_task_state["last_turn"] = result
        return result

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

    def run_pipeline(self):
        """
        Run one direct cycle: Voice → Claude → TTS (no TestingGuardrails).
        Returns a dict with keys: command, response.
        """
        logger.info("Listening for voice command...")
        command = self._voice_parser.speech_to_text()
        logger.info("Command received: %s", command)

        logger.info("Sending to Claude: %s", command)
        response = self._claude_api.generate_code(command)
        logger.info("Response received.")

        logger.info("Speaking response...")
        self._tts_bridge.speak(response)

        return {"command": command, "response": response}

    def _handle_confirmation(self, transcript, intent):
        if self._pending_action is None:
            spoken = "There is no pending change to approve right now."
            self._speak_response(spoken)
            return TurnResult(transcript=transcript, intent=intent, spoken_response=spoken)

        if intent == "cancel":
            summary = self._pending_action.summary
            self._pending_action = None
            spoken = f"Canceled the pending action: {summary}"
            self._speak_response(spoken)
            return TurnResult(transcript=transcript, intent=intent, spoken_response=spoken)

        if self._repo_operations is None:
            raise OrchestratorError("Repo operations are required to execute approved actions.")

        action = self._pending_action
        self._pending_action = None
        actions_taken = self._repo_operations.apply_action(action)
        verification_summary = None

        if action.verification_command:
            verification_output = self._repo_operations.apply_action(
                ProposedAction(
                    action_type="run_command",
                    summary=f"Verification for {action.summary}",
                    command=action.verification_command,
                    requires_confirmation=False,
                )
            )
            verification_summary = " ".join(verification_output)
            actions_taken.extend(verification_output)
        elif self._testing_guardrails is not None and action.action_type in {"edit_file", "create_file"}:
            verification_summary = self._repo_operations.summarize_tests()
            actions_taken.append(verification_summary)

        details = " ".join(actions_taken)
        if verification_summary:
            details = f"{details} Verification: {verification_summary}"
        spoken = self._safe_execution_summary(action.summary, details)
        self._latest_task_state["last_action"] = action
        self._latest_task_state["last_actions_taken"] = actions_taken
        self._latest_task_state["last_verification_summary"] = verification_summary
        self._speak_response(spoken)
        return TurnResult(
            transcript=transcript,
            intent=intent,
            spoken_response=spoken,
            actions_taken=actions_taken,
            verification_summary=verification_summary,
        )

    def _handle_test_request(self, transcript):
        if self._repo_operations is None:
            raise OrchestratorError("Repo operations are required for test requests.")
        summary = self._repo_operations.summarize_tests()
        spoken = f"Test summary: {summary}"
        self._latest_task_state["last_verification_summary"] = summary
        self._speak_response(spoken)
        return TurnResult(
            transcript=transcript,
            intent="test",
            spoken_response=spoken,
            actions_taken=["Ran workspace tests."],
            verification_summary=summary,
        )

    def _handle_explore_request(self, transcript):
        if self._repo_operations is None:
            raise OrchestratorError("Repo operations are required for repo exploration.")

        lowered = transcript.lower()
        if "git status" in lowered or "working tree" in lowered:
            details = self._repo_operations.git_status()
        elif "search " in lowered or "find " in lowered:
            pattern = self._extract_search_pattern(transcript)
            details = self._repo_operations.search_files(pattern)
        elif "open " in lowered or "show " in lowered or "read " in lowered:
            target = self._extract_path_reference(transcript)
            details = self._repo_operations.read_file(target)
        else:
            details = self._repo_operations.describe_workspace()

        spoken = self._safe_answer(transcript, details)
        self._latest_task_state["last_exploration"] = details
        self._speak_response(spoken)
        return TurnResult(
            transcript=transcript,
            intent="explore",
            spoken_response=spoken,
            actions_taken=[details],
        )

    def _handle_explain_request(self, transcript):
        last_action = self._latest_task_state.get("last_action")
        if last_action is None:
            spoken = "I have not made any approved changes yet, so there is nothing new to explain."
            self._speak_response(spoken)
            return TurnResult(transcript=transcript, intent="explain", spoken_response=spoken)

        details = (
            f"Summary: {last_action.summary}\n"
            f"Targets: {', '.join(last_action.target_paths) or 'none'}\n"
            f"Verification: {self._latest_task_state.get('last_verification_summary') or 'none'}"
        )
        spoken = self._safe_answer(transcript, details)
        self._speak_response(spoken)
        return TurnResult(
            transcript=transcript,
            intent="explain",
            spoken_response=spoken,
            actions_taken=[details],
            verification_summary=self._latest_task_state.get("last_verification_summary"),
        )

    def _handle_code_change_request(self, transcript):
        if self._repo_operations is None:
            raise OrchestratorError("Repo operations are required for code change requests.")

        repo_context = self._repo_operations.describe_workspace()
        proposal = self._claude_api.plan_code_change(transcript, repo_context)
        action = ProposedAction(
            action_type=proposal["action_type"],
            summary=proposal["summary"],
            target_paths=proposal.get("target_paths", []),
            content=proposal.get("content"),
            rollback_note=proposal.get("rollback_note", ""),
            verification_command=proposal.get("verification_command"),
        )
        self._pending_action = action
        targets = ", ".join(action.target_paths) or "the repo"
        spoken = (
            f"I’m ready to {action.summary}. "
            f"This would touch {targets}. Say approve or cancel."
        )
        self._speak_response(spoken)
        return TurnResult(
            transcript=transcript,
            intent="code_change",
            spoken_response=spoken,
            pending_approval_request=action,
        )

    def _classify_intent(self, transcript):
        lowered = transcript.lower().strip()
        if lowered in self.APPROVAL_WORDS:
            return "approval"
        if lowered in self.CANCEL_WORDS:
            return "cancel"
        if "run tests" in lowered or "pytest" in lowered or "verify" in lowered:
            return "test"
        if "explain" in lowered or "what changed" in lowered or "summarize" in lowered:
            return "explain"
        explore_tokens = ("git status", "show", "open", "read", "search", "find", "list files")
        if any(token in lowered for token in explore_tokens):
            return "explore"
        code_tokens = ("write", "update", "edit", "change", "fix", "create", "implement", "refactor")
        if any(token in lowered for token in code_tokens):
            return "code_change"
        return "explore"

    def _sanitize_transcript(self, transcript):
        cleaned = re.sub(r"\s+", " ", (transcript or "").strip())
        if not cleaned:
            raise OrchestratorError("Transcript cannot be empty.")
        return cleaned

    def _extract_search_pattern(self, transcript):
        quoted = re.findall(r"['\"]([^'\"]+)['\"]", transcript)
        if quoted:
            return quoted[0]
        match = re.search(r"(?:search|find)\s+(?:for\s+)?(.+)", transcript, re.IGNORECASE)
        return match.group(1).strip() if match else transcript

    def _extract_path_reference(self, transcript):
        match = re.search(
            r"(?:open|show|read)\s+(?:file\s+)?([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+)",
            transcript,
            re.IGNORECASE,
        )
        if not match:
            raise OrchestratorError("I could not determine which file to open.")
        return match.group(1)

    def _safe_answer(self, transcript, details):
        try:
            return self._claude_api.answer_question(transcript, details)
        except Exception:
            return details

    def _safe_execution_summary(self, request, details):
        try:
            return self._claude_api.summarize_execution(request, details)
        except Exception:
            return details

    def _speak_response(self, text):
        if self._tts_bridge is None:
            return
        try:
            self._tts_bridge.speak(text)
        except TTSError as e:
            logger.warning("Unable to speak response: %s", e)
