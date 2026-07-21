"""P5 — SensexPilot dogfood: the first real project managed by ProjectOS.

Proves the minimum end-to-end path using existing contracts only:

    workspace load → SensexPilot registration → rapid-build pack load
    → lookup by project identifier → project-kernel resolution
    → one safe lifecycle operation → persisted state verified

SensexPilot's repository (discovered on disk as `C:\\TradeOS-AI`, remote
`rmanish2000-del/tradeos-ai`) is recorded as *remote metadata* — the project kernel
is hosted inside the workspace, so no external repository is written to and no
trading, broker, or market action is possible. No SensexPilot trading logic lives
in ProjectOS Core; the SensexPilot identity is workspace/project data.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from projectos.domain.enums import Status
from projectos.domain.errors import NotFoundError
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    find_project,
    init_project_kernel,
    open_project_kernel,
    project_status,
)
from projectos.infrastructure.workspace_manifest import resolve_workspace

#: SensexPilot's real repository, discovered on disk (remote of C:\TradeOS-AI).
#: Recorded as metadata only; the dogfood never writes to it.
SENSEXPILOT_ID = "sensexpilot"
SENSEXPILOT_REMOTE = "https://github.com/rmanish2000-del/tradeos-ai.git"
FOUNDER = "founder@sensexpilot.test"


def register_sensexpilot(workspace_root: Path) -> None:
    add_project(
        workspace_root,
        name="SensexPilot",
        pack="rapid-build",
        project_id=SENSEXPILOT_ID,
        description="SENSEX options intraday trading platform (dogfood).",
        repository_remote=SENSEXPILOT_REMOTE,
        repository_branch="main",
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "TradeOS-Workspace"
    bootstrap_workspace(root, name="TradeOS")
    register_sensexpilot(root)
    return root


# -- the end-to-end dogfood path ----------------------------------------------


def test_sensexpilot_is_registered_with_a_stable_identifier(workspace: Path) -> None:
    manifest = yaml.safe_load(
        (workspace / "Projects" / "SensexPilot" / "project.yaml").read_text(encoding="utf-8")
    )
    assert manifest["project"]["id"] == SENSEXPILOT_ID
    assert manifest["pack"] == "rapid-build"
    assert manifest["repository"]["remote"] == SENSEXPILOT_REMOTE
    assert "path" not in manifest["repository"]  # external repo, not hosted here


def test_workspace_resolves_sensexpilot_by_identifier(workspace: Path) -> None:
    resolved = resolve_workspace(workspace).by_id(SENSEXPILOT_ID)
    assert resolved is not None
    assert resolved.name == "SensexPilot"
    assert resolved.repository is not None
    assert resolved.repository.remote == SENSEXPILOT_REMOTE

    assert find_project(workspace, SENSEXPILOT_ID) is not None  # by id
    assert find_project(workspace, "SensexPilot") is not None  # by name


def test_rapid_build_pack_loads_for_sensexpilot(workspace: Path) -> None:
    from projectos.infrastructure.pack_loading import load_pack_from_directory

    pack = load_pack_from_directory(workspace / "Shared" / "Packs" / "rapid-build")
    assert pack.name == "rapid-build"
    assert {t.name for t in pack.templates} == {"define-task", "build-task"}


def test_bridge_resolves_the_project_kernel(workspace: Path) -> None:
    init_project_kernel(workspace, name="SensexPilot", founder_id=FOUNDER, founder_name="Founder")
    kernel = open_project_kernel(workspace, "SensexPilot")

    manifest = kernel.manifests.load()
    assert manifest.project_id == SENSEXPILOT_ID
    assert manifest.packs[0].name == "rapid-build"


def test_safe_lifecycle_operation_and_persisted_state(workspace: Path) -> None:
    """The smallest non-destructive lifecycle op: generate the first assignment,
    then verify it is persisted and the integrity chain holds."""
    init_project_kernel(workspace, name="SensexPilot", founder_id=FOUNDER, founder_name="Founder")
    kernel = open_project_kernel(workspace, "SensexPilot")

    result = kernel.lifecycle.generate_next()
    assert result.assignment is not None
    assert result.assignment.origin_template == "define-task"
    assert result.decision.source.startswith("pack.pipeline")

    # Persisted with existing persistence: the assignment file exists in the
    # workspace-hosted project state, and the audit chain verifies.
    state = workspace / "Projects" / "SensexPilot" / ".projectos"
    assert (state / "assignments" / "A-0001.yaml").is_file()
    reloaded = kernel.assignments.get(result.assignment.id)
    assert reloaded.origin_template == "define-task"
    kernel.lifecycle.verify_integrity()  # audit chain + immutable-field digest


def test_state_lives_in_the_workspace_not_the_external_repo(workspace: Path) -> None:
    """No external side effect: the kernel hosts under the workspace, and the
    recorded repository is a remote (no local path to write into)."""
    init_project_kernel(workspace, name="SensexPilot", founder_id=FOUNDER, founder_name="Founder")
    resolved = resolve_workspace(workspace).by_id(SENSEXPILOT_ID)

    status = project_status(workspace, resolved)
    assert status.initialised is True
    assert Path(status.repository).resolve() == (workspace / "Projects" / "SensexPilot").resolve()
    assert resolved.repository.path is None  # nothing points at an external local repo


def test_status_reflects_the_active_assignment(workspace: Path) -> None:
    init_project_kernel(workspace, name="SensexPilot", founder_id=FOUNDER, founder_name="Founder")
    kernel = open_project_kernel(workspace, "SensexPilot")
    result = kernel.lifecycle.generate_next()
    kernel.lifecycle.start(result.assignment.id)

    resolved = resolve_workspace(workspace).by_id(SENSEXPILOT_ID)
    status = project_status(workspace, resolved)
    assert status.active_assignment == "A-0001"
    assert kernel.assignments.get(result.assignment.id).status is Status.ACTIVE


# -- registration API: repository-remote metadata (defect fix) ----------------


def test_add_project_records_repository_remote(tmp_path: Path) -> None:
    """The defect the dogfood exposed: a project could only record a local repo
    PATH, not a remote — so an external repository could not be referenced without
    the kernel writing into it."""
    root = tmp_path / "WS"
    bootstrap_workspace(root)
    add_project(root, name="X", repository_remote="git@example.com:x.git", repository_branch="dev")

    manifest = yaml.safe_load(
        (root / "Projects" / "X" / "project.yaml").read_text(encoding="utf-8")
    )
    assert manifest["repository"] == {
        "remote": "git@example.com:x.git",
        "default_branch": "dev",
        "adapter": "local_git",
    }


def test_add_project_without_repository_omits_the_block(tmp_path: Path) -> None:
    root = tmp_path / "WS"
    bootstrap_workspace(root)
    add_project(root, name="X")

    manifest = yaml.safe_load(
        (root / "Projects" / "X" / "project.yaml").read_text(encoding="utf-8")
    )
    assert "repository" not in manifest


# -- failure cases ------------------------------------------------------------


def test_lookup_of_wrong_identifier_returns_none(workspace: Path) -> None:
    assert resolve_workspace(workspace).by_id("not-sensexpilot") is None
    assert find_project(workspace, "not-sensexpilot") is None


def test_kernel_resolution_before_init_fails_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError, match="no ProjectOS kernel"):
        open_project_kernel(workspace, "SensexPilot")


def test_init_of_unregistered_project_fails_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError, match="not registered"):
        init_project_kernel(workspace, name="Ghost", founder_id=FOUNDER, founder_name="F")
