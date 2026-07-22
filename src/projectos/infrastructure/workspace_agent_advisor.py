"""Agent selection advisor — deterministic, read-only agent recommendation (P19).

Given one selected assignment, recommend exactly one *supported* worker type — or
explicitly refuse when the persisted metadata does not support a safe choice. The
recommendation is a pure function of two persisted fields — ``work_type`` and
``executor`` — mapped through static ProjectOS policy. It reads nothing else, invokes
no agent, dispatches nothing, and mutates nothing.

Resolution reuses the P18 contracts (the P7 handoff read-model plus the kernel's own
assignment repository); the agent classification never fabricates rationale — when the
two fields disagree, or the work is authority/external/human, it returns
``INSUFFICIENT_INFORMATION`` or ``FOUNDER_DECISION_REQUIRED`` rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from projectos.domain.assignment import Assignment
from projectos.domain.enums import ExecutorType, WorkType
from projectos.domain.errors import NotFoundError
from projectos.infrastructure.workspace_bridge import open_project_kernel
from projectos.infrastructure.workspace_dispatch import SUPPORTED_AGENTS
from projectos.infrastructure.workspace_handoff import build_handoff

# -- static ProjectOS policy: work_type → supported agent ---------------------

CLAUDE_CODE = "claude-code"
CLAUDE_CHAT = "claude-chat"
CLAUDE_COWORK = "claude-cowork"

#: Repository/implementation work → the code worker.
_CODE_WORK: frozenset[WorkType] = frozenset(
    {
        WorkType.IMPLEMENTATION,
        WorkType.REFACTOR,
        WorkType.TEST,
        WorkType.FIX,
        WorkType.DEPLOYMENT,
        WorkType.MERGE,
    }
)
#: Strategy / architecture / analysis / review → the chat worker.
_CHAT_WORK: frozenset[WorkType] = frozenset({WorkType.ARCHITECTURE, WorkType.ANALYSIS})
#: Workflow design / research organisation / documentation → the cowork worker.
_COWORK_WORK: frozenset[WorkType] = frozenset(
    {WorkType.SPECIFICATION, WorkType.RESEARCH, WorkType.DOCUMENT}
)
#: Authority / external actions — a human/founder must decide; no AI worker applies.
_FOUNDER_WORK: frozenset[WorkType] = frozenset(
    {WorkType.APPROVAL, WorkType.EXTERNAL_ACTION}
)

_AGENT_BY_WORK_TYPE: dict[WorkType, str] = {
    **{wt: CLAUDE_CODE for wt in _CODE_WORK},
    **{wt: CLAUDE_CHAT for wt in _CHAT_WORK},
    **{wt: CLAUDE_COWORK for wt in _COWORK_WORK},
}


class Category(StrEnum):
    """The single recommendation category. Exactly one applies."""

    RECOMMEND = "recommend"
    FOUNDER_DECISION_REQUIRED = "founder-decision-required"
    INSUFFICIENT_INFORMATION = "insufficient-information"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class Recommendation:
    """The agent recommendation for one assignment."""

    category: Category
    agent: str | None
    reason: str
    evidence_used: tuple[str, ...]
    missing_or_conflicting: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AgentAdvice:
    """The deterministic advice for one selected assignment."""

    workspace_name: str
    workspace_root: Path
    project_id: str
    project_name: str
    assignment_id: str
    assignment_title: str
    assignment_status: str
    recommendation: Recommendation

    @property
    def is_blocked(self) -> bool:
        return self.recommendation.category is Category.BLOCKED


def build_agent_advice(
    workspace_root: Path, *, project: str, assignment: str | None = None
) -> AgentAdvice:
    """Recommend one supported agent for the selected assignment. Strictly read-only.

    Resolution mirrors P18: the P7 handoff read-model resolves the project context, and
    the assignment is read through the kernel (explicit id, else the in-flight one).
    Fails closed on an unresolved workspace/project, an uninitialised kernel, or a
    missing/ambiguous assignment; an integrity fault is reported as ``BLOCKED``.
    """
    from projectos.domain.ids import AssignmentId

    handoff = build_handoff(workspace_root, project=project)  # fail closed unresolved/malformed
    project_handoff = handoff.projects[0]
    if not project_handoff.initialised:
        raise NotFoundError(
            f"Project {project!r} has no initialised kernel",
            detail="Run `projectos workspace init-project` first.",
        )

    kernel = open_project_kernel(workspace_root, project_handoff.name)
    assignment_id = (
        AssignmentId.parse(assignment)
        if assignment
        else kernel.lifecycle.require_current().id  # fail closed if none in flight
    )
    full = kernel.assignments.get(assignment_id)  # fail closed on missing/malformed

    if project_handoff.failure is not None:
        recommendation = Recommendation(
            category=Category.BLOCKED,
            agent=None,
            reason=f"project state could not be verified — do not dispatch: "
            f"{project_handoff.failure}",
            evidence_used=("audit integrity",),
        )
    else:
        recommendation = _recommend(full)

    return AgentAdvice(
        workspace_name=handoff.workspace_name,
        workspace_root=handoff.workspace_root,
        project_id=project_handoff.project_id,
        project_name=project_handoff.name,
        assignment_id=str(full.id),
        assignment_title=full.title,
        assignment_status=full.status.value,
        recommendation=recommendation,
    )


def _recommend(assignment: Assignment) -> Recommendation:
    """Map (work_type, executor) to exactly one recommendation via static policy."""
    work_type = assignment.work_type
    executor = assignment.executor
    work_evidence = f"work_type={work_type.value}"
    executor_evidence = f"executor={executor.value}"

    # A human executor means a person must act — no AI worker applies.
    if executor is ExecutorType.HUMAN:
        return Recommendation(
            category=Category.FOUNDER_DECISION_REQUIRED,
            agent=None,
            reason="the executor is 'human'; a person must act, not an AI worker",
            evidence_used=(executor_evidence,),
        )

    # Authority / external work is a founder/human decision, not agent work.
    if work_type in _FOUNDER_WORK:
        return Recommendation(
            category=Category.FOUNDER_DECISION_REQUIRED,
            agent=None,
            reason=f"{work_type.value} is an authority/external action requiring a "
            "founder or human decision",
            evidence_used=(work_evidence,),
        )

    agent = _AGENT_BY_WORK_TYPE.get(work_type)
    if agent is None:  # defensive: an unclassified (future) work type
        return Recommendation(
            category=Category.INSUFFICIENT_INFORMATION,
            agent=None,
            reason=f"work_type {work_type.value!r} has no agent policy",
            evidence_used=(work_evidence,),
            missing_or_conflicting=(f"unclassified work_type {work_type.value}",),
        )

    # Cross-check: the executor must agree with the work-type's code/non-code class.
    work_is_code = agent == CLAUDE_CODE
    executor_is_code = executor is ExecutorType.CODE
    if work_is_code != executor_is_code:
        return Recommendation(
            category=Category.INSUFFICIENT_INFORMATION,
            agent=None,
            reason="work_type and executor disagree; the metadata does not support a "
            "safe agent choice",
            evidence_used=(work_evidence, executor_evidence),
            missing_or_conflicting=(
                f"{work_evidence} implies {'code' if work_is_code else 'non-code'} work "
                f"but {executor_evidence}",
            ),
        )

    return Recommendation(
        category=Category.RECOMMEND,
        agent=agent,
        reason=f"{work_type.value} work with the {executor.value} executor maps to {agent}",
        evidence_used=(work_evidence, executor_evidence),
    )


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_advice(advice: AgentAdvice) -> str:
    """Render the advice as deterministic, human-readable text. Pure function."""
    rec = advice.recommendation
    lines = [
        f"AGENT RECOMMENDATION  {advice.workspace_name}  →  {advice.project_id}",
        _RULE,
        f"  workspace       {advice.workspace_name}  ({advice.workspace_root})",
        f"  project         {advice.project_name}  ({advice.project_id})",
        f"  assignment      {advice.assignment_id}  {advice.assignment_title}  "
        f"[{advice.assignment_status}]",
        "",
        f"  recommendation  {rec.category.value.upper()}",
        f"  agent           {rec.agent or '—'}",
        f"  reason          {rec.reason}",
    ]
    lines.append("  evidence used:")
    for item in rec.evidence_used:
        lines.append(f"    - {item}")
    if rec.missing_or_conflicting:
        lines.append("  missing / conflicting:")
        for item in rec.missing_or_conflicting:
            lines.append(f"    - {item}")
    return "\n".join(lines)


def is_supported_agent(agent: str) -> bool:
    """Whether a recommended agent is one the P18 dispatch command accepts."""
    return agent in SUPPORTED_AGENTS
