"""P20 — Workspace dashboard.

`workspace dashboard` aggregates the existing workspace read-models (P7 handoff, P8
status, P9 doctor, P10 queue, P16 planner, P19 advisor) into one deterministic,
read-only founder view. These tests prove it *lifts* values from those models rather
than recomputing them, that the workspace summary counts are correct, that `--project`
focuses the rows while the summary stays workspace-wide, and that the command is
byte-for-byte read-only.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_agent_advisor import build_agent_advice
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_dashboard import (
    DashboardProject,
    build_dashboard,
    render_dashboard,
)
from projectos.infrastructure.workspace_plan import build_plan
from projectos.infrastructure.workspace_queue import build_queue
from projectos.infrastructure.workspace_status import build_status

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


def block(workspace: Path, project_id: str) -> None:
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", project_id, "--assignment", "A-0001", "--reason", "x"])


def escalate(workspace: Path, project_id: str) -> None:
    main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
          "--project", project_id, "--assignment", "A-0001", "--summary", "d",
          "--option", "O1|a|b", "--option", "O2|c|d"])


def row(workspace: Path, project_id: str, focus: str | None = None) -> DashboardProject:
    dashboard = build_dashboard(workspace, project=focus)
    return next(p for p in dashboard.projects if p.project_id == project_id)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- aggregation --------------------------------------------------------------


def test_aggregates_every_registered_project(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    register(workspace, "Bravo", "bravo", tmp_path)

    dashboard = build_dashboard(workspace)

    # ExampleProject (bootstrap) + Alpha + Bravo.
    assert dashboard.project_count == 3
    assert {p.project_id for p in dashboard.projects} == {"example-project", "alpha", "bravo"}


def test_projects_ordered_deterministically(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Zeta", "zeta", tmp_path)
    started(workspace, "Alpha", "alpha", tmp_path)

    ids = [p.project_id for p in build_dashboard(workspace).projects]

    assert ids == sorted(ids)


# -- values are lifted from the source read-models (no recomputation) ---------


def test_health_and_summary_lifted_from_status_and_queue(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    dashboard = build_dashboard(workspace)
    status = build_status(workspace)  # P8
    queue = build_queue(workspace)  # P10

    assert dashboard.health == status.condition.value  # P8 health, not recomputed
    assert dashboard.integrity_failures == status.integrity_failures  # P8
    assert dashboard.project_count == status.registered_projects  # P8
    assert dashboard.active_projects == status.projects_with_active_assignment  # P8
    assert dashboard.completed_work == queue.completed  # P10


def test_next_action_lifted_from_planner(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    dashboard_row = row(workspace, "alpha")
    plan = build_plan(workspace, project="alpha")  # P16

    assert dashboard_row.next_action == plan.recommendation.category.value
    assert dashboard_row.next_command == plan.recommendation.command


def test_recommended_agent_lifted_from_advisor(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    dashboard_row = row(workspace, "alpha")
    advice = build_agent_advice(workspace, project="alpha").recommendation  # P19

    assert dashboard_row.recommended_agent == advice.agent
    assert dashboard_row.agent_category == advice.category.value


def test_queue_and_doctor_and_repository_are_reflected(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    dashboard_row = row(workspace, "alpha")
    queue_alpha = build_queue(workspace, project="alpha").projects[0]  # P10

    assert dashboard_row.queue_active == len(queue_alpha.active)
    assert dashboard_row.assignment_status == "active"
    assert dashboard_row.pack == "rapid-build"
    assert dashboard_row.repository.startswith("path:")  # P7 repository metadata


# -- state indicators ---------------------------------------------------------


def test_blocked_and_escalation_indicators(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Blk", "blk", tmp_path)
    block(workspace, "blk")
    started(workspace, "Esc", "esc", tmp_path)
    escalate(workspace, "esc")

    blk = row(workspace, "blk")
    esc = row(workspace, "esc")

    assert blk.is_blocked  # P10 blocked bucket
    assert esc.open_escalation  # P16 FOUNDER_DECISION_REQUIRED


def test_workspace_summary_counts(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Active", "active", tmp_path)  # ACTIVE
    started(workspace, "Blocked", "blocked", tmp_path)
    block(workspace, "blocked")
    started(workspace, "Escalated", "escalated", tmp_path)
    escalate(workspace, "escalated")

    dashboard = build_dashboard(workspace)

    assert dashboard.active_projects == 1  # only 'active' has an in-flight assignment
    assert dashboard.blocked_projects >= 2  # blocked + escalated (escalated is blocked-set)
    assert dashboard.founder_decision_projects == 1  # escalated


# -- focus --------------------------------------------------------------------


def test_focus_filters_rows_but_keeps_workspace_summary(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    started(workspace, "Bravo", "bravo", tmp_path)

    focused = build_dashboard(workspace, project="alpha")

    assert [p.project_id for p in focused.projects] == ["alpha"]  # rows filtered
    assert focused.focus == "alpha"
    # The summary still counts every project (both are active).
    assert focused.active_projects == 2


def test_focus_by_name(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    assert build_dashboard(workspace, project="Alpha").focus == "alpha"


def test_unresolved_focus_fails_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError):
        build_dashboard(workspace, project="ghost")


# -- determinism & read-only --------------------------------------------------


def test_output_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    started(workspace, "Bravo", "bravo", tmp_path)

    first = render_dashboard(build_dashboard(workspace))
    second = render_dashboard(build_dashboard(workspace))

    assert first == second


def test_dashboard_changes_nothing_on_disk(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    register(workspace, "Bravo", "bravo", tmp_path)
    before = snapshot(workspace)

    build_dashboard(workspace)
    build_dashboard(workspace, project="alpha")

    assert snapshot(workspace) == before


def test_cli_dashboard_is_read_only(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    code = main(["workspace", "dashboard", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)
    assert snapshot(workspace) == before


# -- reuse only: no duplicated logic ------------------------------------------


def test_dashboard_only_aggregates_the_read_models() -> None:
    """The dashboard calls the six read-model builders and recomputes nothing — it does
    not touch the lifecycle, integrity, escalation, or transition logic directly."""
    import projectos.infrastructure.workspace_dashboard as mod

    source = inspect.getsource(mod)
    # It delegates to every mandated read-model.
    for builder in (
        "build_handoff(", "build_status(", "build_report(", "build_queue(",
        "build_plan(", "build_agent_advice(",
    ):
        assert builder in source, f"dashboard must reuse {builder}"
    # It reimplements none of their internals.
    for reimplemented in (
        "verify_integrity(", "open_escalations(", "generate_next", "legal_events",
        ".save(", "_transition", "lifecycle.", "subprocess", ".approve(",
    ):
        assert reimplemented not in source, f"dashboard must not reimplement {reimplemented}"


def test_source_read_models_still_work(workspace: Path, tmp_path: Path) -> None:
    """Regression: the reused models are unchanged and still callable on their own."""
    started(workspace, "Alpha", "alpha", tmp_path)

    assert build_status(workspace).workspace_name == "Dogfood"
    assert build_plan(workspace, project="alpha").project_id == "alpha"
    assert build_agent_advice(workspace, project="alpha").project_id == "alpha"
