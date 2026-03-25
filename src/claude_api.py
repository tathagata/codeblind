import logging
import json
import re
import time

logger = logging.getLogger(__name__)


class ClaudeAPIError(Exception):
    """Raised when Claude API calls fail."""


class ClaudeAPI:
    """Sends prompts to Claude API and processes generated code."""

    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, api_key=None, model=None, client=None):
        self._model = model or self.DEFAULT_MODEL
        if client is not None:
            self._client = client
        else:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError as e:
                raise ClaudeAPIError(
                    "anthropic library is not installed. Run: pip install anthropic"
                ) from e

    def _build_messages(self, prompt):
        """Build the messages list for the Claude API."""
        return [{"role": "user", "content": prompt}]

    def _create_text(self, prompt, max_tokens=4096):
        messages = self._build_messages(prompt)
        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=messages,
                )
                return response.content[0].text
            except Exception as e:
                last_error = e
                logger.warning(
                    "API call failed (attempt %d/%d): %s", attempt, self.MAX_RETRIES, e
                )
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
        raise ClaudeAPIError(
            f"API call failed after {self.MAX_RETRIES} attempts: {last_error}"
        ) from last_error

    def _extract_json_object(self, text):
        cleaned = text.strip()
        fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
        if fenced_match:
            cleaned = fenced_match.group(1)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ClaudeAPIError("Expected a JSON object in the model response.")
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as e:
            raise ClaudeAPIError(f"Failed to parse model JSON response: {e}") from e

    def generate_code(self, prompt):
        """Send a prompt to Claude and return the generated code."""
        logger.info("Working on implementing: %s...", prompt[:60])
        code = self._create_text(prompt)
        logger.info("Code generation complete.")
        return code

    def explain_code(self, code):
        """Request a natural-language explanation of the given code."""
        prompt = (
            "Explain the following code in natural language, describing its behavior "
            "like an algorithm. Be concise and conversational.\n\n" + code
        )
        logger.info("Requesting code explanation...")
        return self.generate_code(prompt)

    def answer_question(self, question, repo_context):
        """Answer a repo question conversationally using available context."""
        prompt = (
            "You are helping with a voice-first coding harness.\n"
            "Answer the user's question concisely and conversationally using the repo context.\n\n"
            f"Repo context:\n{repo_context}\n\n"
            f"Question:\n{question}"
        )
        return self._create_text(prompt, max_tokens=1200).strip()

    def plan_code_change(self, request, repo_context):
        """Return a structured code-change proposal for a local repo task."""
        prompt = (
            "You are planning a local repository change for a voice-controlled coding harness.\n"
            "Return exactly one JSON object with these keys:\n"
            "action_type, target_paths, content, summary, rollback_note, verification_command.\n"
            "Rules:\n"
            "- action_type must be one of edit_file, create_file, run_command.\n"
            "- target_paths must be an array of repo-relative file paths.\n"
            "- content must contain the full desired file content for file actions.\n"
            "- summary and rollback_note must be short strings.\n"
            "- verification_command must be an array command or null.\n\n"
            f"Repo context:\n{repo_context}\n\n"
            f"User request:\n{request}"
        )
        response = self._create_text(prompt)
        proposal = self._extract_json_object(response)
        proposal.setdefault("target_paths", [])
        proposal.setdefault("rollback_note", "")
        proposal.setdefault("verification_command", None)
        return proposal

    def summarize_execution(self, request, details):
        """Summarize a completed action in spoken-friendly language."""
        prompt = (
            "Summarize this coding-harness result for spoken playback in 2 sentences or fewer.\n\n"
            f"Request:\n{request}\n\n"
            f"Details:\n{details}"
        )
        return self._create_text(prompt, max_tokens=500).strip()
