"""Verification engine (spec section 8.3).

Orchestrates: for each acceptance criterion, ask the adapter for facts, hand those
facts to the pure rule engine, collect the verdict. Failures are collected rather
than short-circuited so one run reports everything that is missing.

Every failure mode below converges on FAIL: adapter exception, missing capability,
and unmatched evidence all block the transition (INV-4). There is no branch that
turns an error into a pass.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.application.ports import AuditLog, RepositoryAdapter
from projectos.domain import rule_engine
from projectos.domain.assignment import CODE_EVIDENCE_CLASSES, Assignment
from projectos.domain.enums import CriterionOutcome, Decision, RuleType
from projectos.domain.errors import AdapterError, ValidationError
from projectos.domain.evidence import (
    AcceptanceCriterion,
    CompletionClaim,
    CriterionResult,
    RepositoryFact,
    VerificationReport,
)


@dataclass(frozen=True, slots=True)
class VerificationEngine:
    adapter: RepositoryAdapter
    audit: AuditLog

    def verify(self, assignment: Assignment) -> VerificationReport:
        capabilities = self.adapter.capabilities()
        results = tuple(
            self._verify_criterion(assignment, criterion, capabilities)
            for criterion in assignment.acceptance_criteria
        )
        return VerificationReport(assignment_id=str(assignment.id), results=results)

    def _verify_criterion(
        self,
        assignment: Assignment,
        criterion: AcceptanceCriterion,
        capabilities: dict[str, bool],
    ) -> CriterionResult:
        rule = criterion.verify

        required = rule.required_capability
        if required is not None and not capabilities.get(required, False):
            return rule_engine.failed(
                criterion,
                f"adapter lacks the '{required}' capability required by "
                f"{rule.type.value}; configure the github adapter to check this rule",
            )

        if rule.type is RuleType.APPROVAL_RECORDED:
            return rule_engine.evaluate(criterion, self._approval_fact(assignment, criterion))

        if rule.type is RuleType.HUMAN_ATTESTATION:
            return rule_engine.evaluate(criterion, self._attestation_fact(assignment, criterion))

        try:
            fact = self.adapter.query(rule)
        except AdapterError as exc:
            return rule_engine.failed(criterion, f"adapter error (fails closed): {exc.message}")

        return rule_engine.evaluate(criterion, fact)

    def _approval_fact(
        self, assignment: Assignment, criterion: AcceptanceCriterion
    ) -> RepositoryFact:
        """Approvals live in the audit log, not in the repository tree."""
        return self._recorded_decision_fact(
            assignment, criterion, kind="approval", wanted=Decision.APPROVED
        )

    def _attestation_fact(
        self, assignment: Assignment, criterion: AcceptanceCriterion
    ) -> RepositoryFact:
        """Attestations share the approval trail so the attesting identity is
        recorded alongside the claim (spec 8.2, risk R-8)."""
        return self._recorded_decision_fact(
            assignment, criterion, kind="attestation", wanted=Decision.ATTESTED
        )

    def _recorded_decision_fact(
        self,
        assignment: Assignment,
        criterion: AcceptanceCriterion,
        *,
        kind: str,
        wanted: Decision,
    ) -> RepositoryFact:
        """Find a record for this role carrying the decision the rule needs.

        Both role *and* decision are matched while scanning. Matching on role alone
        and reporting whatever decision the first record happened to carry produced
        a false negative: an attestation recorded before an approval would mask the
        approval that followed it.
        """
        wanted_role = str(criterion.verify.params["role"])
        seen: list[str] = []

        for record in self.audit.approvals_for(assignment.id):
            if record.role.value != wanted_role:
                continue
            if record.decision is wanted:
                return RepositoryFact(
                    kind=kind,
                    found=True,
                    detail=(
                        f"{wanted.value} by {record.actor} as {wanted_role} "
                        f"at {record.timestamp}"
                    ),
                    data={"decision": record.decision.value},
                )
            seen.append(record.decision.value)

        detail = f"no recorded '{wanted_role}' {kind} for {assignment.id}"
        if seen:
            detail += f" (found instead: {', '.join(sorted(set(seen)))})"
        return RepositoryFact(kind=kind, found=False, detail=detail)


def reject_code_evidence_on_document_work(
    assignment: Assignment, claim: CompletionClaim
) -> None:
    """Enforce spec section 4.2: code-touching evidence is invalid on architecture,
    specification, research, analysis, and document assignments.

    Raised at ingestion so a mis-routed claim never reaches verification.
    """
    if assignment.is_code_work:
        return
    offending = claim.classes_present() & CODE_EVIDENCE_CLASSES
    if offending:
        names = ", ".join(sorted(cls.value for cls in offending))
        raise ValidationError(
            f"{assignment.id}: work_type '{assignment.work_type.value}' does not permit "
            f"code-touching evidence",
            detail=(
                f"Rejected evidence classes: {names}. Document work must not change "
                "repository code (spec 4.2)."
            ),
        )


def summarise(report: VerificationReport) -> str:
    lines = [f"Verification report for {report.assignment_id}:"]
    for result in report.results:
        marker = "PASS" if result.outcome is CriterionOutcome.PASS else "FAIL"
        lines.append(f"  [{marker}] {result.criterion_id}  {result.rule}")
        lines.append(f"         {result.reason}")
    verdict = "VERIFIED" if report.passed else "REJECTED"
    lines.append(f"  => {verdict}")
    return "\n".join(lines)
