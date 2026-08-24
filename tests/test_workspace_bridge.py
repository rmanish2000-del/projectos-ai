"""P4.2 — workspace→project-kernel bridge tests.

Covers the three prerequisites P5 needs: rapid-build as a loadable pack, the
bridge that scaffolds and operates a project's kernel from a workspace pack, and
the minimal add-project / list registration surface. Idempotency and read-only
status are asserted throughout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from projectos.application.validation_service import validate_pack
from projectos.cli.main import main
from projectos.domain.errors import ExitCode, NotFoundError, ValidationError
from projectos.infrastructure.pack_loading import load_pack_from_directory
from projectos.infrastructure.template_binding import YamlTemplateBinder
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    list_projects,
    open_project_kernel,
)

FOUNDER = "f@e.test"


def git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(path), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", FOUNDER], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "F"], check=True, capture_output=True
    )
    return path


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


# -- rapid-build is a loadable pack -------------------------------------------


def test_rapid_build_pack_loads_and_validates(workspace: Path) -> None:
    pack_dir = workspace / "Shared" / "Packs" / "rapid-build"
    assert (pack_dir / "pack.yaml").is_file()

    pack = load_pack_from_directory(pack_dir)
    assert pack.name == "rapid-build"
    assert pack.requires_projectos == ">=0.1.0,<0.2.0"
    assert {t.name for t in pack.templates} == {"define-task", "build-task"}

    report = validate_pack(pack, binder=YamlTemplateBinder())
    assert report.ok, [f.message for f in report.errors]


def test_other_packs_remain_skeletons(workspace: Path) -> None:
    for pack in ("software", "trading", "legal"):
        assert not (workspace / "Shared" / "Packs" / pack / "pack.yaml").exists()


def test_cli_pack_validate_passes_on_rapid_build(workspace: Path) -> None:
    path = workspace / "Shared" / "Packs" / "rapid-build"
    assert main(["pack", "validate", str(path)]) == ExitCode.OK


# -- registration -------------------------------------------------------------


def test_add_project_registers_in_workspace_and_writes_manifest(workspace: Path) -> None:
    add_project(workspace, name="Alpha", pack="rapid-build")

    manifest = yaml.safe_load((workspace / "Workspace.yaml").read_text(encoding="utf-8"))
    assert any(p["name"] == "Alpha" for p in manifest["projects"])
    project = yaml.safe_load(
        (workspace / "Projects" / "Alpha" / "project.yaml").read_text(encoding="utf-8")
    )
    assert project["project"]["id"] == "alpha"
    assert project["pack"] == "rapid-build"


def test_add_project_records_repository(workspace: Path, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    add_project(workspace, name="Alpha", repository_path=str(repo))

    project = yaml.safe_load(
        (workspace / "Projects" / "Alpha" / "project.yaml").read_text(encoding="utf-8")
    )
    assert project["repository"]["path"] == str(repo)
    assert project["repository"]["adapter"] == "local_git"


def test_add_project_is_idempotent(workspace: Path) -> None:
    add_project(workspace, name="Alpha", pack="rapid-build")
    add_project(workspace, name="Alpha", pack="rapid-build")

    manifest = yaml.safe_load((workspace / "Workspace.yaml").read_text(encoding="utf-8"))
    assert sum(1 for p in manifest["projects"] if p["name"] == "Alpha") == 1


def test_add_project_requires_a_workspace(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError, match="No workspace"):
        add_project(tmp_path / "nope", name="Alpha")


# -- kernel bridge ------------------------------------------------------------


def test_init_project_kernel_scaffolds_from_the_pack(workspace: Path, tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "repo")
    add_project(workspace, name="Alpha", pack="rapid-build", repository_path=str(repo))

    returned = init_project_kernel(
        workspace, name="Alpha", founder_id=FOUNDER, founder_name="F"
    )

    assert returned == repo
    assert (repo / ".projectos" / "manifest.yaml").is_file()
    assert (repo / ".projectos" / "packs" / "rapid-build" / "pack.yaml").is_file()
    manifest = yaml.safe_load((repo / ".projectos" / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["packs"][0]["name"] == "rapid-build"


def test_init_project_kernel_is_idempotent(workspace: Path, tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "repo")
    add_project(workspace, name="Alpha", repository_path=str(repo))
    init_project_kernel(workspace, name="Alpha", founder_id=FOUNDER, founder_name="F")

    # Create an assignment, then re-init without --force: must not wipe state.
    kernel = open_project_kernel(workspace, "Alpha")
    kernel.lifecycle.generate_next()
    before = sorted((repo / ".projectos" / "assignments").glob("A-*.yaml"))

    init_project_kernel(workspace, name="Alpha", founder_id=FOUNDER, founder_name="F")

    after = sorted((repo / ".projectos" / "assignments").glob("A-*.yaml"))
    assert before  # the generated assignment exists
    assert after == before  # re-init left it untouched


def test_init_project_kernel_rejects_a_non_loadable_pack(workspace: Path, tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "repo")
    add_project(workspace, name="Alpha", pack="software", repository_path=str(repo))  # skeleton

    with pytest.raises(ValidationError, match="not loadable"):
        init_project_kernel(workspace, name="Alpha", founder_id=FOUNDER, founder_name="F")


def test_next_flow_generates_from_rapid_build(workspace: Path, tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "repo")
    add_project(workspace, name="Alpha", pack="rapid-build", repository_path=str(repo))
    init_project_kernel(workspace, name="Alpha", founder_id=FOUNDER, founder_name="F")

    kernel = open_project_kernel(workspace, "Alpha")
    result = kernel.lifecycle.generate_next()

    assert result.assignment is not None
    assert result.assignment.origin_template == "define-task"
    assert result.decision.source.startswith("pack.pipeline")


def test_open_project_kernel_requires_init(workspace: Path) -> None:
    add_project(workspace, name="Alpha", pack="rapid-build")
    with pytest.raises(NotFoundError, match="no ProjectOS kernel"):
        open_project_kernel(workspace, "Alpha")


# -- status (read-only) -------------------------------------------------------


def test_list_projects_reflects_state(workspace: Path, tmp_path: Path) -> None:
    repo = git_repo(tmp_path / "repo")
    add_project(workspace, name="Alpha", pack="rapid-build", repository_path=str(repo))
    init_project_kernel(workspace, name="Alpha", founder_id=FOUNDER, founder_name="F")
    kernel = open_project_kernel(workspace, "Alpha")
    result = kernel.lifecycle.generate_next()
    kernel.lifecycle.start(result.assignment.id)

    statuses = {s.name: s for s in list_projects(workspace)}

    # The P3 default project is still listed (backward compatible), uninitialised.
    assert statuses["ExampleProject"].initialised is False
    alpha = statuses["Alpha"]
    assert alpha.initialised is True
    assert alpha.active_assignment == "A-0001"
    assert alpha.repository == str(repo)


# -- CLI ----------------------------------------------------------------------


def test_cli_add_init_list_next(tmp_path: Path, capsys) -> None:
    ws = tmp_path / "WS"
    repo = git_repo(tmp_path / "repo")
    assert main(["workspace", "init", str(ws), "--name", "Dogfood"]) == ExitCode.OK
    capsys.readouterr()

    assert main(
        ["workspace", "add-project", "Alpha", "--workspace", str(ws),
         "--pack", "rapid-build", "--repo", str(repo)]
    ) == ExitCode.OK
    assert main(
        ["workspace", "init-project", "Alpha", "--workspace", str(ws),
         "--founder-id", FOUNDER, "--founder-name", "F"]
    ) == ExitCode.OK
    assert main(["--repo", str(repo), "--identity", FOUNDER, "next"]) == ExitCode.OK
    capsys.readouterr()

    assert main(["workspace", "list", "--workspace", str(ws)]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "Alpha" in out
    assert "A-0001" in out
    assert "initialised" in out


def test_cli_list_on_fresh_p3_workspace(tmp_path: Path, capsys) -> None:
    ws = tmp_path / "WS"
    main(["workspace", "init", str(ws)])
    capsys.readouterr()

    assert main(["workspace", "list", "--workspace", str(ws)]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "ExampleProject" in out
    assert "not initialised" in out
