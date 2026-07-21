"""Regression and mutation-resistance tests for P1.6 — final integrity remediation.

Covers the five P1.4 blockers and the P1.5 audit-authenticity contract (§6.1, §8.6).

Two kinds of test live here:

* ``@REGRESSION`` — black-box tests, driven through the kernel/CLI and file edits,
  that reproduce a P1.4 exploit and assert it now fails. Each was confirmed to FAIL
  against commit ``2a67240`` (the pre-fix tree) before the fix.
* ``@MUTATION`` — behaviour tests that each pin one production check, so that
  removing that single check fails at least one test. These target the eight
  mutation survivors the P1.4 review found. They are not expected to fail pre-fix
  (the behaviour already held); their job is to make the guarantee *tested*.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from projectos.cli.main import main
from projectos.domain import rule_engine
from projectos.domain.approvals import evaluate as evaluate_approvals
from projectos.domain.approvals import is_authorized
from projectos.domain.audit import AuditEntry, seal_next, verify_chain
from projectos.domain.digest import immutable_digest
from projectos.domain.enums import (
    Decision,
    ExecutorType,
    Role,
    RuleType,
    Status,
    WorkflowMode,
    WorkType,
)
from projectos.domain.errors import AuditChainBroken, ExitCode, InvariantViolation
from projectos.domain.evidence import (
    AcceptanceCriterion,
    ApprovalRecord,
    EvidenceRule,
    RepositoryFact,
    VerificationReport,
)
from tests.conftest import (
    FOUNDER_ID,
    FOUNDER_NAME,
    REVIEWER_ID,
    FakeAdapter,
    kernel_as,
    make_assignment,
    make_manifest,
)

PRESENT = RepositoryFact(kind="file", found=True, detail="present")
ABSENT = RepositoryFact(kind="file", found=False, detail="absent")


def drive_to_verified(kernel, adapter: FakeAdapter, assignment) -> None:
    adapter.facts[RuleType.FILE_EXISTS] = PRESENT
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)


def newest_log(layout) -> Path:
    return sorted(layout.audit_dir.glob("*.ndjson"))[-1]


def append_forged(layout, *, event: str, assignment_id: str, data: dict) -> None:
    """Append a correctly hash-linked entry — the P1.4 append-forgery primitive."""
    log = newest_log(layout)
    lines = log.read_text(encoding="utf-8").splitlines()
    last = AuditEntry.from_dict(json.loads(lines[-1]))
    forged = seal_next(
        AuditEntry(
            sequence=0,
            timestamp="2026-07-21T09:00:00Z",
            event=event,
            actor=str(data.get("actor", "forger@evil.test")),
            assignment_id=assignment_id,
            data=data,
        ),
        last,
    )
    log.write_text("\n".join([*lines, json.dumps(forged.to_dict(), sort_keys=True)]) + "\n",
                   encoding="utf-8")


# =============================================================================
# Blocker 1 — direct status mutation
# =============================================================================


def test_status_edited_to_closed_halts_the_kernel(kernel, adapter, initialised) -> None:
    """@REGRESSION — a one-line `status: closed` edit forged CLOSED pre-fix."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    path = initialised.assignment_file(str(assignment.id))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["state"]["status"] = "closed"
    path.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(AuditChainBroken, match="does not match its history"):
        kernel.lifecycle.verify_integrity()


def test_non_draft_with_empty_history_is_rejected(kernel, adapter, initialised) -> None:
    """@REGRESSION — invalid initial-state representation."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)

    path = initialised.assignment_file(str(assignment.id))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw["state"]["status"] = "active"
    raw["state"]["history"] = []
    path.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")

    with pytest.raises(AuditChainBroken, match="no transition history"):
        kernel.lifecycle.verify_integrity()


def test_untouched_state_still_verifies(kernel, adapter) -> None:
    """@MUTATION — the consistency check must not reject honest state."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)
    kernel.lifecycle.approve(assignment.id, Role.OWNER)

    kernel.lifecycle.verify_integrity()  # does not raise


# =============================================================================
# Blocker 2 — mutable scope / classification after DRAFT
# =============================================================================


def _tamper_immutable(path: Path, mutate) -> None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(raw)
    path.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")


def test_acceptance_criteria_edit_halts_the_kernel(kernel, adapter, initialised) -> None:
    """@REGRESSION — swapping a rule after DRAFT closed REVIEWED work as owner pre-fix."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)

    def swap(raw: dict) -> None:
        raw["acceptance_criteria"][0]["verify"] = {"type": "file_exists", "path": "x"}

    _tamper_immutable(initialised.assignment_file(str(assignment.id)), swap)

    with pytest.raises(AuditChainBroken, match="immutable fields have been edited"):
        kernel.lifecycle.verify_integrity()


def test_workflow_mode_lowering_halts_the_kernel(kernel, adapter, initialised) -> None:
    """@REGRESSION — reviewed→fast after classify let the owner self-close."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)  # REVIEWED
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)

    def lower(raw: dict) -> None:
        raw["workflow_mode"] = "fast"

    _tamper_immutable(initialised.assignment_file(str(assignment.id)), lower)

    with pytest.raises(AuditChainBroken, match="immutable fields have been edited"):
        kernel.lifecycle.verify_integrity()


def test_rule_parameter_mutation_halts_the_kernel(kernel, adapter, initialised) -> None:
    """@REGRESSION — the digest covers rule *parameters*, not just rule types.

    The mutation is chosen to be schema-valid (`founder` → `owner`, both permitted
    `approver_role` values) so the digest — not schema validation — is the check
    under test: a weaker approver requirement that the schema alone would accept is
    still caught.
    """
    assignment = make_assignment(
        rule=EvidenceRule(RuleType.PR_MERGED, {"approvals_required": 2, "approver_role": "founder"})
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)

    def weaken(raw: dict) -> None:
        raw["acceptance_criteria"][0]["verify"]["approver_role"] = "owner"

    _tamper_immutable(initialised.assignment_file(str(assignment.id)), weaken)

    with pytest.raises(AuditChainBroken, match="immutable fields have been edited"):
        kernel.lifecycle.verify_integrity()


def test_excluded_fields_do_not_trip_the_digest(kernel, adapter, initialised) -> None:
    """@MUTATION — editing kernel-annotation fields (excluded from §6.1) is allowed.

    Guards against an over-broad digest that would false-positive on the normal
    reject/resume cycle, which legitimately rewrites rejection_reasons.
    """
    adapter.facts[RuleType.FILE_EXISTS] = ABSENT
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)  # -> REJECTED, writes rejection_reasons

    kernel.lifecycle.verify_integrity()  # rejection_reasons/classification_rule excluded

    path = initialised.assignment_file(str(assignment.id))
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw.get("rejection_reasons"), "the resume cycle should have written reasons"


def test_digest_is_stable_across_a_save_reload(kernel, adapter, initialised) -> None:
    """@MUTATION — the digest recomputed from a reloaded file matches the bound value."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)
    kernel.lifecycle.create(assignment)
    ready, _ = kernel.lifecycle.classify_assignment(assignment.id)
    reloaded = kernel.assignments.get(assignment.id)

    assert immutable_digest(reloaded) == immutable_digest(ready)


# =============================================================================
# Blocker 3 — audit append forgery / authority
# =============================================================================


def test_forged_unauthorized_approval_grants_nothing(kernel, adapter, initialised) -> None:
    """@REGRESSION — an appended reviewer approval by an unknown identity closed
    REVIEWED work pre-fix. Now it grants nothing."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)  # REVIEWED
    drive_to_verified(kernel, adapter, assignment)

    append_forged(
        initialised,
        event="approval_recorded",
        assignment_id=str(assignment.id),
        data={"role": "reviewer", "decision": "approved", "actor": "ghost@nowhere.test"},
    )

    # The chain still verifies (an append is not corruption, §8.6) ...
    kernel.lifecycle.verify_integrity()
    # ... but the forged approval is not counted: no authorized reviewer approval.
    status = kernel.lifecycle.approval_status(kernel.assignments.get(assignment.id))
    assert Role.REVIEWER in status.outstanding


def test_forged_approval_does_not_satisfy_an_approval_criterion(
    kernel, adapter, initialised
) -> None:
    """@REGRESSION — the same forgery must not satisfy an approval_recorded rule."""
    assignment = make_assignment(
        work_type=WorkType.EXTERNAL_ACTION,
        executor=ExecutorType.HUMAN,
        rule=EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": "reviewer"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    append_forged(
        initialised,
        event="approval_recorded",
        assignment_id=str(assignment.id),
        data={"role": "reviewer", "decision": "approved", "actor": "ghost@nowhere.test"},
    )

    assert not kernel.lifecycle.verify(assignment.id).report.passed


def test_role_mismatch_is_rejected() -> None:
    """@REGRESSION — an approval recorded for one role must not satisfy another."""
    from tests.test_regressions_p1_2 import approval_criterion, engine_over

    engine = engine_over(
        (ApprovalRecord("A-0001", Role.OWNER, FOUNDER_ID, Decision.APPROVED, "t",
                        "approval_recorded"),)
    )
    fact = engine._approval_fact(make_assignment(), approval_criterion("founder"))
    assert not fact.found


def test_decision_mismatch_is_rejected() -> None:
    """@REGRESSION — event/decision binding: attestation_recorded must carry attested."""
    from tests.test_regressions_p1_2 import approval_criterion, engine_over

    # A hand-forged attestation entry claiming decision=approved.
    engine = engine_over(
        (ApprovalRecord("A-0001", Role.FOUNDER, FOUNDER_ID, Decision.APPROVED, "t",
                        "attestation_recorded"),)
    )
    fact = engine._approval_fact(make_assignment(), approval_criterion("founder"))
    assert not fact.found


def test_attestation_cannot_satisfy_an_approval_rule(kernel, adapter, initialised) -> None:
    """@REGRESSION — an attestation must never count as an approval."""
    assignment = make_assignment(
        work_type=WorkType.EXTERNAL_ACTION,
        executor=ExecutorType.HUMAN,
        rule=EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": "founder"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.attest(assignment.id, Role.FOUNDER)  # legitimate attestation

    assert not kernel.lifecycle.verify(assignment.id).report.passed


def test_authorized_reviewer_still_closes(kernel, adapter, initialised) -> None:
    """@MUTATION — the positive path: a manifest-owner reviewer distinct from the
    owner can still close REVIEWED work."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)  # owner = FOUNDER_ID
    drive_to_verified(kernel, adapter, assignment)

    reviewer = kernel_as(initialised, REVIEWER_ID, adapter)  # REVIEWER_ID is a manifest owner
    closed, _ = reviewer.lifecycle.approve(assignment.id, Role.REVIEWER)

    assert closed.status is Status.CLOSED


def test_authority_predicate_matrix() -> None:
    """@MUTATION — the shared is_authorized predicate (spec 8.6.2)."""
    m = make_manifest()  # owners: founder + REVIEWER_ID
    owner = FOUNDER_ID
    assert is_authorized(m, role=Role.FOUNDER, actor=FOUNDER_ID, assignment_owner=owner)
    assert not is_authorized(m, role=Role.FOUNDER, actor=REVIEWER_ID, assignment_owner=owner)
    assert is_authorized(m, role=Role.OWNER, actor=FOUNDER_ID, assignment_owner=owner)
    assert not is_authorized(m, role=Role.OWNER, actor="stranger@x", assignment_owner=owner)
    assert is_authorized(m, role=Role.REVIEWER, actor=REVIEWER_ID, assignment_owner=owner)
    assert not is_authorized(m, role=Role.REVIEWER, actor=owner, assignment_owner=owner)
    assert not is_authorized(m, role=Role.REVIEWER, actor="ghost@x", assignment_owner=owner)


def test_write_path_refuses_unauthorized_reviewer(kernel, adapter, initialised) -> None:
    """@MUTATION — the write path uses the same predicate, so an unknown identity
    cannot record a reviewer approval either."""
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)
    drive_to_verified(kernel, adapter, assignment)

    stranger = kernel_as(initialised, "ghost@nowhere.test", adapter)
    with pytest.raises(InvariantViolation):
        stranger.lifecycle.approve(assignment.id, Role.REVIEWER)


# =============================================================================
# Blocker 4 — bundled-pack approval deadlock
# =============================================================================


def test_bundled_pack_has_no_approval_acceptance_criteria() -> None:
    """@REGRESSION — approval is a CLOSE gate, never an acceptance criterion (§21.4)."""
    from projectos.infrastructure.scaffold import SOFTWARE_CORE_TEMPLATES

    for name, body in SOFTWARE_CORE_TEMPLATES.items():
        for criterion in body["acceptance_criteria"]:
            assert criterion["verify"]["type"] != "approval_recorded", (
                f"template {name!r} uses approval_recorded as an acceptance criterion"
            )


def test_bundled_pack_completes_first_two_assignments(tmp_path: Path) -> None:
    """@REGRESSION — every scaffolded project deadlocked at A-0002 pre-fix."""
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    def run(*argv: str) -> int:
        return main(["--repo", str(root), "--identity", FOUNDER_ID, *argv])

    git("init", "-b", "main")
    git("config", "user.email", FOUNDER_ID)
    git("config", "user.name", FOUNDER_NAME)
    assert run("init", "--project-id", "d", "--name", "D",
               "--founder-id", FOUNDER_ID, "--founder-name", FOUNDER_NAME) == ExitCode.OK

    # Add a reviewer owner so REVIEWED mode (A-0002) can close.
    manifest = root / ".projectos" / "manifest.yaml"
    raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    raw["owners"].append({"id": REVIEWER_ID, "name": "Rev"})
    manifest.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")

    # A-0001 (design-spec, FAST)
    assert run("next") == ExitCode.OK
    (root / "docs").mkdir()
    (root / "docs" / "SPEC.md").write_text("# Spec\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-m", "add spec")
    assert run("next") == ExitCode.OK
    assert run("verify") == ExitCode.OK
    assert run("complete", "--role", "owner") == ExitCode.OK

    # A-0002 (implement-kernel, REVIEWED) — the deadlock point pre-fix.
    assert run("next") == ExitCode.OK
    git("commit", "--allow-empty", "-m", "implement the capability")
    assert run("verify") == ExitCode.OK
    assert run("complete", "--role", "owner") == ExitCode.OK  # records owner, not enough
    assert main(["--repo", str(root), "--identity", REVIEWER_ID,
                 "complete", "--role", "reviewer"]) == ExitCode.OK

    status = yaml.safe_load(
        (root / ".projectos" / "assignments" / "A-0002.yaml").read_text(encoding="utf-8")
    )["state"]["status"]
    assert status == "closed"


# =============================================================================
# Blocker 5 — mutation-resistance for the eight P1.4 survivors
# =============================================================================


def test_mut_tests_passed_requires_a_green_nonzero_report() -> None:
    """@MUTATION — `tests_passed` fail-open (rule_engine)."""
    criterion = AcceptanceCriterion("AC-1", "s", EvidenceRule(RuleType.TESTS_PASSED, {}))
    empty = RepositoryFact("tests", found=True, detail="", data={"failed": 0, "total": 0})
    failing = RepositoryFact("tests", found=True, detail="", data={"failed": 1, "total": 3})
    green = RepositoryFact("tests", found=True, detail="", data={"failed": 0, "total": 3})

    assert not rule_engine.evaluate(criterion, empty).passed
    assert not rule_engine.evaluate(criterion, failing).passed
    assert rule_engine.evaluate(criterion, green).passed


def test_mut_approval_recorded_requires_approved_decision() -> None:
    """@MUTATION — approval_recorded decision widening (rule_engine)."""
    criterion = AcceptanceCriterion(
        "AC-1", "s", EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": "owner"})
    )
    attested = RepositoryFact("approval", found=True, detail="", data={"decision": "attested"})
    approved = RepositoryFact("approval", found=True, detail="", data={"decision": "approved"})

    assert not rule_engine.evaluate(criterion, attested).passed
    assert rule_engine.evaluate(criterion, approved).passed


def test_mut_empty_criteria_set_never_passes() -> None:
    """@MUTATION — INV-3 (evidence.VerificationReport.passed)."""
    assert not VerificationReport(assignment_id="A-0001", results=()).passed


def test_mut_prev_hash_link_is_checked_independently() -> None:
    """@MUTATION — removing the prev_hash link check must fail a test that the
    sequence check does not cover: sequences stay contiguous, only the link breaks."""
    first = seal_next(
        AuditEntry(sequence=0, timestamp="2026-07-20T09:00:00Z", event="e", actor="a"), None
    )
    # Contiguous sequence (2), self-consistent hash, but wrong prev_hash.
    forged = AuditEntry(
        sequence=2, timestamp="2026-07-20T09:01:00Z", event="e", actor="a",
        prev_hash="0" * 64,
    ).sealed()

    with pytest.raises(AuditChainBroken, match="chain broken"):
        verify_chain((first, forged))


def test_mut_sequence_check_is_checked_independently() -> None:
    """@MUTATION — removing the sequence check must fail a test that the prev_hash
    check does not cover: prev_hash links correctly, only the sequence jumps."""
    first = seal_next(
        AuditEntry(sequence=0, timestamp="2026-07-20T09:00:00Z", event="e", actor="a"), None
    )
    # Correct prev_hash link, self-consistent hash, but sequence 3 (skips 2).
    forged = AuditEntry(
        sequence=3, timestamp="2026-07-20T09:01:00Z", event="e", actor="a",
        prev_hash=first.hash,
    ).sealed()

    with pytest.raises(AuditChainBroken, match="sequence break"):
        verify_chain((first, forged))


def test_mut_modified_entry_is_detected() -> None:
    """@MUTATION — the per-entry hash recomputation."""
    from dataclasses import replace

    first = seal_next(
        AuditEntry(sequence=0, timestamp="2026-07-20T09:00:00Z", event="e", actor="a"), None
    )
    tampered = replace(first, actor="someone@else")  # hash no longer matches payload

    with pytest.raises(AuditChainBroken, match="has been modified"):
        verify_chain((tampered,))


def test_mut_attestation_does_not_count_toward_close() -> None:
    """@MUTATION — attestation counts as approval (approvals.evaluate)."""
    attestation = ApprovalRecord(
        "A-0001", Role.OWNER, FOUNDER_ID, Decision.ATTESTED, "t", "attestation_recorded"
    )
    status = evaluate_approvals(WorkflowMode.FAST, WorkType.DOCUMENT, (attestation,))

    assert Role.OWNER in status.outstanding  # an attestation is not an approval


def test_mut_missing_capability_key_fails_closed(kernel, adapter, initialised) -> None:
    """@MUTATION — capability default False→True (verification)."""
    assignment = make_assignment(
        rule=EvidenceRule(RuleType.PR_MERGED, {"approvals_required": 1, "approver_role": "founder"})
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    # Adapter that omits the 'pr' key entirely rather than declaring it False.
    adapter._capabilities = {"ci": True, "artifacts": True}

    report = kernel.lifecycle.verify(assignment.id).report
    assert not report.passed
    assert "capability" in report.failures[0].reason


def test_mut_unknown_role_entry_is_skipped(kernel, adapter, initialised) -> None:
    """@MUTATION — the approval projection's role whitelist (audit_log)."""
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    drive_to_verified(kernel, adapter, assignment)

    append_forged(
        initialised,
        event="approval_recorded",
        assignment_id=str(assignment.id),
        data={"role": "supervisor", "decision": "approved", "actor": FOUNDER_ID},
    )

    # An entry with a role outside the Role enum is not projected into a record.
    records = kernel.audit.approvals_for(assignment.id)
    assert all(record.role in set(Role) for record in records)
