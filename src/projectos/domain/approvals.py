"""Approval policy per workflow mode (spec section 7.3, approval column).

Which roles must approve before an assignment may CLOSE is a function of the
classification alone, so the requirement cannot drift from the risk level that was
recorded at classification time.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.enums import Role, WorkflowMode, WorkType
from projectos.domain.evidence import ApprovalRecord

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
