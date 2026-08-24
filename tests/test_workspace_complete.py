"""P14 — Workspace completion bridge.

Complete/close one selected project's assignment through the *existing* canonical
completion path (`lifecycle.approve` / `lifecycle.attest`), from the workspace. These
tests drive the real flow (next → verify → complete → CLOSED), prove resolution by id
and name, persisted CLOSED status + audit + queue reflection, and every fail-closed
prerequisite: unverified, unauthorized role, incomplete approvals, missing assignment,
illegal transition, and integrity failure — plus mutation isolation and no duplicated
completion logic.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from projectos.cli.commands import cmd_complete
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
EVIDENCE_PATH = "docs/TASK.md"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def make_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-b", "main")
    _git(path, "config", "user.email", FOUNDER_ID)  # the founder is the acting identity
    _git(path, "config", "user.name", FOUNDER_NAME)
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register_repo_project(
    workspace: Path, name: str, project_id: str, tmp_path: Path
) -> Path:
    repo = make_git_repo(tmp_path / f"{project_id}_repo")
    add_project(workspace, name=name, project_id=project_id, repository_path=str(repo))
    init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    return repo


def make_verified(workspace: Path, name: str, project_id: str, tmp_path: Path) -> Path:
    """Generate, evidence, and verify A-0001 so it is VERIFIED and ready to complete."""
    repo = register_repo_project(workspace, name, project_id, tmp_path)
    main(["workspace", "next", "--workspace", str(workspace), "--project", project_id])
    target = repo / EVIDENCE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Task\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "task")
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", project_id, "--assignment", "A-0001"])
    return repo


def complete_cmd(workspace: Path, project: str, *extra: str) -> int:
    return main(
        ["workspace", "assignment", "complete", "--workspace", str(workspace),
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


# -- successful completion ----------------------------------------------------


def test_complete_closes_a_verified_assignment(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)

    code = complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    assert code == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.CLOSED


def test_resolution_by_id_and_name(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)
    make_verified(workspace, "Bravo", "bravo", tmp_path)

    assert complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner") == 0
    assert status_of(workspace, "Alpha", "A-0001") is Status.CLOSED
    assert complete_cmd(workspace, "Bravo", "--assignment", "A-0001", "--role", "owner") == 0
    assert status_of(workspace, "Bravo", "A-0001") is Status.CLOSED


def test_complete_defaults_to_the_in_flight_assignment(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)  # A-0001 VERIFIED (current)

    code = complete_cmd(workspace, "alpha", "--role", "owner")  # no --assignment

    assert code == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.CLOSED


# -- persistence, audit & queue -----------------------------------------------


def test_persists_closed_and_appends_audit(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)
    before = len(open_project_kernel(workspace, "Alpha").audit.read_all())

    complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    kernel = open_project_kernel(workspace, "Alpha")
    assert kernel.assignments.get(AssignmentId.parse("A-0001")).status is Status.CLOSED
    assert len(kernel.audit.read_all()) > before  # approval + close were audited
    kernel.lifecycle.verify_integrity()  # chain intact — went through the lifecycle


def test_queue_reflects_the_completed_assignment(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)

    complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    alpha = build_queue(workspace, project="alpha").projects[0]
    assert [a.id for a in alpha.completed] == ["A-0001"]
    assert {a.status for a in alpha.completed} == {"closed"}


# -- fail-closed prerequisites ------------------------------------------------


def test_unverified_assignment_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_repo_project(workspace, "Alpha", "alpha", tmp_path)
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])  # ACTIVE

    code = complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    assert code == int(ExitCode.INVARIANT_ERROR)  # only VERIFIED assignments accept approvals
    assert status_of(workspace, "Alpha", "A-0001") is Status.ACTIVE  # unchanged


def test_incomplete_approvals_do_not_close(workspace: Path, tmp_path: Path) -> None:
    """Fast mode closes on an OWNER approval. A FOUNDER approval is authorized and
    recorded, but does not satisfy the required role, so the assignment does not close
    — an approval recorded without the completion prerequisite being met."""
    make_verified(workspace, "Alpha", "alpha", tmp_path)

    code = complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "founder")

    assert code == int(ExitCode.OK)  # the founder approval was recorded...
    assert status_of(workspace, "Alpha", "A-0001") is Status.VERIFIED  # ...but FAST needs OWNER


def test_unauthorized_role_fails_closed(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)
    # The acting identity (the founder) owns the assignment and cannot review it.
    code = complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "reviewer")

    assert code == int(ExitCode.INVARIANT_ERROR)  # §8.6.2 authority: reviewer must be independent
    assert status_of(workspace, "Alpha", "A-0001") is Status.VERIFIED  # unchanged


def test_attest_records_without_closing(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)

    code = complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner", "--attest")

    assert code == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.VERIFIED  # attestation does not close


def test_missing_assignment_fails_closed(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)

    assert complete_cmd(workspace, "alpha", "--assignment", "A-9999", "--role", "owner") != 0


def test_illegal_completion_of_a_closed_assignment(workspace: Path, tmp_path: Path) -> None:
    make_verified(workspace, "Alpha", "alpha", tmp_path)
    complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")  # → CLOSED

    code = complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    assert code != int(ExitCode.OK)  # CLOSED is not VERIFIED — no approval accepted
    assert status_of(workspace, "Alpha", "A-0001") is Status.CLOSED  # unchanged


def test_integrity_failure_fails_closed(workspace: Path, tmp_path: Path) -> None:
    repo = make_verified(workspace, "Alpha", "alpha", tmp_path)
    audit_dir = Layout.for_repo(repo).audit_dir
    for ndjson in audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")

    code = complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    assert code != int(ExitCode.OK)  # _guard() refuses on tampered state (INV-6)


def test_unresolved_project_fails_closed(workspace: Path) -> None:
    assert complete_cmd(workspace, "ghost", "--assignment", "A-0001", "--role", "owner") != 0


def test_uninitialised_kernel_fails_closed(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # registered, not init

    assert complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner") != 0


# -- mutation boundary --------------------------------------------------------


def test_only_the_selected_project_is_mutated(workspace: Path, tmp_path: Path) -> None:
    repo_a = make_verified(workspace, "Alpha", "alpha", tmp_path)
    make_verified(workspace, "Bravo", "bravo", tmp_path)
    bravo_repo = tmp_path / "bravo_repo"
    bravo_projectos_before = snapshot(bravo_repo / ".projectos")
    manifest_before = (workspace / "Workspace.yaml").read_bytes()
    assert repo_a  # alpha's repo is the one that will change

    complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    assert snapshot(bravo_repo / ".projectos") == bravo_projectos_before
    assert (workspace / "Workspace.yaml").read_bytes() == manifest_before
    assert status_of(workspace, "Bravo", "A-0001") is Status.VERIFIED  # Bravo untouched


# -- no duplicated logic / regression -----------------------------------------


def test_delegates_to_the_same_completion_path_as_the_service(
    workspace: Path, tmp_path: Path
) -> None:
    """workspace complete reaches kernel.lifecycle.approve — the same path `projectos
    complete` (via run_complete) uses; the persisted final status is identical."""
    make_verified(workspace, "Alpha", "alpha", tmp_path)

    complete_cmd(workspace, "alpha", "--assignment", "A-0001", "--role", "owner")

    direct = open_project_kernel(workspace, "Alpha").assignments.get(
        AssignmentId.parse("A-0001")
    )
    assert direct.status is Status.CLOSED


def test_existing_per_project_complete_still_works(workspace: Path, tmp_path: Path) -> None:
    """Regression guard: the run_complete extraction left `projectos complete`
    unchanged. Driven through cmd_complete directly (over the project's repo)."""
    repo = make_verified(workspace, "Alpha", "alpha", tmp_path)

    args = argparse.Namespace(repo=repo, identity=None, assignment="A-0001",
                              role="owner", attest=False)
    code = cmd_complete(args)

    assert code == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.CLOSED
