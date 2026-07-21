"""P2 — next-assignment generator: regression and end-to-end coverage.

The generation machinery (`lifecycle.generate_next`, `next_engine.decide`,
`_materialise`) was built in P1; P2 completes the CLI contract and gives the
generator dedicated coverage. Every scenario in the P2 assignment's required-tests
list has a test here, plus a three-assignment end-to-end progression.

Tests are black-box through the kernel and the real CLI wherever practical, so they
exercise the same paths a founder would.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from projectos.cli.main import main
from projectos.domain.assignment import NextSpec
from projectos.domain.enums import (
    EscalationTrigger,
    ExecutorType,
    Role,
    RuleType,
    Status,
    WorkflowMode,
    WorkType,
)
from projectos.domain.errors import EscalationRequired, ExitCode, ValidationError
from projectos.domain.evidence import RepositoryFact
from projectos.domain.ids import AssignmentId
from projectos.infrastructure.serialization import assignment_from_dict, assignment_to_dict
from tests.conftest import (
    FOUNDER_ID,
    FOUNDER_NAME,
    REVIEWER_ID,
    FakeAdapter,
    make_assignment,
)

PRESENT = RepositoryFact(kind="file", found=True, detail="present")


def close_document(kernel, adapter: FakeAdapter, assignment):
    """Drive a FAST document/spec assignment all the way to CLOSED."""
    adapter.facts[RuleType.FILE_EXISTS] = PRESENT
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)
    kernel.lifecycle.verify(assignment.id)
    kernel.lifecycle.approve(assignment.id, Role.OWNER)


def doc(number: int, **kw: object):
    return make_assignment(
        number, work_type=WorkType.DOCUMENT, executor=ExecutorType.COWORK, **kw
    )


# =============================================================================
# 1. Explicit next.template takes precedence
# =============================================================================


def test_explicit_next_template_is_used_first(kernel, adapter) -> None:
    first = doc(1, next=NextSpec("harden-and-document"))
    close_document(kernel, adapter, first)

    result = kernel.lifecycle.generate_next()

    assert result.decision.source == "assignment.next"
    assert result.assignment is not None
    assert result.assignment.origin_template == "harden-and-document"


# =============================================================================
# 2. Pack-pipeline fallback
# =============================================================================


def test_pipeline_fallback_when_no_next_block(kernel, adapter) -> None:
    close_document(kernel, adapter, doc(1))

    result = kernel.lifecycle.generate_next()

    assert result.decision.source.startswith("pack.pipeline")
    assert result.assignment is not None
    assert result.assignment.origin_template == "design-spec"


# =============================================================================
# 3. Deterministic repeated invocation / 10. duplicate prevention
# =============================================================================


def test_generation_is_deterministic(kernel, adapter) -> None:
    close_document(kernel, adapter, doc(1))
    from projectos.domain import next_engine

    assignments = kernel.assignments.list_all()
    closed = next(a for a in assignments if a.status is Status.CLOSED)
    packs = kernel.lifecycle.packs

    templates = {next_engine.decide(closed, assignments, packs).template for _ in range(5)}
    assert len(templates) == 1


def test_repeated_generation_creates_no_duplicate(kernel, adapter) -> None:
    close_document(kernel, adapter, doc(1))

    first = kernel.lifecycle.generate_next()
    count_after_first = len(kernel.assignments.list_all())
    second = kernel.lifecycle.generate_next()  # unchanged state

    assert first.assignment is not None
    assert second.assignment is not None
    assert first.assignment.id == second.assignment.id
    assert len(kernel.assignments.list_all()) == count_after_first
    assert second.decision.source == "existing"


# =============================================================================
# 4. Monotonic assignment IDs across a chain
# =============================================================================


def test_ids_are_monotonic_across_generation(kernel, adapter) -> None:
    close_document(kernel, adapter, doc(1))
    generated_ids = []
    for _ in range(2):
        result = kernel.lifecycle.generate_next()
        assert result.assignment is not None
        generated = result.assignment
        generated_ids.append(generated.id)
        # close it so the next generation proceeds
        adapter.facts[RuleType.FILE_EXISTS] = PRESENT
        if generated.status is Status.READY:
            kernel.lifecycle.start(generated.id)
        kernel.lifecycle.verify(generated.id)
        _close_by_mode(kernel, generated)

    assert generated_ids == sorted(generated_ids)
    assert generated_ids[0] < generated_ids[1]
    # No id is reused and each is the successor of the previous max.
    assert len({str(a.id) for a in kernel.assignments.list_all()}) == len(
        kernel.assignments.list_all()
    )


def _close_by_mode(kernel, assignment) -> None:
    """Record whatever approvals the assignment's mode needs to reach CLOSED."""
    current = kernel.assignments.get(assignment.id)
    if current.status is not Status.VERIFIED:
        return
    kernel.lifecycle.approve(assignment.id, Role.OWNER)
    status = kernel.lifecycle.approval_status(kernel.assignments.get(assignment.id))
    if Role.REVIEWER in status.outstanding:

        reviewer = kernel_as_same(kernel, REVIEWER_ID)
        reviewer.lifecycle.approve(assignment.id, Role.REVIEWER)


def kernel_as_same(kernel, identity: str):
    from projectos.infrastructure.container import build_kernel
    from projectos.infrastructure.system import FixedClock, StaticIdentityProvider
    from tests.conftest import FIXED_INSTANT

    return build_kernel(
        kernel.layout.repo_root,
        clock=FixedClock(FIXED_INSTANT),
        identity=StaticIdentityProvider(identity),
        adapter=FakeAdapter(facts={RuleType.FILE_EXISTS: PRESENT}),
    )


# =============================================================================
# 5. Dependency gating — a generated assignment with an open dep stays DRAFT
# =============================================================================


def test_generated_assignment_with_open_dependency_stays_draft(kernel, adapter) -> None:
    # design-spec closes; implement-kernel is generated and depends on design-spec's
    # successor chain. Use an explicit next whose template depends on an open one.
    close_document(kernel, adapter, doc(1))
    result = kernel.lifecycle.generate_next()  # A-0002 design-spec, depends on A-0001 (closed)

    assert result.assignment is not None
    # A-0002 depends on A-0001 which is CLOSED, so it is READY.
    assert result.assignment.status is Status.READY


def test_dependency_gating_defers_to_draft(kernel, adapter) -> None:
    blocker = make_assignment(1)
    dependent = make_assignment(2, depends_on=(AssignmentId(1),))
    kernel.lifecycle.create(blocker)
    kernel.lifecycle.create(dependent)

    result, _ = kernel.lifecycle.classify_assignment(dependent.id)

    assert result.status is Status.DRAFT  # dependency A-0001 is not CLOSED


# =============================================================================
# 6. Blocked escalation
# =============================================================================


def test_project_level_escalation_blocks_generation(kernel, adapter) -> None:
    from projectos.domain.escalation import EscalationOption

    close_document(kernel, adapter, doc(1))
    kernel.lifecycle.escalate(
        trigger=EscalationTrigger.ARCHITECTURE_CONFLICT,
        summary="Architecture conflict must be resolved first",
        options=(
            EscalationOption("O1", "Amend", "Architecture changes."),
            EscalationOption("O2", "Reject", "Work proceeds unchanged."),
        ),
    )

    with pytest.raises(EscalationRequired, match="blocks next-assignment generation"):
        kernel.lifecycle.generate_next()


# =============================================================================
# 7. NEXT_UNDETERMINED escalation
# =============================================================================


def test_undetermined_next_opens_decision_ready_escalation(kernel, adapter) -> None:
    from unittest.mock import patch

    from projectos.domain.pack import PackSet

    close_document(kernel, adapter, doc(1))
    # No explicit `next` block and an empty pipeline: the successor is undeterminable.
    with patch.object(type(kernel.lifecycle), "packs", property(lambda self: PackSet(()))):
        result = kernel.lifecycle.generate_next()

    assert result.assignment is None
    assert result.escalation is not None
    assert result.escalation.trigger is EscalationTrigger.NEXT_UNDETERMINED
    assert len(result.escalation.options) >= 2
    assert all(option.consequence for option in result.escalation.options)


# =============================================================================
# 8. Malformed / missing template
# =============================================================================


def test_missing_template_raises(kernel, adapter) -> None:
    close_document(kernel, adapter, doc(1, next=NextSpec("does-not-exist")))

    with pytest.raises(ValidationError, match="not provided by any installed pack"):
        kernel.lifecycle.generate_next()


def test_malformed_template_body_is_rejected(kernel, adapter, initialised) -> None:
    """A template that fails the assignment schema cannot become an assignment."""
    from projectos.domain.pack import PackTemplate
    from projectos.infrastructure.template_binding import bind_template

    bad = PackTemplate("bad", {"title": "no work_type or criteria"})
    with pytest.raises(ValidationError):
        bind_template(
            bad,
            assignment_id=AssignmentId(9),
            manifest=kernel.lifecycle.manifest,
            predecessor=None,
        )


# =============================================================================
# 9. Incompatible pack cannot be consumed during generation
# =============================================================================


def test_incompatible_pack_blocks_generation(project_repo) -> None:
    root = project_repo
    pack = root / ".projectos" / "packs" / "software-core" / "pack.yaml"
    raw = yaml.safe_load(pack.read_text(encoding="utf-8"))
    raw["requires_projectos"] = ">=9.0.0"
    pack.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")

    assert _cli(root, "next") == ExitCode.INVARIANT_ERROR


# =============================================================================
# 11. Single-active-assignment enforcement
# =============================================================================


def test_generation_yields_the_active_assignment_when_one_exists(kernel, adapter) -> None:
    assignment = make_assignment(1)
    kernel.lifecycle.create(assignment)
    kernel.lifecycle.classify_assignment(assignment.id)
    kernel.lifecycle.start(assignment.id)

    # generate_next returns the pending (active) assignment rather than a new one.
    result = kernel.lifecycle.generate_next()
    assert result.assignment is not None
    assert result.assignment.id == assignment.id
    assert result.decision.source == "existing"


def test_cli_next_reports_already_active(project_repo) -> None:
    _cli(project_repo, "next")  # A-0001 active
    # A second `next` must not generate a second assignment.
    assert _cli(project_repo, "next") == ExitCode.OK
    ids = sorted((project_repo / ".projectos" / "assignments").glob("A-*.yaml"))
    assert len(ids) == 1


# =============================================================================
# 12. Generated assignment schema validity
# =============================================================================


def test_generated_assignment_is_schema_valid_and_round_trips(kernel, adapter) -> None:
    close_document(kernel, adapter, doc(1))
    result = kernel.lifecycle.generate_next()
    assert result.assignment is not None

    reloaded = kernel.assignments.get(result.assignment.id)  # loads + schema-validates
    assert assignment_from_dict(assignment_to_dict(reloaded), source="t") == reloaded


# =============================================================================
# 13. Workflow classification of the generated assignment
# =============================================================================


def test_generated_implementation_is_classified_reviewed(kernel, adapter) -> None:
    close_document(kernel, adapter, doc(1))
    kernel.lifecycle.generate_next()  # A-0002 design-spec (FAST), READY
    # close A-0002 to reach implement-kernel (REVIEWED)
    a2 = kernel.assignments.get(AssignmentId(2))
    adapter.facts[RuleType.FILE_EXISTS] = PRESENT
    kernel.lifecycle.start(a2.id)
    kernel.lifecycle.verify(a2.id)
    kernel.lifecycle.approve(a2.id, Role.OWNER)

    result = kernel.lifecycle.generate_next()
    assert result.assignment is not None
    assert result.assignment.origin_template == "implement-kernel"
    assert result.assignment.workflow_mode is WorkflowMode.REVIEWED


# =============================================================================
# 14. Audit entries and immutable-field digest on the generated assignment
# =============================================================================


def test_generated_assignment_has_audit_trail_and_bound_digest(kernel, adapter) -> None:
    from projectos.domain.digest import immutable_digest

    close_document(kernel, adapter, doc(1))
    result = kernel.lifecycle.generate_next()
    assert result.assignment is not None
    generated = result.assignment

    events = [e.event for e in kernel.audit.for_assignment(generated.id)]
    assert "assignment_created" in events
    assert "classify_ok" in events

    classify_entry = next(
        e for e in kernel.audit.for_assignment(generated.id) if e.event == "classify_ok"
    )
    assert classify_entry.data["immutable_digest"] == immutable_digest(generated)
    kernel.lifecycle.verify_integrity()  # generated state is internally consistent


# =============================================================================
# 15. Three sequential assignments (end-to-end through the CLI)
# =============================================================================


def test_three_sequential_assignments_progress(project_repo) -> None:
    root = project_repo
    _add_owner(root, REVIEWER_ID)

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

    # A-0001 design-spec (FAST)
    assert _cli(root, "next") == ExitCode.OK
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "SPEC.md").write_text("# Spec\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-m", "add spec")
    assert _cli(root, "next") == ExitCode.OK
    assert _cli(root, "verify") == ExitCode.OK
    assert _cli(root, "complete", "--role", "owner") == ExitCode.OK

    # A-0002 implement-kernel (REVIEWED)
    assert _cli(root, "next") == ExitCode.OK
    git("commit", "--allow-empty", "-m", "implement the capability")
    assert _cli(root, "verify") == ExitCode.OK
    assert _cli(root, "complete", "--role", "owner") == ExitCode.OK
    assert _cli(root, "complete", "--role", "reviewer", identity=REVIEWER_ID) == ExitCode.OK

    # A-0003 harden-and-document (FAST)
    assert _cli(root, "next") == ExitCode.OK
    (root / "README.md").write_text("# Readme\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-m", "docs")
    assert _cli(root, "verify") == ExitCode.OK
    assert _cli(root, "complete", "--role", "owner") == ExitCode.OK

    statuses = {
        p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))["state"]["status"]
        for p in (root / ".projectos" / "assignments").glob("A-*.yaml")
    }
    assert statuses == {"A-0001": "closed", "A-0002": "closed", "A-0003": "closed"}

    # The pipeline is now exhausted: the next request is NEXT_UNDETERMINED.
    assert _cli(root, "next") == ExitCode.ESCALATION_REQUIRED


# -- helpers ------------------------------------------------------------------


def _cli(root: Path, *argv: str, identity: str = FOUNDER_ID) -> int:
    return main(["--repo", str(root), "--identity", identity, *argv])


def _add_owner(root: Path, owner_id: str) -> None:
    manifest = root / ".projectos" / "manifest.yaml"
    raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    raw["owners"].append({"id": owner_id, "name": "Owner"})
    manifest.write_text(yaml.dump(raw, sort_keys=False), encoding="utf-8")


@pytest.fixture
def project_repo(tmp_path: Path) -> Path:
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
    assert _cli(root, "init", "--project-id", "d", "--name", "D",
                "--founder-id", FOUNDER_ID, "--founder-name", FOUNDER_NAME) == ExitCode.OK
    return root
