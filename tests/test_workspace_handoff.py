"""P7 — Canonical workspace handoff.

A fresh AI session should run one documented command and receive a concise,
repository-backed brief. These tests cover a valid handoff, stable ordering across
several projects, project-first resolution, both forms of repository metadata,
missing optional information, malformed manifest/state, deterministic output, and —
the load-bearing guarantee — that producing a handoff changes nothing on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode, NotFoundError, ValidationError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_handoff import (
    build_handoff,
    render_handoff,
)

FOUNDER_ID = "founder@example.com"
FOUNDER_NAME = "Founder"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file under `root`, by relative path — for read-only assertions."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- valid handoff ------------------------------------------------------------


def test_valid_handoff_carries_workspace_identity(workspace: Path) -> None:
    handoff = build_handoff(workspace)

    assert handoff.workspace_name == "Dogfood"
    assert handoff.workspace_root == workspace.resolve()
    assert handoff.manifest_path == workspace.resolve() / "Workspace.yaml"
    assert handoff.schema_version == 1
    assert handoff.focus is None
    # The P3 workspace ships ExampleProject registered.
    assert [p.project_id for p in handoff.projects] == ["example-project"]


def test_configured_packs_are_listed_sorted(workspace: Path) -> None:
    handoff = build_handoff(workspace)

    names = [p.name for p in handoff.packs]
    assert names == sorted(names)
    assert "rapid-build" in names


def test_render_is_nonempty_text(workspace: Path) -> None:
    text = render_handoff(build_handoff(workspace))

    assert "WORKSPACE HANDOFF  Dogfood" in text
    assert "REGISTERED PROJECTS" in text


# -- stable ordering ----------------------------------------------------------


def test_projects_ordered_by_identifier(workspace: Path) -> None:
    add_project(workspace, name="Zeta", project_id="zeta")
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Mid", project_id="mid")

    ids = [p.project_id for p in build_handoff(workspace).projects]

    assert ids == ["alpha", "example-project", "mid", "zeta"]


# -- project-first resolution -------------------------------------------------


def test_project_first_by_id(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    handoff = build_handoff(workspace, project="alpha")

    assert handoff.focus == "alpha"
    assert [p.project_id for p in handoff.projects] == ["alpha"]


def test_project_first_by_registration_name(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    handoff = build_handoff(workspace, project="Alpha")

    assert handoff.focus == "alpha"
    assert handoff.projects[0].name == "Alpha"


def test_project_first_unknown_is_fail_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError, match="not registered"):
        build_handoff(workspace, project="ghost")


# -- repository metadata ------------------------------------------------------


def test_repository_path_metadata(workspace: Path, tmp_path: Path) -> None:
    repo = tmp_path / "external_repo"
    repo.mkdir()
    add_project(workspace, name="Alpha", project_id="alpha", repository_path=str(repo))

    project = build_handoff(workspace, project="alpha").projects[0]

    assert project.repository.path == str(repo)
    assert project.repository.adapter == "local_git"
    # The kernel runs against the declared repository path, not the workspace dir.
    assert project.kernel_location == str(repo.resolve())


def test_repository_remote_and_branch_metadata(workspace: Path) -> None:
    add_project(
        workspace,
        name="Alpha",
        project_id="alpha",
        repository_remote="git@example.com:acme/alpha.git",
        repository_branch="release",
    )

    project = build_handoff(workspace, project="alpha").projects[0]

    assert project.repository.remote == "git@example.com:acme/alpha.git"
    assert project.repository.default_branch == "release"
    assert "remote=git@example.com:acme/alpha.git" in render_handoff(
        build_handoff(workspace, project="alpha")
    )


# -- missing optional information ---------------------------------------------


def test_missing_repository_is_marked_unavailable(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    project = build_handoff(workspace, project="alpha").projects[0]

    assert project.repository.is_empty
    assert "unavailable — none declared" in render_handoff(
        build_handoff(workspace, project="alpha")
    )


def test_uninitialised_kernel_marks_state_unavailable(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    project = build_handoff(workspace, project="alpha").projects[0]

    assert project.initialised is False
    assert project.current_assignment is None
    assert project.integrity is None
    assert project.failure is None


def test_initialised_kernel_reports_integrity(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    init_project_kernel(
        workspace, name="Alpha", founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )

    project = build_handoff(workspace, project="alpha").projects[0]

    assert project.initialised is True
    assert project.failure is None
    assert project.integrity is not None
    assert "audit entries" in project.integrity


# -- malformed manifest / state ----------------------------------------------


def test_malformed_project_manifest_fails_closed(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    # Corrupt the project manifest so schema validation rejects it.
    (workspace / "Projects" / "Alpha" / "project.yaml").write_text(
        "schema_version: 9\nproject:\n  id: alpha\n  name: Alpha\n", encoding="utf-8"
    )

    with pytest.raises(ValidationError):
        build_handoff(workspace)


def test_malformed_kernel_state_reported_per_project(workspace: Path) -> None:
    """A broken/unreadable audit log is reported against its project, not crashed on,
    and does not blank out the rest of the handoff."""
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Bravo", project_id="bravo")
    repo = init_project_kernel(
        workspace, name="Alpha", founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    # A malformed audit entry makes read_all (hence verify_integrity) fail-closed.
    audit_dir = Layout.for_repo(repo).audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "2026-07.ndjson").write_text("{ not valid json\n", encoding="utf-8")

    handoff = build_handoff(workspace)
    by_id = {p.project_id: p for p in handoff.projects}

    assert by_id["alpha"].failure is not None
    assert by_id["alpha"].integrity is None
    # Bravo and ExampleProject are unaffected — the failure is isolated.
    assert by_id["bravo"].failure is None
    assert "FAILURE" in render_handoff(handoff)


# -- determinism --------------------------------------------------------------


def test_output_is_deterministic(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Beta", project_id="beta")

    first = render_handoff(build_handoff(workspace))
    second = render_handoff(build_handoff(workspace))

    assert first == second


# -- read-only ----------------------------------------------------------------


def test_handoff_changes_nothing_on_disk(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    init_project_kernel(
        workspace, name="Alpha", founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    before = snapshot(workspace)

    build_handoff(workspace)
    build_handoff(workspace, project="alpha")

    assert snapshot(workspace) == before


def test_missing_workspace_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        build_handoff(tmp_path / "nope")


# -- CLI ----------------------------------------------------------------------


def test_cli_handoff_ok(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    code = main(["workspace", "handoff", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)


def test_cli_handoff_project_first(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    code = main(
        ["workspace", "handoff", "--workspace", str(workspace), "--project", "alpha"]
    )

    assert code == int(ExitCode.OK)


def test_cli_handoff_reports_integrity_failure_via_exit_code(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    repo = init_project_kernel(
        workspace, name="Alpha", founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    audit_dir = Layout.for_repo(repo).audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "2026-07.ndjson").write_text("{ not valid json\n", encoding="utf-8")

    code = main(["workspace", "handoff", "--workspace", str(workspace)])

    assert code == int(ExitCode.ESCALATION_REQUIRED)


def test_cli_handoff_is_read_only(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    before = snapshot(workspace)

    main(["workspace", "handoff", "--workspace", str(workspace)])

    assert snapshot(workspace) == before
