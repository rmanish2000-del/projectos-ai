"""Rule evaluation (spec section 8.3).

Pure: it takes a rule and the facts an adapter reported, and returns a verdict. It
never performs I/O and never consults conversation content, agent self-reports, or
model judgment (decision D-4).

The engine has no "unknown" verdict. Absent, ambiguous, or unavailable facts all
evaluate to FAIL (INV-4), so the only way to pass is for the repository to actually
show what the criterion asked for.
"""

from __future__ import annotations

from projectos.domain.enums import CriterionOutcome, Decision, RuleType
from projectos.domain.evidence import (
    AcceptanceCriterion,
    CriterionResult,
    EvidenceRule,
    RepositoryFact,
)


def evaluate(criterion: AcceptanceCriterion, fact: RepositoryFact) -> CriterionResult:
    """Decide one criterion from one fact."""
    rule = criterion.verify
    passed = fact.found and _rule_specific_check(rule, fact)
    outcome = CriterionOutcome.PASS if passed else CriterionOutcome.FAIL
    return CriterionResult(
        criterion_id=criterion.id,
        outcome=outcome,
        rule=rule.describe(),
        reason=fact.detail or _default_reason(rule, passed),
    )


def failed(criterion: AcceptanceCriterion, reason: str) -> CriterionResult:
    """Construct a failure without consulting any fact.

    Used when the adapter errored or lacks the capability the rule needs: the
    criterion fails closed and the reason names what was missing.
    """
    return CriterionResult(
        criterion_id=criterion.id,
        outcome=CriterionOutcome.FAIL,
        rule=criterion.verify.describe(),
        reason=reason,
    )


#: Rule types decided entirely by the adapter's `found` flag. Every other rule type
#: must have an explicit branch below. Listing them positively rather than falling
#: through to a default is deliberate: a new rule type added without a branch now
#: fails closed instead of silently always passing.
_FOUND_IS_SUFFICIENT: frozenset[RuleType] = frozenset(
    {
        RuleType.FILE_EXISTS,
        RuleType.FILE_CONTAINS,
        RuleType.COMMIT_EXISTS,
        RuleType.HUMAN_ATTESTATION,
    }
)


def _rule_specific_check(rule: EvidenceRule, fact: RepositoryFact) -> bool:
    """Checks that need more than the adapter's `found` flag.

    Adapters report facts; these comparisons are the kernel's decision to make.
    """
    if rule.type is RuleType.PR_MERGED:
        required = int(rule.params["approvals_required"])
        approvals = int(fact.data.get("approvals", 0))
        merged = bool(fact.data.get("merged", False))
        role_matched = bool(fact.data.get("approver_role_matched", False))
        return merged and approvals >= required and role_matched

    if rule.type is RuleType.CI_PASSED:
        return str(fact.data.get("conclusion", "")).lower() == "success"

    if rule.type is RuleType.TESTS_PASSED:
        return int(fact.data.get("failed", 1)) == 0 and int(fact.data.get("total", 0)) > 0

    if rule.type is RuleType.APPROVAL_RECORDED:
        # The rule always means an actual approval (spec 8.2). The optional
        # `decision` parameter is pinned to the canonical value at authoring time,
        # so there is nothing here for a criterion author to widen.
        return Decision.parse(fact.data.get("decision")) is Decision.APPROVED

    # Fail closed on anything not explicitly accounted for (INV-4).
    return rule.type in _FOUND_IS_SUFFICIENT


def _default_reason(rule: EvidenceRule, passed: bool) -> str:
    verb = "satisfied" if passed else "not satisfied"
    return f"{rule.describe()} {verb}"
