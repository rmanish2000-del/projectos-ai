"""Regression tests for P1.1 — core integrity fixes.

One test (or group) per defect found in the post-implementation audit. Each was
confirmed to FAIL against the pre-fix implementation, so each genuinely pins the
defect rather than merely describing it.

Numbering matches the P1.1 assignment.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from projectos.application.integrity import verify_state
from projectos.domain.classification import classify
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
    AdapterError,
    AuditChainBroken,
    InvariantViolation,
    RuleFailure,
)
from projectos.domain.escalation import EscalationOption
from projectos.domain.evidence import (
    AcceptanceCriterion,
    EvidenceRule,
    RepositoryFact,
)
from projectos.domain.manifest import (
    Identity,
    Manifest,
    RepositoryConfig,
    WorkflowConfig,
)
from projectos.domain.pack import Pack, PackSet
from tests.conftest import FOUNDER_ID, REVIEWER_ID, FakeAdapter, kernel_as, make_assignment

PRESENT = RepositoryFact(kind="file", found=True, detail="present")
ABSENT = RepositoryFact(kind="file", found=False, detail="absent")


def drive_to_verified(kernel, adapter: FakeAdapter, assignment) -> None:
    adapter.facts[RuleType.FILE_EXISTS] = PRESENT
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)


# -- 1. Attestation identity validation ---------------------------------------


def test_attestation_by_a_non_founder_is_refused(kernel, adapter, initialised) -> None:
    """Pre-fix: any identity could attest as founder and reach VERIFIED."""
    assignment = make_assignment(
        work_type=WorkType.EXTERNAL_ACTION,
        executor=ExecutorType.HUMAN,
        rule=EvidenceRule(RuleType.HUMAN_ATTESTATION, {"role": "founder"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    stranger = kernel_as(initialised, "random-agent@nowhere.test", adapter)

    with pytest.raises(InvariantViolation, match="not the founder"):
        stranger.lifecycle.attest(assignment.id, Role.FOUNDER)


def test_forged_attestation_cannot_reach_verified(kernel, adapter, initialised) -> None:
    """The end-to-end consequence: no attestation, no pass."""
    assignment = make_assignment(
        work_type=WorkType.EXTERNAL_ACTION,
        executor=ExecutorType.HUMAN,
        rule=EvidenceRule(RuleType.HUMAN_ATTESTATION, {"role": "founder"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    stranger = kernel_as(initialised, "random-agent@nowhere.test", adapter)
    with pytest.raises(InvariantViolation):
        stranger.lifecycle.attest(assignment.id, Role.FOUNDER)

    assert not stranger.lifecycle.verify(assignment.id).report.passed


def test_attestation_and_approval_share_one_validation_path(kernel, adapter, initialised) -> None:
    """Both record evidence, so both must gate identically."""
    assignment = make_assignment(
        work_type=WorkType.EXTERNAL_ACTION,
        executor=ExecutorType.HUMAN,
        rule=EvidenceRule(RuleType.HUMAN_ATTESTATION, {"role": "founder"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    impostor = kernel_as(initialised, REVIEWER_ID, adapter)
    with pytest.raises(InvariantViolation, match="not the founder"):
        impostor.lifecycle.attest(assignment.id, Role.FOUNDER)

    # The founder may, and it then satisfies the criterion.
    kernel.lifecycle.attest(assignment.id, Role.FOUNDER)
    assert kernel.lifecycle.verify(assignment.id).report.passed


# -- 2. Audit-chain truncation detection --------------------------------------


def test_tail_truncation_is_detected(kernel, adapter, initialised) -> None:
    """Pre-fix: any prefix of a valid chain verified as intact."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    log = next(initialised.audit_dir.glob("*.ndjson"))
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 2
    log.write_text("\n".join(lines[:2]) + "\n", encoding="utf-8")

    with pytest.raises(AuditChainBroken, match="missing the entry"):
        kernel.lifecycle.verify_integrity()


def test_whole_log_deletion_is_detected(kernel, adapter, initialised) -> None:
    """Pre-fix: an empty log was indistinguishable from a fresh project."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    for log in initialised.audit_dir.glob("*.ndjson"):
        log.unlink()

    with pytest.raises(AuditChainBroken):
        kernel.lifecycle.verify_integrity()


def test_deleting_the_newest_monthly_file_is_detected(kernel, adapter, initialised) -> None:
    """Rotation must not be usable as a way to shed history."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    log = next(initialised.audit_dir.glob("*.ndjson"))
    lines = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join(lines[:1]) + "\n", encoding="utf-8")
    (initialised.audit_dir / "2026-08.ndjson").write_text("", encoding="utf-8")

    with pytest.raises(AuditChainBroken):
        kernel.lifecycle.verify_integrity()


def test_history_removed_from_an_assignment_file_is_detected(kernel, adapter, initialised) -> None:
    """The reverse tamper: log intact, state file edited."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    import yaml

    path = initialised.assignment_file(str(assignment.id))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["state"]["history"] = raw["state"]["history"][:1]
    path.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(AuditChainBroken, match="missing a transition"):
        kernel.lifecycle.verify_integrity()


def test_intact_state_verifies(kernel, adapter) -> None:
    """The check must not be so strict that honest state fails it."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)
    kernel.lifecycle.approve(assignment.id, Role.OWNER)

    report = kernel.lifecycle.verify_integrity()

    assert report.references_checked > 0


def test_truncation_halts_every_kernel_operation(kernel, adapter, initialised) -> None:
    """INV-6: a detected break stops work, not just reporting."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    log = next(initialised.audit_dir.glob("*.ndjson"))
    lines = log.read_text(encoding="utf-8").splitlines()
    log.write_text(lines[0] + "\n", encoding="utf-8")

    with pytest.raises(AuditChainBroken):
        kernel.lifecycle.generate_next()
    with pytest.raises(AuditChainBroken):
        kernel.lifecycle.approve(assignment.id, Role.OWNER)


def test_empty_project_still_verifies() -> None:
    """No assignments and no entries is a valid initial state, not a break."""
    assert verify_state((), ()).entries == 0


# -- 3. Monotonic classification ----------------------------------------------


def _manifest(default: WorkflowMode) -> Manifest:
    founder = Identity(FOUNDER_ID, "F")
    return Manifest(
        schema_version=1,
        project_id="t",
        project_name="T",
        description="",
        founder=founder,
        owners=(founder,),
        repository=RepositoryConfig(adapter="local_git"),  # type: ignore[arg-type]
        workflow=WorkflowConfig(default_mode=default),
    )


REVIEWED_PACK = PackSet(
    (
        Pack(
            schema_version=1,
            name="p",
            version="0.1.0",
            reviewed_work_types=frozenset({"implementation"}),
        ),
    )
)


def test_pack_cannot_lower_below_the_project_default() -> None:
    """Pre-fix: a GOVERNED default was pulled down to REVIEWED by a pack."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)

    result = classify(assignment, _manifest(WorkflowMode.GOVERNED), REVIEWED_PACK)

    assert result.mode is WorkflowMode.GOVERNED


def test_pack_cannot_lower_an_owner_raise() -> None:
    """Pre-fix: an owner's manual raise to GOVERNED was overridden."""
    assignment = make_assignment(
        work_type=WorkType.IMPLEMENTATION, workflow_mode=WorkflowMode.GOVERNED
    )

    result = classify(assignment, _manifest(WorkflowMode.FAST), REVIEWED_PACK)

    assert result.mode is WorkflowMode.GOVERNED


def test_pack_can_still_raise() -> None:
    """Monotonicity must not disable the raising direction."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)

    result = classify(assignment, _manifest(WorkflowMode.FAST), REVIEWED_PACK)

    assert result.mode is WorkflowMode.REVIEWED


def test_risk_flags_still_reach_governed() -> None:
    assignment = make_assignment(
        work_type=WorkType.IMPLEMENTATION, risk_flags=("security_boundary",)
    )

    result = classify(assignment, _manifest(WorkflowMode.FAST), REVIEWED_PACK)

    assert result.mode is WorkflowMode.GOVERNED


@pytest.mark.parametrize("default", list(WorkflowMode))
@pytest.mark.parametrize("declared", list(WorkflowMode))
def test_classification_is_never_below_the_floor(
    default: WorkflowMode, declared: WorkflowMode
) -> None:
    """Exhaustive monotonicity: no combination lands below the project default."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION, workflow_mode=declared)

    result = classify(assignment, _manifest(default), REVIEWED_PACK)

    assert result.mode.rank >= default.rank
    assert result.mode.rank >= min(declared.rank, WorkflowMode.GOVERNED.rank) or declared is default


# -- 4. VERIFIER_ERROR fail-closed --------------------------------------------


class ExplodingAdapter:
    """Raises something the engine does not catch, to reach the error path."""

    def capabilities(self) -> dict[str, bool]:
        return {"pr": True, "ci": True, "artifacts": True}

    def query(self, rule: EvidenceRule) -> RepositoryFact:
        raise RuntimeError("unexpected verifier explosion")


def test_unexpected_verifier_exception_rejects_rather_than_wedging(initialised) -> None:
    """Pre-fix: the assignment stuck in VERIFYING with no legal exit."""
    kernel = kernel_as(initialised, FOUNDER_ID, ExplodingAdapter())  # type: ignore[arg-type]
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    with pytest.raises(RuleFailure, match="verifier errored"):
        kernel.lifecycle.verify(assignment.id)

    stored = kernel.assignments.get(assignment.id)
    assert stored.status is Status.REJECTED
    assert stored.rejection_reasons


def test_a_wedged_assignment_can_still_be_resumed(initialised) -> None:
    """The point of failing closed is that work remains recoverable."""
    kernel = kernel_as(initialised, FOUNDER_ID, ExplodingAdapter())  # type: ignore[arg-type]
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    with pytest.raises(RuleFailure):
        kernel.lifecycle.verify(assignment.id)

    resumed, _ = kernel.lifecycle.resume(assignment.id)

    assert resumed.status is Status.ACTIVE


def test_malformed_regex_is_a_typed_adapter_error(git_repo: Path) -> None:
    """Pre-fix: a raw re.error escaped the adapter mid-transition."""
    from projectos.infrastructure.adapters import LocalGitAdapter

    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "--allow-empty", "-m", "init"],
        check=True,
        capture_output=True,
    )
    adapter = LocalGitAdapter(repo_root=git_repo, default_branch="main")

    with pytest.raises(AdapterError, match="Invalid regex"):
        adapter.query(EvidenceRule(RuleType.COMMIT_EXISTS, {"message_pattern": "[unclosed"}))


# -- 5. No fail-open working-tree fallback ------------------------------------


def test_non_git_directory_is_an_adapter_error(tmp_path: Path) -> None:
    """Pre-fix: an untracked file in a non-repo counted as evidence."""
    from projectos.infrastructure.adapters import LocalGitAdapter

    (tmp_path / "SPEC.md").write_text("hi", encoding="utf-8")
    adapter = LocalGitAdapter(repo_root=tmp_path)

    with pytest.raises(AdapterError, match="not a git repository"):
        adapter.query(EvidenceRule(RuleType.FILE_EXISTS, {"path": "SPEC.md"}))


def test_uncommitted_file_is_not_evidence(git_repo: Path) -> None:
    from projectos.infrastructure.adapters import LocalGitAdapter

    (git_repo / "SPEC.md").write_text("hi", encoding="utf-8")
    adapter = LocalGitAdapter(repo_root=git_repo, default_branch="main")

    assert not adapter.query(EvidenceRule(RuleType.FILE_EXISTS, {"path": "SPEC.md"})).found


def test_uncommitted_content_is_not_evidence_for_file_contains(git_repo: Path) -> None:
    from projectos.infrastructure.adapters import LocalGitAdapter

    (git_repo / "SPEC.md").write_text("Status: READY\n", encoding="utf-8")
    adapter = LocalGitAdapter(repo_root=git_repo, default_branch="main")

    fact = adapter.query(
        EvidenceRule(RuleType.FILE_CONTAINS, {"path": "SPEC.md", "pattern": "READY"})
    )

    assert not fact.found


# -- 6. Rule-engine default fails closed --------------------------------------


def test_unhandled_rule_type_fails_closed(monkeypatch) -> None:
    """Pre-fix: `return True` meant a new rule type silently always passed.

    Simulates a rule type with no branch by removing one from the
    'found is sufficient' set.
    """
    from projectos.domain import rule_engine

    monkeypatch.setattr(rule_engine, "_FOUND_IS_SUFFICIENT", frozenset())
    criterion = AcceptanceCriterion(
        "AC-1", "c", EvidenceRule(RuleType.FILE_EXISTS, {"path": "X"})
    )

    result = rule_engine.evaluate(criterion, RepositoryFact("file", found=True, detail="present"))

    assert not result.passed


def test_known_rule_types_still_pass_on_a_positive_fact() -> None:
    from projectos.domain import rule_engine

    criterion = AcceptanceCriterion(
        "AC-1", "c", EvidenceRule(RuleType.FILE_EXISTS, {"path": "X"})
    )

    result = rule_engine.evaluate(criterion, RepositoryFact("file", found=True, detail="present"))

    assert result.passed


# -- 7. INV-1 on every activation path ----------------------------------------


def test_resume_cannot_create_a_second_active_assignment(kernel, adapter) -> None:
    """Pre-fix: only `start` checked the slot, so `resume` bypassed INV-1."""
    adapter.facts[RuleType.FILE_EXISTS] = ABSENT
    first = make_assignment(1)
    kernel.lifecycle.create(first)
    kernel.lifecycle.classify_assignment(first.id)
    kernel.lifecycle.start(first.id)
    kernel.lifecycle.verify(first.id)  # -> REJECTED, slot now free

    second = make_assignment(2)
    kernel.lifecycle.create(second)
    kernel.lifecycle.classify_assignment(second.id)
    kernel.lifecycle.start(second.id)  # second occupies the slot

    with pytest.raises(InvariantViolation, match="is already active"):
        kernel.lifecycle.resume(first.id)


def test_founder_proceed_cannot_create_a_second_active_assignment(kernel, adapter) -> None:
    """Pre-fix: restoring the pre-escalation status bypassed INV-1."""
    first = make_assignment(1)
    kernel.lifecycle.create(first)
    kernel.lifecycle.classify_assignment(first.id)
    kernel.lifecycle.start(first.id)

    escalation = kernel.lifecycle.escalate(
        trigger=EscalationTrigger.FOUNDER_DECISION,
        summary="A scope question",
        options=(
            EscalationOption("O1", "Proceed", "Work continues."),
            EscalationOption("O2", "Cancel", "Work stops."),
        ),
        assignment_id=first.id,
    )

    second = make_assignment(2)
    kernel.lifecycle.create(second)
    kernel.lifecycle.classify_assignment(second.id)
    kernel.lifecycle.start(second.id)

    with pytest.raises(InvariantViolation, match="is already active"):
        kernel.lifecycle.resolve(escalation.id, "O1", FounderDecision.PROCEED)


def test_founder_proceed_still_works_when_the_slot_is_free(kernel, adapter) -> None:
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    escalation = kernel.lifecycle.escalate(
        trigger=EscalationTrigger.FOUNDER_DECISION,
        summary="A scope question",
        options=(
            EscalationOption("O1", "Proceed", "Work continues."),
            EscalationOption("O2", "Cancel", "Work stops."),
        ),
        assignment_id=assignment.id,
    )

    _, updated = kernel.lifecycle.resolve(escalation.id, "O1", FounderDecision.PROCEED)

    assert updated is not None
    assert updated.status is Status.ACTIVE


# -- 8. Escalation validated before persistence -------------------------------


def test_illegal_escalation_writes_nothing(kernel, adapter) -> None:
    """Pre-fix: the record and its audit entry were written, then the freeze failed,
    leaving an orphan escalation blocking the project."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)  # VERIFIED has no `escalate` edge

    escalations_before = len(kernel.escalations.list_all())
    entries_before = len(kernel.audit.read_all())

    from projectos.domain.errors import IllegalTransition

    with pytest.raises(IllegalTransition):
        kernel.lifecycle.escalate(
            trigger=EscalationTrigger.FOUNDER_DECISION,
            summary="Cannot freeze a verified assignment",
            options=(
                EscalationOption("O1", "One", "Consequence one."),
                EscalationOption("O2", "Two", "Consequence two."),
            ),
            assignment_id=assignment.id,
        )

    assert len(kernel.escalations.list_all()) == escalations_before
    assert len(kernel.audit.read_all()) == entries_before
    assert not kernel.lifecycle.open_escalations()


def test_legal_escalation_still_freezes(kernel, adapter) -> None:
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    kernel.lifecycle.escalate(
        trigger=EscalationTrigger.FOUNDER_DECISION,
        summary="A real decision",
        options=(
            EscalationOption("O1", "One", "Consequence one."),
            EscalationOption("O2", "Two", "Consequence two."),
        ),
        assignment_id=assignment.id,
    )

    assert kernel.assignments.get(assignment.id).status is Status.ESCALATED


# -- 9. Owner approval validated against manifest owners ----------------------


def test_owner_approval_from_a_stranger_is_refused(kernel, adapter, initialised) -> None:
    """Pre-fix: FAST mode closed on an owner approval from any --identity."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    stranger = kernel_as(initialised, "nobody@nowhere.test", adapter)

    with pytest.raises(InvariantViolation, match=r"not listed in manifest\.owners"):
        stranger.lifecycle.approve(assignment.id, Role.OWNER)


def test_owner_approval_from_a_non_owner_of_this_assignment_is_refused(
    kernel, adapter, initialised
) -> None:
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    other = kernel_as(initialised, REVIEWER_ID, adapter)

    with pytest.raises(InvariantViolation):
        other.lifecycle.approve(assignment.id, Role.OWNER)


def test_the_real_owner_may_still_approve(kernel, adapter) -> None:
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    closed, _ = kernel.lifecycle.approve(assignment.id, Role.OWNER)

    assert closed.status is Status.CLOSED


# -- 10. Approval defaults never imply approval -------------------------------


def test_an_entry_without_a_decision_grants_nothing(kernel, adapter) -> None:
    """Pre-fix: a missing `decision` key was read back as 'approved'."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    # Append a properly sealed entry that states a role but no decision.
    kernel.lifecycle._append_event(
        "approval_recorded",
        assignment_id=str(assignment.id),
        data={"role": "owner", "actor": FOUNDER_ID},
    )

    assert kernel.audit.approvals_for(assignment.id) == ()
    assert kernel.assignments.get(assignment.id).status is Status.VERIFIED


def test_a_stated_approval_still_counts(kernel, adapter) -> None:
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)
    kernel.lifecycle.approve(assignment.id, Role.OWNER)

    recorded = kernel.audit.approvals_for(assignment.id)

    assert [r.decision for r in recorded] == ["approved"]


# -- 11. EvidenceRule.params is frozen ----------------------------------------


def test_rule_params_cannot_be_mutated() -> None:
    """Pre-fix: a validated `approvals_required: 2` could be rewritten to 0."""
    rule = EvidenceRule(RuleType.PR_MERGED, {"approvals_required": 2, "approver_role": "founder"})

    with pytest.raises(TypeError):
        rule.params["approvals_required"] = 0  # type: ignore[index]


def test_rule_params_cannot_be_cleared_or_extended() -> None:
    rule = EvidenceRule(RuleType.FILE_EXISTS, {"path": "SPEC.md"})

    with pytest.raises(TypeError):
        del rule.params["path"]  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        rule.params["at_ref"] = "other"  # type: ignore[index]


def test_mutating_the_source_dict_does_not_affect_the_rule() -> None:
    """The rule copies before freezing, so the caller's dict is not a back door."""
    source = {"approvals_required": 2, "approver_role": "founder"}
    rule = EvidenceRule(RuleType.PR_MERGED, source)

    source["approvals_required"] = 0

    assert rule.params["approvals_required"] == 2


def test_a_frozen_rule_still_serialises_and_round_trips() -> None:
    from projectos.infrastructure.serialization import assignment_from_dict, assignment_to_dict

    original = make_assignment(
        rule=EvidenceRule(RuleType.PR_MERGED, {"approvals_required": 2, "approver_role": "founder"})
    )

    assert assignment_from_dict(assignment_to_dict(original), source="test") == original


# -- 12. No infrastructure dependency in the application layer ----------------


def test_application_layer_does_not_import_infrastructure() -> None:
    """Pre-fix: lifecycle._materialise imported infrastructure.template_binding.

    Scans source text rather than module objects so a function-local import — the
    exact form the original violation took — is still caught.
    """
    application = Path(__file__).resolve().parents[1] / "src" / "projectos" / "application"
    offenders: list[str] = []

    for path in application.rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            if "projectos.infrastructure" in stripped or "projectos.cli" in stripped:
                offenders.append(f"{path.name}:{number}: {stripped}")

    assert offenders == [], "application layer must not import outward:\n" + "\n".join(offenders)


def test_domain_layer_does_not_import_outward() -> None:
    domain = Path(__file__).resolve().parents[1] / "src" / "projectos" / "domain"
    offenders: list[str] = []

    for path in domain.rglob("*.py"):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            if any(
                layer in stripped
                for layer in ("projectos.application", "projectos.infrastructure", "projectos.cli")
            ):
                offenders.append(f"{path.name}:{number}: {stripped}")

    assert offenders == [], "domain must import nothing outward:\n" + "\n".join(offenders)


def test_template_binding_still_works_through_the_port(kernel, adapter) -> None:
    """The port must be wired, not merely declared."""
    first = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, first)
    kernel.lifecycle.approve(first.id, Role.OWNER)

    result = kernel.lifecycle.generate_next()

    assert result.assignment is not None
    assert result.assignment.origin_template == "design-spec"
