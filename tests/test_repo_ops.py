from pathlib import Path

import pytest

from harness_types import ProposedAction
from repo_ops import RepoOperationError, RepoOperations


class DummyGuardrails:
    def verify_workspace(self, test_paths=None):
        return {"stdout": "2 passed in 0.10s", "stderr": "", "returncode": 0}

    def summarize(self, run_result):
        return "Your code passed all 2 tests."


def test_read_only_repo_ops(tmp_path):
    (tmp_path / "main.py").write_text("print('hello')\n")
    repo_ops = RepoOperations(repo_root=tmp_path, testing_guardrails=DummyGuardrails())

    assert "main.py" in repo_ops.list_files()
    assert "hello" in repo_ops.read_file("main.py")
    assert "passed all 2 tests" in repo_ops.summarize_tests()


def test_apply_edit_file_action(tmp_path):
    target = tmp_path / "main.py"
    target.write_text("print('before')\n")
    repo_ops = RepoOperations(repo_root=tmp_path, testing_guardrails=DummyGuardrails())

    result = repo_ops.apply_action(
        ProposedAction(
            action_type="edit_file",
            summary="update main.py",
            target_paths=["main.py"],
            content="print('after')\n",
        )
    )

    assert result == ["Updated main.py."]
    assert target.read_text() == "print('after')\n"


def test_apply_create_file_action(tmp_path):
    repo_ops = RepoOperations(repo_root=tmp_path, testing_guardrails=DummyGuardrails())

    result = repo_ops.apply_action(
        ProposedAction(
            action_type="create_file",
            summary="create notes.txt",
            target_paths=["notes.txt"],
            content="todo\n",
        )
    )

    assert result == ["Created notes.txt."]
    assert (tmp_path / "notes.txt").read_text() == "todo\n"


def test_apply_action_rejects_paths_outside_repo(tmp_path):
    repo_ops = RepoOperations(repo_root=tmp_path, testing_guardrails=DummyGuardrails())

    with pytest.raises(RepoOperationError, match="escapes repository root"):
        repo_ops.apply_action(
            ProposedAction(
                action_type="create_file",
                summary="bad path",
                target_paths=["../outside.txt"],
                content="nope\n",
            )
        )
