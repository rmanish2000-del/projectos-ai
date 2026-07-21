"""Approval policy per workflow mode (spec section 7.3, approval column).

Which roles must approve before an assignment may CLOSE is a function of the
classification alone, so the requirement cannot drift from the risk level that was
recorded at classification time.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.enums import Decision, Role, WorkflowMode, WorkType
from projectos.domain.evidence import ApprovalRecord
from projectos.domain.manifest import Manifest

#: Roles required to close an assignment in each mode.
REQUIRED_ROLES: dict[WorkflowMode, frozenset[Role]] = {
    WorkflowMode.FAST: frozenset({Role.OWNER}),
    WorkflowMode.REVIEWED: frozenset({Role.REVIEWER}),
    WorkflowMode.GOVERNED: frozenset({Role.REVIEWER, Role.FOUNDER}),
}

#: Work types that always require an explicit human founder approval, whatever the
#: classification says (spec section 8.4). The kernel never merges or deploys, so
#: these close only on a recorded human decision.
ALWAYS_FOUNDER_APPROVED: frozenset[WorkType] = frozenset(
    {WorkType.MERGE, WorkType.DEPLOYMENT, WorkType.EXTERNAL_ACTION}
)


@dataclass(frozen=True, slots=True)
class ApprovalStatus:
    required: frozenset[Role]
    recorded: frozenset[Role]

    @property
    def outstanding(self) -> frozenset[Role]:
        return self.required - self.recorded

    @property
    def complete(self) -> bool:
        return not self.outstanding

    def describe(self) -> str:
        if self.complete:
            return "all required approvals recorded"
        missing = ", ".join(sorted(role.value for role in self.outstanding))
        return f"awaiting approval from: {missing}"


def required_roles(mode: WorkflowMode, work_type: WorkType) -> frozenset[Role]:
    roles = REQUIRED_ROLES[mode]
    if work_type in ALWAYS_FOUNDER_APPROVED:
        roles = roles | {Role.FOUNDER}
    return roles


def evaluate(
    mode: WorkflowMode,
    work_type: WorkType,
    approvals: tuple[ApprovalRecord, ...],
) -> ApprovalStatus:
    recorded = frozenset(
        approval.role for approval in approvals if approval.is_approval
    )
    return ApprovalStatus(required=required_roles(mode, work_type), recorded=recorded)


def reviewer_is_independent(reviewer_identity: str, executor_identity: str) -> bool:
    """A reviewer must not be the executor of the same assignment (spec 4.1)."""
    return reviewer_identity.strip().lower() != executor_identity.strip().lower()


#: The event name each canonical decision must be paired with (spec 8.6.2 rule 1).
EVENT_FOR_DECISION: dict[Decision, str] = {
    Decision.APPROVED: "approval_recorded",
    Decision.ATTESTED: "attestation_recorded",
}


def is_authorized(
    manifest: Manifest, *, role: Role, actor: str, assignment_owner: str
) -> bool:
    """Whether `actor` may speak in `role` for an assignment owned by `assignment_owner`.

    The single authority predicate for approvals and attestations (spec 8.6.2). Both
    the write path (recording a decision) and the read path (counting one during
    verification) call this, so a hand-appended entry is held to exactly the same
    rules as one the kernel produced — which is what turns audit append forgery from
    "append any approval" into "impersonate a specific manifest-authorized identity"
    (R-9).

    Only `manifest.owners` and the founder are authorized identities in v0.1; there
    is no separate reviewer registry, so a reviewer must be a manifest owner who is
    not the assignment's owner.
    """
    if role is Role.FOUNDER:
        return manifest.is_founder(actor)
    if role is Role.OWNER:
        return manifest.is_owner(actor) and (
            actor == assignment_owner or manifest.is_founder(actor)
        )
    # Role.REVIEWER — the only remaining member.
    return manifest.is_owner(actor) and reviewer_is_independent(actor, assignment_owner)


def decision_matches_event(decision: Decision, event: str) -> bool:
    """Event/decision binding (spec 8.6.2 rule 1): an `approval_recorded` entry must
    carry `approved`, an `attestation_recorded` entry must carry `attested`."""
    return EVENT_FOR_DECISION.get(decision) == event
