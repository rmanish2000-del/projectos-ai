"""P10 — Workspace assignment queue.

A read-only, deterministic view over the assignments each project's kernel already
persists — partitioned into active / ready / blocked / completed / other. These tests
exercise the partition against every state, ordering, aggregate counts, project-first
focus, uninitialised and empty projects, per-project fault isolation, that a genuine
lifecycle-driven state is read (not just injected fixtures), and strict read-only
behavior. P10 adds no persistence: assignments are written through the *existing*
assignment repository and read back through the queue.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.enums import Status
from projectos.domain.errors import ExitCode, NotFoundError, ValidationError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.repositories import FileAssignmentRepository
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    open_project_kernel,
)
from projectos.infrastructure.workspace_handoff import build_handoff
from projectos.infrastructure.workspace_queue import (
    ProjectQueue,
    WorkspaceQueue,
    build_queue,
    render_queue,
)
from tests.conftest import make_assignment

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def register_and_init(workspace: Path, name: str, project_id: str) -> Path:
    add_project(workspace, name=name, project_id=project_id)
    return init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )


def seed_assignments(repo: Path, states: list[tuple[int, Status]]) -> None:
    """Persist assignments in chosen states through the *existing* repository — the
    same store the kernel writes, so the queue reads real persisted state."""
    assignments = FileAssignmentRepository(Layout.for_repo(repo))
    for number, status in states:
        assignments.save(make_assignment(number, status=status))


def project_named(queue: WorkspaceQueue, project_id: str) -> ProjectQueue:
    return next(p for p in queue.projects if p.project_id == project_id)


# -- partition ----------------------------------------------------------------


def test_partitions_each_bucket(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(
        repo,
        [
            (1, Status.CLOSED),
            (2, Status.ACTIVE),
            (3, Status.READY),
            (4, Status.BLOCKED),
            (5, Status.VERIFIED),
        ],
    )

    alpha = build_queue(workspace, project="alpha").projects[0]

    assert [a.id for a in alpha.active] == ["A-0002"]
    assert [a.id for a in alpha.ready] == ["A-0003"]
    assert [a.id for a in alpha.blocked] == ["A-0004"]
    assert [a.id for a in alpha.completed] == ["A-0001"]
    assert [a.id for a in alpha.other] == ["A-0005"]  # verified → other
    assert alpha.total == 5


def test_active_bucket_covers_all_active_slot_states(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(
        repo,
        [(1, Status.ACTIVE), (2, Status.EVIDENCE_SUBMITTED), (3, Status.VERIFYING)],
    )

    alpha = build_queue(workspace, project="alpha").projects[0]

    assert {a.id for a in alpha.active} == {"A-0001", "A-0002", "A-0003"}
    assert alpha.ready == ()
    assert alpha.completed == ()


def test_blocked_bucket_covers_blocked_and_escalated(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(repo, [(1, Status.BLOCKED), (2, Status.ESCALATED)])

    alpha = build_queue(workspace, project="alpha").projects[0]

    assert {a.id for a in alpha.blocked} == {"A-0001", "A-0002"}


def test_completed_is_closed_only_others_fall_through(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(
        repo,
        [
            (1, Status.CLOSED),
            (2, Status.CANCELLED),
            (3, Status.DRAFT),
            (4, Status.REJECTED),
        ],
    )

    alpha = build_queue(workspace, project="alpha").projects[0]

    assert [a.id for a in alpha.completed] == ["A-0001"]
    # cancelled, draft, rejected are neither completed nor lost — they carry status.
    assert {a.id for a in alpha.other} == {"A-0002", "A-0003", "A-0004"}
    assert {a.status for a in alpha.other} == {"cancelled", "draft", "rejected"}


# -- reads genuine lifecycle state --------------------------------------------


def test_reads_real_lifecycle_state(workspace: Path) -> None:
    """Not just injected fixtures: drive the real kernel and read what it persisted."""
    register_and_init(workspace, "Alpha", "alpha")
    kernel = open_project_kernel(workspace, "Alpha")
    result = kernel.lifecycle.generate_next()
    assert result.assignment is not None
    kernel.lifecycle.start(result.assignment.id)  # → ACTIVE

    alpha = build_queue(workspace, project="alpha").projects[0]

    assert [a.id for a in alpha.active] == ["A-0001"]
    assert alpha.ready == ()


# -- ordering & counts --------------------------------------------------------


def test_entries_sorted_by_id_within_a_bucket(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(repo, [(3, Status.READY), (1, Status.READY), (2, Status.READY)])

    alpha = build_queue(workspace, project="alpha").projects[0]

    assert [a.id for a in alpha.ready] == ["A-0001", "A-0002", "A-0003"]


def test_projects_ordered_by_identifier(workspace: Path) -> None:
    register_and_init(workspace, "Zeta", "zeta")
    register_and_init(workspace, "Alpha", "alpha")

    ids = [p.project_id for p in build_queue(workspace).projects]

    assert ids == ["alpha", "example-project", "zeta"]


def test_aggregate_counts_across_projects(workspace: Path) -> None:
    repo_a = register_and_init(workspace, "Alpha", "alpha")
    repo_b = register_and_init(workspace, "Bravo", "bravo")
    seed_assignments(repo_a, [(1, Status.ACTIVE), (2, Status.READY)])
    seed_assignments(repo_b, [(1, Status.READY), (2, Status.CLOSED)])

    queue = build_queue(workspace)

    assert queue.active == 1
    assert queue.ready == 2
    assert queue.completed == 1
    assert queue.total == 4


# -- uninitialised / empty ----------------------------------------------------


def test_uninitialised_project_has_no_queue(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # registered, not init

    alpha = project_named(build_queue(workspace), "alpha")

    assert alpha.initialised is False
    assert alpha.total == 0
    assert alpha.failure is None


def test_initialised_but_empty_project(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")  # kernel, zero assignments

    alpha = build_queue(workspace, project="alpha").projects[0]

    assert alpha.initialised is True
    assert alpha.total == 0


# -- focus --------------------------------------------------------------------


def test_project_focus_by_id_and_name(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")

    by_id = build_queue(workspace, project="alpha")
    by_name = build_queue(workspace, project="Alpha")

    assert by_id.focus == by_name.focus == "alpha"
    assert [p.project_id for p in by_id.projects] == ["alpha"]


def test_unresolved_focus_is_fail_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError):
        build_queue(workspace, project="ghost")


# -- failure isolation & fail-closed ------------------------------------------


def test_per_project_state_failure_is_isolated(workspace: Path) -> None:
    repo_a = register_and_init(workspace, "Alpha", "alpha")
    register_and_init(workspace, "Bravo", "bravo")
    seed_assignments(repo_a, [(1, Status.READY)])
    # Corrupt one of Bravo's assignment files so reading its queue fails.
    bravo_assignments = Layout.for_repo(workspace / "Projects" / "Bravo").assignments_dir
    (bravo_assignments / "A-0001.yaml").write_text("not: [a, valid, assignment\n", encoding="utf-8")

    queue = build_queue(workspace)

    assert project_named(queue, "bravo").failure is not None
    assert project_named(queue, "alpha").failure is None  # Alpha unaffected
    assert queue.has_failures is True


def test_malformed_workspace_is_fail_closed(workspace: Path) -> None:
    (workspace / "Workspace.yaml").write_text(
        "schema_version: 9\nworkspace:\n  name: Broken\n", encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        build_queue(workspace)


def test_missing_workspace_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        build_queue(tmp_path / "nope")


# -- determinism & read-only --------------------------------------------------


def test_output_is_deterministic(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(repo, [(1, Status.ACTIVE), (2, Status.READY), (3, Status.CLOSED)])

    first = render_queue(build_queue(workspace))
    second = render_queue(build_queue(workspace))

    assert first == second


def test_queue_changes_nothing_on_disk(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(repo, [(1, Status.ACTIVE), (2, Status.READY)])
    before = snapshot(workspace)

    build_queue(workspace)
    build_queue(workspace, project="alpha")

    assert snapshot(workspace) == before


# -- P7/P8 reuse (non-regression) ---------------------------------------------


def test_queue_reuses_handoff_projects(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")
    add_project(workspace, name="Beta", project_id="beta")

    queue_ids = {p.project_id for p in build_queue(workspace).projects}
    handoff_ids = {p.project_id for p in build_handoff(workspace).projects}

    assert queue_ids == handoff_ids


# -- CLI ----------------------------------------------------------------------


def test_cli_queue_ok(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(repo, [(1, Status.ACTIVE)])

    code = main(["workspace", "queue", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)


def test_cli_queue_failure_exit_code(workspace: Path) -> None:
    register_and_init(workspace, "Alpha", "alpha")
    assignments = Layout.for_repo(workspace / "Projects" / "Alpha").assignments_dir
    (assignments / "A-0001.yaml").write_text("not: [valid\n", encoding="utf-8")

    code = main(["workspace", "queue", "--workspace", str(workspace)])

    assert code == int(ExitCode.ESCALATION_REQUIRED)


def test_cli_queue_is_read_only(workspace: Path) -> None:
    repo = register_and_init(workspace, "Alpha", "alpha")
    seed_assignments(repo, [(1, Status.READY)])
    before = snapshot(workspace)

    main(["workspace", "queue", "--workspace", str(workspace)])

    assert snapshot(workspace) == before
