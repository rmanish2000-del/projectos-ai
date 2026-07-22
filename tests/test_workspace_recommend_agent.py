"""P19 — Agent selection advisor.

`workspace recommend-agent` recommends exactly one supported worker type for one
selected assignment, from persisted `work_type` + `executor` and static ProjectOS
policy — or refuses (founder decision / insufficient information / blocked). These
tests cover the code/chat/cowork mappings, conflicting and authority metadata,
explicit and current resolution, id/name resolution, integrity → BLOCKED, determinism,
strict read-only behavior, that no agent is invoked, and that every recommendation is a
P18-dispatchable agent.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.enums import ExecutorType, Status, WorkType
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.repositories import FileAssignmentRepository
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_agent_advisor import (
    Category,
    Recommendation,
    _recommend,
    build_agent_advice,
    render_advice,
)
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    project_repository,
)
from projectos.infrastructure.workspace_dispatch import SUPPORTED_AGENTS, build_dispatch
from projectos.infrastructure.workspace_manifest import resolve_workspace
from tests.conftest import make_assignment

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register(workspace: Path, name: str, project_id: str) -> None:
    add_project(workspace, name=name, project_id=project_id)
    init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )


def repo_of(workspace: Path, project_id: str) -> Path:
    resolved = resolve_workspace(workspace).by_id(project_id)
    assert resolved is not None
    return project_repository(workspace, resolved.manifest, resolved.ref.path)


def inject(
    workspace: Path, project_id: str, number: int, work_type: WorkType, executor: ExecutorType
) -> str:
    """Persist a DRAFT assignment (valid empty history) with chosen metadata, so the
    advisor's classification can be exercised across work types."""
    repo = repo_of(workspace, project_id)
    FileAssignmentRepository(Layout.for_repo(repo)).save(
        make_assignment(number, work_type=work_type, executor=executor)
    )
    return f"A-{number:04d}"


def advise(workspace: Path, project: str, assignment: str | None = None) -> Recommendation:
    return build_agent_advice(workspace, project=project, assignment=assignment).recommendation


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- unit: the static policy (all categories) ---------------------------------


@pytest.mark.parametrize(
    ("work_type", "executor", "agent"),
    [
        (WorkType.IMPLEMENTATION, ExecutorType.CODE, "claude-code"),
        (WorkType.REFACTOR, ExecutorType.CODE, "claude-code"),
        (WorkType.TEST, ExecutorType.CODE, "claude-code"),
        (WorkType.FIX, ExecutorType.CODE, "claude-code"),
        (WorkType.DEPLOYMENT, ExecutorType.CODE, "claude-code"),
        (WorkType.MERGE, ExecutorType.CODE, "claude-code"),
        (WorkType.ARCHITECTURE, ExecutorType.COWORK, "claude-chat"),
        (WorkType.ANALYSIS, ExecutorType.COWORK, "claude-chat"),
        (WorkType.SPECIFICATION, ExecutorType.COWORK, "claude-cowork"),
        (WorkType.RESEARCH, ExecutorType.COWORK, "claude-cowork"),
        (WorkType.DOCUMENT, ExecutorType.COWORK, "claude-cowork"),
    ],
)
def test_policy_recommends_the_expected_agent(
    work_type: WorkType, executor: ExecutorType, agent: str
) -> None:
    rec = _recommend(make_assignment(1, work_type=work_type, executor=executor))
    assert rec.category is Category.RECOMMEND
    assert rec.agent == agent
    assert rec.agent in SUPPORTED_AGENTS  # P18-dispatchable


@pytest.mark.parametrize(
    ("work_type", "executor"),
    [
        (WorkType.IMPLEMENTATION, ExecutorType.COWORK),  # code work, non-code executor
        (WorkType.ARCHITECTURE, ExecutorType.CODE),  # non-code work, code executor
    ],
)
def test_policy_refuses_conflicting_metadata(
    work_type: WorkType, executor: ExecutorType
) -> None:
    rec = _recommend(make_assignment(1, work_type=work_type, executor=executor))
    assert rec.category is Category.INSUFFICIENT_INFORMATION
    assert rec.agent is None
    assert rec.missing_or_conflicting  # the conflict is named, not guessed around


@pytest.mark.parametrize(
    ("work_type", "executor"),
    [
        (WorkType.APPROVAL, ExecutorType.HUMAN),
        (WorkType.EXTERNAL_ACTION, ExecutorType.CODE),
        (WorkType.IMPLEMENTATION, ExecutorType.HUMAN),  # human executor → a person acts
    ],
)
def test_policy_defers_authority_and_human_work(
    work_type: WorkType, executor: ExecutorType
) -> None:
    rec = _recommend(make_assignment(1, work_type=work_type, executor=executor))
    assert rec.category is Category.FOUNDER_DECISION_REQUIRED
    assert rec.agent is None


def test_policy_covers_every_work_type() -> None:
    """Every WorkType is classified — no silent gap that would force a guess."""
    for work_type in WorkType:
        executor = (
            ExecutorType.CODE
            if work_type not in {
                WorkType.ARCHITECTURE, WorkType.SPECIFICATION, WorkType.RESEARCH,
                WorkType.ANALYSIS, WorkType.DOCUMENT,
            }
            else ExecutorType.COWORK
        )
        rec = _recommend(make_assignment(1, work_type=work_type, executor=executor))
        assert rec.category in Category  # always a definite category, never an exception


# -- end-to-end: code / chat / cowork -----------------------------------------


def test_code_assignment_recommends_claude_code(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    aid = inject(workspace, "alpha", 1, WorkType.IMPLEMENTATION, ExecutorType.CODE)

    rec = advise(workspace, "alpha", aid)

    assert rec.category is Category.RECOMMEND
    assert rec.agent == "claude-code"


def test_architecture_assignment_recommends_claude_chat(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    aid = inject(workspace, "alpha", 1, WorkType.ARCHITECTURE, ExecutorType.COWORK)

    assert advise(workspace, "alpha", aid).agent == "claude-chat"


def test_documentation_assignment_recommends_claude_cowork(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    # The rapid-build define-task (specification/cowork) is generated by `next`.
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])

    assert advise(workspace, "alpha", "A-0001").agent == "claude-cowork"


# -- resolution ---------------------------------------------------------------


def test_explicit_and_current_assignment_resolution(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])

    explicit = build_agent_advice(workspace, project="alpha", assignment="A-0001")
    current = build_agent_advice(workspace, project="alpha")  # in-flight one

    assert explicit.assignment_id == current.assignment_id == "A-0001"


def test_project_resolution_by_id_and_name(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])

    assert build_agent_advice(workspace, project="alpha").project_id == "alpha"  # id
    assert build_agent_advice(workspace, project="Alpha").project_id == "alpha"  # name


def test_missing_assignment_fails_closed(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    with pytest.raises(NotFoundError):
        build_agent_advice(workspace, project="alpha", assignment="A-9999")


def test_no_current_assignment_fails_closed(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")  # no `next` → nothing in flight
    with pytest.raises(NotFoundError):
        build_agent_advice(workspace, project="alpha")


def test_unresolved_project_fails_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError):
        build_agent_advice(workspace, project="ghost")


# -- integrity → BLOCKED ------------------------------------------------------


def test_integrity_failure_is_blocked(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])
    for ndjson in Layout.for_repo(repo_of(workspace, "alpha")).audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")

    advice = build_agent_advice(workspace, project="alpha", assignment="A-0001")

    assert advice.recommendation.category is Category.BLOCKED
    assert advice.recommendation.agent is None
    assert advice.is_blocked


# -- determinism, one recommendation, read-only -------------------------------


def test_output_is_deterministic(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])

    first = render_advice(build_agent_advice(workspace, project="alpha"))
    second = render_advice(build_agent_advice(workspace, project="alpha"))

    assert first == second


def test_exactly_one_recommendation(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])

    advice = build_agent_advice(workspace, project="alpha")

    assert isinstance(advice.recommendation, Recommendation)
    assert advice.recommendation.category in Category


def test_advice_changes_nothing_on_disk(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])
    before = snapshot(workspace)

    build_agent_advice(workspace, project="alpha")
    build_agent_advice(workspace, project="alpha", assignment="A-0001")

    assert snapshot(workspace) == before


def test_cli_recommend_agent_is_read_only(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])
    before = snapshot(workspace)

    code = main(["workspace", "recommend-agent", "--workspace", str(workspace),
                 "--project", "alpha"])

    assert code == int(ExitCode.OK)
    assert snapshot(workspace) == before


# -- no shell / network / agent invocation ------------------------------------


def test_no_shell_network_or_agent_invocation() -> None:
    import projectos.infrastructure.workspace_agent_advisor as mod

    source = inspect.getsource(mod)
    forbidden = [
        "subprocess", "os.system(", "socket", "urllib", "http.client", "requests.",
        "urlopen", "anthropic", "openai", ".post(", "asyncio", "build_dispatch(",
    ]
    for token in forbidden:
        assert token not in source, f"advisor must not use {token!r}"


# -- P18 compatibility & regression -------------------------------------------


def test_recommended_agent_is_dispatchable_via_p18(workspace: Path) -> None:
    """A recommendation is only ever a P18 supported agent, so it can be handed
    straight to `workspace dispatch`."""
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])

    advice = build_agent_advice(workspace, project="alpha")
    assert advice.recommendation.agent in SUPPORTED_AGENTS

    # The recommended agent is accepted by the P18 dispatch command (regression proof).
    package = build_dispatch(
        workspace, agent=advice.recommendation.agent, project="alpha", assignment="A-0001"
    )
    assert package.agent == advice.recommendation.agent


def test_p18_dispatch_still_works(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])

    package = build_dispatch(workspace, agent="claude-code", project="alpha")

    assert str(package.assignment.id) == "A-0001"


# -- isolation ----------------------------------------------------------------


def test_advising_one_project_does_not_touch_another(workspace: Path) -> None:
    register(workspace, "Alpha", "alpha")
    register(workspace, "Bravo", "bravo")
    main(["workspace", "next", "--workspace", str(workspace), "--project", "alpha"])
    bravo_before = snapshot(repo_of(workspace, "bravo"))

    build_agent_advice(workspace, project="alpha")

    assert snapshot(repo_of(workspace, "bravo")) == bravo_before
    # Injected DRAFT with status assertion keeps the fixture honest.
    assert make_assignment(1).status is Status.DRAFT
