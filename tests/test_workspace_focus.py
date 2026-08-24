"""P21 — Founder focus selector.

`workspace focus` selects the one project most deserving the founder's attention, by
verified operational urgency the P20 dashboard already exposes — never invented
business priority. These tests cover the priority order (integrity → escalation →
blocked → active-external → ready), deterministic stable-id tie-break, the
NO_FOCUS_REQUIRED cases, that the output is grounded in dashboard fields, strict
read-only behavior, and that no dashboard/planner logic is duplicated.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_dashboard import build_dashboard
from projectos.infrastructure.workspace_focus import (
    FocusCategory,
    FocusResult,
    build_focus,
    render_focus,
)
from projectos.infrastructure.workspace_manifest import resolve_workspace
from projectos.infrastructure.yaml_io import read_yaml, write_yaml

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register(workspace: Path, name: str, project_id: str, tmp_path: Path) -> Path:
    repo = tmp_path / f"{project_id}_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", FOUNDER_ID)
    _git(repo, "config", "user.name", "Actor")
    add_project(workspace, name=name, project_id=project_id, repository_path=str(repo))
    init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    return repo


def started(workspace: Path, name: str, project_id: str, tmp_path: Path) -> Path:
    repo = register(workspace, name, project_id, tmp_path)
    main(["workspace", "next", "--workspace", str(workspace), "--project", project_id])
    return repo


def make_integrity_failure(repo: Path) -> None:
    for ndjson in Layout.for_repo(repo).audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")


def make_escalated(workspace: Path, project_id: str) -> None:
    main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
          "--project", project_id, "--assignment", "A-0001", "--summary", "d",
          "--option", "O1|a|b", "--option", "O2|c|d"])


def make_blocked(workspace: Path, project_id: str) -> None:
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", project_id, "--assignment", "A-0001", "--reason", "x"])


def keep_only(workspace: Path, project_ids: set[str]) -> None:
    """Rewrite Workspace.yaml to keep only the named projects (drops ExampleProject),
    so NO_FOCUS scenarios can be exercised without the bootstrap sample project."""
    raw = read_yaml(workspace / "Workspace.yaml")
    raw["projects"] = [p for p in raw.get("projects", []) if _pid(workspace, p) in project_ids]
    write_yaml(workspace / "Workspace.yaml", raw, header="test")


def _pid(workspace: Path, entry: dict[str, str]) -> str:
    # Resolve a registration entry's project.id from its project.yaml.
    manifest = read_yaml(workspace / entry["path"] / "project.yaml")
    return str(manifest["project"]["id"])


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- priority order -----------------------------------------------------------


def test_integrity_failure_is_selected_first(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Escal", "escal", tmp_path)
    make_escalated(workspace, "escal")  # priority 2
    repo = started(workspace, "Broken", "broken", tmp_path)
    make_integrity_failure(repo)  # priority 1

    result = build_focus(workspace)

    assert result.category is FocusCategory.INTEGRITY_FAILURE
    assert result.project_id == "broken"


def test_founder_escalation_before_ordinary_block(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Blk", "blk", tmp_path)
    make_blocked(workspace, "blk")  # priority 3
    started(workspace, "Esc", "esc", tmp_path)
    make_escalated(workspace, "esc")  # priority 2

    result = build_focus(workspace)

    assert result.category is FocusCategory.FOUNDER_DECISION_REQUIRED
    assert result.project_id == "esc"


def test_blocked_before_ready(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Ready", "ready", tmp_path)  # fresh → priority 5
    started(workspace, "Blk", "blk", tmp_path)
    make_blocked(workspace, "blk")  # priority 3

    result = build_focus(workspace)

    assert result.category is FocusCategory.BLOCKED
    assert result.project_id == "blk"


def test_active_external_input_before_ready(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Ready", "ready", tmp_path)  # fresh → priority 5
    started(workspace, "Act", "act", tmp_path)  # ACTIVE → priority 4

    result = build_focus(workspace)

    assert result.category is FocusCategory.EXTERNAL_INPUT_REQUIRED
    assert result.project_id == "act"


def test_ready_to_execute_when_nothing_more_urgent(workspace: Path, tmp_path: Path) -> None:
    keep_only(workspace, {"alpha"})
    register(workspace, "Alpha", "alpha", tmp_path)  # fresh → RUN_COMMAND (next) → priority 5

    result = build_focus(workspace)

    assert result.category is FocusCategory.READY_TO_EXECUTE
    assert result.project_id == "alpha"


# -- deterministic tie-break --------------------------------------------------


def test_deterministic_tie_break_by_project_id(workspace: Path, tmp_path: Path) -> None:
    keep_only(workspace, {"beta", "alpha"})
    started(workspace, "Beta", "beta", tmp_path)  # both ACTIVE → priority 4
    started(workspace, "Alpha", "alpha", tmp_path)

    result = build_focus(workspace)

    assert result.project_id == "alpha"  # stable id order (alpha < beta)
    assert "beta" in result.tie_break  # the loser is named in the explanation


# -- no focus -----------------------------------------------------------------


def test_no_projects_reports_no_focus(workspace: Path) -> None:
    keep_only(workspace, set())  # drop ExampleProject → zero registered projects

    result = build_focus(workspace)

    assert result.category is FocusCategory.NO_FOCUS_REQUIRED
    assert result.project_id is None


def test_all_complete_reports_no_focus(workspace: Path, tmp_path: Path) -> None:
    keep_only(workspace, {"done"})
    repo = started(workspace, "Done", "done", tmp_path)
    # Drive A-0001 to CLOSED so the only project is complete (priority 6, not selected).
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "TASK.md").write_text("# Task\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "task")
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "done", "--assignment", "A-0001"])
    main(["workspace", "assignment", "complete", "--workspace", str(workspace),
          "--project", "done", "--assignment", "A-0001", "--role", "owner"])

    result = build_focus(workspace)

    assert result.category is FocusCategory.NO_FOCUS_REQUIRED


# -- exactly one, grounded in dashboard ---------------------------------------


def test_exactly_one_result(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    result = build_focus(workspace)

    assert isinstance(result, FocusResult)
    assert result.category in FocusCategory


def test_output_is_grounded_in_dashboard_fields(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    result = build_focus(workspace)
    dashboard = build_dashboard(workspace)
    row = next(p for p in dashboard.projects if p.project_id == result.project_id)

    assert result.project_name == row.name
    assert result.recommended_agent == row.recommended_agent  # P19, via the dashboard
    assert row.next_action.upper() in (result.next_action or "")  # P16, via the dashboard
    assert result.assignment == (
        f"{row.active_assignment} [{row.assignment_status}]" if row.active_assignment else None
    )


# -- determinism & read-only --------------------------------------------------


def test_output_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    started(workspace, "Bravo", "bravo", tmp_path)

    first = render_focus(build_focus(workspace))
    second = render_focus(build_focus(workspace))

    assert first == second


def test_focus_changes_nothing_on_disk(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    make_blocked(workspace, "alpha")
    before = snapshot(workspace)

    build_focus(workspace)

    assert snapshot(workspace) == before


def test_cli_focus_is_read_only(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    code = main(["workspace", "focus", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)
    assert snapshot(workspace) == before


def test_cli_focus_integrity_failure_exit_code(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Alpha", "alpha", tmp_path)
    make_integrity_failure(repo)

    code = main(["workspace", "focus", "--workspace", str(workspace)])

    assert code == int(ExitCode.INVARIANT_ERROR)


# -- reuse only: no duplicated logic ------------------------------------------


def test_focus_only_selects_over_the_dashboard() -> None:
    import projectos.infrastructure.workspace_focus as mod

    source = inspect.getsource(mod)
    assert "build_dashboard(" in source  # it selects over the P20 dashboard
    for reimplemented in (
        "verify_integrity(", "open_escalations(", "build_plan(", "build_agent_advice(",
        "build_status(", "build_queue(", "generate_next", "_transition", ".save(",
        "subprocess", "urllib", "anthropic", "openai",
    ):
        assert reimplemented not in source, f"focus must not reimplement {reimplemented}"


def test_p20_dashboard_still_works(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    dashboard = build_dashboard(workspace)

    assert dashboard.workspace_name == "Dogfood"
    assert any(p.project_id == "alpha" for p in dashboard.projects)


def test_focus_resolution_matches_registered_projects(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    make_blocked(workspace, "alpha")

    result = build_focus(workspace)

    assert result.project_id in {p.project_id for p in resolve_workspace(workspace).projects}
