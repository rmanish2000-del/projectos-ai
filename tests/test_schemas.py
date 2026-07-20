"""Schema, serialisation, and security-boundary tests (spec sections 5, 6, 10, 14).

Schemas are the outer gate. These tests assert the gate is closed in the ways that
matter: unknown fields rejected, v0.1 pins enforced, secrets refused, and every
value surviving a round-trip unchanged.
"""

from __future__ import annotations

import pytest

from projectos.domain.enums import RepositoryAdapterKind, RuleType, WorkType
from projectos.domain.errors import ValidationError
from projectos.domain.evidence import EvidenceRule
from projectos.infrastructure.serialization import (
    assignment_from_dict,
    assignment_to_dict,
    escalation_from_dict,
    escalation_to_dict,
    manifest_from_dict,
    manifest_to_dict,
)
from projectos.infrastructure.validation import scan_for_secrets, validate
from tests.conftest import FOUNDER_ID, FOUNDER_NAME, make_assignment

VALID_MANIFEST = {
    "schema_version": 1,
    "project": {
        "id": "test-project",
        "name": "Test Project",
        "founder": {"id": FOUNDER_ID, "name": FOUNDER_NAME},
    },
    "owners": [{"id": FOUNDER_ID, "name": FOUNDER_NAME}],
    "repository": {"adapter": "local_git", "config": {"default_branch": "main"}},
}


# -- manifest -----------------------------------------------------------------


def test_valid_manifest_loads() -> None:
    manifest = manifest_from_dict(dict(VALID_MANIFEST))
    assert manifest.project_id == "test-project"
    assert manifest.repository.adapter is RepositoryAdapterKind.LOCAL_GIT


def test_unknown_manifest_fields_are_rejected() -> None:
    """Spec 5: unknown fields rejected, fail closed."""
    raw = {**VALID_MANIFEST, "surprise": True}
    with pytest.raises(ValidationError, match="Schema validation failed"):
        manifest_from_dict(raw)


def test_founder_must_be_an_owner() -> None:
    raw = {
        **VALID_MANIFEST,
        "owners": [{"id": "someone@else.test", "name": "Someone Else"}],
    }
    with pytest.raises(ValidationError, match=r"must also appear in manifest\.owners"):
        manifest_from_dict(raw)


def test_approvals_must_be_manual_in_v0_1() -> None:
    """Spec 5 and 8.4 — the kernel has no automatic merge or deploy path."""
    raw = {**VALID_MANIFEST, "approvals": {"merge": "automatic"}}
    with pytest.raises(ValidationError):
        manifest_from_dict(raw)


def test_governed_triggers_may_be_added_to_but_not_removed() -> None:
    """Spec 5: packs and manifests may ADD kernel triggers, never remove them."""
    raw = {**VALID_MANIFEST, "workflow": {"governed_triggers": ["frozen_architecture"]}}
    with pytest.raises(ValidationError, match="never remove kernel triggers"):
        manifest_from_dict(raw)

    extended = {
        **VALID_MANIFEST,
        "workflow": {
            "governed_triggers": [
                "frozen_architecture",
                "research_mathematics",
                "risk_model",
                "legal_filing",
                "security_boundary",
                "breaking_contract",
                "extra_project_trigger",
            ]
        },
    }
    assert "extra_project_trigger" in manifest_from_dict(extended).workflow.governed_triggers


def test_github_adapter_requires_owner_and_repo() -> None:
    raw = {**VALID_MANIFEST, "repository": {"adapter": "github", "config": {}}}
    with pytest.raises(ValidationError, match=r"github\.owner"):
        manifest_from_dict(raw)


def test_manifest_round_trips_unchanged() -> None:
    manifest = manifest_from_dict(dict(VALID_MANIFEST))
    assert manifest_from_dict(manifest_to_dict(manifest)) == manifest


# -- assignment ---------------------------------------------------------------


def test_assignment_round_trips_unchanged() -> None:
    original = make_assignment(work_type=WorkType.IMPLEMENTATION)
    restored = assignment_from_dict(assignment_to_dict(original), source="test")
    assert restored == original


def test_serialisation_is_deterministic() -> None:
    """Byte-identical output keeps `git diff` on .projectos/ meaningful."""
    assignment = make_assignment()
    assert assignment_to_dict(assignment) == assignment_to_dict(assignment)


def test_unknown_rule_parameters_are_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown parameters"):
        EvidenceRule(RuleType.FILE_EXISTS, {"path": "a", "typo_param": 1})


def test_missing_required_rule_parameters_are_rejected() -> None:
    with pytest.raises(ValidationError, match="missing required parameters"):
        EvidenceRule(RuleType.FILE_CONTAINS, {"path": "a"})


def test_assignment_with_an_unknown_rule_type_is_rejected() -> None:
    raw = assignment_to_dict(make_assignment())
    raw["acceptance_criteria"][0]["verify"] = {"type": "vibes_check"}
    with pytest.raises(ValidationError):
        assignment_from_dict(raw, source="test")


def test_duplicate_criterion_ids_are_rejected() -> None:
    from projectos.domain.evidence import AcceptanceCriterion

    rule = EvidenceRule(RuleType.FILE_EXISTS, {"path": "a"})
    with pytest.raises(ValidationError, match="duplicate criterion id"):
        make_assignment(
            acceptance_criteria=(
                AcceptanceCriterion("AC-1", "One", rule),
                AcceptanceCriterion("AC-1", "Duplicate", rule),
            )
        )


def test_self_dependency_is_rejected() -> None:
    from projectos.domain.ids import AssignmentId

    with pytest.raises(ValidationError, match="cannot depend on itself"):
        make_assignment(1, depends_on=(AssignmentId(1),))


def test_malformed_assignment_id_is_rejected() -> None:
    from projectos.domain.ids import AssignmentId

    for raw in ("A-1", "A-00001", "B-0001", "", "A0001"):
        with pytest.raises(ValidationError, match="Malformed identifier"):
            AssignmentId.parse(raw)


# -- escalation ---------------------------------------------------------------


def test_escalation_schema_requires_two_options() -> None:
    raw = {
        "schema_version": 1,
        "id": "E-0001",
        "trigger": "founder_decision",
        "summary": "A decision",
        "options": [{"id": "O1", "description": "One", "consequence": "Consequence."}],
        "state": "open",
    }
    with pytest.raises(ValidationError):
        escalation_from_dict(raw, source="test")


def test_escalation_round_trips_unchanged() -> None:
    from projectos.domain.enums import EscalationTrigger
    from projectos.domain.escalation import Escalation, EscalationOption
    from projectos.domain.ids import EscalationId

    original = Escalation(
        id=EscalationId(1),
        trigger=EscalationTrigger.FOUNDER_DECISION,
        summary="Which direction?",
        options=(
            EscalationOption("O1", "Left", "Cheaper, slower."),
            EscalationOption("O2", "Right", "Faster, costlier."),
        ),
        recommendation="O1",
        created_at="2026-07-20T09:00:00Z",
    )

    assert escalation_from_dict(escalation_to_dict(original), source="test") == original


def test_recommendation_must_name_a_real_option() -> None:
    from projectos.domain.enums import EscalationTrigger
    from projectos.domain.escalation import Escalation, EscalationOption
    from projectos.domain.ids import EscalationId

    with pytest.raises(ValidationError, match="recommends unknown option"):
        Escalation(
            id=EscalationId(1),
            trigger=EscalationTrigger.FOUNDER_DECISION,
            summary="A decision",
            options=(
                EscalationOption("O1", "One", "Consequence one."),
                EscalationOption("O2", "Two", "Consequence two."),
            ),
            recommendation="O9",
        )


# -- packs --------------------------------------------------------------------


def test_pack_pipeline_cannot_reference_a_missing_template() -> None:
    from projectos.domain.pack import Pack, PipelinePhase

    with pytest.raises(ValidationError, match="unknown template"):
        Pack(
            schema_version=1,
            name="broken-pack",
            version="0.1.0",
            pipeline=(PipelinePhase("foundation", ("does-not-exist",)),),
        )


def test_templates_cannot_set_kernel_issued_fields() -> None:
    """Spec 10.2: packs cannot mint identity or pre-set state."""
    from projectos.domain.ids import AssignmentId
    from projectos.domain.pack import PackTemplate
    from projectos.infrastructure.template_binding import bind_template

    manifest = manifest_from_dict(dict(VALID_MANIFEST))
    template = PackTemplate("sneaky", {"state": {"status": "closed"}})

    with pytest.raises(ValidationError, match="kernel-issued fields"):
        bind_template(template, assignment_id=AssignmentId(1), manifest=manifest)


# -- security (spec 14.1) -----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "token: ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "aws: AKIAIOSFODNN7EXAMPLE",
        "key: sk-abcdefghijklmnopqrstuvwxyz012345",
        "-----BEGIN RSA PRIVATE KEY-----",
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123",
        'password: "hunter2hunter2"',
    ],
)
def test_secret_patterns_are_detected(text: str) -> None:
    with pytest.raises(ValidationError, match="Possible secret"):
        scan_for_secrets(text, source="test")


def test_ordinary_state_content_is_not_flagged() -> None:
    scan_for_secrets(
        "id: A-0001\ntitle: Implement the kernel\nowner: founder@example.test\n",
        source="test",
    )


def test_audit_entry_schema_rejects_a_short_hash() -> None:
    raw = {
        "sequence": 1,
        "timestamp": "2026-07-20T09:00:00Z",
        "event": "start",
        "actor": FOUNDER_ID,
        "prev_hash": "0" * 64,
        "hash": "abc",
    }
    with pytest.raises(ValidationError):
        validate(raw, "audit_entry.schema.json", source="test")
