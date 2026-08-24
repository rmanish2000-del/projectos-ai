"""P4.2 — Minimum workspace wiring: the resolution fields a registered project exposes.

Scope 1 through 3 (a loadable `Shared/Packs/rapid-build`, `workspace add-project`,
`workspace list`, and the workspace → project → repository → kernel bridge) already
existed; these tests pin them as regressions and cover the two fields P4.2 added:
the project-level **workflow mode** and the live **active branch**.

`active_branch` is deliberately environment-dependent and is confined to this resolution
path — the deterministic workspace read-models must never carry it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.enums import WorkflowMode
from projectos.domain.errors import ExitCode
from projectos.infrastructure.pack_loading import load_pack_from_directory
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    active_branch,
    add_project,
    init_project_kernel,
    list_projects,
    open_project_kernel,
)
from projectos.infrastructure.workspace_manifest import resolve_workspace

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Wiring")
    return root


def make_repo(tmp_path: Path, name: str, branch: str = "main") -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", branch)
    _git(repo, "config", "user.email", FOUNDER_ID)
    _git(repo, "config", "user.name", "Actor")
    return repo


# -- scope 1: the seeded pack is valid and loadable ---------------------------


def test_shared_packs_rapid_build_is_loadable(workspace: Path) -> None:
    pack_dir = workspace / "Shared" / "Packs" / "rapid-build"

    pack = load_pack_from_directory(pack_dir)

    assert pack.name == "rapid-build"
    assert pack.version
    assert (pack_dir / "pack.yaml").is_file()


# -- scope 2/3: add-project, list, and the kernel bridge ----------------------


def test_add_project_and_list(workspace: Path, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "tradeos_repo")

    add_project(workspace, name="TradeOS", project_id="tradeos", repository_path=str(repo))
    statuses = list_projects(workspace)

    assert any(s.project_id == "tradeos" for s in statuses)


def test_add_project_is_idempotent(workspace: Path, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "tradeos_repo")

    first = add_project(workspace, name="TradeOS", project_id="tradeos",
                        repository_path=str(repo))
    before = (first / "project.yaml").read_bytes()
    second = add_project(workspace, name="TradeOS", project_id="tradeos",
                         repository_path=str(repo))

    assert first == second
    assert (second / "project.yaml").read_bytes() == before  # unchanged
    assert sum(1 for s in list_projects(workspace) if s.project_id == "tradeos") == 1


def test_bridge_resolves_project_kernel(workspace: Path, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "tradeos_repo")
    add_project(workspace, name="TradeOS", project_id="tradeos", repository_path=str(repo))
    init_project_kernel(workspace, name="TradeOS", founder_id=FOUNDER_ID,
                        founder_name=FOUNDER_NAME)

    kernel = open_project_kernel(workspace, "TradeOS")

    assert kernel.layout.root == repo / ".projectos"


# -- scope 4: all seven resolution fields -------------------------------------


def test_registered_project_resolves_all_required_fields(
    workspace: Path, tmp_path: Path
) -> None:
    repo = make_repo(tmp_path, "tradeos_repo", branch="feature/tradeos")
    add_project(workspace, name="TradeOS", project_id="tradeos", repository_path=str(repo),
                workflow_mode=WorkflowMode.GOVERNED)
    init_project_kernel(workspace, name="TradeOS", founder_id=FOUNDER_ID,
                        founder_name=FOUNDER_NAME)
    main(["workspace", "next", "--workspace", str(workspace), "--project", "tradeos"])

    status = next(s for s in list_projects(workspace) if s.project_id == "tradeos")

    assert status.project_id == "tradeos"  # 1. id
    assert status.name == "TradeOS"  # 1. name
    assert status.repository == str(repo)  # 2. repository path
    assert status.pack == "rapid-build"  # 3. selected pack
    assert status.workflow_mode == WorkflowMode.GOVERNED.value  # 4. workflow mode
    assert status.state_location == str(repo / ".projectos")  # 5. state location
    assert status.active_branch == "feature/tradeos"  # 6. active branch
    assert status.active_assignment == "A-0001"  # 7. active assignment


def test_workflow_mode_defaults_to_fast(workspace: Path, tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "tradeos_repo")
    add_project(workspace, name="TradeOS", project_id="tradeos", repository_path=str(repo))

    manifest = next(
        p.manifest for p in resolve_workspace(workspace).projects if p.project_id == "tradeos"
    )

    assert manifest.workflow_mode is WorkflowMode.FAST


def test_workflow_mode_round_trips_through_the_manifest(
    workspace: Path, tmp_path: Path
) -> None:
    repo = make_repo(tmp_path, "tradeos_repo")
    add_project(workspace, name="TradeOS", project_id="tradeos", repository_path=str(repo),
                workflow_mode=WorkflowMode.REVIEWED)

    manifest = next(
        p.manifest for p in resolve_workspace(workspace).projects if p.project_id == "tradeos"
    )

    assert manifest.workflow_mode is WorkflowMode.REVIEWED


def test_manifest_without_workflow_mode_still_loads(workspace: Path, tmp_path: Path) -> None:
    """Existing project.yaml files predate the field — they must keep loading."""
    repo = make_repo(tmp_path, "legacy_repo")
    project_dir = add_project(workspace, name="Legacy", project_id="legacy",
                              repository_path=str(repo))
    project_yaml = project_dir / "project.yaml"
    kept = [
        line for line in project_yaml.read_text(encoding="utf-8").splitlines()
        if not line.startswith("workflow_mode")
    ]
    project_yaml.write_text("\n".join(kept) + "\n", encoding="utf-8")

    manifest = next(
        p.manifest for p in resolve_workspace(workspace).projects if p.project_id == "legacy"
    )

    assert manifest.workflow_mode is WorkflowMode.FAST  # defaulted, not a load failure


# -- active branch is live, and fail-safe -------------------------------------


def test_active_branch_reads_an_unborn_branch(tmp_path: Path) -> None:
    """A freshly registered repository has no commits yet — still a real branch."""
    repo = make_repo(tmp_path, "fresh", branch="feature/x")

    assert active_branch(repo) == "feature/x"


def test_active_branch_after_a_commit(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "committed", branch="develop")
    (repo / "f.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c")

    assert active_branch(repo) == "develop"


def test_active_branch_is_none_when_detached(tmp_path: Path) -> None:
    repo = make_repo(tmp_path, "detached")
    (repo / "f.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c")
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "checkout", sha],
                   capture_output=True, check=True)

    assert active_branch(repo) is None


def test_active_branch_is_none_outside_a_repository(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert active_branch(plain) is None
    assert active_branch(tmp_path / "does-not-exist") is None


# -- CLI smoke ----------------------------------------------------------------


def test_cli_smoke_init_add_list_resolve(tmp_path: Path) -> None:
    """workspace init → add-project → list → resolve kernel."""
    ws = tmp_path / "WS"
    repo = make_repo(tmp_path, "smoke_repo", branch="main")

    assert main(["workspace", "init", str(ws), "--name", "Smoke"]) == int(ExitCode.OK)
    assert main(["workspace", "add-project", "TradeOS", "--workspace", str(ws),
                 "--repo", str(repo), "--workflow", "reviewed"]) == int(ExitCode.OK)
    assert main(["workspace", "list", "--workspace", str(ws)]) == int(ExitCode.OK)
    init_project_kernel(ws, name="TradeOS", founder_id=FOUNDER_ID,
                        founder_name=FOUNDER_NAME)

    status = next(s for s in list_projects(ws) if s.project_id == "tradeos")
    assert status.workflow_mode == "reviewed"
    assert status.active_branch == "main"
    assert open_project_kernel(ws, "TradeOS").layout.root == repo / ".projectos"


# -- the deterministic read-models must not carry the live branch -------------


def test_deterministic_read_models_do_not_expose_active_branch() -> None:
    """`active_branch` is environment-dependent; it must stay out of the read-models
    whose byte-identical output is a load-bearing guarantee (P7/P8/P20/P21/P22/P23)."""
    import dataclasses

    from projectos.infrastructure.workspace_dashboard import DashboardProject
    from projectos.infrastructure.workspace_handoff import ProjectHandoff
    from projectos.infrastructure.workspace_inbox import InboxItem
    from projectos.infrastructure.workspace_inbox_detail import InboxDetail
    from projectos.infrastructure.workspace_status import ProjectStatusLine

    for model in (ProjectHandoff, ProjectStatusLine, DashboardProject, InboxItem, InboxDetail):
        names = {f.name for f in dataclasses.fields(model)}
        assert "active_branch" not in names, f"{model.__name__} must not carry the live branch"
