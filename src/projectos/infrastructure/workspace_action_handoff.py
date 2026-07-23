"""Founder action handoff — deterministic, read-only, copy-ready execution brief (P24).

`workspace inbox --project <id> --handoff` converts one Founder Inbox item into a
complete handoff the recommended agent can execute from. It decides nothing: the project
selection, the urgency classification, and the agent recommendation are all made by
existing read-models, and the assignment content comes from the existing handoff package.

Composition — two existing models, joined, nothing recomputed:

* P23 :func:`build_inbox_detail` — resolves the project (fails closed on an unknown id)
  and supplies the founder-facing context: identity, goal, active assignment, priority
  and focus reason, blockers, dependencies, required evidence, relevant context,
  integrity status, and the **P19 recommended agent** (via P20/P22/P21).
* P18 :func:`build_dispatch` — the existing copy-ready handoff model, invoked *with the
  agent P19 already recommended*. It supplies the execution content: objective,
  milestone (assignment title), acceptance criteria, stopping point, repository/kernel/
  pack source references, and the static per-agent guidance.

The dispatch package is only built when it is safe and meaningful to do so — the chain
verifies, an assignment is in flight, and a supported agent was recommended. Otherwise
the fields it would have supplied are reported as ``UNAVAILABLE`` rather than invented.
Integrity failure stays **fail-closed**: no execution package is produced, a warning is
surfaced, and the command exits non-zero.

Strictly read-only: no assignment is created or mutated, no file is written, no project
state is updated, no agent is invoked, and identical state yields identical output.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.infrastructure import workspace_dispatch as dispatch_model
from projectos.infrastructure.workspace_dispatch import (
    SUPPORTED_AGENTS,
    DispatchPackage,
    build_dispatch,
)
from projectos.infrastructure.workspace_inbox_detail import InboxDetail, build_inbox_detail

UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ActionHandoff:
    """One complete, copy-ready execution handoff for an inbox item. Immutable."""

    workspace_name: str
    workspace_root: Path
    project_id: str
    project_name: str
    goal: str  # current goal (assignment objective), or UNAVAILABLE
    milestone: str  # current milestone (assignment title), or UNAVAILABLE
    assignment: str  # active assignment, or UNAVAILABLE
    recommended_agent: str  # P19 recommendation, or UNAVAILABLE
    agent_category: str  # P19 category
    priority: str  # P21 priority + category, or a no-action note
    focus_reason: str  # P21 verified reason
    objective: str  # assignment objective (P18), or UNAVAILABLE
    context: tuple[str, ...]  # relevant context refs
    dependencies: tuple[str, ...]
    blockers: tuple[str, ...]
    required_evidence: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]  # rendered criterion lines (P18), or empty
    stopping_point: str  # P18, or UNAVAILABLE
    source_refs: tuple[str, ...]  # where every value came from
    agent_guidance: tuple[str, ...]  # static P18 per-agent policy, or empty
    integrity: str
    integrity_ok: bool
    executable: bool  # whether a dispatch package could be built

    @property
    def assignment_known(self) -> bool:
        """Whether the assignment's persisted content could be read at all.

        Distinguishes *no data* (report ``UNAVAILABLE``) from *empty data* (report
        ``none``) for the collections lifted off the assignment.
        """
        return self.assignment != UNAVAILABLE and self.integrity_ok

    @property
    def integrity_warning(self) -> str | None:
        """The warning to surface when the chain could not be verified."""
        if self.integrity_ok:
            return None
        return (
            "audit integrity could not be verified — do NOT execute this handoff. "
            "Repair the audit chain first; no execution package was produced."
        )


def build_action_handoff(workspace_root: Path, project: str) -> ActionHandoff:
    """Build the copy-ready execution handoff for one inbox item. Read-only.

    ``project`` is resolved by the reused P23 detail, which fails closed with a typed
    error on an unknown id (surfacing as a non-zero exit). Creates and mutates nothing.
    """
    detail = build_inbox_detail(workspace_root, project)  # P23 — context + P19 agent
    package = _dispatch_package(workspace_root, project, detail)  # P18 — execution content

    if package is not None:
        assignment = package.assignment
        milestone = assignment.title.strip() or UNAVAILABLE
        objective = assignment.objective.strip() or UNAVAILABLE
        stopping_point = assignment.stopping_point.strip() or UNAVAILABLE
        criteria = _criteria(package)
        guidance = dispatch_model._AGENT_GUIDANCE[package.agent]  # static P18 policy
    else:
        milestone = objective = stopping_point = UNAVAILABLE
        criteria = ()
        guidance = ()

    return ActionHandoff(
        workspace_name=detail.workspace_name,
        workspace_root=detail.workspace_root,
        project_id=detail.project_id,
        project_name=detail.project_name,
        goal=detail.goal if detail.goal != "unavailable" else UNAVAILABLE,
        milestone=milestone,
        assignment=detail.assignment or UNAVAILABLE,
        recommended_agent=detail.recommended_agent or UNAVAILABLE,
        agent_category=detail.agent_category,
        priority=_priority(detail),
        focus_reason=detail.focus_reason,
        objective=objective,
        context=detail.context_refs,
        dependencies=detail.dependencies,
        blockers=detail.blockers,
        required_evidence=detail.evidence_refs,
        acceptance_criteria=criteria,
        stopping_point=stopping_point,
        source_refs=_source_refs(detail, package),
        agent_guidance=guidance,
        integrity=detail.integrity,
        integrity_ok=detail.integrity_ok,
        executable=package is not None,
    )


def _dispatch_package(
    workspace_root: Path, project: str, detail: InboxDetail
) -> DispatchPackage | None:
    """The P18 handoff package for the agent P19 recommended, when one is meaningful.

    Skipped — leaving the execution fields ``UNAVAILABLE`` — when the chain does not
    verify (fail-closed), no assignment is in flight, or no supported agent was
    recommended (e.g. the item needs a founder decision). The agent is never chosen here;
    it is the recommendation the detail already carries.
    """
    if not detail.integrity_ok or detail.assignment is None:
        return None
    if detail.recommended_agent not in SUPPORTED_AGENTS:
        return None
    return build_dispatch(workspace_root, agent=detail.recommended_agent, project=project)


def _criteria(package: DispatchPackage) -> tuple[str, ...]:
    """The assignment's acceptance criteria, verbatim from the persisted contract."""
    lines: list[str] = []
    for criterion in package.assignment.acceptance_criteria:
        params = ", ".join(f"{k}={v}" for k, v in sorted(criterion.verify.params.items()))
        lines.append(
            f"{criterion.id}: {criterion.statement}"
            f"  [verified by {criterion.verify.type.value}({params})]"
        )
    return tuple(lines)


def _priority(detail: InboxDetail) -> str:
    if detail.priority is None or detail.focus_category is None:
        return "— (no action required)"
    return f"{detail.priority}  ({detail.focus_category.value})"


def _source_refs(detail: InboxDetail, package: DispatchPackage | None) -> tuple[str, ...]:
    """Where every value in this handoff came from — auditable, never invented."""
    refs = [
        f"workspace: {detail.workspace_root}",
        f"project: {detail.project_id}",
    ]
    if package is not None:
        refs.append(f"repository: {_repository(package)}")
        refs.append(f"kernel: {package.kernel_location}")
        refs.append(f"pack: {package.pack or UNAVAILABLE}")
        refs.append(f"assignment: {package.assignment.id}")
    return tuple(refs)


def _repository(package: DispatchPackage) -> str:
    repository = package.repository
    if repository.is_empty:
        return UNAVAILABLE
    fields = [
        ("adapter", repository.adapter),
        ("remote", repository.remote),
        ("branch", repository.default_branch),
        ("path", repository.path),
    ]
    return "  ".join(f"{label}={value}" for label, value in fields if value)


# -- rendering (deterministic, copy-ready text) --------------------------------

_RULE = "─" * 68


def render_action_handoff(handoff: ActionHandoff) -> str:
    """Render the handoff as deterministic, copy-ready text. Pure function."""
    lines = [
        f"FOUNDER ACTION HANDOFF  {handoff.project_name}  ({handoff.project_id})",
        _RULE,
    ]

    warning = handoff.integrity_warning
    if warning is not None:
        lines.extend(["", "  !! INTEGRITY WARNING", f"     {warning}", ""])

    lines.extend(
        [
            f"  workspace        {handoff.workspace_name}  ({handoff.workspace_root})",
            f"  project          {handoff.project_name}  ({handoff.project_id})",
            f"  goal             {handoff.goal}",
            f"  milestone        {handoff.milestone}",
            f"  assignment       {handoff.assignment}",
            f"  recommended agent {handoff.recommended_agent}  ({handoff.agent_category})",
            f"  priority         {handoff.priority}",
            f"  reason           {handoff.focus_reason}",
            f"  integrity        {handoff.integrity}",
        ]
    )

    lines.append("")
    lines.append("EXECUTION")
    lines.append(_RULE)
    lines.append(f"  objective        {handoff.objective}")
    lines.append(f"  stopping point   {handoff.stopping_point}")
    known = handoff.assignment_known
    lines.extend(_block("acceptance criteria", handoff.acceptance_criteria, handoff.executable))
    lines.extend(_block("required evidence", handoff.required_evidence, known))
    lines.extend(_block("relevant context", handoff.context, known))
    lines.extend(_block("dependencies", handoff.dependencies, known))
    # Blockers are always computed by the reused detail — empty means none, not unknown.
    lines.extend(_block("blockers", handoff.blockers, known=True))

    if handoff.agent_guidance:
        lines.append("")
        lines.append(f"AGENT GUIDANCE ({handoff.recommended_agent})")
        lines.append(_RULE)
        lines.extend(f"  - {item}" for item in handoff.agent_guidance)

    lines.append("")
    lines.append("SOURCE REFERENCES")
    lines.append(_RULE)
    lines.extend(f"  {ref}" for ref in handoff.source_refs)

    if not handoff.executable:
        lines.append("")
        lines.append(
            "  NOTE: no execution package — the assignment, agent, or audit chain is "
            f"{UNAVAILABLE}. Resolve the blockers above first."
        )

    return "\n".join(lines)


def _block(label: str, values: tuple[str, ...], known: bool) -> list[str]:
    """Render a list block. Empty + known ⇒ ``none``; empty + unknown ⇒ ``UNAVAILABLE``."""
    if not values:
        return [f"  {label}:", f"    - {'none' if known else UNAVAILABLE}"]
    return [f"  {label}:", *(f"    - {value}" for value in values)]
