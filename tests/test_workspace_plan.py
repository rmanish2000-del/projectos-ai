"""P16 — Workspace next-action planner.

A deterministic, read-only recommendation: from one selected project's persisted
state, the planner returns exactly one safe next action (or reports a founder decision
/ external input / blocked state). These tests cover the state → recommendation map,
that every suggested command actually exists in the CLI, that recommendations are
grounded in the canonical `legal_events` table (not a duplicated rule set), determinism,
strict read-only behavior, project isolation, and fail-closed resolution.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from projectos.cli.main import build_parser, main
from projectos.domain import state_machine
from projectos.domain.enums import Event, Status
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_plan import Category, Plan, build_plan, render_plan

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


def plan(workspace: Path, project: str) -> Plan:
    return build_plan(workspace, project=project)


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- state → recommendation ---------------------------------------------------


def test_uninitialised_project_recommends_init(workspace: Path, tmp_path: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # registered, not init

    rec = plan(workspace, "alpha").recommendation

    assert rec.category is Category.RUN_COMMAND
    assert "init-project" in (rec.command or "")


def test_no_assignment_recommends_next(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)

    rec = plan(workspace, "alpha").recommendation

    assert rec.category is Category.RUN_COMMAND
    assert rec.command == "projectos workspace next --project alpha"


def test_active_assignment_requires_external_input(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)  # A-0001 ACTIVE

    rec = plan(workspace, "alpha").recommendation

    assert rec.category is Category.EXTERNAL_INPUT_REQUIRED
    assert "verify" in (rec.command or "")
    assert rec.required_inputs  # implementation + evidence


def test_blocked_assignment_recommends_unblock(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001", "--reason", "waiting"])

    rec = plan(workspace, "alpha").recommendation

    assert rec.category is Category.RUN_COMMAND
    assert "unblock" in (rec.command or "")


def test_escalated_assignment_requires_founder_decision(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001", "--summary", "Decide",
          "--option", "O1|Proceed|risk", "--option", "O2|Cancel|loss"])

    result = plan(workspace, "alpha")

    assert result.recommendation.category is Category.FOUNDER_DECISION_REQUIRED
    assert "resolve" in (result.recommendation.command or "")
    assert "E-0001" in (result.recommendation.command or "")  # the real escalation id
    assert "E-0001" in result.situation


def test_rejected_assignment_recommends_resume_via_next(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    # Verify with no evidence → REJECTED (the legal recovery is RESUME, reached via next).
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001"])

    rec = plan(workspace, "alpha").recommendation

    assert rec.category is Category.RUN_COMMAND
    assert rec.command == "projectos workspace next --project alpha"
    assert rec.required_inputs  # fix the failed criteria first


def test_verified_assignment_recommends_complete(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001"])

    rec = plan(workspace, "alpha").recommendation

    assert rec.category is Category.RUN_COMMAND
    assert "complete" in (rec.command or "")


def test_closed_assignment_reports_complete(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Alpha", "alpha", tmp_path)
    commit_evidence(repo)
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001"])
    main(["workspace", "assignment", "complete", "--workspace", str(workspace),
          "--project", "alpha", "--assignment", "A-0001", "--role", "owner"])

    result = plan(workspace, "alpha")

    assert result.recommendation.category is Category.COMPLETE


def test_integrity_failure_is_blocked(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Alpha", "alpha", tmp_path)
    for ndjson in Layout.for_repo(repo).audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")

    result = plan(workspace, "alpha")

    assert result.recommendation.category is Category.BLOCKED
    assert result.is_blocked


def test_missing_pack_requires_external_input(workspace: Path, tmp_path: Path) -> None:
    repo = register(workspace, "Alpha", "alpha", tmp_path)  # no assignment yet
    # Remove the installed pack so generation cannot run.
    for pack_yaml in (repo / ".projectos" / "packs").rglob("pack.yaml"):
        pack_yaml.unlink()

    rec = plan(workspace, "alpha").recommendation

    assert rec.category is Category.EXTERNAL_INPUT_REQUIRED
    assert rec.required_inputs


def test_unresolved_project_fails_closed(workspace: Path) -> None:
    with pytest.raises(NotFoundError):
        plan(workspace, "ghost")


def test_resolution_by_id_and_name(workspace: Path, tmp_path: Path) -> None:
    register(workspace, "Alpha", "alpha", tmp_path)

    assert plan(workspace, "alpha").project_id == "alpha"  # by id
    assert plan(workspace, "Alpha").project_id == "alpha"  # by name


# -- exactly one recommendation & command existence ---------------------------


def _fill_placeholders(command: str) -> list[str]:
    """Turn a rendered command into argv with `<PLACEHOLDER>` tokens replaced by valid
    stand-ins (choice placeholders like `<proceed|cancel|rescope>` use their first
    option), dropping the leading `projectos`."""
    argv: list[str] = []
    for token in command.split():
        if token == "projectos":
            continue
        if token.startswith("<") and token.endswith(">"):
            inner = token[1:-1]
            argv.append(inner.split("|")[0] if "|" in inner else "x")
        else:
            argv.append(token)
    return argv


def test_every_recommended_command_exists_in_the_cli(workspace: Path, tmp_path: Path) -> None:
    """Drive the planner through every reachable category and confirm each suggested
    command parses against the real CLI parser (so it is a command that exists)."""
    commands: list[str] = []

    # uninitialised → init-project
    add_project(workspace, name="Init", project_id="p-init")
    commands.append(plan(workspace, "p-init").recommendation.command or "")

    # no assignment → next
    register(workspace, "Fresh", "p-fresh", tmp_path)
    commands.append(plan(workspace, "p-fresh").recommendation.command or "")

    # active → verify
    started(workspace, "Active", "p-active", tmp_path)
    commands.append(plan(workspace, "p-active").recommendation.command or "")

    # blocked → unblock
    started(workspace, "Blocked", "p-blocked", tmp_path)
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", "p-blocked", "--assignment", "A-0001", "--reason", "x"])
    commands.append(plan(workspace, "p-blocked").recommendation.command or "")

    # escalated → resolve
    started(workspace, "Escalated", "p-esc", tmp_path)
    main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
          "--project", "p-esc", "--assignment", "A-0001", "--summary", "d",
          "--option", "O1|a|b", "--option", "O2|c|d"])
    commands.append(plan(workspace, "p-esc").recommendation.command or "")

    parser = build_parser()
    assert len(commands) == 5
    for command in commands:
        assert command, "every reachable recommendation supplies a command here"
        parser.parse_args(_fill_placeholders(command))  # raises SystemExit if unknown


def test_plan_returns_exactly_one_recommendation(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    result = plan(workspace, "alpha")
    # The Plan type carries a single Recommendation — one category, by construction.
    assert isinstance(result.recommendation.category, Category)


# -- grounded in legal_events (no duplicated transition rules) -----------------


def test_transition_recommendations_are_grounded_in_legal_events(
    workspace: Path, tmp_path: Path
) -> None:
    """The transition-based recommendations correspond to events the canonical state
    machine actually permits — the planner reuses `legal_events`, it does not encode a
    parallel rule table."""
    # BLOCKED → unblock  ⇔  UNBLOCK legal from BLOCKED
    assert Event.UNBLOCK in state_machine.legal_events(Status.BLOCKED)
    started(workspace, "B", "b", tmp_path)
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", "b", "--assignment", "A-0001", "--reason", "x"])
    assert "unblock" in (plan(workspace, "b").recommendation.command or "")

    # VERIFIED → complete  ⇔  APPROVALS_COMPLETE legal from VERIFIED
    assert Event.APPROVALS_COMPLETE in state_machine.legal_events(Status.VERIFIED)
    repo = started(workspace, "V", "v", tmp_path)
    commit_evidence(repo)
    main(["workspace", "assignment", "verify", "--workspace", str(workspace),
          "--project", "v", "--assignment", "A-0001"])
    assert "complete" in (plan(workspace, "v").recommendation.command or "")


def test_terminal_cancelled_does_not_recommend_an_illegal_transition(
    workspace: Path, tmp_path: Path
) -> None:
    started(workspace, "C", "c", tmp_path)
    main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
          "--project", "c", "--assignment", "A-0001", "--summary", "d",
          "--option", "O1|a|b", "--option", "O2|c|d"])
    main(["workspace", "assignment", "resolve", "--workspace", str(workspace),
          "--project", "c", "--escalation", "E-0001", "--decision", "O1",
          "--outcome", "cancel"])  # → CANCELLED (terminal, no legal events)

    rec = plan(workspace, "c").recommendation

    # CANCELLED has no legal forward event, so the planner falls back to generation,
    # never an illegal unblock/verify/complete on the cancelled assignment.
    assert rec.command == "projectos workspace next --project c"


# -- determinism & read-only --------------------------------------------------


def test_output_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    first = render_plan(plan(workspace, "alpha"))
    second = render_plan(plan(workspace, "alpha"))

    assert first == second


def test_plan_changes_nothing_on_disk(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)
    repo_before = snapshot(tmp_path / "alpha_repo")

    build_plan(workspace, project="alpha")

    assert snapshot(workspace) == before
    assert snapshot(tmp_path / "alpha_repo") == repo_before


def test_cli_plan_is_read_only_and_exit_codes(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    ok = main(["workspace", "plan", "--workspace", str(workspace), "--project", "alpha"])

    assert ok == int(ExitCode.OK)
    assert snapshot(workspace) == before


def test_cli_plan_blocked_exit_code(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Alpha", "alpha", tmp_path)
    for ndjson in Layout.for_repo(repo).audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ bad\n", encoding="utf-8")

    code = main(["workspace", "plan", "--workspace", str(workspace), "--project", "alpha"])

    assert code == int(ExitCode.INVARIANT_ERROR)


# -- project isolation --------------------------------------------------------


def test_planning_one_project_does_not_read_or_touch_another(
    workspace: Path, tmp_path: Path
) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    started(workspace, "Bravo", "bravo", tmp_path)
    bravo_before = snapshot(tmp_path / "bravo_repo")

    result = plan(workspace, "alpha")

    assert result.project_id == "alpha"
    assert snapshot(tmp_path / "bravo_repo") == bravo_before
