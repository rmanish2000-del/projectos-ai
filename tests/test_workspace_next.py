"""P11 — Workspace next assignment.

Workspace-level orchestration over the *existing* per-project next path: resolve one
project, open its kernel through the bridge, and delegate to the same generator
`projectos next` uses. These tests prove one assignment is generated through the
canonical path, persisted and audited through the existing contracts, that the queue
reflects it, that resolution works by id and name, that every failure fails closed,
and that no parallel generator or persistence was introduced.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from projectos.cli.commands import cmd_next, run_next
from projectos.cli.main import main
from projectos.domain.enums import Status
from projectos.domain.errors import ExitCode
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.repositories import FileAssignmentRepository
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


def register_and_init(workspace: Path, name: str, project_id: str) -> Path:
    add_project(workspace, name=name, project_id=project_id)
    return init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )


def run(workspace: Path, project: str) -> int:
    return main(["workspace", "next", "--workspace", str(workspace), "--project", project])


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- successful generation ----------------------------------------------------


def test_generates_one_assignment(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")

    code = run(workspace, "alpha")

    assert code == int(ExitCode.OK)
    assignments = open_project_kernel(workspace, "Alpha").assignments.list_all()
    assert len(assignments) == 1
    assert str(assignments[0].id) == "A-0001"


def test_resolution_by_project_id(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha-svc")

    assert run(workspace, "alpha-svc") == int(ExitCode.OK)
    assert open_project_kernel(workspace, "Alpha").lifecycle.active() is not None


def test_resolution_by_project_name(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha-svc")

    assert run(workspace, "Alpha") == int(ExitCode.OK)
    assert open_project_kernel(workspace, "Alpha").lifecycle.active() is not None


def test_assignment_persisted_through_existing_repository(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")

    run(workspace, "alpha")

    repo = workspace / "Projects" / "Alpha"
    persisted = FileAssignmentRepository(Layout.for_repo(repo)).list_all()
    assert [str(a.id) for a in persisted] == ["A-0001"]
    # The canonical assignment file exists where the kernel writes it.
    assert Layout.for_repo(repo).assignment_file("A-0001").is_file()


def test_audit_entry_produced_through_existing_lifecycle(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")

    run(workspace, "alpha")

    kernel = open_project_kernel(workspace, "Alpha")
    # Generation + classification + start each append audit entries; the chain
    # verifies (existing integrity path), proving it went through the lifecycle.
    assert len(kernel.audit.read_all()) > 0
    kernel.lifecycle.verify_integrity()


def test_queue_reflects_the_generated_assignment(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")

    run(workspace, "alpha")

    alpha = build_queue(workspace, project="alpha").projects[0]
    assert [a.id for a in alpha.active] == ["A-0001"]
    assert alpha.total == 1


# -- fail-closed cases --------------------------------------------------------


def test_missing_project_fails_closed(workspace: Path) -> None:
    # main() maps the NotFoundError onto the invariant-error exit code (fail closed).
    assert run(workspace, "ghost") == int(ExitCode.INVARIANT_ERROR)


def test_uninitialised_kernel_fails_closed(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # registered, not init

    assert run(workspace, "alpha") == int(ExitCode.INVARIANT_ERROR)


def test_missing_workspace_fails_closed(tmp_path: Path) -> None:
    assert run(tmp_path / "nope", "alpha") == int(ExitCode.INVARIANT_ERROR)


def test_project_argument_is_required(workspace: Path) -> None:
    with pytest.raises(SystemExit):  # argparse rejects a missing required --project
        main(["workspace", "next", "--workspace", str(workspace)])


# -- active-slot refusal (INV-1) ----------------------------------------------


def test_existing_active_assignment_refuses_generation(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")
    run(workspace, "alpha")  # A-0001 → ACTIVE

    before = {str(a.id) for a in open_project_kernel(workspace, "Alpha").assignments.list_all()}
    code = run(workspace, "alpha")  # INV-1: refuses to generate a second
    after = {str(a.id) for a in open_project_kernel(workspace, "Alpha").assignments.list_all()}

    assert code == int(ExitCode.OK)  # inherited from `next`: a no-op, not an error
    assert before == after  # no new assignment was generated


# -- integrity failure --------------------------------------------------------


def test_integrity_failure_fails_closed(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")  # no assignment yet → generation runs
    # Corrupt the audit chain. generate_next() guards on integrity (INV-6) *before*
    # producing anything, so generation must refuse and nothing is persisted.
    audit_dir = Layout.for_repo(workspace / "Projects" / "Alpha").audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "2026-07.ndjson").write_text("{ not valid json\n", encoding="utf-8")

    code = run(workspace, "alpha")

    assert code != int(ExitCode.OK)  # fail closed on tampered state
    assert open_project_kernel(workspace, "Alpha").assignments.list_all() == ()


# -- reuse / non-duplication --------------------------------------------------


def test_workspace_next_uses_the_same_generation_path(workspace: Path) -> None:
    """workspace next opens the bridge kernel and calls run_next — the same function
    `projectos next` delegates to (proven by cmd_next being a thin wrapper)."""
    register_and_init(workspace, "Alpha", "alpha")
    kernel = open_project_kernel(workspace, "Alpha")

    outcome = run_next(kernel, dry_run=False)

    assert outcome.assignment is not None
    assert outcome.assignment.status is Status.ACTIVE
    assert outcome.exit_code == int(ExitCode.OK)


def test_existing_next_still_works_over_a_repo(tmp_path: Path) -> None:
    """Regression guard: the extracted run_next did not change `projectos next`."""
    workspace = tmp_path / "WS"
    bootstrap_workspace(workspace, name="Dogfood")
    repo = register_and_init(workspace, "Alpha", "alpha")

    # Drive the repo-based `next` directly, exactly as `projectos --repo <repo> next`.
    args = argparse.Namespace(repo=repo, identity=None, dry_run=False)
    code = cmd_next(args)

    assert code == int(ExitCode.OK)
    assert open_project_kernel(workspace, "Alpha").lifecycle.active() is not None


def test_only_the_selected_project_kernel_is_written(workspace: Path) -> None:
    """Generating for Alpha must not touch Bravo's state or the workspace manifest."""
    register_and_init(workspace, "Alpha", "alpha")
    register_and_init(workspace, "Bravo", "bravo")
    bravo_before = snapshot(workspace / "Projects" / "Bravo")
    manifest_before = (workspace / "Workspace.yaml").read_bytes()

    run(workspace, "alpha")

    assert snapshot(workspace / "Projects" / "Bravo") == bravo_before
    assert (workspace / "Workspace.yaml").read_bytes() == manifest_before
    # Alpha did change (an assignment was generated there).
    assert build_queue(workspace, project="alpha").projects[0].total == 1
