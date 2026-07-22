"""P22 — Founder inbox.

`workspace inbox` produces the founder's prioritised operational inbox: every project
needing attention, most urgent first, aggregated from the existing read-models (P20
dashboard + P21 ranking). These tests cover the priority ordering, the stable-id
tie-break, that only actionable projects appear, the empty-inbox cases, that every field
is grounded in the dashboard / P21 maps (no recomputation), strict read-only behavior,
determinism, the CLI exit code, and that no read-model logic is duplicated.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode
from projectos.infrastructure import workspace_focus as focus
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_dashboard import build_dashboard
from projectos.infrastructure.workspace_focus import FocusCategory, build_focus
from projectos.infrastructure.workspace_inbox import (
    InboxItem,
    WorkspaceInbox,
    build_inbox,
    render_inbox,
)
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
    so inbox scenarios can be exercised without the bootstrap sample project."""
    raw = read_yaml(workspace / "Workspace.yaml")
    raw["projects"] = [p for p in raw.get("projects", []) if _pid(workspace, p) in project_ids]
    write_yaml(workspace / "Workspace.yaml", raw, header="test")


def _pid(workspace: Path, entry: dict[str, str]) -> str:
    manifest = read_yaml(workspace / entry["path"] / "project.yaml")
    return str(manifest["project"]["id"])


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- priority ordering --------------------------------------------------------


def test_items_ordered_most_urgent_first(workspace: Path, tmp_path: Path) -> None:
    ready = register(workspace, "Ready", "ready", tmp_path)  # rank 5
    _ = ready
    started(workspace, "Ext", "ext", tmp_path)  # ACTIVE → rank 4
    started(workspace, "Blk", "blk", tmp_path)
    make_blocked(workspace, "blk")  # rank 3
    started(workspace, "Esc", "esc", tmp_path)
    make_escalated(workspace, "esc")  # rank 2
    repo = started(workspace, "Broken", "broken", tmp_path)
    make_integrity_failure(repo)  # rank 1
    keep_only(workspace, {"ready", "ext", "blk", "esc", "broken"})

    inbox = build_inbox(workspace)

    assert [item.priority for item in inbox.items] == [1, 2, 3, 4, 5]
    assert [item.project_id for item in inbox.items] == [
        "broken", "esc", "blk", "ext", "ready",
    ]
    assert [item.category for item in inbox.items] == [
        FocusCategory.INTEGRITY_FAILURE,
        FocusCategory.FOUNDER_DECISION_REQUIRED,
        FocusCategory.BLOCKED,
        FocusCategory.EXTERNAL_INPUT_REQUIRED,
        FocusCategory.READY_TO_EXECUTE,
    ]


def test_deterministic_tie_break_by_project_id(workspace: Path, tmp_path: Path) -> None:
    keep_only(workspace, {"beta", "alpha"})
    started(workspace, "Beta", "beta", tmp_path)  # both ACTIVE → rank 4
    started(workspace, "Alpha", "alpha", tmp_path)

    inbox = build_inbox(workspace)

    # Same priority → stable project-id order (alpha before beta).
    assert [item.project_id for item in inbox.items] == ["alpha", "beta"]


def test_completed_project_is_omitted(workspace: Path, tmp_path: Path) -> None:
    keep_only(workspace, {"done", "act"})
    repo = started(workspace, "Done", "done", tmp_path)
    started(workspace, "Act", "act", tmp_path)  # stays actionable (rank 4)
    # Drive "done" to CLOSED so it is complete (rank 6, omitted from the inbox).
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "TASK.md").write_text("# Task\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "task")
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "done", "--assignment", "A-0001"])
    main(["workspace", "assignment", "complete", "--workspace", str(workspace),
          "--project", "done", "--assignment", "A-0001", "--role", "owner"])

    inbox = build_inbox(workspace)

    ids = [item.project_id for item in inbox.items]
    assert "done" not in ids
    assert "act" in ids


# -- empty inbox --------------------------------------------------------------


def test_no_projects_is_empty_inbox(workspace: Path) -> None:
    keep_only(workspace, set())  # drop ExampleProject → zero registered projects

    inbox = build_inbox(workspace)

    assert inbox.items == ()
    assert "inbox empty" in render_inbox(inbox)


def test_all_complete_is_empty_inbox(workspace: Path, tmp_path: Path) -> None:
    keep_only(workspace, {"done"})
    repo = started(workspace, "Done", "done", tmp_path)
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "TASK.md").write_text("# Task\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "task")
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "done", "--assignment", "A-0001"])
    main(["workspace", "assignment", "complete", "--workspace", str(workspace),
          "--project", "done", "--assignment", "A-0001", "--role", "owner"])

    inbox = build_inbox(workspace)

    assert inbox.items == ()


# -- grounded in existing read-models (no recomputation) ----------------------


def test_items_grounded_in_dashboard_and_focus_ranking(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    started(workspace, "Bravo", "bravo", tmp_path)
    make_blocked(workspace, "bravo")

    inbox = build_inbox(workspace)
    dashboard = build_dashboard(workspace)
    by_id = {p.project_id: p for p in dashboard.projects}

    assert isinstance(inbox, WorkspaceInbox)
    for item in inbox.items:
        row = by_id[item.project_id]
        assert isinstance(item, InboxItem)
        assert item.project_name == row.name
        assert item.recommended_agent == row.recommended_agent  # P19, via dashboard
        assert item.command == row.next_command  # P16, via dashboard
        assert item.next_action == row.next_action.upper()  # P16, via dashboard
        assert item.priority == focus._rank(row)  # P21 ranking, reused verbatim
        assert item.assignment == (
            f"{row.active_assignment} [{row.assignment_status}]"
            if row.active_assignment else None
        )


def test_top_of_inbox_matches_focus_selection(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Ready", "ready", tmp_path)
    started(workspace, "Blk", "blk", tmp_path)
    make_blocked(workspace, "blk")

    inbox = build_inbox(workspace)
    selected = build_focus(workspace)  # P21 picks the single most urgent project

    assert inbox.items[0].project_id == selected.project_id
    assert inbox.items[0].category is selected.category


# -- determinism & read-only --------------------------------------------------


def test_output_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    started(workspace, "Bravo", "bravo", tmp_path)

    first = render_inbox(build_inbox(workspace))
    second = render_inbox(build_inbox(workspace))

    assert first == second


def test_inbox_changes_nothing_on_disk(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    make_blocked(workspace, "alpha")
    before = snapshot(workspace)

    build_inbox(workspace)

    assert snapshot(workspace) == before


def test_cli_inbox_is_read_only(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    code = main(["workspace", "inbox", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)
    assert snapshot(workspace) == before


def test_cli_inbox_integrity_failure_exit_code(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Ready", "ready", tmp_path)
    repo = started(workspace, "Broken", "broken", tmp_path)
    make_integrity_failure(repo)

    code = main(["workspace", "inbox", "--workspace", str(workspace)])

    assert code == int(ExitCode.INVARIANT_ERROR)


# -- reuse only: no duplicated logic ------------------------------------------


def test_inbox_only_aggregates_existing_read_models() -> None:
    import projectos.infrastructure.workspace_inbox as mod

    source = inspect.getsource(mod)
    assert "build_dashboard(" in source  # aggregates the P20 dashboard
    assert "workspace_focus" in source  # reuses P21 ranking
    for reimplemented in (
        "build_plan(", "build_agent_advice(", "build_status(", "build_queue(",
        "build_report(", "verify_integrity(", "open_escalations(", "generate_next",
        "_transition", ".save(", "subprocess", "urllib", "anthropic", "openai",
    ):
        assert reimplemented not in source, f"inbox must not reimplement {reimplemented}"


def test_p20_dashboard_and_p21_focus_still_work(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    dashboard = build_dashboard(workspace)
    selected = build_focus(workspace)

    assert dashboard.workspace_name == "Dogfood"
    assert any(p.project_id == "alpha" for p in dashboard.projects)
    assert selected.category in FocusCategory
