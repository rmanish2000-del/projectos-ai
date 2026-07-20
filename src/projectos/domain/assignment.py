"""Assignment model (spec section 6).

Assignments are immutable values. Every lifecycle operation returns a *new*
assignment rather than mutating one, which is what makes the transition history a
faithful record: there is no code path that changes state without appending to it.

Scope is immutable after DRAFT (decision D-5): changing scope means CANCELLED plus
a fresh assignment, so acceptance criteria can never be edited to fit the evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from projectos.domain.enums import (
    Event,
    EvidenceClass,
    ExecutorType,
    Status,
    WorkflowMode,
    WorkType,
)
from projectos.domain.errors import InvariantViolation, ValidationError
from projectos.domain.evidence import AcceptanceCriterion
from projectos.domain.ids import AssignmentId

#: Work types that must not produce repository code changes. Evidence carrying
#: commits or PRs on these assignments is rejected (spec section 4.2, acceptance
#: criterion 10).
NON_CODE_WORK_TYPES: frozenset[WorkType] = frozenset(
    {
        WorkType.ARCHITECTURE,
        WorkType.SPECIFICATION,
        WorkType.RESEARCH,
        WorkType.ANALYSIS,
        WorkType.DOCUMENT,
    }
)

#: Evidence classes that indicate repository code changes.
CODE_EVIDENCE_CLASSES: frozenset[EvidenceClass] = frozenset(
    {EvidenceClass.COMMIT, EvidenceClass.PR}
)


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    """One entry in an assignment's history. `audit_ref` links to the audit hash."""

    event: Event
    from_status: Status
    to_status: Status
    actor: str
    timestamp: str
    audit_ref: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ContextRef:
    path: str


@dataclass(frozen=True, slots=True)
class NextSpec:
    """Deterministic successor declaration (spec section 3.3, step 1)."""

    template: str


@dataclass(frozen=True, slots=True)
class Assignment:
    id: AssignmentId
    title: str
    work_type: WorkType
    objective: str
    owner: str
    executor: ExecutorType
    stopping_point: str
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    schema_version: int = 1
    workflow_mode: WorkflowMode = WorkflowMode.FAST
    risk_flags: tuple[str, ...] = ()
    depends_on: tuple[AssignmentId, ...] = ()
    context_refs: tuple[ContextRef, ...] = ()
    evidence_required: tuple[EvidenceClass, ...] = ()
    next: NextSpec | None = None
    #: The pack template this assignment was generated from, if any. Recorded so the
    #: next-assignment engine can tell which pipeline steps have already been issued.
    origin_template: str | None = None
    status: Status = Status.DRAFT
    history: tuple[TransitionRecord, ...] = ()
    classification_rule: str | None = None
    rejection_reasons: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValidationError(f"Unsupported assignment schema_version {self.schema_version}")
        if not self.title.strip():
            raise ValidationError(f"{self.id} must have a title")
        if not self.acceptance_criteria:
            # INV-3 would be unsatisfiable: an assignment with no criteria could
            # never legitimately reach VERIFIED.
            raise ValidationError(
                f"{self.id} must declare at least one acceptance criterion",
                detail="INV-3 requires every criterion to map to a passing evidence check.",
            )
        seen: set[str] = set()
        for criterion in self.acceptance_criteria:
            if criterion.id in seen:
                raise ValidationError(f"{self.id} has duplicate criterion id {criterion.id!r}")
            seen.add(criterion.id)
        if self.id in self.depends_on:
            raise ValidationError(f"{self.id} cannot depend on itself")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValidationError(f"{self.id} has duplicate entries in depends_on")

    # -- queries ---------------------------------------------------------------

    @property
    def is_code_work(self) -> bool:
        return self.work_type not in NON_CODE_WORK_TYPES

    @property
    def occupies_active_slot(self) -> bool:
        return self.status.is_active_slot

    def criterion(self, criterion_id: str) -> AcceptanceCriterion:
        for criterion in self.acceptance_criteria:
            if criterion.id == criterion_id:
                return criterion
        raise ValidationError(f"{self.id} has no criterion {criterion_id!r}")

    # -- transformations (each returns a new value) -----------------------------

    def with_status(self, status: Status, record: TransitionRecord) -> Assignment:
        return replace(self, status=status, history=(*self.history, record))

    def with_classification(self, mode: WorkflowMode, rule: str) -> Assignment:
        """Classification is only meaningful before the assignment leaves DRAFT."""
        if self.status is not Status.DRAFT:
            raise InvariantViolation(
                f"{self.id} cannot be reclassified in status {self.status.value}",
                detail="Classification is fixed when an assignment leaves DRAFT (decision D-5).",
            )
        return replace(self, workflow_mode=mode, classification_rule=rule)

    def with_rejection_reasons(self, reasons: tuple[str, ...]) -> Assignment:
        return replace(self, rejection_reasons=reasons)

    def cleared_of_rejections(self) -> Assignment:
        return replace(self, rejection_reasons=())
