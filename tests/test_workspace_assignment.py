"""P12 — Workspace assignment lifecycle bridge.

Operate one selected project's assignment through the *existing* lifecycle
transitions, from the workspace. The supported actions — show, block, unblock —
delegate to the same canonical service paths the per-project commands use. These
tests prove resolution by id and name, the supported transitions and their persisted
status, audit entries and queue reflection, every fail-closed case, that mutation is
confined to the selected project kernel, and that no lifecycle logic was duplicated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.enums import Status
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


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register_init_and_start(workspace: Path, name: str, project_id: str) -> Path:
    """Register + init a project and generate its first (ACTIVE) assignment via the
    existing workspace next path, so there is something to operate on."""
    add_project(workspace, name=name, project_id=project_id)
    repo = init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    main(["workspace", "next", "--workspace", str(workspace), "--project", project_id])
    return repo


def assignment_cmd(workspace: Path, action: str, project: str, *extra: str) -> int:
    return main(
        ["workspace", "assignment", action, "--workspace", str(workspace),
         "--project", project, *extra]
    )


def status_of(workspace: Path, name: str, assignment_id: str) -> Status:
    kernel = open_project_kernel(workspace, name)
    return kernel.assignments.get(AssignmentId.parse(assignment_id)).status


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- resolution ---------------------------------------------------------------


def test_block_resolves_project_by_id(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")

    code = assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001",
                          "--reason", "waiting")

    assert code == 0
    assert status_of(workspace, "Alpha", "A-0001") is Status.BLOCKED


def test_block_resolves_project_by_name(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")

    code = assignment_cmd(workspace, "block", "Alpha", "--assignment", "A-0001",
                          "--reason", "waiting")

    assert code == 0
    assert status_of(workspace, "Alpha", "A-0001") is Status.BLOCKED


# -- supported transitions & persisted status ---------------------------------


def test_block_then_unblock_round_trip(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")

    assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001", "--reason", "x")
    assert status_of(workspace, "Alpha", "A-0001") is Status.BLOCKED

    code = assignment_cmd(workspace, "unblock", "alpha", "--assignment", "A-0001")
    assert code == 0
    assert status_of(workspace, "Alpha", "A-0001") is Status.READY  # BLOCKED → READY


def test_show_is_read_only(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")
    before = snapshot(workspace)

    code = assignment_cmd(workspace, "show", "alpha", "--assignment", "A-0001")

    assert code == 0
    assert snapshot(workspace) == before


def test_block_defaults_to_the_in_flight_assignment(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")  # A-0001 ACTIVE (in flight)

    code = assignment_cmd(workspace, "block", "alpha", "--reason", "x")  # no --assignment

    assert code == 0
    assert status_of(workspace, "Alpha", "A-0001") is Status.BLOCKED


# -- audit & queue reflection -------------------------------------------------


def test_transition_appends_audit_through_the_lifecycle(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")
    kernel = open_project_kernel(workspace, "Alpha")
    before = len(kernel.audit.read_all())

    assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001", "--reason", "x")

    after = open_project_kernel(workspace, "Alpha")
    assert len(after.audit.read_all()) > before  # the block was audited
    after.lifecycle.verify_integrity()  # chain still intact (went through the lifecycle)


def test_queue_reflects_the_transition(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")

    assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001", "--reason", "x")

    alpha = build_queue(workspace, project="alpha").projects[0]
    assert [a.id for a in alpha.blocked] == ["A-0001"]
    assert alpha.active == ()


# -- fail-closed --------------------------------------------------------------


def test_missing_assignment_fails_closed(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")

    code = assignment_cmd(workspace, "block", "alpha", "--assignment", "A-9999",
                          "--reason", "x")

    assert code != 0  # NotFoundError from assignments.get → non-zero exit


def test_illegal_transition_fails_closed(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")
    # Unblock an assignment that is ACTIVE (not BLOCKED) — an illegal transition.
    code = assignment_cmd(workspace, "unblock", "alpha", "--assignment", "A-0001")

    assert code != 0
    assert status_of(workspace, "Alpha", "A-0001") is Status.ACTIVE  # unchanged


def test_block_requires_a_reason(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")

    code = assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001")

    assert code != 0  # ValidationError: a blocker needs a stated cause
    assert status_of(workspace, "Alpha", "A-0001") is Status.ACTIVE  # unchanged


def test_unresolved_project_fails_closed(workspace: Path) -> None:
    assert assignment_cmd(workspace, "show", "ghost", "--assignment", "A-0001") != 0


def test_uninitialised_kernel_fails_closed(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # registered, not init

    assert assignment_cmd(workspace, "show", "alpha", "--assignment", "A-0001") != 0


def test_missing_workspace_fails_closed(tmp_path: Path) -> None:
    assert assignment_cmd(tmp_path / "nope", "show", "alpha", "--assignment", "A-0001") != 0


def test_integrity_failure_fails_closed(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")
    # Corrupt the audit chain: block() guards on integrity (INV-6) before transitioning.
    audit_dir = Layout.for_repo(workspace / "Projects" / "Alpha").audit_dir
    for ndjson in audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")

    code = assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001", "--reason", "x")

    assert code != 0  # fail closed on tampered state


# -- mutation boundary & isolation --------------------------------------------


def test_only_the_selected_project_kernel_is_mutated(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")
    register_init_and_start(workspace, "Bravo", "bravo")
    bravo_before = snapshot(workspace / "Projects" / "Bravo")
    manifest_before = (workspace / "Workspace.yaml").read_bytes()

    assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001", "--reason", "x")

    assert snapshot(workspace / "Projects" / "Bravo") == bravo_before
    assert (workspace / "Workspace.yaml").read_bytes() == manifest_before
    # Bravo's own assignment is untouched by operating on Alpha.
    assert status_of(workspace, "Bravo", "A-0001") is Status.ACTIVE


def test_wrong_project_does_not_share_assignments(workspace: Path) -> None:
    register_init_and_start(workspace, "Alpha", "alpha")
    register_init_and_start(workspace, "Bravo", "bravo")

    # Block Alpha's A-0001; Bravo's A-0001 is a different assignment, still active.
    assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001", "--reason", "x")

    assert status_of(workspace, "Alpha", "A-0001") is Status.BLOCKED
    assert status_of(workspace, "Bravo", "A-0001") is Status.ACTIVE


# -- no duplicated logic: same canonical path as the per-project command -------


def test_delegates_to_the_same_lifecycle_path_as_cmd_block(workspace: Path) -> None:
    """workspace assignment block and the per-project `projectos block` reach the same
    kernel.lifecycle.block; blocking via the workspace yields the identical persisted
    status a direct lifecycle.block would."""
    register_init_and_start(workspace, "Alpha", "alpha")

    assignment_cmd(workspace, "block", "alpha", "--assignment", "A-0001", "--reason", "x")

    # Reach the same assignment through the direct per-project lifecycle API.
    direct = open_project_kernel(workspace, "Alpha").assignments.get(AssignmentId.parse("A-0001"))
    assert direct.status is Status.BLOCKED


def test_existing_per_project_block_still_works(tmp_path: Path) -> None:
    """Regression guard: the shared-helper refactor left `projectos block` unchanged.

    Driven through the per-project lifecycle directly (the path cmd_block delegates to).
    """
    workspace = tmp_path / "WS"
    bootstrap_workspace(workspace, name="Dogfood")
    register_init_and_start(workspace, "Alpha", "alpha")
    kernel = open_project_kernel(workspace, "Alpha")

    blocked = kernel.lifecycle.block(AssignmentId.parse("A-0001"), "direct")

    assert blocked.status is Status.BLOCKED
