"""Evidence rules, repository facts, and verification results (spec section 8).

Three separate concepts that must not blur:

* :class:`EvidenceRule` — what the owner asked to be true (authored, immutable).
* :class:`RepositoryFact` — what the repository adapter observed (facts, no verdict).
* :class:`CriterionResult` — the kernel's verdict, produced only by the rule engine.

A completion *claim* is none of these. Claims stage evidence references for
verification; they never carry a verdict (spec section 4.3).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from projectos.domain.enums import CriterionOutcome, EvidenceClass, Role, RuleType
from projectos.domain.errors import ValidationError

#: Parameters each rule type accepts, and which of those are required.
#: The rule engine refuses to evaluate a rule whose parameters fall outside this table,
#: so an unknown or misspelled parameter fails closed at authoring time.
RULE_PARAMETERS: dict[RuleType, tuple[frozenset[str], frozenset[str]]] = {
    RuleType.FILE_EXISTS: (frozenset({"path"}), frozenset({"path", "at_ref"})),
    RuleType.FILE_CONTAINS: (
        frozenset({"path", "pattern"}),
        frozenset({"path", "pattern", "at_ref"}),
    ),
    RuleType.COMMIT_EXISTS: (
        frozenset(),
        frozenset({"message_pattern", "author", "since", "branch"}),
    ),
    RuleType.PR_MERGED: (
        frozenset({"approvals_required", "approver_role"}),
        frozenset({"number", "approvals_required", "approver_role"}),
    ),
    RuleType.CI_PASSED: (frozenset({"ref"}), frozenset({"workflow", "ref"})),
    RuleType.TESTS_PASSED: (frozenset(), frozenset({"report_path"})),
    RuleType.APPROVAL_RECORDED: (frozenset({"role"}), frozenset({"role", "decision"})),
    RuleType.HUMAN_ATTESTATION: (frozenset({"role"}), frozenset({"role"})),
}

#: Capabilities a rule needs from the repository adapter. A rule requiring a
#: capability the adapter lacks fails closed with a message naming the capability
#: (spec section 11).
RULE_CAPABILITIES: dict[RuleType, str | None] = {
    RuleType.FILE_EXISTS: None,
    RuleType.FILE_CONTAINS: None,
    RuleType.COMMIT_EXISTS: None,
    RuleType.PR_MERGED: "pr",
    RuleType.CI_PASSED: "ci",
    RuleType.TESTS_PASSED: "artifacts",
    RuleType.APPROVAL_RECORDED: None,
    RuleType.HUMAN_ATTESTATION: None,
}


@dataclass(frozen=True, slots=True)
class EvidenceRule:
    """One machine-checkable rule attached to an acceptance criterion.

    `params` is validated once in `__post_init__` and then made genuinely
    read-only. A plain dict on a frozen dataclass was an escape hatch: a
    `pr_merged` rule validated as requiring two approvals could afterwards be
    rewritten in place to require zero, and the rule engine would read the
    mutated value. `frozen=True` protects the field binding, not the object it
    points at, so the mapping itself has to be closed.
    """

    type: RuleType
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required, allowed = RULE_PARAMETERS[self.type]
        supplied = set(self.params)
        missing = required - supplied
        if missing:
            raise ValidationError(
                f"Rule {self.type.value} is missing required parameters",
                detail=f"Missing: {', '.join(sorted(missing))}",
            )
        unknown = supplied - allowed
        if unknown:
            raise ValidationError(
                f"Rule {self.type.value} received unknown parameters",
                detail=f"Unknown: {', '.join(sorted(unknown))}",
            )
        # Copy first so a caller holding the original dict cannot reach in later,
        # then wrap read-only so the copy itself cannot be mutated either.
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))

    @property
    def required_capability(self) -> str | None:
        return RULE_CAPABILITIES[self.type]

    def describe(self) -> str:
        if not self.params:
            return self.type.value
        rendered = ", ".join(f"{k}={v!r}" for k, v in sorted(self.params.items()))
        return f"{self.type.value}({rendered})"


@dataclass(frozen=True, slots=True)
class AcceptanceCriterion:
    """A statement plus the rule that decides it. Every criterion carries a rule
    (spec section 6); a criterion without one cannot be represented."""

    id: str
    statement: str
    verify: EvidenceRule

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValidationError("Acceptance criterion id must be non-empty")
        if not self.statement.strip():
            raise ValidationError(f"Acceptance criterion {self.id} must have a statement")


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    """An immutable reference to evidence produced by an executor.

    References only: the kernel never copies artifacts into its state.
    """

    evidence_class: EvidenceClass
    reference: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class CompletionClaim:
    """An executor's report, parsed by an agent adapter. Untrusted input
    (spec section 14.5): it can move state to EVIDENCE_SUBMITTED and nothing further."""

    assignment_id: str
    summary: str
    evidence: tuple[EvidenceRef, ...] = ()

    def classes_present(self) -> frozenset[EvidenceClass]:
        return frozenset(ref.evidence_class for ref in self.evidence)


@dataclass(frozen=True, slots=True)
class RepositoryFact:
    """What the adapter observed. Adapters report facts and never verdicts
    (spec section 11)."""

    kind: str
    found: bool
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CriterionResult:
    criterion_id: str
    outcome: CriterionOutcome
    rule: str
    reason: str

    @property
    def passed(self) -> bool:
        return self.outcome is CriterionOutcome.PASS


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """The full per-criterion report. Failures are collected, never short-circuited,
    so one run tells the executor everything that is missing (spec section 8.3)."""

    assignment_id: str
    results: tuple[CriterionResult, ...]

    @property
    def passed(self) -> bool:
        # An empty criteria set cannot pass: INV-3 requires every criterion mapped to
        # a passing check, and "no criteria" is not evidence of completion.
        return bool(self.results) and all(result.passed for result in self.results)

    @property
    def failures(self) -> tuple[CriterionResult, ...]:
        return tuple(result for result in self.results if not result.passed)


@dataclass(frozen=True, slots=True)
class ApprovalRecord:
    """A recorded human approval (spec section 8.1, `approval` evidence class)."""

    assignment_id: str
    role: Role
    actor: str
    decision: str
    timestamp: str
