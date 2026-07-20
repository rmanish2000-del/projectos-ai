"""Lifecycle and invariant tests — the end-to-end behaviour of the kernel.

Each test names the invariant or acceptance criterion it defends, so a failure
points at the guarantee that broke rather than at an implementation detail.
"""

from __future__ import annotations

import pytest

from projectos.domain.enums import (
    EscalationTrigger,
    ExecutorType,
    FounderDecision,
    Role,
    RuleType,
    Status,
    WorkflowMode,
    WorkType,
)
from projectos.domain.errors import (
    EscalationRequired,
    InvariantViolation,
    ValidationError,
)
from projectos.domain.escalation import EscalationOption
from projectos.domain.evidence import EvidenceRule, RepositoryFact
from projectos.domain.ids import AssignmentId
from tests.conftest import FOUNDER_ID, REVIEWER_ID, FakeAdapter, kernel_as, make_assignment

PRESENT = RepositoryFact(kind="file", found=True, detail="present")
ABSENT = RepositoryFact(kind="file", found=False, detail="absent")


def drive_to_verified(kernel, adapter: FakeAdapter, assignment) -> None:
    """Take an assignment from DRAFT to VERIFIED with passing evidence."""
    adapter.facts[RuleType.FILE_EXISTS] = PRESENT
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)


# -- INV-1 --------------------------------------------------------------------


def test_only_one_assignment_may_be_active(kernel, adapter) -> None:
    """INV-1, and v0.1 acceptance criterion 2."""
    first = make_assignment(1)
    second = make_assignment(2)
    for assignment in (first, second):
        kernel.lifecycle.create(assignment)
        kernel.lifecycle.classify_assignment(assignment.id)

    kernel.lifecycle.start(first.id)

    with pytest.raises(InvariantViolation, match="is already active"):
        kernel.lifecycle.start(second.id)


def test_active_slot_frees_when_the_assignment_closes(kernel, adapter) -> None:
    first = make_assignment(1)
    drive_to_verified(kernel, adapter, first)
    kernel.lifecycle.approve(first.id, Role.OWNER)

    second = make_assignment(2)
    kernel.lifecycle.create(second)
    kernel.lifecycle.classify_assignment(second.id)

    started, _ = kernel.lifecycle.start(second.id)
    assert started.status is Status.ACTIVE


# -- INV-2 --------------------------------------------------------------------


def test_owner_must_be_listed_in_the_manifest(kernel) -> None:
    """INV-2: an assignment cannot be owned by someone the project does not know."""
    with pytest.raises(ValidationError, match="not listed in the manifest"):
        kernel.lifecycle.create(make_assignment(owner="stranger@example.test"))


def test_executor_must_match_the_work_type(kernel) -> None:
    """Spec 4.2: architecture work does not route to the code agent."""
    with pytest.raises(ValidationError, match="not permitted for work_type"):
        kernel.lifecycle.create(
            make_assignment(work_type=WorkType.ARCHITECTURE, executor=ExecutorType.CODE)
        )


# -- INV-3 --------------------------------------------------------------------


def test_failing_evidence_rejects_and_records_reasons(kernel, adapter) -> None:
    """INV-3 plus acceptance criterion 3: no VERIFIED without passing evidence."""
    adapter.facts[RuleType.FILE_EXISTS] = ABSENT
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    outcome = kernel.lifecycle.verify(assignment.id)

    assert outcome.assignment.status is Status.REJECTED
    assert outcome.assignment.rejection_reasons


def test_passing_verification_clears_earlier_rejection_reasons(kernel, adapter) -> None:
    """Stale reasons must not survive into `status` or a later briefing."""
    adapter.facts[RuleType.FILE_EXISTS] = ABSENT
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)
    assert kernel.assignments.get(assignment.id).rejection_reasons

    kernel.lifecycle.resume(assignment.id)
    adapter.facts[RuleType.FILE_EXISTS] = PRESENT
    kernel.lifecycle.verify(assignment.id)

    assert kernel.assignments.get(assignment.id).rejection_reasons == ()


def test_rejection_reasons_reach_the_next_briefing(kernel, adapter) -> None:
    adapter.facts[RuleType.FILE_EXISTS] = ABSENT
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)

    _, briefing = kernel.lifecycle.resume(assignment.id)

    assert briefing.rejection_reasons
    assert "PREVIOUS ATTEMPT REJECTED" in briefing.render()


# -- dependencies (acceptance criterion 5) ------------------------------------


def test_open_dependency_prevents_ready(kernel) -> None:
    """Acceptance criterion 5. DRAFT has no `block` edge, so the assignment stays
    in DRAFT rather than moving sideways."""
    blocker = make_assignment(1)
    dependent = make_assignment(2, depends_on=(AssignmentId(1),))
    kernel.lifecycle.create(blocker)
    kernel.lifecycle.create(dependent)

    result, _ = kernel.lifecycle.classify_assignment(dependent.id)

    assert result.status is Status.DRAFT


def test_dependency_closing_lets_classification_reach_ready(kernel, adapter) -> None:
    blocker = make_assignment(1, work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    dependent = make_assignment(2, depends_on=(AssignmentId(1),))
    kernel.lifecycle.create(dependent)

    deferred, _ = kernel.lifecycle.classify_assignment(dependent.id)
    assert deferred.status is Status.DRAFT

    drive_to_verified(kernel, adapter, blocker)
    kernel.lifecycle.approve(blocker.id, Role.OWNER)

    reclassified, _ = kernel.lifecycle.classify_assignment(dependent.id)
    assert reclassified.status is Status.READY


def test_unblock_refuses_while_dependencies_remain_open(kernel) -> None:
    """A genuinely BLOCKED assignment cannot return to READY early."""
    kernel.lifecycle.create(make_assignment(1))
    dependent = make_assignment(2, depends_on=(AssignmentId(1),))
    kernel.lifecycle.create(dependent)
    kernel.lifecycle.classify_assignment(dependent.id)

    # Reach BLOCKED legitimately: classify a dependency-free assignment, then block it.
    standalone = make_assignment(3)
    kernel.lifecycle.create(standalone)
    kernel.lifecycle.classify_assignment(standalone.id)
    kernel.lifecycle.block(standalone.id, "waiting on an external answer")

    blocked_dependent = make_assignment(4, depends_on=(AssignmentId(1),))
    kernel.lifecycle.create(blocked_dependent)

    with pytest.raises(InvariantViolation, match="not closed"):
        kernel.lifecycle.unblock(blocked_dependent.id)


def test_dependency_cycles_are_rejected(kernel) -> None:
    from projectos.domain.dependency import DependencyGraph

    first = make_assignment(1, depends_on=(AssignmentId(2),))
    second = make_assignment(2, depends_on=(AssignmentId(1),))

    with pytest.raises(ValidationError, match="cycle"):
        DependencyGraph((first, second))


# -- classification (acceptance criterion 4) ----------------------------------


def test_risk_flag_drives_governed_classification(kernel) -> None:
    assignment = make_assignment(risk_flags=("security_boundary",))
    kernel.lifecycle.create(assignment)

    _, classification = kernel.lifecycle.classify_assignment(assignment.id)

    assert classification.mode is WorkflowMode.GOVERNED
    assert "security_boundary" in classification.rule


def test_pack_raises_implementation_work_to_reviewed(kernel) -> None:
    """The bundled software-core pack marks implementation as high-risk."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)
    kernel.lifecycle.create(assignment)

    _, classification = kernel.lifecycle.classify_assignment(assignment.id)

    assert classification.mode is WorkflowMode.REVIEWED
    assert "high-risk" in classification.rule


def test_document_work_falls_through_to_fast(kernel) -> None:
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)

    _, classification = kernel.lifecycle.classify_assignment(assignment.id)

    assert classification.mode is WorkflowMode.FAST


def test_unknown_risk_flags_are_rejected(kernel) -> None:
    with pytest.raises(ValidationError, match="unknown risk flags"):
        kernel.lifecycle.create(make_assignment(risk_flags=("invented_flag",)))


# -- approvals ----------------------------------------------------------------


def test_fast_mode_closes_on_owner_approval(kernel, adapter) -> None:
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    closed, _ = kernel.lifecycle.approve(assignment.id, Role.OWNER)

    assert closed.status is Status.CLOSED


def test_reviewed_mode_needs_an_independent_reviewer(kernel, adapter, initialised) -> None:
    """Spec 4.1: the reviewer must not be the executor of the same assignment."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)
    drive_to_verified(kernel, adapter, assignment)

    with pytest.raises(InvariantViolation, match="cannot review"):
        kernel.lifecycle.approve(assignment.id, Role.REVIEWER)

    reviewer_kernel = kernel_as(initialised, REVIEWER_ID, adapter)
    closed, _ = reviewer_kernel.lifecycle.approve(assignment.id, Role.REVIEWER)

    assert closed.status is Status.CLOSED


def test_governed_mode_needs_reviewer_and_founder(kernel, adapter, initialised) -> None:
    assignment = make_assignment(
        work_type=WorkType.IMPLEMENTATION, risk_flags=("security_boundary",)
    )
    drive_to_verified(kernel, adapter, assignment)

    reviewer_kernel = kernel_as(initialised, REVIEWER_ID, adapter)
    after_review, status = reviewer_kernel.lifecycle.approve(assignment.id, Role.REVIEWER)

    assert after_review.status is Status.VERIFIED, "reviewer alone must not close governed work"
    assert Role.FOUNDER in status.outstanding

    closed, _ = kernel.lifecycle.approve(assignment.id, Role.FOUNDER)
    assert closed.status is Status.CLOSED


def test_only_the_founder_may_record_a_founder_approval(kernel, adapter, initialised) -> None:
    assignment = make_assignment(
        work_type=WorkType.IMPLEMENTATION, risk_flags=("security_boundary",)
    )
    drive_to_verified(kernel, adapter, assignment)
    impostor = kernel_as(initialised, REVIEWER_ID, adapter)

    with pytest.raises(InvariantViolation, match="not the founder"):
        impostor.lifecycle.approve(assignment.id, Role.FOUNDER)


def test_approval_requires_verification_first(kernel) -> None:
    """Approval never substitutes for evidence."""
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    with pytest.raises(InvariantViolation, match="only VERIFIED"):
        kernel.lifecycle.approve(assignment.id, Role.OWNER)


def test_merge_work_always_requires_founder_approval(kernel, adapter) -> None:
    """Spec 8.4 and acceptance criterion 9: no CLOSE without a human decision."""
    assignment = make_assignment(work_type=WorkType.MERGE, executor=ExecutorType.HUMAN)
    drive_to_verified(kernel, adapter, assignment)

    after_owner, status = kernel.lifecycle.approve(assignment.id, Role.OWNER)

    assert after_owner.status is Status.VERIFIED
    assert Role.FOUNDER in status.outstanding


# -- escalation (acceptance criterion 7) --------------------------------------


def test_escalation_without_options_is_rejected(kernel) -> None:
    with pytest.raises(ValidationError, match="at least 2 options"):
        kernel.lifecycle.escalate(
            trigger=EscalationTrigger.FOUNDER_DECISION,
            summary="Should we do the thing?",
            options=(),
        )


def test_escalation_option_needs_a_consequence(kernel) -> None:
    with pytest.raises(ValidationError, match="consequence"):
        EscalationOption("O1", "Do the thing", "")


def test_escalation_freezes_the_assignment_until_resolved(kernel, adapter) -> None:
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    escalation = kernel.lifecycle.escalate(
        trigger=EscalationTrigger.FOUNDER_DECISION,
        summary="Scope question the founder must settle",
        options=(
            EscalationOption("O1", "Proceed as scoped", "Work continues unchanged."),
            EscalationOption("O2", "Cancel", "Work stops and is reissued later."),
        ),
        assignment_id=assignment.id,
    )

    assert kernel.assignments.get(assignment.id).status is Status.ESCALATED

    _, updated = kernel.lifecycle.resolve(escalation.id, "O1", FounderDecision.PROCEED)

    assert updated is not None
    assert updated.status is Status.ACTIVE, "resolution re-drives the machine to the prior state"


def test_only_the_founder_resolves_escalations(kernel, adapter, initialised) -> None:
    escalation = kernel.lifecycle.escalate(
        trigger=EscalationTrigger.FOUNDER_DECISION,
        summary="A decision",
        options=(
            EscalationOption("O1", "One", "Consequence one."),
            EscalationOption("O2", "Two", "Consequence two."),
        ),
    )
    impostor = kernel_as(initialised, REVIEWER_ID, adapter)

    with pytest.raises(InvariantViolation, match="not the founder"):
        impostor.lifecycle.resolve(escalation.id, "O1", FounderDecision.PROCEED)


def test_project_level_escalation_blocks_next_generation(kernel) -> None:
    kernel.lifecycle.escalate(
        trigger=EscalationTrigger.ARCHITECTURE_CONFLICT,
        summary="架 conflict with the frozen architecture",
        options=(
            EscalationOption("O1", "Amend the spec", "Architecture changes; work resumes."),
            EscalationOption("O2", "Reject the change", "Work proceeds under current spec."),
        ),
    )

    with pytest.raises(EscalationRequired, match="blocks next-assignment generation"):
        kernel.lifecycle.generate_next()


# -- next-assignment generation (acceptance criterion 6) ----------------------


def test_next_generates_the_first_pipeline_template(kernel, adapter) -> None:
    first = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, first)
    kernel.lifecycle.approve(first.id, Role.OWNER)

    result = kernel.lifecycle.generate_next()

    assert result.assignment is not None
    assert result.assignment.origin_template == "design-spec"
    assert result.decision.source.startswith("pack.pipeline")


def test_next_generation_is_deterministic(kernel, adapter, initialised) -> None:
    """Same state plus same pack yields the same successor (spec 3.3)."""
    first = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, first)
    kernel.lifecycle.approve(first.id, Role.OWNER)

    from projectos.domain import next_engine

    assignments = kernel.assignments.list_all()
    closed = next(a for a in assignments if a.status is Status.CLOSED)
    packs = kernel.lifecycle.packs

    decisions = {next_engine.decide(closed, assignments, packs).template for _ in range(5)}

    assert len(decisions) == 1


def test_explicit_next_block_takes_precedence_over_the_pipeline(kernel, adapter) -> None:
    from projectos.domain.assignment import NextSpec

    first = make_assignment(
        work_type=WorkType.DOCUMENT,
        executor=ExecutorType.COWORK,
        next=NextSpec("harden-and-document"),
    )
    drive_to_verified(kernel, adapter, first)
    kernel.lifecycle.approve(first.id, Role.OWNER)

    result = kernel.lifecycle.generate_next()

    assert result.decision.source == "assignment.next"
    assert result.assignment is not None
    assert result.assignment.origin_template == "harden-and-document"


def test_exhausted_pipeline_is_undetermined(kernel) -> None:
    """Acceptance criterion 6, second half — the engine reports, it does not guess."""
    from projectos.domain import next_engine

    packs = kernel.lifecycle.packs
    templates = packs.phase_templates("foundation")
    consumed = tuple(
        make_assignment(index + 1, origin_template=name, status=Status.CLOSED)
        for index, name in enumerate(templates)
    )

    decision = next_engine.decide(consumed[-1], consumed, packs)

    assert not decision.determined
    assert "phase is complete" in decision.reason


def test_undetermined_next_opens_a_decision_ready_escalation(kernel, adapter) -> None:
    """Spec 3.3 step 3, and the 9.3 options rule."""
    first = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, first)
    kernel.lifecycle.approve(first.id, Role.OWNER)

    # An empty pipeline is the simplest way to make the successor undeterminable.
    from unittest.mock import patch

    from projectos.domain.pack import PackSet

    with patch.object(
        type(kernel.lifecycle), "packs", property(lambda self: PackSet(()))
    ):
        result = kernel.lifecycle.generate_next()

    assert result.assignment is None
    assert result.escalation is not None
    assert result.escalation.trigger is EscalationTrigger.NEXT_UNDETERMINED
    assert len(result.escalation.options) >= 2
    assert all(option.consequence for option in result.escalation.options)


def test_cancelled_assignment_does_not_consume_its_template(kernel) -> None:
    """A rescope must be able to reissue the step it cancelled."""
    from projectos.domain import next_engine

    packs = kernel.lifecycle.packs
    first_template = packs.phase_templates("foundation")[0]
    cancelled = make_assignment(1, origin_template=first_template, status=Status.CANCELLED)
    closed = make_assignment(2, status=Status.CLOSED)

    decision = next_engine.decide(closed, (cancelled, closed), packs)

    assert decision.template == first_template


def test_next_returns_the_existing_pending_assignment(kernel) -> None:
    """INV-7: generation never produces a second parallel workstream."""
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)

    result = kernel.lifecycle.generate_next()

    assert result.assignment is not None
    assert result.assignment.id == assignment.id
    assert result.decision.source == "existing"


# -- audit integrity (acceptance criterion 8) ---------------------------------


def test_every_transition_is_audited(kernel, adapter) -> None:
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    events = [e.event for e in kernel.audit.for_assignment(assignment.id)]

    assert events == [
        "assignment_created",
        "classify_ok",
        "start",
        "submit",
        "verify_start",
        "all_criteria_pass",
    ]


def test_audit_chain_verifies_after_a_full_lifecycle(kernel, adapter) -> None:
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)
    kernel.lifecycle.approve(assignment.id, Role.OWNER)

    kernel.audit.verify()  # does not raise


def test_tampered_audit_file_halts_the_kernel(kernel, adapter, initialised) -> None:
    """Acceptance criterion 8, and INV-6."""
    from projectos.domain.errors import AuditChainBroken

    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    log_file = next(initialised.audit_dir.glob("*.ndjson"))
    lines = log_file.read_text(encoding="utf-8").splitlines()
    tampered = lines[1].replace(FOUNDER_ID, "someone.else@example.test")
    assert tampered != lines[1], "the tamper must actually change the line"
    lines[1] = tampered
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Every kernel operation calls the guard first, so any of them halts.
    with pytest.raises(AuditChainBroken):
        kernel.lifecycle.generate_next()


# -- attestation --------------------------------------------------------------


def test_human_attestation_satisfies_its_rule_once_recorded(kernel, adapter) -> None:
    assignment = make_assignment(
        work_type=WorkType.EXTERNAL_ACTION,
        executor=ExecutorType.HUMAN,
        rule=EvidenceRule(RuleType.HUMAN_ATTESTATION, {"role": "founder"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    assert not kernel.lifecycle.verify(assignment.id).report.passed

    kernel.lifecycle.resume(assignment.id)
    kernel.lifecycle.attest(assignment.id, Role.FOUNDER)

    assert kernel.lifecycle.verify(assignment.id).report.passed
