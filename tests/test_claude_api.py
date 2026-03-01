import pytest
from unittest.mock import MagicMock, patch

from claude_api import ClaudeAPI, ClaudeAPIError


def _make_api(response_text="def fib(n): pass"):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=response_text)]
    mock_client.messages.create.return_value = mock_response
    return ClaudeAPI(client=mock_client), mock_client


class TestClaudeAPIGenerateCode:
    def test_generate_code_returns_text(self):
        api, _ = _make_api("def fib(n): return n")
        assert api.generate_code("Write a fibonacci function") == "def fib(n): return n"

    def test_generate_code_builds_correct_messages(self):
        api, mock_client = _make_api()
        api.generate_code("Write a fibonacci function")
        call_kwargs = mock_client.messages.create.call_args[1]
        assert call_kwargs["messages"][0]["role"] == "user"
        assert "fibonacci" in call_kwargs["messages"][0]["content"].lower()

    def test_generate_code_retries_on_transient_failure(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="code")]
        mock_client.messages.create.side_effect = [Exception("transient"), mock_response]
        api = ClaudeAPI(client=mock_client)
        with patch("claude_api.time.sleep"):
            result = api.generate_code("prompt")
        assert result == "code"
        assert mock_client.messages.create.call_count == 2

    def test_generate_code_raises_after_max_retries(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("persistent error")
        api = ClaudeAPI(client=mock_client)
        with patch("claude_api.time.sleep"):
            with pytest.raises(ClaudeAPIError):
                api.generate_code("prompt")


class TestClaudeAPIExplainCode:
    def test_explain_code_returns_explanation(self):
        api, _ = _make_api("This function calculates fibonacci.")
        result = api.explain_code("def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)")
        assert result == "This function calculates fibonacci."

    def test_explain_code_includes_code_in_prompt(self):
        api, mock_client = _make_api("explanation")
        code = "def fib(n): return n if n <= 1 else fib(n-1) + fib(n-2)"
        api.explain_code(code)
        call_kwargs = mock_client.messages.create.call_args[1]
        assert code in call_kwargs["messages"][0]["content"]
