"""P23 — Founder inbox detail (drill-down).

`workspace inbox --project <id>` explains one Founder Inbox item and shows the evidence
behind its recommended next action, aggregated from existing read-models (P20 dashboard,
P21 focus, P22 inbox, P7 handoff, and the kernel's own assignment read). These tests
cover a valid project detail, an unknown project id (non-zero exit), a blocked project,
an integrity failure, deterministic text and structured output, the CLI exit codes,
read-only behavior, and regression protection that the reused read-models are unchanged.
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
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_dashboard import build_dashboard
from projectos.infrastructure.workspace_focus import FocusCategory, build_focus
from projectos.infrastructure.workspace_inbox import build_inbox
from projectos.infrastructure.workspace_inbox_detail import (
    InboxDetail,
    build_inbox_detail,
    render_inbox_detail,
)

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


# -- valid detail -------------------------------------------------------------


def test_valid_project_detail(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    detail = build_inbox_detail(workspace, "alpha")

    assert isinstance(detail, InboxDetail)
    assert detail.project_id == "alpha"
    assert detail.project_name == "Alpha"
    assert detail.assignment is not None
    assert detail.assignment.startswith("A-0001")
    assert detail.owner == FOUNDER_ID
    assert detail.priority == 4  # ACTIVE → EXTERNAL_INPUT_REQUIRED
    assert detail.focus_category is FocusCategory.EXTERNAL_INPUT_REQUIRED
    assert detail.integrity_ok is True
    assert detail.integrity.startswith("verified")
    assert detail.next_action  # P16, non-empty
    assert detail.recommended_agent is not None  # P19


def test_detail_resolves_by_name(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    by_id = build_inbox_detail(workspace, "alpha")
    by_name = build_inbox_detail(workspace, "Alpha")

    assert by_id == by_name  # project-first resolution, identical result


def test_detail_values_come_from_existing_read_models(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    detail = build_inbox_detail(workspace, "alpha")
    row = next(p for p in build_dashboard(workspace).projects if p.project_id == "alpha")
    item = next(it for it in build_inbox(workspace).items if it.project_id == "alpha")

    # Every displayed value is lifted, not recomputed.
    assert detail.next_action == row.next_action.upper()  # P16, via dashboard
    assert detail.next_command == row.next_command  # P16, via dashboard
    assert detail.recommended_agent == row.recommended_agent  # P19, via dashboard
    assert detail.agent_category == row.agent_category  # P19, via dashboard
    assert detail.priority == item.priority  # P21 ranking, via P22 inbox
    assert detail.focus_category == item.category  # P21 classification, via P22 inbox
    assert detail.focus_reason == item.reason  # P21 verified reason
    assert detail.founder_input == item.founder_input  # P21 founder-input guidance


# -- unknown project ----------------------------------------------------------


def test_unknown_project_raises(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    with pytest.raises(NotFoundError):
        build_inbox_detail(workspace, "does-not-exist")


def test_cli_unknown_project_nonzero_exit(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    code = main(["workspace", "inbox", "--workspace", str(workspace),
                 "--project", "does-not-exist"])

    assert code != int(ExitCode.OK)
    assert code == int(ExitCode.INVARIANT_ERROR)  # typed NotFoundError exit code


# -- blockers -----------------------------------------------------------------


def test_project_with_blockers(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Blk", "blk", tmp_path)
    make_blocked(workspace, "blk")

    detail = build_inbox_detail(workspace, "blk")

    assert detail.priority == 3
    assert detail.focus_category is FocusCategory.BLOCKED
    assert detail.blockers  # non-empty
    assert any("blocked assignment" in b for b in detail.blockers)


# -- integrity failure --------------------------------------------------------


def test_project_with_integrity_failure(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Broken", "broken", tmp_path)
    make_integrity_failure(repo)

    detail = build_inbox_detail(workspace, "broken")

    assert detail.integrity_ok is False
    assert detail.integrity.startswith("FAILURE")
    assert detail.priority == 1
    assert detail.focus_category is FocusCategory.INTEGRITY_FAILURE
    assert any("integrity" in b for b in detail.blockers)
    # Assignment metadata is not invented when the chain cannot be verified.
    assert detail.goal == "unavailable"
    assert detail.owner == "unavailable"


def test_cli_integrity_failure_exit_code(workspace: Path, tmp_path: Path) -> None:
    repo = started(workspace, "Broken", "broken", tmp_path)
    make_integrity_failure(repo)

    code = main(["workspace", "inbox", "--workspace", str(workspace), "--project", "broken"])

    assert code == int(ExitCode.INVARIANT_ERROR)


def test_cli_valid_detail_ok_exit(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    code = main(["workspace", "inbox", "--workspace", str(workspace), "--project", "alpha"])

    assert code == int(ExitCode.OK)


# -- determinism & read-only --------------------------------------------------


def test_text_output_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    first = render_inbox_detail(build_inbox_detail(workspace, "alpha"))
    second = render_inbox_detail(build_inbox_detail(workspace, "alpha"))

    assert first == second


def test_structured_output_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    first = build_inbox_detail(workspace, "alpha")
    second = build_inbox_detail(workspace, "alpha")

    assert first == second  # frozen dataclass — structural equality


def test_detail_changes_nothing_on_disk(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    make_blocked(workspace, "alpha")
    before = snapshot(workspace)

    build_inbox_detail(workspace, "alpha")

    assert snapshot(workspace) == before


def test_cli_detail_is_read_only(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    main(["workspace", "inbox", "--workspace", str(workspace), "--project", "alpha"])

    assert snapshot(workspace) == before


# -- regression: reused read-models unchanged ---------------------------------


def test_detail_only_aggregates_existing_read_models() -> None:
    import projectos.infrastructure.workspace_inbox_detail as mod

    source = inspect.getsource(mod)
    # It aggregates the canonical read-models…
    assert "build_dashboard(" in source
    assert "build_inbox(" in source
    assert "build_handoff(" in source
    # …and reimplements no ranking / classification / recommendation / lifecycle logic.
    for reimplemented in (
        "build_plan(", "build_agent_advice(", "build_status(", "build_queue(",
        "build_report(", "_rank(", "_RANK_CATEGORY", "verify_integrity(",
        "generate_next", "_transition", ".save(", "subprocess", "urllib",
        "anthropic", "openai",
    ):
        assert reimplemented not in source, f"detail must not reimplement {reimplemented}"


def test_list_inbox_output_contract_preserved(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)
    before = snapshot(workspace)

    # `workspace inbox` with no --project still lists (P22 contract unchanged).
    code = main(["workspace", "inbox", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)
    assert snapshot(workspace) == before


def test_p20_p21_p22_still_work(workspace: Path, tmp_path: Path) -> None:
    started(workspace, "Alpha", "alpha", tmp_path)

    dashboard = build_dashboard(workspace)
    focus = build_focus(workspace)
    inbox = build_inbox(workspace)

    assert dashboard.workspace_name == "Dogfood"
    assert focus.category in FocusCategory
    assert any(it.project_id == "alpha" for it in inbox.items)
