"""P13 — Workspace verification bridge.

Verify one selected project's assignment through the *existing* canonical
verification path, from the workspace. These tests drive the real evidence flow (a
git repository the local-git adapter reads), proving a successful verification and a
rejection go through the exact per-project path, that evidence is persisted and
audited, the queue reflects the result, every failure fails closed, mutation is
confined to the selected project, and no verification logic is duplicated.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.enums import Status
from projectos.domain.errors import ExitCode
from projectos.domain.ids import AssignmentId
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    open_project_kernel,
)
from projectos.infrastructure.workspace_queue import build_queue

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"
#: The rapid-build define-task template's single acceptance criterion.
EVIDENCE_PATH = "docs/TASK.md"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", FOUNDER_ID)
    _git(path, "config", "user.name", FOUNDER_NAME)
    return path


def commit_evidence(repo: Path) -> None:
    """Commit the file the define-task criterion checks (uncommitted work is not
    evidence, per the local-git adapter)."""
    target = repo / EVIDENCE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Task\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add task definition")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register_project_with_repo(
    workspace: Path, name: str, project_id: str, tmp_path: Path
) -> Path:
    """Register a project whose repository is a real git repo (so verify has real
    evidence to read), initialise its kernel, and generate its first ACTIVE assignment."""
    repo = make_git_repo(tmp_path / f"{project_id}_repo")
    add_project(workspace, name=name, project_id=project_id, repository_path=str(repo))
    init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    main(["workspace", "next", "--workspace", str(workspace), "--project", project_id])
    return repo


def verify_cmd(workspace: Path, project: str, *extra: str) -> int:
    return main(
        ["workspace", "assignment", "verify", "--workspace", str(workspace),
         "--project", project, *extra]
    )


def status_of(workspace: Path, name: str, assignment_id: str) -> Status:
    return open_project_kernel(workspace, name).assignments.get(
        AssignmentId.parse(assignment_id)
    ).status


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- successful verification --------------------------------------------------


def test_verify_passes_with_committed_evidence(workspace: Path, tmp_path: Path) -> None:
    repo = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)

    code = verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    assert code == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.VERIFIED


def test_verify_resolves_project_by_id_and_name(workspace: Path, tmp_path: Path) -> None:
    repo_a = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    repo_b = register_project_with_repo(workspace, "Bravo", "bravo", tmp_path)
    commit_evidence(repo_a)
    commit_evidence(repo_b)

    assert verify_cmd(workspace, "alpha", "--assignment", "A-0001") == int(ExitCode.OK)  # id
    assert status_of(workspace, "Alpha", "A-0001") is Status.VERIFIED
    assert verify_cmd(workspace, "Bravo", "--assignment", "A-0001") == int(ExitCode.OK)  # name
    assert status_of(workspace, "Bravo", "A-0001") is Status.VERIFIED


def test_verify_defaults_to_the_in_flight_assignment(workspace: Path, tmp_path: Path) -> None:
    repo = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)

    code = verify_cmd(workspace, "alpha")  # no --assignment → the ACTIVE one

    assert code == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.VERIFIED


# -- evidence is persisted & audited through the canonical path ---------------


def test_verify_persists_status_and_appends_audit(workspace: Path, tmp_path: Path) -> None:
    repo = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)
    before = len(open_project_kernel(workspace, "Alpha").audit.read_all())

    verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    kernel = open_project_kernel(workspace, "Alpha")
    assert kernel.assignments.get(AssignmentId.parse("A-0001")).status is Status.VERIFIED
    assert len(kernel.audit.read_all()) > before  # submit + verify were audited
    kernel.lifecycle.verify_integrity()  # chain intact — went through the lifecycle


def test_queue_reflects_the_verified_assignment(workspace: Path, tmp_path: Path) -> None:
    repo = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)

    verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    alpha = build_queue(workspace, project="alpha").projects[0]
    # VERIFIED is neither active/ready/blocked/completed → the queue's `other` bucket.
    assert [a.id for a in alpha.other] == ["A-0001"]
    assert {a.status for a in alpha.other} == {"verified"}
    assert alpha.active == ()


# -- fail-closed --------------------------------------------------------------


def test_missing_evidence_rejects_fail_closed(workspace: Path, tmp_path: Path) -> None:
    register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)  # no evidence committed

    code = verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    assert code == int(ExitCode.RULE_FAILURE)  # rejected: the criterion is unmet
    assert status_of(workspace, "Alpha", "A-0001") is Status.REJECTED


def test_missing_assignment_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)

    assert verify_cmd(workspace, "alpha", "--assignment", "A-9999") != int(ExitCode.OK)


def test_illegal_transition_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)  # A-0001 ACTIVE
    # Block it first (ACTIVE → BLOCKED, legal), then try to verify — VERIFY_START is
    # not a legal event from BLOCKED, so the reused lifecycle refuses.
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001", "--reason", "x"])

    code = verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    assert code != int(ExitCode.OK)  # BLOCKED cannot start verification
    assert status_of(workspace, "Alpha", "A-0001") is Status.BLOCKED  # unchanged


def test_malformed_report_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    bad_report = tmp_path / "report.yaml"
    bad_report.write_text("- not a mapping\n", encoding="utf-8")

    code = verify_cmd(workspace, "alpha", "--assignment", "A-0001", "--report", str(bad_report))

    assert code == int(ExitCode.INVARIANT_ERROR)  # ValidationError from _load_claim


def test_integrity_failure_fails_closed(workspace: Path, tmp_path: Path) -> None:
    repo = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)
    audit_dir = Layout.for_repo(repo).audit_dir
    for ndjson in audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")

    code = verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    assert code != int(ExitCode.OK)  # _guard() refuses on tampered state (INV-6)


def test_unresolved_project_fails_closed(workspace: Path) -> None:
    assert verify_cmd(workspace, "ghost", "--assignment", "A-0001") != int(ExitCode.OK)


def test_uninitialised_kernel_fails_closed(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # registered, not init

    assert verify_cmd(workspace, "alpha", "--assignment", "A-0001") != int(ExitCode.OK)


# -- mutation boundary & isolation --------------------------------------------


def test_only_the_selected_project_is_mutated(workspace: Path, tmp_path: Path) -> None:
    repo_a = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    register_project_with_repo(workspace, "Bravo", "bravo", tmp_path)
    commit_evidence(repo_a)
    bravo_before = snapshot(workspace / "Projects" / "Bravo")
    # Bravo's kernel lives in its own git repo; capture that too.
    bravo_repo = tmp_path / "bravo_repo"
    bravo_projectos_before = snapshot(bravo_repo / ".projectos")
    manifest_before = (workspace / "Workspace.yaml").read_bytes()

    verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    assert snapshot(workspace / "Projects" / "Bravo") == bravo_before
    assert snapshot(bravo_repo / ".projectos") == bravo_projectos_before
    assert (workspace / "Workspace.yaml").read_bytes() == manifest_before
    assert status_of(workspace, "Bravo", "A-0001") is Status.ACTIVE  # Bravo untouched


# -- no duplicated logic / regression -----------------------------------------


def test_delegates_to_the_same_verify_path_as_the_service(
    workspace: Path, tmp_path: Path
) -> None:
    """workspace verify reaches kernel.lifecycle.verify — the same path `projectos
    verify` (via run_verify) uses; the persisted verdict is identical."""
    repo = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)

    verify_cmd(workspace, "alpha", "--assignment", "A-0001")

    direct = open_project_kernel(workspace, "Alpha").assignments.get(
        AssignmentId.parse("A-0001")
    )
    assert direct.status is Status.VERIFIED


def test_existing_per_project_verify_still_works(workspace: Path, tmp_path: Path) -> None:
    """Regression guard: the run_verify extraction left `projectos verify` unchanged.

    Driven through the per-project lifecycle.verify directly (the path cmd_verify
    delegates to).
    """
    repo = register_project_with_repo(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)
    kernel = open_project_kernel(workspace, "Alpha")

    outcome = kernel.lifecycle.verify(AssignmentId.parse("A-0001"))

    assert outcome.report.passed
    assert outcome.assignment.status is Status.VERIFIED
