"""P6 — Workspace discovery & auto-registration.

Registration (P4.2) is one project at a time and intentional. Discovery is the
standard onboarding mechanism that scales it: drop a project directory under the
workspace's `Projects/` area and let discovery find, validate, classify, and
(on request) register it. These tests cover successful discovery, the duplicate
and invalid classifications, dry-run vs register modes, non-destructive registration,
and idempotent repeated execution.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import add_project
from projectos.infrastructure.workspace_discovery import (
    DEFAULT_MAX_DEPTH,
    DiscoveryReport,
    DiscoveryStatus,
    discover_workspace,
)
from projectos.infrastructure.workspace_manifest import resolve_workspace
from projectos.infrastructure.yaml_io import write_yaml

HEADER = "test project manifest"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A bootstrapped workspace — ships one registered project, ExampleProject."""
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def drop_project(
    workspace_root: Path,
    name: str,
    *,
    project_id: str,
    pack: str = "rapid-build",
    repository: dict[str, str] | None = None,
    rel_dir: str | None = None,
) -> Path:
    """Write a valid `project.yaml` on disk *without* registering it — the exact
    situation discovery exists to detect. `rel_dir` overrides the default flat
    `Projects/<name>` location to exercise the bounded walk."""
    project_dir = workspace_root / (rel_dir or f"Projects/{name}")
    body: dict[str, object] = {
        "schema_version": 1,
        "project": {"id": project_id, "name": name, "description": f"{name} desc"},
        "pack": pack,
    }
    if repository is not None:
        body["repository"] = repository
    write_yaml(project_dir / "project.yaml", body, header=HEADER)
    return project_dir


def status_of(report: DiscoveryReport, rel_path: str) -> DiscoveryStatus:
    return next(p.status for p in report.projects if p.rel_path == rel_path)


# -- successful discovery -----------------------------------------------------


def test_discovers_unregistered_project(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")

    report = discover_workspace(workspace)

    assert report.scanned == 2  # ExampleProject + Alpha
    assert status_of(report, "Projects/ExampleProject") is DiscoveryStatus.REGISTERED
    assert status_of(report, "Projects/Alpha") is DiscoveryStatus.UNREGISTERED
    assert {p.rel_path for p in report.unregistered} == {"Projects/Alpha"}


def test_existing_registration_is_recognised(workspace: Path) -> None:
    """The P3 ExampleProject ships registered and must classify as REGISTERED."""
    report = discover_workspace(workspace)

    assert [p.rel_path for p in report.already_registered] == ["Projects/ExampleProject"]
    assert not report.unregistered


def test_bounded_walk_finds_a_nested_project(workspace: Path) -> None:
    drop_project(workspace, "Beta", project_id="beta", rel_dir="Projects/group/Beta")

    report = discover_workspace(workspace)

    assert status_of(report, "Projects/group/Beta") is DiscoveryStatus.UNREGISTERED


def test_walk_stops_at_project_boundary(workspace: Path) -> None:
    """A project directory is a boundary — nested `project.yaml` below it is not
    a separate candidate."""
    drop_project(workspace, "Alpha", project_id="alpha")
    drop_project(
        workspace, "Inner", project_id="inner", rel_dir="Projects/Alpha/vendor/Inner"
    )

    report = discover_workspace(workspace)

    rel_paths = {p.rel_path for p in report.projects}
    assert "Projects/Alpha" in rel_paths
    assert "Projects/Alpha/vendor/Inner" not in rel_paths


def test_ignore_rules_skip_dot_and_vendor_dirs(workspace: Path) -> None:
    drop_project(workspace, "Hidden", project_id="hidden", rel_dir="Projects/.hidden")
    drop_project(
        workspace, "Vendored", project_id="vendored", rel_dir="Projects/node_modules/v"
    )

    report = discover_workspace(workspace)

    assert {p.rel_path for p in report.projects} == {"Projects/ExampleProject"}


def test_depth_bound_does_not_recurse_forever(workspace: Path) -> None:
    deep = "Projects/" + "/".join(f"d{i}" for i in range(DEFAULT_MAX_DEPTH + 2))
    drop_project(workspace, "TooDeep", project_id="too-deep", rel_dir=deep)

    report = discover_workspace(workspace)

    # Beyond the depth bound, the candidate is simply never reached — no error.
    assert all(p.name != "TooDeep" for p in report.projects)


# -- duplicate identifiers ----------------------------------------------------


def test_duplicate_identifier_between_candidates(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="dup")
    drop_project(workspace, "Bravo", project_id="dup")

    report = discover_workspace(workspace)

    statuses = {p.rel_path: p.status for p in report.projects}
    # Alpha sorts first, claims the id; Bravo is the duplicate.
    assert statuses["Projects/Alpha"] is DiscoveryStatus.UNREGISTERED
    assert statuses["Projects/Bravo"] is DiscoveryStatus.DUPLICATE_IDENTIFIER
    bravo = next(p for p in report.projects if p.rel_path == "Projects/Bravo")
    assert bravo.conflicts_with == "Projects/Alpha"


def test_duplicate_identifier_against_registered_project(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    drop_project(workspace, "Clone", project_id="alpha")

    report = discover_workspace(workspace)

    clone = next(p for p in report.projects if p.rel_path == "Projects/Clone")
    assert clone.status is DiscoveryStatus.DUPLICATE_IDENTIFIER
    assert clone.conflicts_with == "Alpha"  # the registered project's name


def test_register_skips_duplicate_identifier(workspace: Path) -> None:
    """Only the canonical candidate is registered; registering the duplicate too
    would break the fail-closed unique-identifier rule of resolve_workspace."""
    drop_project(workspace, "Alpha", project_id="dup")
    drop_project(workspace, "Bravo", project_id="dup")

    discover_workspace(workspace, register=True, dry_run=False)

    workspace_obj = resolve_workspace(workspace)  # must not raise
    assert workspace_obj.by_name("Alpha") is not None
    assert workspace_obj.by_name("Bravo") is None


# -- duplicate repositories ---------------------------------------------------


def test_duplicate_repository_between_candidates(workspace: Path) -> None:
    remote = {"remote": "git@example.com:acme/shared.git"}
    drop_project(workspace, "Alpha", project_id="alpha", repository=remote)
    drop_project(workspace, "Bravo", project_id="bravo", repository=remote)

    report = discover_workspace(workspace)

    statuses = {p.rel_path: p.status for p in report.projects}
    assert statuses["Projects/Alpha"] is DiscoveryStatus.UNREGISTERED
    assert statuses["Projects/Bravo"] is DiscoveryStatus.DUPLICATE_REPOSITORY


def test_projects_without_repository_do_not_collide(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")
    drop_project(workspace, "Bravo", project_id="bravo")

    report = discover_workspace(workspace)

    assert not report.duplicates
    assert len(report.unregistered) == 2


# -- invalid manifests --------------------------------------------------------


def test_invalid_manifest_is_reported_not_fatal(workspace: Path) -> None:
    drop_project(workspace, "Good", project_id="good")
    # Bad schema_version fails schema validation (fail-closed load).
    (workspace / "Projects" / "Bad").mkdir(parents=True)
    (workspace / "Projects" / "Bad" / "project.yaml").write_text(
        "schema_version: 2\nproject:\n  id: bad\n  name: Bad\n", encoding="utf-8"
    )

    report = discover_workspace(workspace)

    bad = next(p for p in report.projects if p.rel_path == "Projects/Bad")
    assert bad.status is DiscoveryStatus.INVALID
    assert bad.error is not None
    assert bad.project_id is None
    # The valid one alongside it is still classified normally.
    assert status_of(report, "Projects/Good") is DiscoveryStatus.UNREGISTERED


def test_register_never_registers_invalid(workspace: Path) -> None:
    (workspace / "Projects" / "Bad").mkdir(parents=True)
    (workspace / "Projects" / "Bad" / "project.yaml").write_text(
        "schema_version: 1\nproject:\n  name: Bad\n", encoding="utf-8"  # missing id
    )

    discover_workspace(workspace, register=True, dry_run=False)

    assert resolve_workspace(workspace).by_name("Bad") is None


# -- dry-run mode -------------------------------------------------------------


def test_dry_run_changes_no_state(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")
    manifest_path = workspace / "Workspace.yaml"
    before = manifest_path.read_bytes()

    report = discover_workspace(workspace, register=True, dry_run=True)

    assert manifest_path.read_bytes() == before  # dry-run overrides register
    assert report.dry_run is True
    assert not report.newly_registered
    assert resolve_workspace(workspace).by_name("Alpha") is None


def test_default_is_report_only(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")
    before = (workspace / "Workspace.yaml").read_bytes()

    discover_workspace(workspace)  # no register flag

    assert (workspace / "Workspace.yaml").read_bytes() == before


# -- registration mode --------------------------------------------------------


def test_register_registers_valid_unregistered(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")

    report = discover_workspace(workspace, register=True, dry_run=False)

    assert report.dry_run is False
    assert [p.rel_path for p in report.newly_registered] == ["Projects/Alpha"]
    resolved = resolve_workspace(workspace).by_name("Alpha")
    assert resolved is not None
    assert resolved.project_id == "alpha"


def test_registration_preserves_existing_project_yaml(workspace: Path) -> None:
    """Discovery registers the workspace entry but must not rewrite the project's
    own on-disk manifest."""
    project_dir = drop_project(workspace, "Alpha", project_id="alpha")
    before = (project_dir / "project.yaml").read_bytes()

    discover_workspace(workspace, register=True, dry_run=False)

    assert (project_dir / "project.yaml").read_bytes() == before


def test_registration_preserves_prior_registrations(workspace: Path) -> None:
    add_project(workspace, name="Existing", project_id="existing")
    drop_project(workspace, "Alpha", project_id="alpha")

    discover_workspace(workspace, register=True, dry_run=False)

    workspace_obj = resolve_workspace(workspace)
    assert workspace_obj.by_name("Existing") is not None
    assert workspace_obj.by_name("Alpha") is not None
    assert workspace_obj.by_name("ExampleProject") is not None


# -- idempotency --------------------------------------------------------------


def test_repeated_registration_is_idempotent(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")

    discover_workspace(workspace, register=True, dry_run=False)
    after_first = (workspace / "Workspace.yaml").read_bytes()
    second = discover_workspace(workspace, register=True, dry_run=False)

    assert (workspace / "Workspace.yaml").read_bytes() == after_first
    assert not second.newly_registered
    assert status_of(second, "Projects/Alpha") is DiscoveryStatus.REGISTERED


def test_repeated_discovery_is_stable(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")

    first = discover_workspace(workspace)
    second = discover_workspace(workspace)

    assert [(p.rel_path, p.status) for p in first.projects] == [
        (p.rel_path, p.status) for p in second.projects
    ]


# -- errors -------------------------------------------------------------------


def test_missing_workspace_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        discover_workspace(tmp_path / "nope")


# -- CLI ----------------------------------------------------------------------


def test_cli_discover_reports_ok(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")

    code = main(["workspace", "discover", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)
    # default is report-only
    assert resolve_workspace(workspace).by_name("Alpha") is None


def test_cli_discover_register(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")

    code = main(["workspace", "discover", "--workspace", str(workspace), "--register"])

    assert code == int(ExitCode.OK)
    assert resolve_workspace(workspace).by_name("Alpha") is not None


def test_cli_discover_register_with_dry_run_is_report_only(workspace: Path) -> None:
    drop_project(workspace, "Alpha", project_id="alpha")

    code = main(
        ["workspace", "discover", "--workspace", str(workspace), "--register", "--dry-run"]
    )

    assert code == int(ExitCode.OK)
    assert resolve_workspace(workspace).by_name("Alpha") is None
