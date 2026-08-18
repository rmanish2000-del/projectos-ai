"""One command births a fleet-aligned project (PROJECT-BOOTSTRAP).

Offline: git and gh are stubbed; the scaffold's own file work is real
against tmp directories standing in for C:\\ and the Drive root.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from projectos.domain.errors import ValidationError
from projectos.infrastructure.project_bootstrap import (
    delete_project,
    scaffold_project,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "templates" / "project-pack"


def _ok_runner(log: list[list[str]]) -> Callable[[list[str], Path], tuple[int, str]]:
    def run(args: list[str], cwd: Path) -> tuple[int, str]:
        log.append(args)
        return 0, "stub ok"

    return run


class TestScaffold:
    def test_full_scaffold_produces_every_artifact(self, tmp_path: Path) -> None:
        parent, drive = tmp_path / "c", tmp_path / "drive"
        parent.mkdir(), drive.mkdir()
        calls: list[list[str]] = []
        result = scaffold_project(
            "Testos", "A throwaway drill project",
            projects_parent=parent, drive_root=drive,
            templates_dir=TEMPLATES, run=_ok_runner(calls),
        )
        assert result.ok, [s for s in result.steps if not s.ok]
        local = parent / "Testos"
        for artifact in (
            "README_FOR_AI.md", "wake-prompt.md", "build_order.json",
            ".gitignore", "docs/README.md", "docs/wake-task.cmd",
        ):
            assert (local / artifact).exists(), artifact
        # Tokens are filled, not left as markers.
        readme = (local / "README_FOR_AI.md").read_text(encoding="utf-8")
        assert "Testos" in readme
        assert "__NAME__" not in readme
        # Drive contract: three folders + DOCS, three INBOX assignments, pointer.
        for folder in ("AGENT-REPORTS/DOCS", "INBOX", "DONE"):
            assert (drive / "Testos" / folder).is_dir()
        inbox = sorted(p.name for p in (drive / "Testos" / "INBOX").iterdir())
        assert len(inbox) == 3
        assert any("CHAT-01" in n for n in inbox)
        assert (drive / "Testos" / "AGENT-REPORTS" / "DOCS" / "SEAT-BOOT-POINTER.txt").exists()
        # FLEET-ROOT created with header and the PENDING row.
        fleet = (drive / "FLEET-ROOT.md").read_text(encoding="utf-8")
        assert "only declaration of project roots" in fleet
        assert "| Testos |" in fleet
        assert "PENDING founder ratification" in fleet
        # Pointer is exactly three lines and names the project.
        lines = [line for line in result.pointer_text.strip().splitlines() if line.strip()]
        assert len(lines) == 3
        assert "Testos" in result.pointer_text
        # gh created a PRIVATE repo and pushed; git ran init/add/commit.
        gh_calls = [c for c in calls if c[0] == "gh"]
        assert gh_calls
        assert "--private" in gh_calls[0]
        assert "--push" in gh_calls[0]

    def test_invalid_name_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            scaffold_project("bad name!", "desc", projects_parent=tmp_path, drive_root=tmp_path)

    def test_empty_description_is_refused(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError):
            scaffold_project("Fine", "   ", projects_parent=tmp_path, drive_root=tmp_path)

    def test_existing_local_dir_is_never_overwritten(self, tmp_path: Path) -> None:
        (tmp_path / "Testos").mkdir()
        result = scaffold_project(
            "Testos", "desc", projects_parent=tmp_path, drive_root=tmp_path / "d",
            templates_dir=TEMPLATES, run=_ok_runner([]),
        )
        assert not result.ok
        assert "refusing to overwrite" in result.steps[-1].detail

    def test_failed_git_step_stops_the_sequence(self, tmp_path: Path) -> None:
        parent, drive = tmp_path / "c", tmp_path / "drive"
        parent.mkdir(), drive.mkdir()

        def failing(args: list[str], cwd: Path) -> tuple[int, str]:
            return (128, "boom") if args[0] == "git" else (0, "ok")

        result = scaffold_project(
            "Testos", "desc", projects_parent=parent, drive_root=drive,
            templates_dir=TEMPLATES, run=failing,
        )
        assert not result.ok
        # Nothing after git ran: no GitHub step, no Drive folders.
        assert [s.step for s in result.steps if not s.ok] == ["git"]
        assert not (drive / "Testos").exists()

    def test_github_failure_leaves_no_drive_state(self, tmp_path: Path) -> None:
        parent, drive = tmp_path / "c", tmp_path / "drive"
        parent.mkdir(), drive.mkdir()

        def gh_fails(args: list[str], cwd: Path) -> tuple[int, str]:
            return (1, "HTTP 403") if args[0] == "gh" else (0, "ok")

        result = scaffold_project(
            "Testos", "desc", projects_parent=parent, drive_root=drive,
            templates_dir=TEMPLATES, run=gh_fails,
        )
        assert not result.ok
        assert not (drive / "Testos").exists()


class TestDelete:
    def test_delete_removes_local_drive_and_fleet_row(self, tmp_path: Path) -> None:
        parent, drive = tmp_path / "c", tmp_path / "drive"
        parent.mkdir(), drive.mkdir()
        scaffold_project(
            "Testos", "desc", projects_parent=parent, drive_root=drive,
            templates_dir=TEMPLATES, run=_ok_runner([]),
        )
        steps = delete_project(
            "Testos", projects_parent=parent, drive_root=drive, run=_ok_runner([])
        )
        assert not (parent / "Testos").exists()
        assert not (drive / "Testos").exists()
        assert "| Testos |" not in (drive / "FLEET-ROOT.md").read_text(encoding="utf-8")
        assert all(s.ok for s in steps)

    def test_github_scope_failure_is_recorded_as_blocked(self, tmp_path: Path) -> None:
        def no_scope(args: list[str], cwd: Path) -> tuple[int, str]:
            return (1, "HTTP 403: Must have admin rights / delete_repo scope")

        steps = delete_project(
            "Testos", projects_parent=tmp_path, drive_root=tmp_path, run=no_scope
        )
        github = next(s for s in steps if s.step == "github")
        assert not github.ok
        assert "BLOCKED" in github.detail
