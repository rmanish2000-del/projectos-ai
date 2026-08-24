"""Founder focus selector — deterministic, read-only single-project selection (P21).

Given the whole workspace, pick the *one* project most deserving the founder's
attention — by verified operational urgency already exposed by the P20 dashboard, never
by invented business priority. It is a pure selection layer over
:func:`build_dashboard`: it computes no state of its own, re-derives nothing the
dashboard already computed, and mutates nothing.

Priority order (most urgent first), each mapped to a field the dashboard already
carries — from P16 planner categories, P10 queue state, and P9/P8 signals:

1. integrity / malformed-state failure   — P16 category BLOCKED
2. founder decision / open escalation     — P16 FOUNDER_DECISION_REQUIRED
3. blocked project                        — P10 queue blocked bucket
4. active project needing external input  — P16 EXTERNAL_INPUT_REQUIRED
5. ready-to-execute project               — P16 RUN_COMMAND
6. completed / no-action                  — P16 COMPLETE (never selected)

Within a priority the choice is stable project-id order — the dashboard already orders
projects by id, so the first match wins. No revenue, deadline, customer-value, or
business-impact signal is invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from projectos.infrastructure.workspace_dashboard import (
    DashboardProject,
    build_dashboard,
)
from projectos.infrastructure.workspace_plan import Category as PlanCategory


class FocusCategory(StrEnum):
    """The category of the selected focus (or that none is required)."""

    INTEGRITY_FAILURE = "integrity-failure"
    FOUNDER_DECISION_REQUIRED = "founder-decision-required"
    BLOCKED = "blocked"
    EXTERNAL_INPUT_REQUIRED = "external-input-required"
    READY_TO_EXECUTE = "ready-to-execute"
    NO_FOCUS_REQUIRED = "no-focus-required"


#: Priority rank (lower = more urgent) → the focus category it selects.
_RANK_CATEGORY: dict[int, FocusCategory] = {
    1: FocusCategory.INTEGRITY_FAILURE,
    2: FocusCategory.FOUNDER_DECISION_REQUIRED,
    3: FocusCategory.BLOCKED,
    4: FocusCategory.EXTERNAL_INPUT_REQUIRED,
    5: FocusCategory.READY_TO_EXECUTE,
}
#: Rank 6 (COMPLETE) and anything unclassified do not need attention.
_NO_ATTENTION_RANK = 6

_REASON: dict[FocusCategory, str] = {
    FocusCategory.INTEGRITY_FAILURE:
        "audit integrity could not be verified — the project is unsafe to operate on",
    FocusCategory.FOUNDER_DECISION_REQUIRED:
        "an open escalation awaits a founder decision",
    FocusCategory.BLOCKED:
        "an assignment is blocked and cannot progress",
    FocusCategory.EXTERNAL_INPUT_REQUIRED:
        "the active assignment needs external input (implementation / evidence) to proceed",
    FocusCategory.READY_TO_EXECUTE:
        "a next action is available for the founder to run",
}

_FOUNDER_INPUT: dict[FocusCategory, str] = {
    FocusCategory.INTEGRITY_FAILURE:
        "investigate and repair the audit chain; do not operate until resolved",
    FocusCategory.FOUNDER_DECISION_REQUIRED:
        "a founder decision to resolve the open escalation",
    FocusCategory.BLOCKED:
        "clear the blocking dependency, then unblock the assignment",
    FocusCategory.EXTERNAL_INPUT_REQUIRED:
        "implementation and committed evidence for the assignment's acceptance criteria",
    FocusCategory.READY_TO_EXECUTE:
        "run the next recommended action (some actions also need explicit inputs)",
}


@dataclass(frozen=True, slots=True)
class FocusResult:
    """Exactly one focus selection (or that none is required)."""

    workspace_name: str
    workspace_root: Path
    category: FocusCategory
    project_id: str | None
    project_name: str | None
    reason: str
    assignment: str | None
    recommended_agent: str | None
    next_action: str | None
    founder_input: str
    tie_break: str


def build_focus(workspace_root: Path) -> FocusResult:
    """Select the single most urgent project from the P20 dashboard. Read-only.

    Fails closed on a missing workspace (raised by the reused dashboard). Reports
    ``NO_FOCUS_REQUIRED`` when there are no projects or every project is complete.
    """
    dashboard = build_dashboard(workspace_root)  # P20 — the sole source of truth

    # The dashboard already orders projects by stable id, so the first project at the
    # minimum rank is the stable-id winner without any re-sorting here.
    ranked = [(_rank(project), project) for project in dashboard.projects]
    attention = [(rank, project) for rank, project in ranked if rank < _NO_ATTENTION_RANK]

    if not attention:
        return FocusResult(
            workspace_name=dashboard.workspace_name,
            workspace_root=dashboard.workspace_root,
            category=FocusCategory.NO_FOCUS_REQUIRED,
            project_id=None,
            project_name=None,
            reason="no project needs founder attention"
            + (" — every project is complete or idle" if dashboard.projects else " — no projects"),
            assignment=None,
            recommended_agent=None,
            next_action=None,
            founder_input="none",
            tie_break="no attention-needing project",
        )

    min_rank = min(rank for rank, _ in attention)
    at_min = [project for rank, project in attention if rank == min_rank]
    selected = at_min[0]  # first in id order (dashboard-ordered)
    category = _RANK_CATEGORY[min_rank]

    if len(at_min) == 1:
        tie_break = f"the only project at priority {min_rank} ({category.value})"
    else:
        others = ", ".join(p.project_id for p in at_min[1:])
        tie_break = (
            f"{len(at_min)} projects at priority {min_rank} ({category.value}); "
            f"chosen by stable project-id order over: {others}"
        )

    return FocusResult(
        workspace_name=dashboard.workspace_name,
        workspace_root=dashboard.workspace_root,
        category=category,
        project_id=selected.project_id,
        project_name=selected.name,
        reason=_REASON[category],
        assignment=_assignment(selected),
        recommended_agent=selected.recommended_agent,
        next_action=_next_action(selected),
        founder_input=_FOUNDER_INPUT[category],
        tie_break=tie_break,
    )


def _rank(project: DashboardProject) -> int:
    """Map a dashboard row to its priority rank using only fields it already carries."""
    if project.next_action == PlanCategory.BLOCKED.value:  # P16 BLOCKED = integrity
        return 1
    if project.open_escalation:  # P16 FOUNDER_DECISION_REQUIRED
        return 2
    if project.queue_blocked > 0:  # P10 queue blocked bucket (escalated already ranked 2)
        return 3
    if project.next_action == PlanCategory.EXTERNAL_INPUT_REQUIRED.value:
        return 4
    if project.next_action == PlanCategory.RUN_COMMAND.value:
        return 5
    return _NO_ATTENTION_RANK  # COMPLETE / no action


def _assignment(project: DashboardProject) -> str | None:
    if project.active_assignment is None:
        return None
    return f"{project.active_assignment} [{project.assignment_status}]"


def _next_action(project: DashboardProject) -> str:
    if project.next_command:
        return f"{project.next_action.upper()}  →  {project.next_command}"
    return project.next_action.upper()


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_focus(result: FocusResult) -> str:
    """Render the focus selection as deterministic, human-readable text. Pure."""
    lines = [
        f"FOUNDER FOCUS  {result.workspace_name}  [{result.category.value.upper()}]",
        _RULE,
        f"  workspace       {result.workspace_name}  ({result.workspace_root})",
    ]
    if result.category is FocusCategory.NO_FOCUS_REQUIRED:
        lines.append(f"  focus           none — {result.reason}")
        return "\n".join(lines)

    lines.extend(
        [
            f"  project         {result.project_name}  ({result.project_id})",
            f"  category        {result.category.value}",
            f"  reason          {result.reason}",
            f"  assignment      {result.assignment or '—'}",
            f"  agent           {result.recommended_agent or '—'}",
            f"  next action     {result.next_action or '—'}",
            f"  founder input   {result.founder_input}",
            f"  tie-break       {result.tie_break}",
        ]
    )
    return "\n".join(lines)
