"""Local-git adapter tests (spec section 11).

Two properties matter: the adapter reports facts about *committed* history rather
than the working tree, and it declares its missing capabilities honestly so the
kernel can fail dependent rules closed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from projectos.domain.enums import RuleType
from projectos.domain.errors import UnsupportedCapability
from projectos.domain.evidence import EvidenceRule
from projectos.infrastructure.adapters import LocalGitAdapter, UnavailableGitHubAdapter


def commit(repo: Path, path: str, content: str, message: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", path], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", message], check=True, capture_output=True
    )


@pytest.fixture
def adapter(git_repo: Path) -> LocalGitAdapter:
    return LocalGitAdapter(repo_root=git_repo, default_branch="main")


def test_declares_no_pr_ci_or_artifact_capability(adapter: LocalGitAdapter) -> None:
    assert adapter.capabilities() == {"pr": False, "ci": False, "artifacts": False}


def test_file_exists_reports_committed_content(git_repo: Path, adapter: LocalGitAdapter) -> None:
    commit(git_repo, "docs/SPEC.md", "# Spec\n", "add spec")

    fact = adapter.query(EvidenceRule(RuleType.FILE_EXISTS, {"path": "docs/SPEC.md"}))

    assert fact.found


def test_file_exists_is_false_for_an_absent_path(git_repo: Path, adapter: LocalGitAdapter) -> None:
    commit(git_repo, "README.md", "hello\n", "initial")

    fact = adapter.query(EvidenceRule(RuleType.FILE_EXISTS, {"path": "nope.md"}))

    assert not fact.found


def test_uncommitted_file_is_not_evidence(git_repo: Path, adapter: LocalGitAdapter) -> None:
    """Evidence is committed history, not the working tree (risk R-3)."""
    commit(git_repo, "README.md", "hello\n", "initial")
    (git_repo / "draft.md").write_text("not committed\n", encoding="utf-8")

    fact = adapter.query(EvidenceRule(RuleType.FILE_EXISTS, {"path": "draft.md"}))

    assert not fact.found


def test_file_contains_matches_a_regex(git_repo: Path, adapter: LocalGitAdapter) -> None:
    commit(git_repo, "README.md", "# Title\n\nStatus: READY\n", "add readme")

    rule = EvidenceRule(
        RuleType.FILE_CONTAINS, {"path": "README.md", "pattern": r"^Status: READY$"}
    )

    assert adapter.query(rule).found


def test_file_contains_is_false_when_the_pattern_is_absent(
    git_repo: Path, adapter: LocalGitAdapter
) -> None:
    commit(git_repo, "README.md", "# Title\n", "add readme")

    rule = EvidenceRule(RuleType.FILE_CONTAINS, {"path": "README.md", "pattern": "DEPLOYED"})

    assert not adapter.query(rule).found


def test_commit_exists_matches_a_message_pattern(
    git_repo: Path, adapter: LocalGitAdapter
) -> None:
    commit(git_repo, "src/kernel.py", "x = 1\n", "implement the kernel skeleton")

    rule = EvidenceRule(RuleType.COMMIT_EXISTS, {"message_pattern": "(?i)implement"})

    assert adapter.query(rule).found


def test_commit_exists_is_false_for_an_unmatched_pattern(
    git_repo: Path, adapter: LocalGitAdapter
) -> None:
    commit(git_repo, "README.md", "hello\n", "initial")

    rule = EvidenceRule(RuleType.COMMIT_EXISTS, {"message_pattern": "release v9"})

    assert not adapter.query(rule).found


def test_pr_and_ci_rules_are_unsupported(adapter: LocalGitAdapter) -> None:
    """Fails closed with a message naming what is missing (spec 11)."""
    rule = EvidenceRule(RuleType.CI_PASSED, {"ref": "main"})

    with pytest.raises(UnsupportedCapability, match="cannot evaluate ci_passed"):
        adapter.query(rule)


def test_github_adapter_placeholder_fails_closed() -> None:
    """A manifest configured for github must not silently degrade to local-git."""
    adapter = UnavailableGitHubAdapter(owner="acme", repo="widgets")

    with pytest.raises(UnsupportedCapability, match="not implemented"):
        adapter.query(EvidenceRule(RuleType.FILE_EXISTS, {"path": "README.md"}))
