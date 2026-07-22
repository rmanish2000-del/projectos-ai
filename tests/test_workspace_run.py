"""P17 — Safe plan executor.

`workspace run` obtains a *fresh* P16 recommendation and, only with explicit
confirmation, executes at most one fully-determined safe operation by delegating to an
existing typed helper. These tests prove the confirmation gate, the executable
allowlist (next / unblock), refusal of every authority/evidence/external/blocked/
complete/placeholder recommendation, stale-plan protection, single delegation, absence
of any shell/arbitrary-command execution, project isolation, and that every refusal is
read-only.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from projectos.cli.commands import ExecutionResult, execute_plan
from projectos.cli.main import main
from projectos.domain.enums import Status
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.domain.ids import AssignmentId
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    open_project_kernel,
)
from projectos.infrastructure.workspace_plan import Category
from projectos.infrastructure.workspace_queue import build_queue

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register(workspace: Path, name: str, project_id: str, tmp_path: Path) -> Path:
    repo = tmp_path / f"{project_id}_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", FOUNDER_ID)
    _git(repo, "config", "user.name", "Actor")
    add_project(workspace, name=name, project_id=project_id, repository_path=str(repo))
    init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    return repo


def started(workspace: Path, name: str, project_id: str, tmp_path: Path) -> Path:
    repo = register(workspace, name, project_id, tmp_path)
    main(["workspace", "next", "--workspace", str(workspace), "--project", project_id])
    return repo


def commit_evidence(repo: Path) -> None:
    (repo / "docs").mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "TASK.md").write_text("# Task\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "task")


def run(workspace: Path, project: str, *, confirm: bool) -> ExecutionResult:
    return execute_plan(workspace, project=project, confirm=confirm)


def status_of(workspace: Path, name: str, assignment_id: str) -> Status:
    return open_project_kernel(workspace, name).assignments.get(
        AssignmentId.parse(assignment_id)
    ).status


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- confirmation gate --------------------------------------------------------


def test_missing_confirmation_executes_nothing(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)  # fresh → recommendation is next
    before = snapshot(workspace)

    result = run(workspace, "alpha", confirm=False)

    assert result.executed is False
    assert "not confirmed" in (result.refusal or "")
    assert snapshot(workspace) == before  # no mutation without --confirm
    assert open_project_kernel(workspace, "Alpha").assignments.list_all() == ()


# -- executable allowlist -----------------------------------------------------


def test_confirmed_next_generates_the_first_assignment(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)

    result = run(workspace, "alpha", confirm=True)

    assert result.executed is True
    assignments = open_project_kernel(workspace, "Alpha").assignments.list_all()
    assert [str(a.id) for a in assignments] == ["A-0001"]  # exactly one operation
    assert result.result_assignment == "A-0001"


def test_confirmed_unblock_when_fully_determined(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001", "--reason", "waiting"])

    result = run(workspace, "alpha", confirm=True)

    assert result.executed is True
    assert status_of(workspace, "Alpha", "A-0001") is Status.READY  # BLOCKED → READY


# -- refusals (each must be read-only) ----------------------------------------


@pytest.mark.parametrize("scenario", ["active", "verified", "escalated", "blocked-integrity",
                                       "closed", "uninitialised"])
def test_non_executable_recommendations_are_refused_read_only(
    workspace: Path, tmp_path: Path, scenario: str
) -> None:
    project = f"p-{scenario}"
    if scenario == "active":
        started(workspace, scenario, project, tmp_path)
    elif scenario == "verified":
        repo = started(workspace, scenario, project, tmp_path)
        commit_evidence(repo)
        main(["workspace", "assignment", "verify", "--workspace", str(workspace),
              "--project", project, "--assignment", "A-0001"])
    elif scenario == "escalated":
        started(workspace, scenario, project, tmp_path)
        main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
              "--project", project, "--assignment", "A-0001", "--summary", "d",
              "--option", "O1|a|b", "--option", "O2|c|d"])
    elif scenario == "blocked-integrity":
        repo = started(workspace, scenario, project, tmp_path)
        for ndjson in Layout.for_repo(repo).audit_dir.glob("*.ndjson"):
            ndjson.write_text("{ bad\n", encoding="utf-8")
    elif scenario == "closed":
        repo = started(workspace, scenario, project, tmp_path)
        commit_evidence(repo)
        main(["workspace", "assignment", "verify", "--workspace", str(workspace),
              "--project", project, "--assignment", "A-0001"])
        main(["workspace", "assignment", "complete", "--workspace", str(workspace),
              "--project", project, "--assignment", "A-0001", "--role", "owner"])
    else:  # uninitialised → the recommended init-project carries <PLACEHOLDER>s
        add_project(workspace, name=scenario, project_id=project)

    before = snapshot(workspace)
    result = run(workspace, project, confirm=True)

    assert result.executed is False
    assert result.refusal is not None
    assert result.plan.recommendation.action is None  # not on the executable allowlist
    assert snapshot(workspace) == before  # every refusal is non-mutating


def test_rejected_recommendation_is_refused_needs_external_fix(
    workspace: Path, tmp_path: Path
) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001"])  # → REJECTED
    before = snapshot(workspace)

    result = run(workspace, "alpha", confirm=True)

    # REJECTED recommends `next` (resume) but requires the criteria be fixed first —
    # an external prerequisite, so the executor refuses.
    assert result.executed is False
    assert snapshot(workspace) == before


# -- stale-plan protection ----------------------------------------------------


def test_plan_is_rebuilt_from_current_state_each_call(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)

    # First confirmed run: fresh → GENERATE_NEXT executes (A-0001 ACTIVE).
    first = run(workspace, "alpha", confirm=True)
    assert first.executed is True

    # Second confirmed run: the plan is rebuilt from the now-ACTIVE state, so the
    # recommendation is EXTERNAL_INPUT_REQUIRED and the executor refuses — proving it
    # never reuses the earlier plan.
    second = run(workspace, "alpha", confirm=True)
    assert second.executed is False
    assert second.plan.recommendation.category is Category.EXTERNAL_INPUT_REQUIRED


def test_execute_plan_takes_no_saved_plan(workspace: Path) -> None:
    """The signature accepts only (workspace_root, project, confirm) — a caller cannot
    inject a stale recommendation."""
    params = set(inspect.signature(execute_plan).parameters)
    assert params == {"workspace_root", "project", "confirm"}


# -- no shell / no arbitrary command parsing ----------------------------------


def test_executor_uses_no_shell_subprocess_or_command_string_parsing() -> None:
    # Scan the executable code, not the docstring prose.
    source = inspect.getsource(execute_plan)
    doc = inspect.getdoc(execute_plan) or ""
    code = source.replace(doc, "")

    forbidden = ["subprocess.", "os.system(", "shlex", "eval(", "exec(", "shell=True",
                 "import subprocess", ".split("]
    for token in forbidden:
        assert token not in code, f"executor must not use {token!r}"
    # It must delegate via the typed action, never by parsing the rendered command string.
    assert ".command" not in code  # the command string is never read for execution
    assert "action.kind" in code  # delegation is keyed on the typed PlannedAction


# -- audit & queue reflection -------------------------------------------------


def test_permitted_action_reflects_in_audit_and_queue(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)

    run(workspace, "alpha", confirm=True)  # generate A-0001

    kernel = open_project_kernel(workspace, "Alpha")
    assert len(kernel.audit.read_all()) > 0
    kernel.lifecycle.verify_integrity()
    alpha = build_queue(workspace, project="alpha").projects[0]
    assert [a.id for a in alpha.active] == ["A-0001"]


# -- project isolation & fail-closed ------------------------------------------


def test_only_the_selected_project_is_mutated(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)
    register(workspace, "Bravo", "bravo", tmp_path)
    bravo_before = snapshot(tmp_path / "bravo_repo")

    run(workspace, "alpha", confirm=True)

    assert snapshot(tmp_path / "bravo_repo") == bravo_before  # Bravo untouched
    assert open_project_kernel(workspace, "Bravo").assignments.list_all() == ()


def test_unresolved_project_fails_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError):
        run(workspace, "ghost", confirm=True)


# -- CLI wiring & exit codes --------------------------------------------------


def test_cli_run_requires_confirm_for_mutation(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)

    no_confirm = main(["workspace", "run", "--workspace", str(workspace), "--project", "alpha"])
    assert no_confirm == int(ExitCode.INVARIANT_ERROR)  # refusal without --confirm
    assert open_project_kernel(workspace, "Alpha").assignments.list_all() == ()

    confirmed = main(["workspace", "run", "--workspace", str(workspace),
                      "--project", "alpha", "--confirm"])
    assert confirmed == int(ExitCode.OK)
    assert len(open_project_kernel(workspace, "Alpha").assignments.list_all()) == 1
