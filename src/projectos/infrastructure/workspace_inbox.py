"""Founder inbox — deterministic, read-only operational inbox (P22).

Aggregates the existing workspace read-models into one prioritised list of the projects
that need founder attention, so the founder sees — in a single view — what to act on next
and how. It is a pure aggregation layer: it invents no priority, computes no state of its
own, re-derives nothing the read-models already computed, and mutates nothing.

Every row is lifted from existing read-models:

* P20 :func:`build_dashboard` — the sole data source; itself an aggregation of
  P7/P8/P9/P10 plus P16 planner and P19 agent advisor.
* P21 focus ranking (:func:`~projectos.infrastructure.workspace_focus._rank` and its
  category / reason / founder-input maps) — the *same* operational-urgency classification
  the focus selector uses, applied to every actionable project instead of only the top
  one. The classification is imported and reused verbatim; nothing is recomputed here.

Only actionable projects appear (P21 ranks 1 through 5; rank 6 = complete/idle is omitted).
Ordering is by ``(priority, project-id)`` ascending — most urgent first, with a stable
project-id tie-break — so identical state always yields identical output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.infrastructure import workspace_focus as focus
from projectos.infrastructure.workspace_dashboard import (
    DashboardProject,
    build_dashboard,
)
from projectos.infrastructure.workspace_focus import FocusCategory


@dataclass(frozen=True, slots=True)
class InboxItem:
    """One actionable project — every field lifted from the dashboard or P21's ranking."""

    priority: int  # P21 rank (1 = most urgent)
    category: FocusCategory  # P21 category for the rank
    project_id: str
    project_name: str
    assignment: str | None  # P8 (via dashboard): "A-0001 [ACTIVE]"
    reason: str  # P21 verified reason for the category
    next_action: str  # P16 (via dashboard): the recommended action
    command: str | None  # P16 (via dashboard): the one-click command, if any
    recommended_agent: str | None  # P19 (via dashboard)
    founder_input: str  # P21 founder-input guidance for the category


@dataclass(frozen=True, slots=True)
class WorkspaceInbox:
    """The founder's prioritised operational inbox."""

    workspace_name: str
    workspace_root: Path
    items: tuple[InboxItem, ...]

    @property
    def has_integrity_failure(self) -> bool:
        """True when any inbox item is an unsafe integrity failure (P21 rank 1)."""
        return any(item.category is FocusCategory.INTEGRITY_FAILURE for item in self.items)


def build_inbox(workspace_root: Path) -> WorkspaceInbox:
    """Aggregate the existing read-models into the founder's inbox. Strictly read-only.

    Calls :func:`build_dashboard` once (P20 — the sole source), classifies each project
    with P21's existing ranking, and keeps only the projects that need attention. Computes
    no state of its own and mutates nothing. Fails closed on an unresolved workspace
    (raised by the reused dashboard). An empty inbox means no project needs attention.
    """
    dashboard = build_dashboard(workspace_root)  # P20 — the single source of truth

    items: list[InboxItem] = []
    for project in dashboard.projects:
        rank = focus._rank(project)  # P21 classification, reused verbatim (no recompute)
        if rank >= focus._NO_ATTENTION_RANK:
            continue  # complete / idle — nothing for the founder to do
        category = focus._RANK_CATEGORY[rank]
        items.append(
            InboxItem(
                priority=rank,
                category=category,
                project_id=project.project_id,
                project_name=project.name,
                assignment=_assignment(project),
                reason=focus._REASON[category],
                next_action=project.next_action.upper(),  # P16, via the dashboard
                command=project.next_command,  # P16, via the dashboard
                recommended_agent=project.recommended_agent,  # P19, via the dashboard
                founder_input=focus._FOUNDER_INPUT[category],
            )
        )

    # Most urgent first; stable project-id tie-break within a priority. The dashboard is
    # already id-ordered, so this only reorders across priorities.
    items.sort(key=lambda item: (item.priority, item.project_id))

    return WorkspaceInbox(
        workspace_name=dashboard.workspace_name,
        workspace_root=dashboard.workspace_root,
        items=tuple(items),
    )


def _assignment(project: DashboardProject) -> str | None:
    if project.active_assignment is None:
        return None
    return f"{project.active_assignment} [{project.assignment_status}]"


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_inbox(inbox: WorkspaceInbox) -> str:
    """Render the inbox as deterministic, human-readable text. Pure function."""
    lines = [
        f"FOUNDER INBOX  {inbox.workspace_name}  ({len(inbox.items)} needing attention)",
        _RULE,
        f"  root        {inbox.workspace_root}",
    ]
    if not inbox.items:
        lines.append("  inbox empty — no project needs founder attention")
        return "\n".join(lines)

    for item in inbox.items:
        lines.extend(_render_item(item))
    return "\n".join(lines)


def _render_item(item: InboxItem) -> list[str]:
    return [
        "",
        f"  [{item.priority}] {item.category.value}   {item.project_id}  ({item.project_name})",
        f"      assignment    {item.assignment or '—'}",
        f"      why           {item.reason}",
        f"      next action   {item.next_action}",
        f"      agent         {item.recommended_agent or '—'}",
        f"      command       {item.command or '—'}",
        f"      founder       {item.founder_input}",
    ]
