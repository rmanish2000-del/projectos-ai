"""Shared fixtures.

Every test gets its own repository under `tmp_path` with a pinned clock and a
known identity, so nothing depends on the machine's git config, wall clock, or the
order tests happen to run in.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from projectos.domain.assignment import Assignment
from projectos.domain.enums import ExecutorType, RepositoryAdapterKind, RuleType, WorkType
from projectos.domain.evidence import AcceptanceCriterion, EvidenceRule, RepositoryFact
from projectos.domain.ids import AssignmentId
from projectos.infrastructure.container import Kernel, build_kernel
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.scaffold import build_manifest, scaffold
from projectos.infrastructure.system import FixedClock, StaticIdentityProvider

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"
REVIEWER_ID = "reviewer@example.test"
FIXED_INSTANT = "2026-07-20T09:00:00Z"


class FakeAdapter:
    """A repository adapter whose answers the test controls outright.

    Declares full capabilities so capability gating does not mask the behaviour a
    test is actually exercising; tests that want gating use `capabilities` directly.
    """

    def __init__(
        self,
        facts: dict[RuleType, RepositoryFact] | None = None,
        capabilities: dict[str, bool] | None = None,
    ) -> None:
        self.facts = facts or {}
        self._capabilities = capabilities or {"pr": True, "ci": True, "artifacts": True}
        self.queries: list[EvidenceRule] = []

    def capabilities(self) -> dict[str, bool]:
        return dict(self._capabilities)

    def query(self, rule: EvidenceRule) -> RepositoryFact:
        self.queries.append(rule)
        return self.facts.get(
            rule.type, RepositoryFact(kind=rule.type.value, found=False, detail="no fact staged")
        )


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path / "repo"


@pytest.fixture
def git_repo(repo_root: Path) -> Path:
    """A real git repository, for adapter tests that need committed history."""
    repo_root.mkdir(parents=True, exist_ok=True)
    run = lambda *args: subprocess.run(  # noqa: E731 - terse local helper
        ["git", "-C", str(repo_root), *args], check=True, capture_output=True
    )
    run("init", "-b", "main")
    run("config", "user.email", FOUNDER_ID)
    run("config", "user.name", FOUNDER_NAME)
    return repo_root


@pytest.fixture
def initialised(repo_root: Path) -> Layout:
    repo_root.mkdir(parents=True, exist_ok=True)
    layout = Layout.for_repo(repo_root)
    manifest = build_manifest(
        project_id="test-project",
        project_name="Test Project",
        description="Fixture project",
        founder_id=FOUNDER_ID,
        founder_name=FOUNDER_NAME,
        adapter=RepositoryAdapterKind.LOCAL_GIT,
        default_branch="main",
    )
    scaffold(layout, manifest)
    return layout


@pytest.fixture
def adapter() -> FakeAdapter:
    return FakeAdapter()


@pytest.fixture
def kernel(initialised: Layout, adapter: FakeAdapter) -> Iterator[Kernel]:
    return build_kernel(
        initialised.repo_root,
        clock=FixedClock(FIXED_INSTANT),
        identity=StaticIdentityProvider(FOUNDER_ID),
        adapter=adapter,
    )


def kernel_as(layout: Layout, identity: str, adapter: FakeAdapter) -> Kernel:
    """A kernel over the same repository, acting as a different identity."""
    return build_kernel(
        layout.repo_root,
        clock=FixedClock(FIXED_INSTANT),
        identity=StaticIdentityProvider(identity),
        adapter=adapter,
    )


def make_assignment(
    number: int = 1,
    *,
    work_type: WorkType = WorkType.IMPLEMENTATION,
    executor: ExecutorType = ExecutorType.CODE,
    owner: str = FOUNDER_ID,
    rule: EvidenceRule | None = None,
    depends_on: tuple[AssignmentId, ...] = (),
    risk_flags: tuple[str, ...] = (),
    **overrides: object,
) -> Assignment:
    """Build a valid assignment; every field a test cares about is overridable."""
    default_criteria = (
        AcceptanceCriterion(
            id="AC-1",
            statement="The specification file exists.",
            verify=rule or EvidenceRule(RuleType.FILE_EXISTS, {"path": "SPEC.md"}),
        ),
    )
    criteria = overrides.pop("acceptance_criteria", default_criteria)
    return Assignment(
        id=AssignmentId(number),
        title=f"Test assignment {number}",
        work_type=work_type,
        objective="Do the thing the test needs done.",
        owner=owner,
        executor=executor,
        stopping_point="Stop when the criterion is satisfiable.",
        acceptance_criteria=criteria,  # type: ignore[arg-type]
        depends_on=depends_on,
        risk_flags=risk_flags,
        **overrides,  # type: ignore[arg-type]
    )
