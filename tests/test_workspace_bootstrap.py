"""P3 — workspace bootstrap generator tests.

The generator is pure local-first scaffolding: these tests assert the structure it
lays down, that every generated YAML is valid, and — most importantly — that it is
idempotent and never overwrites a user's edits without `--force`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from projectos.cli.main import main
from projectos.domain.errors import ExitCode
from projectos.infrastructure.workspace import (
    DEFAULT_PACKS,
    PACK_FILES,
    SHARED_DIRS,
    WorkspaceLayout,
    bootstrap_workspace,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "Workspace"
    bootstrap_workspace(root)
    return root


# -- structure ----------------------------------------------------------------


def test_top_level_layout(workspace: Path) -> None:
    assert (workspace / "Workspace.yaml").is_file()
    assert (workspace / "ProjectOS").is_dir()
    assert (workspace / "Shared").is_dir()
    assert (workspace / "Projects").is_dir()


def test_shared_subdirectories(workspace: Path) -> None:
    for subdir in SHARED_DIRS:
        assert (workspace / "Shared" / subdir).is_dir(), subdir


def test_all_default_packs_are_created(workspace: Path) -> None:
    created = {p.name for p in (workspace / "Shared" / "Packs").iterdir() if p.is_dir()}
    assert created == set(DEFAULT_PACKS)


def test_each_pack_has_all_starter_files(workspace: Path) -> None:
    for pack in DEFAULT_PACKS:
        pack_dir = workspace / "Shared" / "Packs" / pack
        for filename in PACK_FILES:
            assert (pack_dir / filename).is_file(), f"{pack}/{filename}"
        assert (pack_dir / "templates").is_dir()


def test_example_project_is_registered(workspace: Path) -> None:
    project = workspace / "Projects" / "ExampleProject" / "project.yaml"
    assert project.is_file()
    data = yaml.safe_load(project.read_text(encoding="utf-8"))
    assert data["project"]["name"] == "ExampleProject"
    assert data["pack"] == "rapid-build"


def test_workspace_manifest_registers_projects_and_packs(workspace: Path) -> None:
    manifest = yaml.safe_load((workspace / "Workspace.yaml").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert manifest["workspace"]["name"] == "Workspace"
    assert {p["name"] for p in manifest["packs"]} == set(DEFAULT_PACKS)
    assert manifest["projects"][0]["name"] == "ExampleProject"
    # Shared pack locations are registered.
    assert manifest["shared"]["packs"] == "Shared/Packs"
    for subdir in SHARED_DIRS:
        assert subdir.lower() in {v.split("/")[-1].lower() for v in manifest["shared"].values()}


def test_every_generated_yaml_is_valid(workspace: Path) -> None:
    files = list(workspace.rglob("*.yaml"))
    assert files
    for path in files:
        yaml.safe_load(path.read_text(encoding="utf-8"))  # raises on invalid


def test_name_defaults_to_directory_name(tmp_path: Path) -> None:
    root = tmp_path / "TradingDesk"
    bootstrap_workspace(root)
    manifest = yaml.safe_load((root / "Workspace.yaml").read_text(encoding="utf-8"))
    assert manifest["workspace"]["name"] == "TradingDesk"


def test_explicit_name_overrides_directory(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    bootstrap_workspace(root, name="Acme Ventures")
    manifest = yaml.safe_load((root / "Workspace.yaml").read_text(encoding="utf-8"))
    assert manifest["workspace"]["name"] == "Acme Ventures"


# -- idempotency --------------------------------------------------------------


def test_first_run_reports_fresh(tmp_path: Path) -> None:
    result = bootstrap_workspace(tmp_path / "Workspace")
    assert result.is_fresh
    assert result.created
    assert not result.kept


def test_second_run_is_a_no_op(workspace: Path) -> None:
    result = bootstrap_workspace(workspace)
    assert not result.is_fresh
    assert result.created == ()
    assert result.kept  # everything preserved


def test_second_run_preserves_user_edits(workspace: Path) -> None:
    readme = workspace / "Shared" / "Packs" / "software" / "README.md"
    readme.write_text("# My customised software pack\n", encoding="utf-8")

    bootstrap_workspace(workspace)  # second run

    assert readme.read_text(encoding="utf-8") == "# My customised software pack\n"


def test_force_overwrites_generated_files(workspace: Path) -> None:
    readme = workspace / "Shared" / "Packs" / "software" / "README.md"
    readme.write_text("# customised\n", encoding="utf-8")

    bootstrap_workspace(workspace, force=True)

    assert readme.read_text(encoding="utf-8") != "# customised\n"
    assert "software pack" in readme.read_text(encoding="utf-8")


def test_partial_workspace_is_completed(tmp_path: Path) -> None:
    """A workspace missing some structure is repaired without touching the rest."""
    root = tmp_path / "Workspace"
    bootstrap_workspace(root)
    # Remove one pack directory entirely.
    import shutil

    shutil.rmtree(root / "Shared" / "Packs" / "legal")
    assert not (root / "Shared" / "Packs" / "legal").exists()

    result = bootstrap_workspace(root)

    assert (root / "Shared" / "Packs" / "legal" / "README.md").is_file()
    assert any(path.startswith("Shared/Packs/legal") for path in result.created)


def test_layout_exists_reflects_manifest(tmp_path: Path) -> None:
    layout = WorkspaceLayout.at(tmp_path / "Workspace")
    assert not layout.exists()
    bootstrap_workspace(tmp_path / "Workspace")
    assert layout.exists()


# -- CLI ----------------------------------------------------------------------


def test_cli_workspace_init(tmp_path: Path, capsys) -> None:
    root = tmp_path / "W"
    code = main(["workspace", "init", str(root)])
    assert code == ExitCode.OK
    assert (root / "Workspace.yaml").is_file()
    assert "WORKSPACE CREATED" in capsys.readouterr().out


def test_cli_workspace_init_is_idempotent(tmp_path: Path, capsys) -> None:
    root = tmp_path / "W"
    assert main(["workspace", "init", str(root)]) == ExitCode.OK
    capsys.readouterr()
    assert main(["workspace", "init", str(root)]) == ExitCode.OK
    out = capsys.readouterr().out
    assert "UPDATED (idempotent)" in out
    assert "created: 0" in out


def test_cli_workspace_default_path(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["workspace", "init"]) == ExitCode.OK
    assert (tmp_path / "Workspace" / "Workspace.yaml").is_file()


def test_cli_workspace_name_flag(tmp_path: Path) -> None:
    root = tmp_path / "W"
    main(["workspace", "init", str(root), "--name", "Portfolio"])
    manifest = yaml.safe_load((root / "Workspace.yaml").read_text(encoding="utf-8"))
    assert manifest["workspace"]["name"] == "Portfolio"
