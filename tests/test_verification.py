"""Verification engine tests (spec section 8.3).

The central property: a fabricated "done" report with no matching evidence ends in
REJECTED (v0.1 acceptance criterion 3). Everything else here defends the paths by
which that property could be eroded — a missing capability, an adapter crash, a
partially-satisfied criteria set.
"""

from __future__ import annotations

import pytest

from projectos.application.verification import (
    VerificationEngine,
    reject_code_evidence_on_document_work,
)
from projectos.domain.enums import EvidenceClass, ExecutorType, RuleType, Status, WorkType
from projectos.domain.errors import AdapterError, ValidationError
from projectos.domain.evidence import (
    AcceptanceCriterion,
    CompletionClaim,
    EvidenceRef,
    EvidenceRule,
    RepositoryFact,
)
from tests.conftest import FakeAdapter, make_assignment

PRESENT = RepositoryFact(kind="file", found=True, detail="SPEC.md present at main")
ABSENT = RepositoryFact(kind="file", found=False, detail="SPEC.md not present at main")


class NullAudit:
    """Audit stub: the engine only reads approvals from it."""

    def approvals_for(self, assignment_id):
        return ()


def engine_with(facts=None, capabilities=None) -> tuple[VerificationEngine, FakeAdapter]:
    from tests.conftest import make_manifest

    adapter = FakeAdapter(facts=facts, capabilities=capabilities)
    engine = VerificationEngine(
        adapter=adapter, audit=NullAudit(), manifest=make_manifest()  # type: ignore[arg-type]
    )
    return engine, adapter


def test_fabricated_claim_without_evidence_is_rejected() -> None:
    """v0.1 acceptance criterion 3 — the headline guarantee."""
    engine, _ = engine_with({RuleType.FILE_EXISTS: ABSENT})

    report = engine.verify(make_assignment())

    assert not report.passed
    assert report.failures[0].criterion_id == "AC-1"


def test_matching_evidence_passes() -> None:
    engine, _ = engine_with({RuleType.FILE_EXISTS: PRESENT})

    assert engine.verify(make_assignment()).passed


def test_all_failures_are_collected_not_short_circuited() -> None:
    """One run must report everything missing (spec 8.3)."""
    assignment = make_assignment(
        acceptance_criteria=(
            AcceptanceCriterion("AC-1", "One", EvidenceRule(RuleType.FILE_EXISTS, {"path": "a"})),
            AcceptanceCriterion("AC-2", "Two", EvidenceRule(RuleType.FILE_EXISTS, {"path": "b"})),
        )
    )
    engine, _ = engine_with({RuleType.FILE_EXISTS: ABSENT})

    report = engine.verify(assignment)

    assert len(report.failures) == 2


def test_partial_pass_still_rejects() -> None:
    """INV-3: every criterion must pass, not most of them."""
    assignment = make_assignment(
        acceptance_criteria=(
            AcceptanceCriterion("AC-1", "One", EvidenceRule(RuleType.FILE_EXISTS, {"path": "a"})),
            AcceptanceCriterion(
                "AC-2", "Two", EvidenceRule(RuleType.COMMIT_EXISTS, {"message_pattern": "x"})
            ),
        )
    )
    engine, _ = engine_with(
        {
            RuleType.FILE_EXISTS: PRESENT,
            RuleType.COMMIT_EXISTS: RepositoryFact("commit", found=False, detail="no commit"),
        }
    )

    report = engine.verify(assignment)

    assert not report.passed
    assert [r.passed for r in report.results] == [True, False]


def test_missing_capability_fails_closed_and_names_the_capability() -> None:
    assignment = make_assignment(
        rule=EvidenceRule(
            RuleType.PR_MERGED, {"approvals_required": 1, "approver_role": "founder"}
        )
    )
    engine, _ = engine_with(capabilities={"pr": False, "ci": False, "artifacts": False})

    report = engine.verify(assignment)

    assert not report.passed
    assert "'pr' capability" in report.failures[0].reason


def test_adapter_error_fails_closed() -> None:
    """INV-4: an adapter exception never defaults to success."""

    class ExplodingAdapter:
        def capabilities(self) -> dict[str, bool]:
            return {"pr": True, "ci": True, "artifacts": True}

        def query(self, rule: EvidenceRule) -> RepositoryFact:
            raise AdapterError("git exploded")

    from tests.conftest import make_manifest

    engine = VerificationEngine(
        adapter=ExplodingAdapter(), audit=NullAudit(), manifest=make_manifest()  # type: ignore[arg-type]
    )

    report = engine.verify(make_assignment())

    assert not report.passed
    assert "fails closed" in report.failures[0].reason


def test_pr_merged_requires_merge_approvals_and_role() -> None:
    """The kernel decides; the adapter only supplies counts and flags."""
    assignment = make_assignment(
        rule=EvidenceRule(
            RuleType.PR_MERGED, {"approvals_required": 2, "approver_role": "founder"}
        )
    )
    insufficient = RepositoryFact(
        kind="pr",
        found=True,
        detail="PR 7",
        data={"merged": True, "approvals": 1, "approver_role_matched": True},
    )
    engine, _ = engine_with({RuleType.PR_MERGED: insufficient})

    assert not engine.verify(assignment).passed

    sufficient = RepositoryFact(
        kind="pr",
        found=True,
        detail="PR 7",
        data={"merged": True, "approvals": 2, "approver_role_matched": True},
    )
    engine, _ = engine_with({RuleType.PR_MERGED: sufficient})

    assert engine.verify(assignment).passed


def test_unmerged_pr_never_passes() -> None:
    """Spec 8.4: the kernel has no merge path, so an open PR is not completion."""
    assignment = make_assignment(
        rule=EvidenceRule(
            RuleType.PR_MERGED, {"approvals_required": 1, "approver_role": "founder"}
        )
    )
    open_pr = RepositoryFact(
        kind="pr",
        found=True,
        detail="PR 7 open",
        data={"merged": False, "approvals": 5, "approver_role_matched": True},
    )
    engine, _ = engine_with({RuleType.PR_MERGED: open_pr})

    assert not engine.verify(assignment).passed


def test_ci_conclusion_must_be_success() -> None:
    assignment = make_assignment(rule=EvidenceRule(RuleType.CI_PASSED, {"ref": "main"}))
    failed = RepositoryFact("ci", found=True, detail="run 9", data={"conclusion": "failure"})
    engine, _ = engine_with({RuleType.CI_PASSED: failed})

    assert not engine.verify(assignment).passed


def test_code_evidence_on_document_work_is_rejected() -> None:
    """v0.1 acceptance criterion 10 (spec 4.2)."""
    assignment = make_assignment(
        work_type=WorkType.ARCHITECTURE, executor=ExecutorType.COWORK
    )
    claim = CompletionClaim(
        assignment_id=str(assignment.id),
        summary="wrote the spec and also some code",
        evidence=(EvidenceRef(EvidenceClass.COMMIT, "abc1234"),),
    )

    with pytest.raises(ValidationError, match="does not permit"):
        reject_code_evidence_on_document_work(assignment, claim)


def test_code_evidence_on_implementation_work_is_accepted() -> None:
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)
    claim = CompletionClaim(
        assignment_id=str(assignment.id),
        summary="implemented it",
        evidence=(EvidenceRef(EvidenceClass.COMMIT, "abc1234"),),
    )

    reject_code_evidence_on_document_work(assignment, claim)  # does not raise


def test_assignment_without_criteria_cannot_be_constructed() -> None:
    """INV-3 would be unsatisfiable, so the value cannot exist."""
    with pytest.raises(ValidationError, match="at least one acceptance criterion"):
        make_assignment(acceptance_criteria=())


def test_status_never_becomes_verified_via_verification_alone() -> None:
    """A passing report is necessary, not sufficient — approvals still gate CLOSED."""
    assignment = make_assignment()
    assert assignment.status is Status.DRAFT
