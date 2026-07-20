"""CLI tests, focused on the exit-code contract (spec section 13).

Agents branch on exit codes rather than on prose, so the codes are the interface
and are asserted directly:

    0  ok      1  rule failure      2  invariant/validation      3  escalation
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode
from tests.conftest import FOUNDER_ID, FOUNDER_NAME


def run(*argv: str) -> int:
    return main(list(argv))


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    code = run(
        "--repo", str(root),
        "init",
        "--project-id", "cli-test",
        "--name", "CLI Test",
        "--founder-id", FOUNDER_ID,
        "--founder-name", FOUNDER_NAME,
    )
    assert code == ExitCode.OK
    return root


def test_output_survives_a_legacy_console_codepage(tmp_path: Path) -> None:
    """Regression: the CLI must not die on a cp1252 console.

    pytest captures output as UTF-8, so this drives a real cp1252 stream instead —
    which is what a default Windows terminal gives us.
    """
    import io
    import sys

    root = tmp_path / "repo"
    root.mkdir()
    buffer = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    original = sys.stdout
    sys.stdout = buffer
    try:
        code = run(
            "--repo", str(root),
            "init",
            "--project-id", "codepage-test",
            "--name", "Codepage Test",
            "--founder-id", FOUNDER_ID,
            "--founder-name", FOUNDER_NAME,
        )
    finally:
        sys.stdout = original

    assert code == ExitCode.OK


def test_init_creates_a_valid_projectos_directory(project: Path) -> None:
    """v0.1 acceptance criterion 1."""
    layout = project / ".projectos"
    assert (layout / "manifest.yaml").is_file()
    assert (layout / "packs" / "software-core" / "pack.yaml").is_file()
    assert (layout / "assignments").is_dir()
    assert (layout / "audit").is_dir()


def test_init_refuses_to_overwrite_without_force(project: Path) -> None:
    code = run(
        "--repo", str(project),
        "init",
        "--project-id", "cli-test",
        "--name", "CLI Test",
        "--founder-id", FOUNDER_ID,
        "--founder-name", FOUNDER_NAME,
    )
    assert code == ExitCode.INVARIANT_ERROR


def test_status_reports_ok_on_a_clean_project(project: Path, capsys) -> None:
    code = run("--repo", str(project), "status")

    assert code == ExitCode.OK
    assert "CLI Test" in capsys.readouterr().out


def test_history_verify_passes_on_an_untouched_log(project: Path) -> None:
    assert run("--repo", str(project), "history", "--verify") == ExitCode.OK


def test_history_verify_fails_after_tampering(project: Path) -> None:
    """Acceptance criterion 8 — through the CLI this time."""
    run("--repo", str(project), "--identity", FOUNDER_ID, "next")

    log_file = next((project / ".projectos" / "audit").glob("*.ndjson"))
    lines = log_file.read_text(encoding="utf-8").splitlines()
    tampered = lines[0].replace(FOUNDER_ID, "impostor@example.test")
    assert tampered != lines[0], "the tamper must actually change the line"
    lines[0] = tampered
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert run("--repo", str(project), "history", "--verify") == ExitCode.ESCALATION_REQUIRED


def test_escalation_without_options_is_rejected(project: Path) -> None:
    """Spec 9.3 — no options, no escalation."""
    code = run(
        "--repo", str(project),
        "founder", "escalate",
        "--summary", "Just thinking out loud",
    )
    assert code == ExitCode.INVARIANT_ERROR


def test_valid_escalation_returns_the_escalation_exit_code(project: Path) -> None:
    code = run(
        "--repo", str(project),
        "--identity", FOUNDER_ID,
        "founder", "escalate",
        "--summary", "Which way should the project go?",
        "--option", "O1|Go left|Cheaper, slower.",
        "--option", "O2|Go right|Faster, costlier.",
        "--recommend", "O1",
    )
    assert code == ExitCode.ESCALATION_REQUIRED


def test_status_signals_an_open_founder_decision(project: Path) -> None:
    run(
        "--repo", str(project),
        "--identity", FOUNDER_ID,
        "founder", "escalate",
        "--summary", "A real decision",
        "--option", "O1|One|Consequence one.",
        "--option", "O2|Two|Consequence two.",
    )

    assert run("--repo", str(project), "status") == ExitCode.ESCALATION_REQUIRED


def test_founder_list_is_empty_on_a_fresh_project(project: Path) -> None:
    assert run("--repo", str(project), "founder", "list") == ExitCode.OK


def test_malformed_option_is_rejected(project: Path) -> None:
    code = run(
        "--repo", str(project),
        "--identity", FOUNDER_ID,
        "founder", "escalate",
        "--summary", "A decision",
        "--option", "O1|missing the consequence",
        "--option", "O2|Two|Consequence two.",
    )
    assert code == ExitCode.INVARIANT_ERROR


def test_block_requires_a_reason(project: Path) -> None:
    run("--repo", str(project), "next")
    code = run("--repo", str(project), "block")
    assert code == ExitCode.INVARIANT_ERROR


def test_unknown_assignment_id_is_an_invariant_error(project: Path) -> None:
    assert run("--repo", str(project), "verify", "A-9999") == ExitCode.INVARIANT_ERROR


def test_malformed_assignment_id_is_rejected(project: Path) -> None:
    assert run("--repo", str(project), "verify", "nonsense") == ExitCode.INVARIANT_ERROR


def test_next_then_verify_rejects_without_evidence(project: Path, capsys) -> None:
    """The full loop through the CLI: a claim with no matching evidence fails."""
    assert run("--repo", str(project), "next") == ExitCode.OK
    capsys.readouterr()

    code = run("--repo", str(project), "verify")

    assert code == ExitCode.RULE_FAILURE


def test_rejected_work_resumes_and_then_passes(project: Path, capsys) -> None:
    """The full reject-fix-retry loop, entirely through the CLI.

    The bundled design-spec template asks for docs/SPEC.md. Verifying without it
    rejects; creating it and resuming verifies.
    """
    assert run("--repo", str(project), "next") == ExitCode.OK
    assert run("--repo", str(project), "verify") == ExitCode.RULE_FAILURE

    spec = project / "docs" / "SPEC.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Specification\n", encoding="utf-8")

    # `next` resumes the rejected assignment and re-briefs the executor.
    assert run("--repo", str(project), "next") == ExitCode.OK
    assert "RESUMED AFTER REJECTION" in capsys.readouterr().out

    assert run("--repo", str(project), "verify") == ExitCode.OK


def test_closing_an_assignment_advances_the_pipeline(project: Path, capsys) -> None:
    """Acceptance criterion 6, through the CLI."""
    run("--repo", str(project), "next")
    spec = project / "docs" / "SPEC.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Specification\n", encoding="utf-8")
    run("--repo", str(project), "next")
    assert run("--repo", str(project), "verify") == ExitCode.OK

    assert run("--repo", str(project), "complete", "--role", "owner") == ExitCode.OK
    capsys.readouterr()

    assert run("--repo", str(project), "next") == ExitCode.OK
    output = capsys.readouterr().out
    assert "A-0002" in output
    assert "Implement the specified capability" in output
