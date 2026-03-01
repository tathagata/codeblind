import logging
import os
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)


class TestingGuardrails:
    """Validates generated code by running pytest and summarizing results conversationally."""

    def __init__(self, python_executable=None):
        self._python = python_executable or sys.executable

    def run_tests(self, test_paths=None):
        """Run pytest on the given paths and return a result dict."""
        paths = test_paths or ["tests/"]
        cmd = [self._python, "-m", "pytest", "--tb=short", "-q"] + paths
        logger.info("Running tests: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def parse_results(self, run_result):
        """Parse pytest output to extract passed/failed counts."""
        stdout = run_result.get("stdout", "")
        passed = 0
        failed = 0
        for line in stdout.splitlines():
            if "passed" in line or "failed" in line:
                for part in line.split(","):
                    part = part.strip()
                    try:
                        if "passed" in part:
                            passed = int(part.split()[0])
                        if "failed" in part:
                            failed = int(part.split()[0])
                    except (ValueError, IndexError):
                        pass
        return {"passed": passed, "failed": failed}

    def summarize(self, run_result):
        """Return a conversational summary of test results."""
        counts = self.parse_results(run_result)
        passed = counts["passed"]
        failed = counts["failed"]
        total = passed + failed
        if total == 0:
            return "No tests were collected. Please add tests to validate the generated code."
        if failed == 0:
            return f"Your code passed all {passed} tests. Everything looks good!"
        return (
            f"Your code passed {passed} of {total} tests. "
            f"Failures may be related to edge cases like invalid input handling. "
            f"Would you like to refine?"
        )

    def validate_code(self, code, test_code=None, test_paths=None):
        """
        Write code to a temp directory, optionally run provided test_code against it,
        then run pytest and return a conversational summary.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            module_path = os.path.join(tmpdir, "generated_module.py")
            with open(module_path, "w") as f:
                f.write(code)

            if test_code:
                test_path = os.path.join(tmpdir, "test_generated.py")
                with open(test_path, "w") as f:
                    f.write(test_code)
                run_result = self.run_tests([tmpdir])
            elif test_paths:
                run_result = self.run_tests(test_paths)
            else:
                run_result = self.run_tests([tmpdir])

            summary = self.summarize(run_result)
            logger.info(summary)
            return summary
