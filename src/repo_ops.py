import logging
import os
import subprocess
from pathlib import Path

from harness_types import ProposedAction

logger = logging.getLogger(__name__)


class RepoOperationError(Exception):
    """Raised when a repo operation fails."""


class RepoOperations:
    """Provides read-only and mutating operations for the local repository."""

    def __init__(self, repo_root=None, testing_guardrails=None):
        self._repo_root = Path(repo_root or os.getcwd()).resolve()
        self._testing_guardrails = testing_guardrails

    @property
    def repo_root(self):
        return str(self._repo_root)

    def list_files(self, limit=50):
        result = subprocess.run(
            ["rg", "--files"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return files[:limit]

    def search_files(self, pattern):
        result = subprocess.run(
            ["rg", "-n", pattern],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode not in (0, 1):
            raise RepoOperationError(result.stderr.strip() or "Failed to search files.")
        return result.stdout.strip() or f"No matches found for '{pattern}'."

    def read_file(self, relative_path, max_lines=80):
        path = self._resolve_path(relative_path)
        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        content = "".join(lines[:max_lines]).rstrip()
        if len(lines) > max_lines:
            content += "\n..."
        return content or f"{relative_path} is empty."

    def git_status(self):
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=self._repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RepoOperationError(result.stderr.strip() or "Failed to read git status.")
        return result.stdout.strip() or "Working tree is clean."

    def summarize_tests(self, test_paths=None):
        if self._testing_guardrails is None:
            raise RepoOperationError("Testing guardrails are not configured.")
        run_result = self._testing_guardrails.verify_workspace(test_paths=test_paths)
        return self._testing_guardrails.summarize(run_result)

    def describe_workspace(self, limit=20):
        files = self.list_files(limit=limit)
        status = self.git_status()
        files_summary = ", ".join(files) if files else "No files found."
        return f"Repo root: {self._repo_root}\nFiles: {files_summary}\nGit status:\n{status}"

    def apply_action(self, action):
        if not isinstance(action, ProposedAction):
            raise RepoOperationError("Unsupported action payload.")

        logger.info("Applying action: %s", action.summary)
        if action.action_type == "edit_file":
            if not action.target_paths or action.content is None:
                raise RepoOperationError("edit_file requires a target path and content.")
            path = self._resolve_path(action.target_paths[0])
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(action.content)
            return [f"Updated {action.target_paths[0]}."]

        if action.action_type == "create_file":
            if not action.target_paths or action.content is None:
                raise RepoOperationError("create_file requires a target path and content.")
            path = self._resolve_path(action.target_paths[0], allow_missing=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(action.content)
            return [f"Created {action.target_paths[0]}."]

        if action.action_type == "run_command":
            if not action.command:
                raise RepoOperationError("run_command requires a command.")
            result = subprocess.run(
                action.command,
                cwd=self._repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
            output = (result.stdout or result.stderr).strip() or "Command completed with no output."
            return [f"Ran {' '.join(action.command)}.", output]

        if action.action_type == "run_tests":
            return [self.summarize_tests()]

        raise RepoOperationError(f"Unsupported action type: {action.action_type}")

    def _resolve_path(self, relative_path, allow_missing=False):
        path = (self._repo_root / relative_path).resolve()
        if self._repo_root not in path.parents and path != self._repo_root:
            raise RepoOperationError(f"Path escapes repository root: {relative_path}")
        if not allow_missing and not path.exists():
            raise RepoOperationError(f"File not found: {relative_path}")
        return path
