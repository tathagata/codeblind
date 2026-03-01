import pytest

from testing_guardrails import TestingGuardrails


class TestParseResults:
    def test_parse_all_passed(self):
        guardrails = TestingGuardrails()
        result = guardrails.parse_results({"stdout": "5 passed in 0.12s"})
        assert result == {"passed": 5, "failed": 0}

    def test_parse_mixed_results(self):
        guardrails = TestingGuardrails()
        result = guardrails.parse_results({"stdout": "3 passed, 2 failed in 0.5s"})
        assert result == {"passed": 3, "failed": 2}

    def test_parse_empty_output(self):
        guardrails = TestingGuardrails()
        result = guardrails.parse_results({"stdout": ""})
        assert result == {"passed": 0, "failed": 0}


class TestSummarize:
    def test_summarize_all_passed(self):
        guardrails = TestingGuardrails()
        summary = guardrails.summarize({"stdout": "5 passed in 0.12s"})
        assert "passed all 5 tests" in summary

    def test_summarize_mixed_results(self):
        guardrails = TestingGuardrails()
        summary = guardrails.summarize({"stdout": "3 passed, 2 failed in 0.5s"})
        assert "3 of 5" in summary
        assert "refine" in summary.lower()

    def test_summarize_no_tests(self):
        guardrails = TestingGuardrails()
        summary = guardrails.summarize({"stdout": ""})
        assert "No tests were collected" in summary


class TestValidateCode:
    def test_validate_code_with_passing_test(self):
        guardrails = TestingGuardrails()
        code = "def add(a, b):\n    return a + b\n"
        test_code = (
            "import sys, os\n"
            "sys.path.insert(0, os.path.dirname(__file__))\n"
            "from generated_module import add\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
        )
        summary = guardrails.validate_code(code, test_code=test_code)
        assert "passed" in summary.lower()

    def test_validate_code_with_failing_test(self):
        guardrails = TestingGuardrails()
        code = "def add(a, b):\n    return a - b\n"  # intentionally wrong
        test_code = (
            "import sys, os\n"
            "sys.path.insert(0, os.path.dirname(__file__))\n"
            "from generated_module import add\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
        )
        summary = guardrails.validate_code(code, test_code=test_code)
        assert "refine" in summary.lower() or "no tests were collected" in summary.lower()
