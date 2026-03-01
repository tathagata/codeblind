import logging
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

    def generate_code(self, prompt):
        """Send a prompt to Claude and return the generated code."""
        logger.info("Working on implementing: %s...", prompt[:60])
        messages = self._build_messages(prompt)
        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    messages=messages,
                )
                code = response.content[0].text
                logger.info("Code generation complete.")
                return code
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

    def explain_code(self, code):
        """Request a natural-language explanation of the given code."""
        prompt = (
            "Explain the following code in natural language, describing its behavior "
            "like an algorithm. Be concise and conversational.\n\n" + code
        )
        logger.info("Requesting code explanation...")
        return self.generate_code(prompt)
