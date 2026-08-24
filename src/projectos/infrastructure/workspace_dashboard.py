"""Workspace dashboard — one deterministic, read-only founder view (P20).

A pure aggregation layer: it calls the existing workspace read-models and stitches
their outputs together by project id. It computes nothing of its own — every value on
the dashboard is lifted verbatim from one of:

* P7  :func:`build_handoff`      — repository metadata, pack, kernel location
* P8  :func:`build_status`       — workspace health/condition, per-project status, counts
* P9  :func:`build_report`       — doctor outcome and per-project diagnostics
* P10 :func:`build_queue`        — per-project assignment buckets and counts
* P16 :func:`build_plan`         — the next recommended action per project
* P19 :func:`build_agent_advice` — the recommended agent per project

Nothing here writes, transitions, dispatches, or invokes an agent. Ordering follows
the read-models' own stable project-id ordering, so identical state yields identical
output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.domain.errors import NotFoundError
from projectos.infrastructure.workspace_agent_advisor import build_agent_advice
from projectos.infrastructure.workspace_doctor import DiagnosticResult, build_report
from projectos.infrastructure.workspace_handoff import ProjectHandoff, build_handoff
from projectos.infrastructure.workspace_manifest import resolve_workspace
from projectos.infrastructure.workspace_plan import Category as PlanCategory
from projectos.infrastructure.workspace_plan import build_plan
from projectos.infrastructure.workspace_queue import ProjectQueue, build_queue
from projectos.infrastructure.workspace_status import (
    ProjectStatusLine,
    build_status,
)


@dataclass(frozen=True, slots=True)
class DashboardProject:
    """One project's row — every field lifted from an existing read-model."""

    project_id: str
    name: str
    initialised: bool
    active_assignment: str | None  # P8
    assignment_status: str | None  # P8
    recommended_agent: str | None  # P19
    agent_category: str  # P19
    next_action: str  # P16 category
    next_command: str | None  # P16
    queue_active: int  # P10
    queue_ready: int  # P10
    queue_blocked: int  # P10
    queue_completed: int  # P10
    doctor_fail: int  # P9
    doctor_warn: int  # P9
    integrity: str  # P8
    open_escalation: bool  # P16 (FOUNDER_DECISION_REQUIRED)
    is_blocked: bool  # P10 blocked bucket or P16 BLOCKED
    ready_to_execute: bool  # P16/P17 executable action present
    pack: str | None  # P7/P8
    repository: str  # P7


@dataclass(frozen=True, slots=True)
class WorkspaceDashboard:
    """The aggregated founder view."""

    workspace_name: str
    workspace_root: Path
    focus: str | None
    health: str  # P8 condition
    integrity_failures: int  # P8
    doctor_outcome: str  # P9
    project_count: int  # P8
    projects: tuple[DashboardProject, ...]  # displayed rows (filtered by focus)
    active_projects: int  # P8
    blocked_projects: int
    founder_decision_projects: int
    ready_to_execute_projects: int
    completed_work: int  # P10


def build_dashboard(workspace_root: Path, *, project: str | None = None) -> WorkspaceDashboard:
    """Aggregate the existing read-models into one dashboard. Strictly read-only.

    Builds the workspace-wide models once, then the per-project planner/advisor for each
    registered project, and joins by project id. ``project`` filters which rows are
    displayed; the workspace summary is always computed across every project. Fails
    closed on an unresolved workspace/project (raised by the reused models).
    """
    workspace_root = workspace_root.resolve()

    handoff = build_handoff(workspace_root)  # P7
    status = build_status(workspace_root)  # P8
    doctor = build_report(workspace_root)  # P9
    queue = build_queue(workspace_root)  # P10

    handoff_by = {p.project_id: p for p in handoff.projects}
    queue_by = {p.project_id: p for p in queue.projects}
    fail_by: dict[str, int] = {}
    warn_by: dict[str, int] = {}
    for diagnostic in doctor.diagnostics:
        if diagnostic.result is DiagnosticResult.FAIL:
            fail_by[diagnostic.scope] = fail_by.get(diagnostic.scope, 0) + 1
        elif diagnostic.result is DiagnosticResult.WARN:
            warn_by[diagnostic.scope] = warn_by.get(diagnostic.scope, 0) + 1

    rows: list[DashboardProject] = []
    for line in status.projects:  # P8 already orders projects by stable id
        pid = line.project_id
        plan = build_plan(workspace_root, project=pid)  # P16
        agent, agent_category = _agent(workspace_root, pid)  # P19
        rows.append(
            _row(
                line,
                handoff_by.get(pid),
                queue_by.get(pid),
                plan,
                agent,
                agent_category,
                fail_by.get(pid, 0),
                warn_by.get(pid, 0),
            )
        )

    focus = _resolve_focus(workspace_root, project)
    displayed = tuple(r for r in rows if focus is None or r.project_id == focus)

    return WorkspaceDashboard(
        workspace_name=status.workspace_name,
        workspace_root=workspace_root,
        focus=focus,
        health=status.condition.value,  # P8
        integrity_failures=status.integrity_failures,  # P8
        doctor_outcome=doctor.outcome.value,  # P9
        project_count=status.registered_projects,  # P8
        projects=displayed,
        active_projects=status.projects_with_active_assignment,  # P8
        blocked_projects=sum(1 for r in rows if r.is_blocked),
        founder_decision_projects=sum(1 for r in rows if r.open_escalation),
        ready_to_execute_projects=sum(1 for r in rows if r.ready_to_execute),
        completed_work=queue.completed,  # P10
    )


def _agent(workspace_root: Path, project_id: str) -> tuple[str | None, str]:
    """The P19 recommendation, or a neutral marker when there is no in-flight
    assignment / kernel to advise on (build_agent_advice fails closed there)."""
    try:
        advice = build_agent_advice(workspace_root, project=project_id).recommendation
    except NotFoundError:
        return None, "no-assignment"
    return advice.agent, advice.category.value


def _resolve_focus(workspace_root: Path, project: str | None) -> str | None:
    if project is None:
        return None
    workspace = resolve_workspace(workspace_root)
    resolved = workspace.by_id(project) or workspace.by_name(project)
    if resolved is None:
        known = ", ".join(sorted(p.project_id for p in workspace.projects)) or "none"
        raise NotFoundError(
            f"Project {project!r} is not registered in this workspace",
            detail=f"Known project identifiers: {known}.",
        )
    return resolved.project_id


def _row(
    line: ProjectStatusLine,
    handoff: ProjectHandoff | None,
    queue: ProjectQueue | None,
    plan: object,
    agent: str | None,
    agent_category: str,
    doctor_fail: int,
    doctor_warn: int,
) -> DashboardProject:
    from projectos.infrastructure.workspace_plan import Plan

    assert isinstance(plan, Plan)
    recommendation = plan.recommendation
    queue_blocked = queue.bucket("blocked") if queue is not None else ()
    is_blocked = bool(queue_blocked) or recommendation.category is PlanCategory.BLOCKED

    return DashboardProject(
        project_id=line.project_id,
        name=line.name,
        initialised=line.initialised,
        active_assignment=line.active_assignment.id if line.active_assignment else None,
        assignment_status=line.active_assignment.status if line.active_assignment else None,
        recommended_agent=agent,
        agent_category=agent_category,
        next_action=recommendation.category.value,
        next_command=recommendation.command,
        queue_active=len(queue.active) if queue is not None else 0,
        queue_ready=len(queue.ready) if queue is not None else 0,
        queue_blocked=len(queue_blocked),
        queue_completed=len(queue.completed) if queue is not None else 0,
        doctor_fail=doctor_fail,
        doctor_warn=doctor_warn,
        integrity=line.integrity.value,
        open_escalation=recommendation.category is PlanCategory.FOUNDER_DECISION_REQUIRED,
        is_blocked=is_blocked,
        ready_to_execute=recommendation.action is not None,
        pack=line.pack,
        repository=_repository(handoff),
    )


def _repository(handoff: ProjectHandoff | None) -> str:
    if handoff is None or handoff.repository.is_empty:
        return "none"
    repo = handoff.repository
    if repo.remote:
        return f"remote:{repo.remote}"
    if repo.path:
        return f"path:{repo.path}"
    return repo.adapter or "declared"


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_dashboard(dashboard: WorkspaceDashboard) -> str:
    """Render the dashboard as deterministic, human-readable text. Pure function."""
    lines: list[str] = []
    lines.append(f"WORKSPACE DASHBOARD  {dashboard.workspace_name}  [{dashboard.health.upper()}]")
    lines.append(_RULE)
    lines.append(f"  root        {dashboard.workspace_root}")
    lines.append(f"  focus       {dashboard.focus or 'none'}")
    lines.append(
        f"  health {dashboard.health}    integrity-failures {dashboard.integrity_failures}"
        f"    doctor {dashboard.doctor_outcome}    projects {dashboard.project_count}"
    )

    lines.append("")
    lines.append(f"PROJECTS  ({len(dashboard.projects)})")
    if not dashboard.projects:
        lines.append("  none")
    for project in dashboard.projects:
        lines.extend(_render_project(project))

    lines.append("")
    lines.append("WORKSPACE SUMMARY")
    lines.append(_RULE)
    lines.append(f"  active projects            {dashboard.active_projects}")
    lines.append(f"  blocked projects           {dashboard.blocked_projects}")
    lines.append(f"  needing founder decision   {dashboard.founder_decision_projects}")
    lines.append(f"  ready to execute           {dashboard.ready_to_execute_projects}")
    lines.append(f"  completed work             {dashboard.completed_work}")
    return "\n".join(lines)


def _render_project(project: DashboardProject) -> list[str]:
    assignment = (
        f"{project.active_assignment} [{project.assignment_status}]"
        if project.active_assignment
        else "none"
    )
    flags = []
    if project.open_escalation:
        flags.append("FOUNDER-DECISION")
    if project.is_blocked:
        flags.append("BLOCKED")
    if project.ready_to_execute:
        flags.append("READY")
    flag_text = f"    flags: {', '.join(flags)}" if flags else ""
    return [
        "",
        f"  {project.project_id}  ({project.name}){flag_text}",
        f"    assignment   {assignment}    integrity {project.integrity}",
        f"    agent        {project.recommended_agent or '—'}  ({project.agent_category})",
        f"    next action  {project.next_action.upper()}"
        + (f"  →  {project.next_command}" if project.next_command else ""),
        f"    queue        active {project.queue_active}  ready {project.queue_ready}  "
        f"blocked {project.queue_blocked}  completed {project.queue_completed}",
        f"    doctor       fail {project.doctor_fail}  warn {project.doctor_warn}",
        f"    pack         {project.pack or 'none'}    repository {project.repository}",
    ]
