"""P8 — Workspace status.

An operational, read-only view over the same read-model the P7 handoff collects:
is the workspace safe to operate, what is incomplete, what is broken. These tests
cover the healthy/warning/failure conditions, the counts, deterministic ordering,
project-first focus, the actionable-problem list, malformed-manifest reporting, and
the load-bearing guarantee that producing a status changes nothing on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    open_project_kernel,
)
from projectos.infrastructure.workspace_handoff import build_handoff
from projectos.infrastructure.workspace_status import (
    Condition,
    IntegrityState,
    Severity,
    build_status,
    render_status,
)

FOUNDER_ID = "founder@example.com"
FOUNDER_NAME = "Founder"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def initialise(workspace: Path, name: str) -> Path:
    return init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )


def corrupt_audit(repo: Path) -> None:
    audit_dir = Layout.for_repo(repo).audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "2026-07.ndjson").write_text("{ not valid json\n", encoding="utf-8")


# -- healthy ------------------------------------------------------------------


def test_healthy_when_all_initialised_and_packs_present(workspace: Path) -> None:
    # The only registered project (ExampleProject) initialised → nothing incomplete.
    initialise(workspace, "ExampleProject")

    status = build_status(workspace)

    assert status.condition is Condition.HEALTHY
    assert status.problems == ()
    assert status.integrity_failures == 0
    assert "[HEALTHY]" in render_status(status)


# -- multiple projects & counts ----------------------------------------------


def test_counts_across_multiple_projects(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Bravo", project_id="bravo")
    initialise(workspace, "Bravo")

    status = build_status(workspace)

    assert status.registered_projects == 3  # Example + Alpha + Bravo
    assert status.initialised_projects == 1
    assert status.available_packs == len(status.packs) == 7
    # Alpha and ExampleProject uninitialised → two warnings, condition warning.
    assert status.condition is Condition.WARNING


# -- uninitialised warning ----------------------------------------------------


def test_uninitialised_project_is_a_warning(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    status = build_status(workspace)
    alpha = next(p for p in status.projects if p.project_id == "alpha")

    assert alpha.initialised is False
    assert alpha.integrity is IntegrityState.NOT_INITIALISED
    assert any(
        p.scope == "alpha" and p.severity is Severity.WARNING and "not initialised" in p.message
        for p in status.problems
    )


# -- missing pack warning -----------------------------------------------------


def test_missing_configured_pack_path_is_a_warning(workspace: Path) -> None:
    initialise(workspace, "ExampleProject")  # remove the uninitialised warning
    # Remove a configured pack directory that no project depends on.
    import shutil

    shutil.rmtree(workspace / "Shared" / "Packs" / "legal")

    status = build_status(workspace)

    assert status.available_packs == 6
    assert len(status.packs) == 7
    assert status.condition is Condition.WARNING
    assert any(
        p.scope == "workspace" and "legal" in p.message and p.severity is Severity.WARNING
        for p in status.problems
    )


# -- active assignment reporting ----------------------------------------------


def test_active_assignment_is_reported(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    initialise(workspace, "Alpha")
    kernel = open_project_kernel(workspace, "Alpha")
    result = kernel.lifecycle.generate_next()
    assert result.assignment is not None
    kernel.lifecycle.start(result.assignment.id)

    status = build_status(workspace)
    alpha = next(p for p in status.projects if p.project_id == "alpha")

    assert alpha.active_assignment is not None
    assert alpha.active_assignment.id == "A-0001"
    assert status.projects_with_active_assignment == 1


# -- integrity failure --------------------------------------------------------


def test_audit_integrity_failure_is_a_failure(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    repo = initialise(workspace, "Alpha")
    corrupt_audit(repo)

    status = build_status(workspace)
    alpha = next(p for p in status.projects if p.project_id == "alpha")

    assert status.condition is Condition.FAILURE
    assert status.integrity_failures == 1
    assert alpha.integrity is IntegrityState.FAILED
    assert any(
        p.scope == "alpha" and p.severity is Severity.FAILURE for p in status.problems
    )


def test_one_project_failure_does_not_mask_the_others(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Bravo", project_id="bravo")
    initialise(workspace, "Alpha")
    repo = initialise(workspace, "Bravo")
    corrupt_audit(repo)

    status = build_status(workspace)
    alpha = next(p for p in status.projects if p.project_id == "alpha")

    assert alpha.integrity is IntegrityState.VERIFIED  # Alpha unaffected
    assert status.integrity_failures == 1


# -- project-first focus ------------------------------------------------------


def test_focus_by_id_is_marked(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    status = build_status(workspace, project="alpha")

    assert status.focus == "alpha"
    # Focus highlights one project but the counts stay workspace-wide.
    assert status.registered_projects == 2


def test_focus_by_name_resolves_to_id(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    status = build_status(workspace, project="Alpha")

    assert status.focus == "alpha"


def test_unresolved_focus_is_a_failure(workspace: Path) -> None:
    status = build_status(workspace, project="ghost")

    assert status.condition is Condition.FAILURE
    assert status.focus is None
    assert any(
        p.scope == "workspace" and "focus" in p.message and p.severity is Severity.FAILURE
        for p in status.problems
    )


# -- deterministic ordering ---------------------------------------------------


def test_projects_ordered_by_identifier(workspace: Path) -> None:
    add_project(workspace, name="Zeta", project_id="zeta")
    add_project(workspace, name="Alpha", project_id="alpha")

    ids = [p.project_id for p in build_status(workspace).projects]

    assert ids == ["alpha", "example-project", "zeta"]


def test_output_is_deterministic(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Beta", project_id="beta")

    first = render_status(build_status(workspace))
    second = render_status(build_status(workspace))

    assert first == second


# -- malformed manifest -------------------------------------------------------


def test_malformed_workspace_is_reported_as_failure(workspace: Path) -> None:
    (workspace / "Workspace.yaml").write_text(
        "schema_version: 9\nworkspace:\n  name: Broken\n", encoding="utf-8"
    )

    status = build_status(workspace)

    assert status.condition is Condition.FAILURE
    assert status.workspace_name == "Broken"  # best-effort identity is preserved
    assert status.projects == ()
    assert len(status.problems) == 1
    assert status.problems[0].severity is Severity.FAILURE


def test_malformed_project_manifest_is_reported_as_failure(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    (workspace / "Projects" / "Alpha" / "project.yaml").write_text(
        "schema_version: 9\nproject:\n  id: alpha\n  name: Alpha\n", encoding="utf-8"
    )

    status = build_status(workspace)

    assert status.condition is Condition.FAILURE
    assert any(p.severity is Severity.FAILURE for p in status.problems)


def test_missing_workspace_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        build_status(tmp_path / "nope")


# -- read-only ----------------------------------------------------------------


def test_status_changes_nothing_on_disk(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    initialise(workspace, "Alpha")
    before = snapshot(workspace)

    build_status(workspace)
    build_status(workspace, project="alpha")

    assert snapshot(workspace) == before


# -- P7 handoff not regressed / shared collection -----------------------------


def test_status_and_handoff_share_the_same_projects(workspace: Path) -> None:
    """P8 derives from the P7 read-model: same projects, same order, no divergence."""
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Beta", project_id="beta")

    status_ids = [p.project_id for p in build_status(workspace).projects]
    handoff_ids = [p.project_id for p in build_handoff(workspace).projects]

    assert status_ids == handoff_ids


# -- CLI ----------------------------------------------------------------------


def test_cli_status_ok_when_operational(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    code = main(["workspace", "status", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)  # warnings are still operational


def test_cli_status_failure_exit_code(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    repo = initialise(workspace, "Alpha")
    corrupt_audit(repo)

    code = main(["workspace", "status", "--workspace", str(workspace)])

    assert code == int(ExitCode.ESCALATION_REQUIRED)


def test_cli_status_is_read_only(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    before = snapshot(workspace)

    main(["workspace", "status", "--workspace", str(workspace)])

    assert snapshot(workspace) == before
