"""Founder inbox detail — deterministic, read-only drill-down for one project (P23).

`workspace inbox --project <id>` explains a single Founder Inbox item and shows the
evidence behind its recommended next action. It adds no priority, classification, or
recommendation of its own — every displayed value is lifted from an existing read-model:

* P20 :func:`build_dashboard` — resolves the project (fails closed on an unknown id) and
  supplies the structural row: next action, command, recommended agent, integrity, and
  the blocker signals it already computed.
* P22 :func:`build_inbox` — supplies this project's classified inbox item (priority,
  focus category, verified reason, founder input) — i.e. the P21 focus ranking, reused
  verbatim. ``None`` when the project needs no attention (rank 6, complete/idle).
* P7 :func:`build_handoff` — supplies the authoritative integrity summary (or failure
  text) and the current assignment's identity, fail-closed and reporting.
* The kernel's own read path (:func:`open_project_kernel` → ``lifecycle.current()``) —
  supplies the current assignment's persisted metadata that no aggregate read-model
  surfaces: owner, objective (the current goal), dependencies, and evidence references.
  Read only when the kernel is initialised and its chain verifies; a fault is caught and
  reported, never invented.

Strictly read-only and deterministic: no ranking/classification/recommendation is
recomputed, no new business rule is introduced, nothing is written, and identical state
yields identical output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.domain.assignment import Assignment
from projectos.domain.errors import ProjectOSError
from projectos.infrastructure.workspace_bridge import open_project_kernel
from projectos.infrastructure.workspace_dashboard import DashboardProject, build_dashboard
from projectos.infrastructure.workspace_focus import FocusCategory
from projectos.infrastructure.workspace_handoff import build_handoff
from projectos.infrastructure.workspace_inbox import InboxItem, build_inbox

UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class InboxDetail:
    """The drill-down view of one project's inbox item. Every field is read-only."""

    workspace_name: str
    workspace_root: Path
    project_id: str
    project_name: str
    goal: str  # current assignment objective (P-kernel), or UNAVAILABLE
    assignment: str | None  # "A-0001  <title>  [STATUS]" (P7), or None
    owner: str  # current assignment owner (P-kernel), or UNAVAILABLE
    priority: int | None  # P21 rank via P22 inbox; None when no action is required
    focus_category: FocusCategory | None  # P21 category; None when no action is required
    focus_reason: str  # P21 verified reason, or a no-action note
    next_action: str  # P16 (via dashboard)
    next_command: str | None  # P16 (via dashboard)
    blockers: tuple[str, ...]  # labelled from dashboard signals (P9/P10/P16)
    dependencies: tuple[str, ...]  # current assignment depends_on (P-kernel)
    integrity: str  # P7 integrity summary or failure text
    integrity_ok: bool  # P7: whether the chain verified
    recommended_agent: str | None  # P19 (via dashboard)
    agent_category: str  # P19 (via dashboard)
    evidence_refs: tuple[str, ...]  # current assignment evidence_required (P-kernel)
    context_refs: tuple[str, ...]  # current assignment context_refs (P-kernel)
    founder_input: str  # P21 founder-input guidance, or a no-action note


def build_inbox_detail(workspace_root: Path, project: str) -> InboxDetail:
    """Assemble the read-only drill-down for one project. Read-only, deterministic.

    ``project`` is resolved project-first (id then name) by the reused dashboard, which
    fails closed with a typed error on an unknown project — surfacing as a non-zero exit.
    Computes nothing of its own; every value is lifted from an existing read-model.
    """
    # P20 — resolve + structural row (raises NotFoundError on an unknown id).
    dashboard = build_dashboard(workspace_root, project=project)
    row = dashboard.projects[0]

    # P22 — this project's classified inbox item (None ⇒ no attention needed).
    inbox = build_inbox(workspace_root)
    item = next((it for it in inbox.items if it.project_id == row.project_id), None)

    # P7 — authoritative integrity + safe current-assignment identity.
    handoff = build_handoff(workspace_root, project=project)
    ph = handoff.projects[0]
    integrity_ok = ph.failure is None
    if ph.failure is not None:
        integrity = f"FAILURE — {ph.failure}"
    elif ph.integrity is not None:
        integrity = f"verified — {ph.integrity}"
    else:
        integrity = f"{UNAVAILABLE} — kernel not initialised"

    assignment_line: str | None = None
    if ph.current_assignment is not None:
        a = ph.current_assignment
        assignment_line = f"{a.id}  {a.title}  [{a.status}]"

    # Kernel read path — full current-assignment metadata, only when safe to read.
    current = _read_current_assignment(workspace_root, ph.name, ph.initialised, integrity_ok)
    goal = current.objective.strip() if current and current.objective.strip() else UNAVAILABLE
    owner = current.owner if current and current.owner else UNAVAILABLE
    dependencies = (
        tuple(sorted(str(dep) for dep in current.depends_on)) if current else ()
    )
    evidence_refs = (
        tuple(sorted(e.value for e in current.evidence_required)) if current else ()
    )
    context_refs = (
        tuple(sorted(ref.path for ref in current.context_refs)) if current else ()
    )

    return InboxDetail(
        workspace_name=dashboard.workspace_name,
        workspace_root=dashboard.workspace_root,
        project_id=row.project_id,
        project_name=row.name,
        goal=goal,
        assignment=assignment_line,
        owner=owner,
        priority=item.priority if item else None,
        focus_category=item.category if item else None,
        focus_reason=item.reason if item else "no action required — project is complete or idle",
        next_action=row.next_action.upper(),
        next_command=row.next_command,
        blockers=_blockers(row, item),
        dependencies=dependencies,
        integrity=integrity,
        integrity_ok=integrity_ok,
        recommended_agent=row.recommended_agent,
        agent_category=row.agent_category,
        evidence_refs=evidence_refs,
        context_refs=context_refs,
        founder_input=item.founder_input if item else "none",
    )


def _read_current_assignment(
    workspace_root: Path, name: str, initialised: bool, integrity_ok: bool
) -> Assignment | None:
    """The in-flight assignment's full metadata, via the kernel's own read path.

    Read only when the kernel is initialised and its chain verified (per P7); any state or
    integrity fault is caught and reported as *no metadata* rather than invented.
    """
    if not initialised or not integrity_ok:
        return None
    try:
        kernel = open_project_kernel(workspace_root, name)
        return kernel.lifecycle.current()
    except ProjectOSError:
        return None


def _blockers(row: DashboardProject, item: InboxItem | None) -> tuple[str, ...]:
    """Label the blocker signals the dashboard already computed. No recomputation."""
    blockers: list[str] = []
    if item is not None and item.category is FocusCategory.INTEGRITY_FAILURE:
        blockers.append("audit integrity could not be verified — unsafe to operate on")
    if row.open_escalation:
        blockers.append("an open escalation awaits a founder decision")
    if row.queue_blocked > 0:
        blockers.append(f"{row.queue_blocked} blocked assignment(s) in the queue")
    return tuple(blockers)


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_inbox_detail(detail: InboxDetail) -> str:
    """Render the drill-down as deterministic, human-readable text. Pure function."""
    priority = (
        f"{detail.priority}  ({detail.focus_category.value})"
        if detail.priority is not None and detail.focus_category is not None
        else "— (no action required)"
    )
    lines = [
        f"INBOX DETAIL  {detail.project_name}  ({detail.project_id})",
        _RULE,
        f"  workspace       {detail.workspace_name}  ({detail.workspace_root})",
        f"  goal            {detail.goal}",
        f"  assignment      {detail.assignment or f'{UNAVAILABLE} — none in flight'}",
        f"  owner           {detail.owner}",
        f"  priority        {priority}",
        f"  focus reason    {detail.focus_reason}",
        f"  next action     {detail.next_action}"
        + (f"  →  {detail.next_command}" if detail.next_command else ""),
        f"  integrity       {detail.integrity}",
        f"  agent           {detail.recommended_agent or '—'}  ({detail.agent_category})",
        f"  founder input   {detail.founder_input}",
    ]

    lines.append("")
    lines.append("  blockers")
    if detail.blockers:
        lines.extend(f"    - {blocker}" for blocker in detail.blockers)
    else:
        lines.append("    - none")

    lines.append("  dependencies")
    if detail.dependencies:
        lines.extend(f"    - {dep}" for dep in detail.dependencies)
    else:
        lines.append("    - none")

    lines.append("  supporting evidence")
    if detail.evidence_refs or detail.context_refs:
        lines.extend(f"    - evidence: {ref}" for ref in detail.evidence_refs)
        lines.extend(f"    - context:  {ref}" for ref in detail.context_refs)
    else:
        lines.append(f"    - {UNAVAILABLE} — none recorded")

    return "\n".join(lines)
