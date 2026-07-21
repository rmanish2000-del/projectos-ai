"""Agent router and briefing generation (spec sections 4.2 and 4.3).

Routing is a validation, not a choice: the executor is declared on the assignment
and the router checks it against the work type's permitted set. Packs may narrow
the permitted set but never broaden it.

Briefings are produced here, in the domain, because their content is a kernel
guarantee — every briefing carries the same four rules regardless of which agent
receives it.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.assignment import Assignment
from projectos.domain.enums import ExecutorType, WorkType
from projectos.domain.errors import ValidationError

#: Default executor per work type (spec section 4.2 table).
DEFAULT_EXECUTOR: dict[WorkType, ExecutorType] = {
    WorkType.ARCHITECTURE: ExecutorType.COWORK,
    WorkType.SPECIFICATION: ExecutorType.COWORK,
    WorkType.RESEARCH: ExecutorType.COWORK,
    WorkType.ANALYSIS: ExecutorType.COWORK,
    WorkType.DOCUMENT: ExecutorType.COWORK,
    WorkType.IMPLEMENTATION: ExecutorType.CODE,
    WorkType.REFACTOR: ExecutorType.CODE,
    WorkType.TEST: ExecutorType.CODE,
    WorkType.FIX: ExecutorType.CODE,
    WorkType.APPROVAL: ExecutorType.HUMAN,
    WorkType.DEPLOYMENT: ExecutorType.HUMAN,
    WorkType.MERGE: ExecutorType.HUMAN,
    WorkType.EXTERNAL_ACTION: ExecutorType.HUMAN,
}

#: Executors each work type permits. `human` is always permitted — a pack narrowing
#: document work to human review is the motivating case in spec section 4.2.
PERMITTED_EXECUTORS: dict[WorkType, frozenset[ExecutorType]] = {
    work_type: frozenset({default, ExecutorType.HUMAN})
    for work_type, default in DEFAULT_EXECUTOR.items()
}

#: The invariants every briefing states, verbatim, to every agent (spec 4.3).
BRIEFING_RULES: tuple[str, ...] = (
    "You have exactly one active assignment. Do not start any other work.",
    "Stop at the stopping point below. Do not continue past it.",
    "Report evidence references (commits, PRs, CI runs, paths). Claims are not evidence.",
    "Do not self-verify. Only repository evidence decides whether this assignment passes.",
)


@dataclass(frozen=True, slots=True)
class AssignmentBriefing:
    """The rendered briefing handed to an executor. Pure text; no side effects."""

    assignment_id: str
    executor: ExecutorType
    title: str
    objective: str
    work_type: WorkType
    workflow_mode: str
    context_refs: tuple[str, ...]
    acceptance_criteria: tuple[tuple[str, str, str], ...]
    stopping_point: str
    rejection_reasons: tuple[str, ...] = ()

    def render(self) -> str:
        lines = [
            f"ASSIGNMENT {self.assignment_id} — {self.title}",
            f"Executor: {self.executor.value}    Work type: {self.work_type.value}    "
            f"Workflow: {self.workflow_mode}",
            "",
            "RULES",
        ]
        lines += [f"  {index}. {rule}" for index, rule in enumerate(BRIEFING_RULES, start=1)]
        lines += ["", "OBJECTIVE", f"  {self.objective.strip()}"]

        if self.context_refs:
            lines += ["", "CONTEXT (read before starting)"]
            lines += [f"  - {ref}" for ref in self.context_refs]

        if self.rejection_reasons:
            lines += ["", "PREVIOUS ATTEMPT REJECTED — address each reason"]
            lines += [f"  - {reason}" for reason in self.rejection_reasons]

        lines += ["", "ACCEPTANCE CRITERIA (each is machine-verified)"]
        for criterion_id, statement, rule in self.acceptance_criteria:
            lines += [f"  {criterion_id}. {statement}", f"       verified by: {rule}"]

        lines += ["", "STOPPING POINT", f"  {self.stopping_point.strip()}"]
        return "\n".join(lines)


def validate_routing(assignment: Assignment, enabled: tuple[ExecutorType, ...]) -> None:
    """Reject an assignment whose executor is not permitted for its work type."""
    permitted = PERMITTED_EXECUTORS[assignment.work_type]
    if assignment.executor not in permitted:
        allowed = ", ".join(sorted(e.value for e in permitted))
        raise ValidationError(
            f"{assignment.id}: executor '{assignment.executor.value}' is not permitted for "
            f"work_type '{assignment.work_type.value}'",
            detail=f"Permitted executors: {allowed}",
        )
    if assignment.executor not in enabled:
        enabled_names = ", ".join(sorted(e.value for e in enabled))
        raise ValidationError(
            f"{assignment.id}: executor '{assignment.executor.value}' is not enabled in the "
            "manifest",
            detail=f"Enabled agents: {enabled_names}",
        )


def brief(assignment: Assignment) -> AssignmentBriefing:
    """Render the briefing for an assignment. Stateless (spec section 4.3)."""
    return AssignmentBriefing(
        assignment_id=str(assignment.id),
        executor=assignment.executor,
        title=assignment.title,
        objective=assignment.objective,
        work_type=assignment.work_type,
        workflow_mode=assignment.workflow_mode.value,
        context_refs=tuple(ref.path for ref in assignment.context_refs),
        acceptance_criteria=tuple(
            (criterion.id, criterion.statement, criterion.verify.describe())
            for criterion in assignment.acceptance_criteria
        ),
        stopping_point=assignment.stopping_point,
        rejection_reasons=assignment.rejection_reasons,
    )
