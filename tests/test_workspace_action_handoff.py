"""P24 — Founder action handoff.

`workspace inbox --project <id> --handoff` converts one Founder Inbox item into a
complete, copy-ready execution handoff for the agent P19 already recommended. These tests
cover valid generation, an unknown project, a blocked project, missing optional fields
reported as UNAVAILABLE, a fail-closed integrity failure, deterministic output, reuse of
the existing agent recommendation, absence of any state or filesystem mutation, and
regression of the P22 inbox and P23 inbox-detail contracts.
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_action_handoff import (
    UNAVAILABLE,
    ActionHandoff,
    build_action_handoff,
    render_action_handoff,
)
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_dispatch import SUPPORTED_AGENTS
from projectos.infrastructure.workspace_inbox import build_inbox
from projectos.infrastructure.workspace_inbox_detail import build_inbox_detail

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


def make_integrity_failure(repo: Path) -> None:
    for ndjson in Layout.for_repo(repo).audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")


def make_blocked(workspace: Path, project_id: str) -> None:
    main(["workspace", "assignment", "block", "--workspace", str(workspace),
          "--project", project_id, "--assignment", "A-0001", "--reason", "x"])


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- valid handoff ------------------------------------------------------------


def test_valid_handoff_generation(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    handoff = build_action_handoff(workspace, "alpha")

    assert isinstance(handoff, ActionHandoff)
    assert handoff.executable is True
    assert handoff.project_id == "alpha"
    assert handoff.project_name == "Alpha"
    assert handoff.goal != UNAVAILABLE  # current goal
    assert handoff.milestone != UNAVAILABLE  # current milestone
    assert handoff.assignment.startswith("A-0001")  # active assignment
    assert handoff.recommended_agent in SUPPORTED_AGENTS
    assert handoff.objective != UNAVAILABLE
    assert handoff.stopping_point != UNAVAILABLE
    assert handoff.acceptance_criteria  # non-empty
    assert handoff.required_evidence  # non-empty
    assert handoff.agent_guidance  # static P18 policy
    assert handoff.integrity_ok is True
    assert handoff.integrity_warning is None


def test_handoff_text_is_copy_ready(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    text = render_action_handoff(build_action_handoff(workspace, "alpha"))

    for section in ("FOUNDER ACTION HANDOFF", "EXECUTION", "AGENT GUIDANCE",
                    "SOURCE REFERENCES", "objective", "stopping point",
                    "acceptance criteria", "required evidence", "dependencies",
                    "blockers"):
        assert section in text


def test_source_references_present(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    handoff = build_action_handoff(workspace, "alpha")

    joined = "\n".join(handoff.source_refs)
    assert "workspace:" in joined
    assert "project: alpha" in joined
    assert "repository:" in joined
    assert "kernel:" in joined
    assert "assignment: A-0001" in joined


# -- agent recommendation is reused, never re-decided -------------------------


def test_reuses_existing_agent_recommendation(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    handoff = build_action_handoff(workspace, "alpha")
    detail = build_inbox_detail(workspace, "alpha")  # P23 → P19 recommendation

    assert handoff.recommended_agent == detail.recommended_agent
    assert handoff.agent_category == detail.agent_category
    # Priority / reason are the P21 classification carried through, not recomputed.
    assert detail.focus_reason == handoff.focus_reason


# -- unknown project ----------------------------------------------------------


def test_unknown_project_raises(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    with pytest.raises(NotFoundError):
        build_action_handoff(workspace, "does-not-exist")


def test_cli_unknown_project_nonzero_exit(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    code = main(["workspace", "inbox", "--workspace", str(workspace),
                 "--project", "does-not-exist", "--handoff"])

    assert code != int(ExitCode.OK)
    assert code == int(ExitCode.INVARIANT_ERROR)


def test_cli_handoff_without_project_fails(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    code = main(["workspace", "inbox", "--workspace", str(workspace), "--handoff"])

    assert code != int(ExitCode.OK)


# -- blocked project ----------------------------------------------------------


def test_blocked_project_handoff(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Blk", "blk", tmp_path)
    make_blocked(workspace, "blk")

    handoff = build_action_handoff(workspace, "blk")

    # A blocked project has no in-flight assignment, so no execution package is built…
    assert handoff.executable is False
    assert handoff.objective == UNAVAILABLE
    assert handoff.stopping_point == UNAVAILABLE
    assert handoff.acceptance_criteria == ()
    # …but the blocker is reported so the founder knows what to clear first.
    assert handoff.blockers
    assert any("blocked assignment" in b for b in handoff.blockers)
    assert "no execution package" in render_action_handoff(handoff)


def test_cli_blocked_project_exits_ok(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Blk", "blk", tmp_path)
    make_blocked(workspace, "blk")

    code = main(["workspace", "inbox", "--workspace", str(workspace),
                 "--project", "blk", "--handoff"])

    assert code == int(ExitCode.OK)  # blocked is a reportable state, not an unsafe one


# -- missing optional fields -> UNAVAILABLE -----------------------------------


def test_missing_optional_fields_are_unavailable(workspace: Path, tmp_path: Path) -> None:
    # Registered but never started: no assignment in flight at all.
    register(workspace, "Fresh", "fresh", tmp_path)

    handoff = build_action_handoff(workspace, "fresh")

    assert handoff.executable is False
    assert handoff.assignment == UNAVAILABLE
    assert handoff.goal == UNAVAILABLE
    assert handoff.milestone == UNAVAILABLE
    assert handoff.objective == UNAVAILABLE
    assert handoff.stopping_point == UNAVAILABLE
    assert handoff.assignment_known is False
    # Unknown collections render as UNAVAILABLE, not as an empty "none".
    text = render_action_handoff(handoff)
    assert f"required evidence:\n    - {UNAVAILABLE}" in text
    assert f"dependencies:\n    - {UNAVAILABLE}" in text


def test_empty_but_known_collections_render_none(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    text = render_action_handoff(build_action_handoff(workspace, "alpha"))

    # The assignment was readable and simply has no dependencies / no blockers.
    assert "dependencies:\n    - none" in text
    assert "blockers:\n    - none" in text


# -- integrity failure stays fail-closed --------------------------------------


def test_integrity_failure_is_fail_closed(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Broken", "broken", tmp_path)
    make_integrity_failure(repo)

    handoff = build_action_handoff(workspace, "broken")

    assert handoff.integrity_ok is False
    assert handoff.executable is False  # no execution package produced
    assert handoff.integrity_warning is not None
    assert "do NOT execute" in handoff.integrity_warning
    assert handoff.objective == UNAVAILABLE
    assert handoff.acceptance_criteria == ()
    assert "INTEGRITY WARNING" in render_action_handoff(handoff)


def test_cli_integrity_failure_exit_code(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Broken", "broken", tmp_path)
    make_integrity_failure(repo)

    code = main(["workspace", "inbox", "--workspace", str(workspace),
                 "--project", "broken", "--handoff"])

    assert code == int(ExitCode.INVARIANT_ERROR)


def test_cli_valid_handoff_ok_exit(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    code = main(["workspace", "inbox", "--workspace", str(workspace),
                 "--project", "alpha", "--handoff"])

    assert code == int(ExitCode.OK)


# -- determinism & no mutation ------------------------------------------------


def test_output_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    first = build_action_handoff(workspace, "alpha")
    second = build_action_handoff(workspace, "alpha")

    assert first == second  # frozen dataclass — structural equality
    assert render_action_handoff(first) == render_action_handoff(second)


def test_handoff_changes_nothing_on_disk(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    build_action_handoff(workspace, "alpha")

    assert snapshot(workspace) == before


def test_cli_handoff_creates_no_assignment_and_mutates_nothing(
    workspace: Path, tmp_path: Path
) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)
    inbox_before = build_inbox(workspace)

    main(["workspace", "inbox", "--workspace", str(workspace),
          "--project", "alpha", "--handoff"])

    assert snapshot(workspace) == before  # no file written, no state updated
    after = build_inbox(workspace)
    assert [(i.project_id, i.priority) for i in after.items] == [
        (i.project_id, i.priority) for i in inbox_before.items
    ]


# -- regression: reused models unchanged --------------------------------------


def test_handoff_only_composes_existing_models() -> None:
    import projectos.infrastructure.workspace_action_handoff as mod

    source = inspect.getsource(mod)
    # Composes P23 detail + the existing P18 handoff model…
    assert "build_inbox_detail(" in source
    assert "build_dispatch(" in source
    # …and reimplements no ranking / recommendation / lifecycle logic, and never writes.
    for reimplemented in (
        "build_plan(", "build_agent_advice(", "build_status(", "build_queue(",
        "build_report(", "build_dashboard(", "build_inbox(", "_rank(", "_RANK_CATEGORY",
        "generate_next", "_transition", ".save(", "write_text", "mkdir",
        "subprocess", "urllib", "anthropic", "openai",
    ):
        assert reimplemented not in source, f"handoff must not reimplement {reimplemented}"


def test_inbox_and_detail_contracts_preserved(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    # P22 list, and P23 detail without --handoff, are unchanged.
    list_code = main(["workspace", "inbox", "--workspace", str(workspace)])
    detail_code = main(["workspace", "inbox", "--workspace", str(workspace),
                        "--project", "alpha"])

    assert list_code == int(ExitCode.OK)
    assert detail_code == int(ExitCode.OK)
    assert snapshot(workspace) == before

    detail = build_inbox_detail(workspace, "alpha")
    assert detail.project_id == "alpha"
    assert any(i.project_id == "alpha" for i in build_inbox(workspace).items)
