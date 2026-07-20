"""Closed vocabularies for the ProjectOS kernel.

Every enum here is a *closed* set: values outside these sets are rejected at the
schema boundary. The kernel never accepts free-form strings where an enum applies.
"""

from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    """Assignment lifecycle states (spec section 7.1)."""

    DRAFT = "draft"
    READY = "ready"
    ACTIVE = "active"
    EVIDENCE_SUBMITTED = "evidence_submitted"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    CLOSED = "closed"
    REJECTED = "rejected"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"

    @property
    def is_active_slot(self) -> bool:
        """States that occupy the single-active-assignment slot (INV-1)."""
        return self in _ACTIVE_SLOT_STATES

    @property
    def is_terminal(self) -> bool:
        return self in (Status.CLOSED, Status.CANCELLED)


_ACTIVE_SLOT_STATES: frozenset[Status] = frozenset(
    {Status.ACTIVE, Status.EVIDENCE_SUBMITTED, Status.VERIFYING}
)


class Event(StrEnum):
    """State machine events (spec section 7.2)."""

    CLASSIFY_OK = "classify_ok"
    CANCEL = "cancel"
    START = "start"
    BLOCK = "block"
    ESCALATE = "escalate"
    SUBMIT = "submit"
    VERIFY_START = "verify_start"
    ALL_CRITERIA_PASS = "all_criteria_pass"
    ANY_CRITERION_FAIL = "any_criterion_fail"
    VERIFIER_ERROR = "verifier_error"
    APPROVALS_COMPLETE = "approvals_complete"
    REVIEW_REJECT = "review_reject"
    RESUME = "resume"
    UNBLOCK = "unblock"
    FOUNDER_RESOLVE_PROCEED = "founder_resolve_proceed"
    FOUNDER_RESOLVE_CANCEL = "founder_resolve_cancel"
    FOUNDER_RESOLVE_RESCOPE = "founder_resolve_rescope"


class Actor(StrEnum):
    """Who is permitted to drive a transition (spec section 7.2, column 4)."""

    KERNEL = "kernel"
    OWNER = "owner"
    FOUNDER = "founder"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"


class WorkType(StrEnum):
    """Assignment work types (spec section 4.2)."""

    ARCHITECTURE = "architecture"
    SPECIFICATION = "specification"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    DOCUMENT = "document"
    IMPLEMENTATION = "implementation"
    REFACTOR = "refactor"
    TEST = "test"
    FIX = "fix"
    APPROVAL = "approval"
    DEPLOYMENT = "deployment"
    MERGE = "merge"
    EXTERNAL_ACTION = "external_action"


class ExecutorType(StrEnum):
    """Agent adapters enabled in v0.1 (spec section 4.1)."""

    COWORK = "cowork"
    CODE = "code"
    HUMAN = "human"


class WorkflowMode(StrEnum):
    """Workflow-risk classification (spec section 7.3), ordered least to most strict."""

    FAST = "fast"
    REVIEWED = "reviewed"
    GOVERNED = "governed"

    @property
    def rank(self) -> int:
        return _MODE_RANK[self]

    def raised_to(self, other: WorkflowMode) -> WorkflowMode:
        """Packs may raise a classification, never lower it (spec section 7.3)."""
        return self if self.rank >= other.rank else other


_MODE_RANK: dict[WorkflowMode, int] = {
    WorkflowMode.FAST: 0,
    WorkflowMode.REVIEWED: 1,
    WorkflowMode.GOVERNED: 2,
}


class EvidenceClass(StrEnum):
    """Evidence classes (spec section 8.1)."""

    COMMIT = "commit"
    PR = "pr"
    CI_RUN = "ci_run"
    TEST_REPORT = "test_report"
    ARTIFACT = "artifact"
    APPROVAL = "approval"


class RuleType(StrEnum):
    """Evidence-rule vocabulary shipped in v0.1 (spec section 8.2)."""

    FILE_EXISTS = "file_exists"
    FILE_CONTAINS = "file_contains"
    COMMIT_EXISTS = "commit_exists"
    PR_MERGED = "pr_merged"
    CI_PASSED = "ci_passed"
    TESTS_PASSED = "tests_passed"
    APPROVAL_RECORDED = "approval_recorded"
    HUMAN_ATTESTATION = "human_attestation"


class Role(StrEnum):
    """Approval roles (spec section 4.1)."""

    OWNER = "owner"
    REVIEWER = "reviewer"
    FOUNDER = "founder"


class Decision(StrEnum):
    """The only decisions a recorded human action may carry (spec 8.1, 8.2).

    Closed and canonical. `approval_recorded` means an actual approval, so it pins
    to `approved`; `human_attestation` pins to `attested`. There is deliberately no
    `rejected` or `pending` member: review rejection is a state transition
    (`review_reject`, spec 7.2), not an approval record, and a pending decision is
    simply the absence of a record.

    Parsing is exact-match on the canonical lowercase value. Case and whitespace
    variants are rejected rather than normalised: silently mapping `"Approved "`
    onto approval would mean the kernel guessing at intent on the authority path.
    """

    APPROVED = "approved"
    ATTESTED = "attested"

    @classmethod
    def parse(cls, raw: object) -> Decision | None:
        """Return the canonical decision, or None if the value is not one.

        Returning None rather than raising lets callers reading historical records
        skip an unrecognised entry (granting nothing) instead of halting; callers
        on a write path use the constructor directly and get a hard failure.
        """
        if isinstance(raw, Decision):
            return raw
        if not isinstance(raw, str):
            return None
        for member in cls:
            if raw == member.value:
                return member
        return None


class EscalationTrigger(StrEnum):
    """Exhaustive escalation triggers (spec section 9.1)."""

    FOUNDER_DECISION = "founder_decision"
    BLOCKER = "blocker"
    SECURITY_RISK = "security_risk"
    LEGAL_RISK = "legal_risk"
    ARCHITECTURE_CONFLICT = "architecture_conflict"
    NEXT_UNDETERMINED = "next_undetermined"


class EscalationState(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class FounderDecision(StrEnum):
    """Founder resolution outcomes (spec section 7.2, ESCALATED rows)."""

    PROCEED = "proceed"
    CANCEL = "cancel"
    RESCOPE = "rescope"


class RepositoryAdapterKind(StrEnum):
    GITHUB = "github"
    LOCAL_GIT = "local_git"


class CriterionOutcome(StrEnum):
    """Result of evaluating one acceptance criterion. There is no third 'unknown'
    outcome that means success: ambiguity is FAIL by construction (INV-4)."""

    PASS = "pass"
    FAIL = "fail"
