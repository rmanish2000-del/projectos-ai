"""Regression tests for P1.2 — frozen-core contract completion.

Grouped by the assignment's scope sections. Regression tests are marked
`@REGRESSION` in their docstring and were each confirmed to fail against the
pre-P1.2 tree; control tests are marked `@CONTROL` and assert that the legitimate
direction still works. Control tests are not counted as defects caught.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from projectos.application import validation_service
from projectos.cli.main import main
from projectos.domain import compatibility
from projectos.domain.compatibility import KERNEL_VERSION
from projectos.domain.enums import Decision, ExecutorType, Role, RuleType, Status, WorkType
from projectos.domain.errors import ExitCode, ValidationError
from projectos.domain.evidence import AcceptanceCriterion, ApprovalRecord, EvidenceRule
from projectos.domain.pack import Pack
from projectos.infrastructure.pack_loading import load_pack_from_directory
from projectos.infrastructure.template_binding import YamlTemplateBinder
from tests.conftest import FOUNDER_ID, FOUNDER_NAME, REVIEWER_ID, kernel_as, make_assignment

PRESENT: Any = None  # placeholder replaced per-test; kept explicit for readability


def run(*argv: str) -> int:
    return main(list(argv))


def state_digest(root: Path) -> str:
    """A hash over every state file, for proving a command mutated nothing."""
    import hashlib

    digest = hashlib.sha256()
    for path in sorted((root / ".projectos").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "-C", str(root), "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", FOUNDER_ID],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(root), "config", "user.name", FOUNDER_NAME],
        check=True,
        capture_output=True,
    )
    assert run(
        "--repo", str(root),
        "init",
        "--project-id", "p12-test",
        "--name", "P1.2 Test",
        "--founder-id", FOUNDER_ID,
        "--founder-name", FOUNDER_NAME,
    ) == ExitCode.OK
    return root


def pack_yaml(root: Path) -> Path:
    return root / ".projectos" / "packs" / "software-core" / "pack.yaml"


def edit_yaml(path: Path, **changes: Any) -> None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw.update(changes)
    path.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")


# =============================================================================
# 6.1  Kernel extensions formalized into spec 7.2
# =============================================================================


def test_no_production_transition_exists_outside_the_specification() -> None:
    """@CONTROL — acceptance criterion 2.

    Pre-fix the table carried rows in a separate KERNEL_EXTENSIONS list, i.e.
    implemented but unspecified. Every row must now be in the spec transcription.
    """
    from projectos.domain.state_machine import TRANSITIONS
    from tests.test_state_machine import LEGAL_PAIRS

    implemented = {(t.from_status, t.event) for t in TRANSITIONS}

    assert implemented == LEGAL_PAIRS


def test_kernel_extensions_concept_is_gone() -> None:
    """@REGRESSION — the informal escape hatch must not survive anywhere."""
    import tests.test_state_machine as module

    assert not hasattr(module, "KERNEL_EXTENSIONS")

    sources = list((Path(__file__).resolve().parents[1] / "src").rglob("*.py"))
    offenders = [p.name for p in sources if "KERNEL_EXTENSIONS" in p.read_text(encoding="utf-8")]
    assert offenders == []


def test_unused_actor_widenings_were_narrowed() -> None:
    """@REGRESSION — spec 7.2 authority columns are matched exactly.

    P1.1 permitted `kernel` on approvals_complete and `founder` on escalate;
    neither is used by any code path, so both were narrowed back to the spec.
    """
    from projectos.domain.enums import Actor, Event, Status
    from projectos.domain.state_machine import lookup

    assert Actor.KERNEL not in lookup(Status.VERIFIED, Event.APPROVALS_COMPLETE).allowed_actors
    assert Actor.FOUNDER not in lookup(Status.ACTIVE, Event.ESCALATE).allowed_actors


def test_blocking_transitions_remain_available(kernel, adapter) -> None:
    """@CONTROL — narrowing must not remove the paths the CLI needs."""
    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    blocked = kernel.lifecycle.block(assignment.id, "external dependency failed")

    assert blocked.status is Status.BLOCKED


def test_block_requires_a_reason_per_spec_7_2_1(project: Path) -> None:
    """@CONTROL — spec 7.2.1 makes the reason a normative condition."""
    run("--repo", str(project), "next")

    assert run("--repo", str(project), "block") == ExitCode.INVARIANT_ERROR


# =============================================================================
# 6.2 / 6.3  validate and pack validate
# =============================================================================


def test_validate_succeeds_on_a_valid_repository(project: Path) -> None:
    """@REGRESSION — the command did not exist before P1.2."""
    assert run("--repo", str(project), "validate") == ExitCode.OK


def test_validate_reports_an_incompatible_pack_version(project: Path, capsys) -> None:
    """@REGRESSION — constraints were accepted but never checked."""
    edit_yaml(pack_yaml(project), requires_projectos=">=9.0.0")

    code = run("--repo", str(project), "validate")

    assert code == ExitCode.INVARIANT_ERROR
    assert "requires ProjectOS" in capsys.readouterr().out


def test_validate_reports_every_finding_not_just_the_first(project: Path, capsys) -> None:
    """@REGRESSION — a report that stops at the first error is not a report."""
    edit_yaml(pack_yaml(project), requires_projectos=">=9.0.0")
    manifest = project / ".projectos" / "manifest.yaml"
    raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    raw["packs"][0]["version"] = ">=5.0.0"
    manifest.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")

    code = run("--repo", str(project), "validate")
    output = capsys.readouterr().out

    assert code == ExitCode.INVARIANT_ERROR
    assert "does not satisfy the manifest constraint" in output
    assert "requires ProjectOS" in output


def test_validate_fails_on_a_malformed_manifest(project: Path) -> None:
    """@REGRESSION — malformed input must fail closed, not crash uncaught."""
    manifest = project / ".projectos" / "manifest.yaml"
    manifest.write_text("schema_version: 1\nproject: not-a-mapping\n", encoding="utf-8")

    assert run("--repo", str(project), "validate") == ExitCode.INVARIANT_ERROR


def test_validate_mutates_nothing(project: Path) -> None:
    """@REGRESSION — acceptance criterion 5."""
    before = state_digest(project)

    run("--repo", str(project), "validate")

    assert state_digest(project) == before


def test_pack_validate_succeeds_on_the_bundled_pack(project: Path) -> None:
    """@REGRESSION — the command did not exist before P1.2."""
    path = project / ".projectos" / "packs" / "software-core"

    assert run("--repo", str(project), "pack", "validate", str(path)) == ExitCode.OK


def test_pack_validate_mutates_nothing(project: Path) -> None:
    """@REGRESSION — acceptance criterion 5."""
    path = project / ".projectos" / "packs" / "software-core"
    before = state_digest(project)

    run("--repo", str(project), "pack", "validate", str(path))

    assert state_digest(project) == before


def test_pack_validate_rejects_an_invalid_evidence_rule(project: Path, tmp_path: Path) -> None:
    """@REGRESSION — a template with an unusable rule must not validate."""
    pack_dir = tmp_path / "badpack"
    (pack_dir / "templates").mkdir(parents=True)
    (pack_dir / "pack.yaml").write_text(
        yaml.dump(
            {
                "schema_version": 1,
                "name": "badpack",
                "version": "0.1.0",
                "requires_projectos": ">=0.1.0,<0.2.0",
                "pipeline": [{"phase": "foundation", "templates": ["broken"]}],
            }
        ),
        encoding="utf-8",
    )
    (pack_dir / "templates" / "broken.yaml").write_text(
        yaml.dump(
            {
                "title": "Broken",
                "work_type": "document",
                "executor": "cowork",
                "objective": "o",
                "stopping_point": "s",
                # `path` is required by file_exists; omitting it makes the rule unusable.
                "acceptance_criteria": [
                    {"id": "AC-1", "statement": "s", "verify": {"type": "file_exists"}}
                ],
            }
        ),
        encoding="utf-8",
    )

    assert run("--repo", str(project), "pack", "validate", str(pack_dir)) == (
        ExitCode.INVARIANT_ERROR
    )


def test_pack_validate_rejects_a_dangling_pipeline_reference(tmp_path: Path) -> None:
    """@CONTROL — internal referential integrity."""
    pack_dir = tmp_path / "danglingpack"
    pack_dir.mkdir()
    (pack_dir / "pack.yaml").write_text(
        yaml.dump(
            {
                "schema_version": 1,
                "name": "danglingpack",
                "version": "0.1.0",
                "pipeline": [{"phase": "foundation", "templates": ["missing-template"]}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="unknown template"):
        load_pack_from_directory(pack_dir)


def test_pack_validate_rejects_an_unknown_work_type(tmp_path: Path) -> None:
    """@REGRESSION — authority/reference declarations are checked."""
    pack = Pack(
        schema_version=1,
        name="oddpack",
        version="0.1.0",
        reviewed_work_types=frozenset({"telepathy"}),
    )

    report = validation_service.validate_pack(pack, binder=YamlTemplateBinder())

    assert not report.ok
    assert any(f.code == "pack.classification.unknown_work_type" for f in report.errors)


def test_pack_validate_reports_a_missing_directory(project: Path, tmp_path: Path) -> None:
    """@REGRESSION — a clear error, not a traceback."""
    assert run(
        "--repo", str(project), "pack", "validate", str(tmp_path / "nope")
    ) == ExitCode.INVARIANT_ERROR


def test_validation_service_is_side_effect_free(project: Path) -> None:
    """@CONTROL — constraint 4: validation must not write."""
    pack = load_pack_from_directory(project / ".projectos" / "packs" / "software-core")
    before = state_digest(project)

    validation_service.validate_pack(pack, binder=YamlTemplateBinder())

    assert state_digest(project) == before


# =============================================================================
# 6.4  approval_recorded decision semantics
# =============================================================================


def test_canonical_approved_is_accepted() -> None:
    """@REGRESSION."""
    record = ApprovalRecord("A-0001", Role.OWNER, FOUNDER_ID, Decision.APPROVED, "t")

    assert record.is_approval


@pytest.mark.parametrize(
    "value",
    ["rejected", "pending", "Approved", "APPROVED", " approved ", "approved\n", "yes", "ok", ""],
)
def test_non_canonical_decisions_are_rejected_at_the_domain_boundary(value: str) -> None:
    """@REGRESSION — acceptance criterion 7.

    Covers free-form text, semantically different decisions, and case/whitespace
    variants. The contract is exact canonical match; variants are rejected rather
    than normalised.
    """
    with pytest.raises(ValidationError, match="canonical Decision"):
        ApprovalRecord("A-0001", Role.OWNER, FOUNDER_ID, value, "t")  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["rejected", "pending", "Approved", " approved ", "attested"])
def test_approval_recorded_rule_pins_its_decision(value: str) -> None:
    """@REGRESSION — a criterion cannot be authored to accept a non-approval."""
    with pytest.raises(ValidationError, match="must be 'approved'"):
        EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": "owner", "decision": value})


def test_approval_recorded_rule_accepts_the_canonical_value() -> None:
    """@CONTROL."""
    rule = EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": "owner", "decision": "approved"})

    assert rule.params["decision"] == "approved"


@pytest.mark.parametrize("value", ["rejected", "pending", "Approved", " approved ", "", None, 7])
def test_non_canonical_decisions_cannot_enter_through_deserialization(
    kernel, adapter, value: object
) -> None:
    """@REGRESSION — acceptance criterion 6.

    A chain-valid audit entry carrying a non-canonical decision must grant nothing.
    """
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle._append_event(
        "approval_recorded",
        assignment_id=str(assignment.id),
        data={"role": "owner", "actor": FOUNDER_ID, "decision": value},
    )

    assert kernel.audit.approvals_for(assignment.id) == ()


def test_a_canonical_approval_still_round_trips(kernel, adapter) -> None:
    """@CONTROL — backward compatibility for unambiguously canonical records."""
    from projectos.domain.evidence import RepositoryFact

    adapter.facts[RuleType.FILE_EXISTS] = RepositoryFact(
        kind="file", found=True, detail="present"
    )
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)
    kernel.lifecycle.approve(assignment.id, Role.OWNER)

    recorded = kernel.audit.approvals_for(assignment.id)

    assert [r.decision for r in recorded] == [Decision.APPROVED]


def test_decision_parse_is_exact_match_only() -> None:
    """@REGRESSION — the explicit case/whitespace contract."""
    assert Decision.parse("approved") is Decision.APPROVED
    assert Decision.parse("attested") is Decision.ATTESTED
    for variant in ("Approved", "APPROVED", " approved", "approved ", "appr0ved", None, 1, ""):
        assert Decision.parse(variant) is None


# =============================================================================
# 6.5  Pack version constraints
# =============================================================================


def result_for(version: str, constraint: str) -> bool:
    return compatibility.check(
        subject="kernel", version=version, constraint=constraint, source="test"
    ).compatible


def test_exact_compatible_version() -> None:
    """@CONTROL."""
    assert result_for("0.1.0", "==0.1.0")


def test_compatible_bounded_range() -> None:
    """@CONTROL."""
    assert result_for("0.1.0", ">=0.1.0,<0.2.0")


def test_whitespace_separated_range_is_accepted() -> None:
    """@CONTROL — spec 5 writes constraints with spaces rather than commas."""
    assert result_for("0.1.0", ">=0.1.0 <0.2.0")


def test_incompatible_lower_boundary() -> None:
    """@REGRESSION — constraints were previously never evaluated."""
    assert not result_for("0.0.9", ">=0.1.0,<0.2.0")


def test_incompatible_upper_boundary() -> None:
    """@REGRESSION."""
    assert not result_for("0.2.0", ">=0.1.0,<0.2.0")


@pytest.mark.parametrize("constraint", ["^1.0.0", "~>1.0", "1.x", ">=", "not-a-constraint", ""])
def test_malformed_or_unsupported_constraints_are_rejected(constraint: str) -> None:
    """@REGRESSION — unsupported syntax must fail closed, not be approximated."""
    with pytest.raises(ValidationError):
        compatibility.parse_constraint(constraint, source="test")


@pytest.mark.parametrize("version", ["not-a-version", "", "1.0.0.0.0.x"])
def test_malformed_versions_are_rejected(version: str) -> None:
    """@REGRESSION."""
    with pytest.raises(ValidationError):
        compatibility.parse_version(version, source="test")


def test_prereleases_are_excluded_unless_the_constraint_names_one() -> None:
    """@REGRESSION — explicit prerelease policy.

    The library default would admit `0.2.0rc1` for `>=0.1.0`; the kernel pins the
    conservative reading instead.
    """
    assert not result_for("0.2.0rc1", ">=0.1.0")
    assert result_for("0.2.0rc1", ">=0.2.0rc1")


def test_wildcard_constraint_accepts_any_version() -> None:
    """@CONTROL — the documented escape hatch."""
    assert result_for("9.9.9", "*")


def test_pack_loading_cannot_bypass_compatibility(project: Path) -> None:
    """@REGRESSION — acceptance criterion 9.

    Loading is the only route a pack takes into the kernel, so the check lives
    there and not merely in the commands.
    """
    edit_yaml(pack_yaml(project), requires_projectos=">=9.0.0")

    from projectos.infrastructure.container import build_kernel

    kernel = build_kernel(project)
    manifest = kernel.manifests.load()

    with pytest.raises(ValidationError, match="not compatible"):
        kernel.packs.load_all(manifest)


def test_generation_cannot_bypass_compatibility(project: Path) -> None:
    """@CONTROL — the path that actually consumes pack data is blocked too."""
    edit_yaml(pack_yaml(project), requires_projectos=">=9.0.0")

    assert run("--repo", str(project), "next") == ExitCode.INVARIANT_ERROR


def test_a_malformed_constraint_in_a_pack_is_rejected_at_construction() -> None:
    """@REGRESSION — a bad constraint cannot sit unnoticed inside a pack."""
    with pytest.raises(ValidationError, match="unsupported version constraint"):
        Pack(schema_version=1, name="p", version="0.1.0", requires_projectos="^1.0.0")


def test_a_malformed_pack_version_is_rejected_at_construction() -> None:
    """@REGRESSION."""
    with pytest.raises(ValidationError, match="malformed version"):
        Pack(schema_version=1, name="p", version="not-a-version")


def test_missing_constraint_is_a_warning_not_an_error() -> None:
    """@REGRESSION — the documented policy for packs predating requires_projectos."""
    pack = Pack(
        schema_version=1,
        name="legacy",
        version="0.1.0",
        templates=(),
        pipeline=(),
    )

    report = validation_service.validate_pack(pack, binder=YamlTemplateBinder())

    assert report.ok
    assert any(f.code == "pack.requires_projectos.missing" for f in report.warnings)


def test_kernel_version_has_one_authoritative_source() -> None:
    """@CONTROL — no duplicated version literal."""
    import projectos

    assert projectos.__version__ == KERNEL_VERSION

    # The compatibility module must derive the kernel version, never restate it.
    source = (
        Path(__file__).resolve().parents[1]
        / "src" / "projectos" / "domain" / "compatibility.py"
    ).read_text(encoding="utf-8")
    assert "__version__" in source
    assert f'KERNEL_VERSION: str = "{projectos.__version__}"' not in source


# =============================================================================
# 6.6  _approval_fact contract coverage
# =============================================================================


def approval_criterion(role: str = "owner") -> AcceptanceCriterion:
    return AcceptanceCriterion(
        "AC-1", "approved", EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": role})
    )


def _rec(role: Role, actor: str, decision: Decision) -> ApprovalRecord:
    """An approval record carrying the event its decision implies (spec 8.6.2)."""
    event = "attestation_recorded" if decision is Decision.ATTESTED else "approval_recorded"
    return ApprovalRecord("A-0001", role, actor, decision, "t", event)


def engine_over(records: tuple[ApprovalRecord, ...]):
    from projectos.application.verification import VerificationEngine
    from tests.conftest import make_manifest

    class Stub:
        def approvals_for(self, assignment_id: object) -> tuple[ApprovalRecord, ...]:
            return records

    class NoAdapter:
        def capabilities(self) -> dict[str, bool]:
            return {"pr": True, "ci": True, "artifacts": True}

        def query(self, rule: object) -> object:
            raise AssertionError("approval rules must not reach the adapter")

    return VerificationEngine(
        adapter=NoAdapter(), audit=Stub(), manifest=make_manifest()  # type: ignore[arg-type]
    )


def test_approval_fact_finds_a_valid_owner_approval() -> None:
    """@CONTROL."""
    engine = engine_over(
        (_rec(Role.OWNER, FOUNDER_ID, Decision.APPROVED),)
    )

    fact = engine._approval_fact(make_assignment(), approval_criterion())

    assert fact.found
    assert fact.data["decision"] == "approved"


def test_approval_fact_finds_an_authorized_reviewer_approval() -> None:
    """@CONTROL — a non-owner reviewer is permitted (spec 4.1)."""
    engine = engine_over(
        (_rec(Role.REVIEWER, REVIEWER_ID, Decision.APPROVED),)
    )

    assert engine._approval_fact(make_assignment(), approval_criterion("reviewer")).found


def test_approval_fact_is_absent_when_no_record_exists() -> None:
    """@CONTROL — missing evidence."""
    fact = engine_over(())._approval_fact(make_assignment(), approval_criterion())

    assert not fact.found
    assert "no authorized" in fact.detail


def test_approval_fact_ignores_a_different_role() -> None:
    """@CONTROL — missing authority must not satisfy the criterion."""
    engine = engine_over(
        (_rec(Role.REVIEWER, REVIEWER_ID, Decision.APPROVED),)
    )

    assert not engine._approval_fact(make_assignment(), approval_criterion("founder")).found


def test_an_attestation_does_not_satisfy_an_approval_rule() -> None:
    """@REGRESSION — the two evidence kinds must not be interchangeable."""
    engine = engine_over(
        (_rec(Role.FOUNDER, FOUNDER_ID, Decision.ATTESTED),)
    )

    fact = engine._approval_fact(make_assignment(), approval_criterion("founder"))

    assert not fact.found
    assert "attested" in fact.detail


def test_an_approval_after_an_attestation_is_still_found() -> None:
    """@CONTROL — the pre-fix scan matched on role alone and returned the first
    record, so an earlier attestation masked a later genuine approval."""
    engine = engine_over(
        (
            _rec(Role.FOUNDER, FOUNDER_ID, Decision.ATTESTED),
            _rec(Role.FOUNDER, FOUNDER_ID, Decision.APPROVED),
        )
    )

    assert engine._approval_fact(make_assignment(), approval_criterion("founder")).found


def test_approval_fact_never_consults_the_repository_adapter() -> None:
    """@CONTROL — approvals live in the audit log; the stub asserts on contact."""
    engine = engine_over(
        (_rec(Role.OWNER, FOUNDER_ID, Decision.APPROVED),)
    )

    assert engine.verify(make_assignment(rule=EvidenceRule(
        RuleType.APPROVAL_RECORDED, {"role": "owner"}
    ))).passed


def test_forged_authority_cannot_produce_an_approval(kernel, adapter, initialised) -> None:
    """@CONTROL — end to end: an unauthorized actor records nothing."""
    assignment = make_assignment(
        work_type=WorkType.DOCUMENT,
        executor=ExecutorType.COWORK,
        rule=EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": "founder"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    stranger = kernel_as(initialised, "nobody@nowhere.test", adapter)
    from projectos.domain.errors import InvariantViolation

    with pytest.raises(InvariantViolation):
        stranger.lifecycle.attest(assignment.id, Role.FOUNDER)

    assert not kernel.lifecycle.verify(assignment.id).report.passed


def test_approval_is_included_in_the_hash_chained_audit(kernel, adapter) -> None:
    """@CONTROL — serialization and audit-chain inclusion."""
    from projectos.domain.evidence import RepositoryFact

    adapter.facts[RuleType.FILE_EXISTS] = RepositoryFact("file", found=True, detail="present")
    assignment = make_assignment(work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)
    kernel.lifecycle.approve(assignment.id, Role.OWNER)

    events = [e.event for e in kernel.audit.for_assignment(assignment.id)]

    assert "approval_recorded" in events
    kernel.lifecycle.verify_integrity()


def test_approval_on_a_non_verified_assignment_is_refused(kernel, adapter) -> None:
    """@CONTROL — incompatible lifecycle state."""
    from projectos.domain.errors import InvariantViolation

    assignment = make_assignment()
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)

    with pytest.raises(InvariantViolation, match="only VERIFIED"):
        kernel.lifecycle.approve(assignment.id, Role.OWNER)


def test_duplicate_approval_does_not_satisfy_two_required_roles(
    kernel, adapter, initialised
) -> None:
    """@CONTROL — approving twice as owner must not stand in for a reviewer."""
    from projectos.domain.evidence import RepositoryFact

    adapter.facts[RuleType.FILE_EXISTS] = RepositoryFact("file", found=True, detail="present")
    assignment = make_assignment(work_type=WorkType.IMPLEMENTATION)  # -> REVIEWED mode
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)

    # Approving twice as owner is permitted but cannot stand in for the reviewer
    # that REVIEWED mode requires, so the assignment stays VERIFIED.
    kernel.lifecycle.approve(assignment.id, Role.OWNER)
    _, status = kernel.lifecycle.approve(assignment.id, Role.OWNER)

    assert Role.REVIEWER in status.outstanding
    assert kernel.assignments.get(assignment.id).status is Status.VERIFIED


def test_verifier_internal_error_on_the_approval_path_fails_closed(kernel, adapter) -> None:
    """@CONTROL — an internal error must reject, never pass."""
    from projectos.domain.errors import RuleFailure

    class ExplodingProjection:
        """Delegates everything except the approvals projection, which raises."""

        def __init__(self, inner: object) -> None:
            self._inner = inner

        def __getattr__(self, name):  # noqa: ANN204
            return getattr(self._inner, name)

        def approvals_for(self, assignment_id: object) -> object:
            raise RuntimeError("audit projection failed")

    assignment = make_assignment(
        work_type=WorkType.DOCUMENT,
        executor=ExecutorType.COWORK,
        rule=EvidenceRule(RuleType.APPROVAL_RECORDED, {"role": "owner"}),
    )
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle._audit = ExplodingProjection(kernel.audit)  # type: ignore[assignment]

    with pytest.raises(RuleFailure, match="verifier errored"):
        kernel.lifecycle.verify(assignment.id)
