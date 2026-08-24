"""P18 — Agent handoff package.

`workspace dispatch` prepares a deterministic, read-only, copy-ready handoff for one
explicitly-selected assignment and one explicitly-selected worker type. It invokes no
agent, runs no shell, and opens no network. These tests cover the three agent packages
and their distinct static guidance, explicit and current assignment resolution, id/name
project resolution, repository path and remote/branch metadata, pack metadata, that
absent schema fields are labelled UNAVAILABLE (never invented), fail-closed cases,
determinism, read-only behavior, project isolation, and that no shell/network/agent
call exists.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.enums import Status
from projectos.domain.errors import ExitCode, NotFoundError, ProjectOSError, ValidationError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    project_repository,
)
from projectos.infrastructure.workspace_dispatch import (
    SUPPORTED_AGENTS,
    DispatchPackage,
    build_dispatch,
    render_dispatch,
)
from projectos.infrastructure.workspace_handoff import build_handoff
from projectos.infrastructure.workspace_manifest import resolve_workspace

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register_started(
    workspace: Path,
    name: str,
    project_id: str,
    *,
    repository_path: str | None = None,
    repository_remote: str | None = None,
    repository_branch: str | None = None,
) -> None:
    add_project(
        workspace,
        name=name,
        project_id=project_id,
        repository_path=repository_path,
        repository_remote=repository_remote,
        repository_branch=repository_branch,
    )
    init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    main(["workspace", "next", "--workspace", str(workspace), "--project", project_id])


def repo_of(workspace: Path, project_id: str) -> Path:
    resolved = resolve_workspace(workspace).by_id(project_id)
    assert resolved is not None
    return project_repository(workspace, resolved.manifest, resolved.ref.path)


def dispatch(
    workspace: Path, project: str, agent: str, assignment: str | None = None
) -> DispatchPackage:
    return build_dispatch(workspace, agent=agent, project=project, assignment=assignment)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- the three agent packages -------------------------------------------------


@pytest.mark.parametrize("agent", ["claude-code", "claude-chat", "claude-cowork"])
def test_package_for_each_agent(workspace: Path, agent: str) -> None:
    register_started(workspace, "Alpha", "alpha")

    package = dispatch(workspace, "alpha", agent)
    text = render_dispatch(package)

    assert package.agent == agent
    assert f"PROJECTOS AGENT HANDOFF  ({agent})" in text
    assert "handoff version  projectos-handoff/1" in text


def test_agent_guidance_is_role_specific(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")

    code = render_dispatch(dispatch(workspace, "alpha", "claude-code"))
    chat = render_dispatch(dispatch(workspace, "alpha", "claude-chat"))
    cowork = render_dispatch(dispatch(workspace, "alpha", "claude-cowork"))

    assert "open a PR" in code  # code implements
    assert "do NOT claim any repository implementation" in chat  # chat is analysis-only
    assert "implementation-ready artifacts" in cowork  # cowork designs
    # The three guidance blocks are distinct.
    assert code != chat != cowork != code


# -- assignment resolution ----------------------------------------------------


def test_explicit_assignment_resolution(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")

    package = dispatch(workspace, "alpha", "claude-code", assignment="A-0001")

    assert str(package.assignment.id) == "A-0001"


def test_current_assignment_resolution(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")  # A-0001 ACTIVE (in flight)

    package = dispatch(workspace, "alpha", "claude-code")  # no --assignment

    assert str(package.assignment.id) == "A-0001"
    assert package.assignment.status is Status.ACTIVE


def test_project_resolution_by_id_and_name(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")

    assert dispatch(workspace, "alpha", "claude-code").project_id == "alpha"  # id
    assert dispatch(workspace, "Alpha", "claude-code").project_id == "alpha"  # name


# -- repository & pack metadata -----------------------------------------------


def test_repository_path_metadata(workspace: Path, tmp_path: Path) -> None:
    repo = tmp_path / "external"
    repo.mkdir()
    register_started(workspace, "Alpha", "alpha", repository_path=str(repo))

    text = render_dispatch(dispatch(workspace, "alpha", "claude-code"))

    assert f"path={repo}" in text
    assert "adapter=local_git" in text


def test_repository_remote_and_branch_metadata(workspace: Path) -> None:
    register_started(
        workspace, "Alpha", "alpha",
        repository_remote="git@example.com:acme/alpha.git", repository_branch="release",
    )

    text = render_dispatch(dispatch(workspace, "alpha", "claude-code"))

    assert "remote=git@example.com:acme/alpha.git" in text
    assert "branch=release" in text


def test_pack_metadata(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")

    package = dispatch(workspace, "alpha", "claude-code")

    assert package.pack == "rapid-build"
    assert "pack             rapid-build" in render_dispatch(package)


# -- unavailable optional fields (never invented) -----------------------------


def test_absent_fields_are_labelled_unavailable(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")

    text = render_dispatch(dispatch(workspace, "alpha", "claude-code"))

    # rapid-build's template does not define these — they must be UNAVAILABLE, not made up.
    for field in ("inputs", "scope", "out of scope", "constraints", "quality checks"):
        assert f"{field}" in text
    assert text.count("UNAVAILABLE") >= 5
    # ...but the genuinely-persisted fields are present verbatim.
    assert "State the task" in text  # objective
    assert "docs/TASK.md" in text  # acceptance criterion
    assert "Stop when the task definition is committed" in text  # stopping point


# -- fail-closed --------------------------------------------------------------


def test_unsupported_agent_fails_closed(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")
    with pytest.raises(ValidationError):
        build_dispatch(workspace, agent="gpt-4", project="alpha", assignment="A-0001")


def test_missing_assignment_fails_closed(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")
    with pytest.raises(NotFoundError):
        dispatch(workspace, "alpha", "claude-code", assignment="A-9999")


def test_no_current_assignment_fails_closed(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    init_project_kernel(workspace, name="Alpha", founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME)
    # No `next` → no in-flight assignment; a current-resolution request fails closed.
    with pytest.raises(NotFoundError):
        dispatch(workspace, "alpha", "claude-code")


def test_uninitialised_kernel_fails_closed(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # registered, not init
    with pytest.raises(NotFoundError):
        dispatch(workspace, "alpha", "claude-code", assignment="A-0001")


def test_integrity_failure_fails_closed(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")
    for ndjson in Layout.for_repo(repo_of(workspace, "alpha")).audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")

    with pytest.raises(ProjectOSError):  # INV-6 integrity guard fails closed
        dispatch(workspace, "alpha", "claude-code")


def test_unresolved_project_fails_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError):
        dispatch(workspace, "ghost", "claude-code")


# -- determinism, one package, read-only --------------------------------------


def test_output_is_deterministic(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")

    first = render_dispatch(dispatch(workspace, "alpha", "claude-code"))
    second = render_dispatch(dispatch(workspace, "alpha", "claude-code"))

    assert first == second


def test_build_produces_exactly_one_package(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")

    package = dispatch(workspace, "alpha", "claude-code")

    assert isinstance(package, DispatchPackage)


def test_dispatch_changes_nothing_on_disk(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")
    before = snapshot(workspace)

    for agent in SUPPORTED_AGENTS:
        build_dispatch(workspace, agent=agent, project="alpha", assignment="A-0001")

    assert snapshot(workspace) == before


def test_cli_dispatch_is_read_only(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")
    before = snapshot(workspace)

    code = main(["workspace", "dispatch", "--workspace", str(workspace),
                 "--project", "alpha", "--agent", "claude-code"])

    assert code == int(ExitCode.OK)
    assert snapshot(workspace) == before


# -- project isolation --------------------------------------------------------


def test_dispatching_one_project_does_not_touch_another(workspace: Path) -> None:
    register_started(workspace, "Alpha", "alpha")
    register_started(workspace, "Bravo", "bravo")
    bravo_before = snapshot(repo_of(workspace, "bravo"))

    package = dispatch(workspace, "alpha", "claude-code")

    assert package.project_id == "alpha"
    assert snapshot(repo_of(workspace, "bravo")) == bravo_before


# -- no shell / network / agent invocation ------------------------------------


def test_no_shell_network_or_agent_invocation() -> None:
    import projectos.infrastructure.workspace_dispatch as mod

    source = inspect.getsource(mod)
    forbidden = [
        "subprocess", "os.system(", "socket", "urllib", "http.client", "requests.",
        "urlopen", "anthropic", "openai", ".post(", ".get(http", "asyncio",
    ]
    for token in forbidden:
        assert token not in source, f"dispatch must not use {token!r}"


# -- P7 handoff reuse (non-regression) ----------------------------------------


def test_reuses_p7_handoff_context(workspace: Path) -> None:
    """The package's repository/pack context matches the P7 handoff read-model it
    reuses — proving handoff behavior is unchanged and not duplicated."""
    register_started(workspace, "Alpha", "alpha", repository_remote="git@x:a.git")

    package = dispatch(workspace, "alpha", "claude-code")
    handoff_project = build_handoff(workspace, project="alpha").projects[0]

    assert package.pack == handoff_project.pack
    assert package.repository == handoff_project.repository
    assert package.kernel_location == handoff_project.kernel_location
