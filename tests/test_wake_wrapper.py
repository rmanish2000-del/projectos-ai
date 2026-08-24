"""Tests for the wake wrapper's failure paths.

The wrapper is PowerShell, so the fast failure paths are exercised end-to-end
by actually running it (they return before any engine is invoked), and the
paths that need a live engine are asserted structurally. Which is which is
stated on every test, because a structural assertion is weaker evidence and
saying so is the difference between a test suite and a comfort blanket.

The runs these encode, all on 2026-08-24:
  * WARRANT: engine exited 0 having declared STATUS: FAILED -> wrapper logged
    "OK: wake completed". A false success.
  * WEB: no wake-prompt.md, because it was committed to a feature branch the
    seat had since left.
  * WARRANT: the orphan sweep killed two unrelated python processes.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WAKE = REPO_ROOT / "scripts" / "wake.ps1"

pytestmark = pytest.mark.skipif(
    shutil.which("powershell") is None, reason="PowerShell not available"
)


def _fresh_seat(tmp_path: Path) -> str:
    """A seat name no previous run has used.

    The wrapper keeps per-seat backoff state, so a seat that has just failed
    is skipped (exit 0) for the next 20 minutes. That is correct in
    production and fatal to an idempotent test: the second run of the same
    test would assert against a skip rather than the path under test.
    """
    return "TEST" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper()


def _state_files(seat: str) -> list[Path]:
    state = Path.home() / ".projectos"
    return list(state.glob(f"wake-{seat}.*"))


def _run_wake(
    tmp_path: Path,
    *extra: str,
    seat: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    seat = seat or _fresh_seat(tmp_path)
    reports = tmp_path / "reports"
    reports.mkdir(exist_ok=True)
    return subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(WAKE),
            "-RepoRoot", str(tmp_path),
            "-Seat", seat,
            "-ReportsDir", str(reports),
            *extra,
        ],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )


def _path_without_engines() -> dict[str, str]:
    """An environment where no engine CLI can be found.

    `-Engine` is a ValidateSet, so an unknown NAME is rejected by PowerShell
    before the script runs. The real unreachable-engine case is a valid engine
    whose CLI is absent, which is what a rate-limited or uninstalled engine
    looks like from the wrapper's side.
    """
    env = dict(os.environ)
    env["PATH"] = str(Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32")
    env["USERPROFILE"] = os.environ.get("USERPROFILE", "")
    return env


def _failure_text(tmp_path: Path) -> str:
    files = list((tmp_path / "reports").glob("*WAKE-FAILURE*"))
    return files[0].read_text(encoding="utf-8", errors="replace") if files else ""


# --- prompt resolution (end-to-end) ----------------------------------------


def test_a_missing_prompt_with_no_fallback_fails_loudly(tmp_path: Path) -> None:
    # END-TO-END. Returns before any engine runs.
    result = _run_wake(tmp_path)
    assert result.returncode == 2
    text = _failure_text(tmp_path)
    assert "wake-prompt.md missing" in text
    assert "feature branch" in text  # names the cause, not just the symptom


def test_a_prompt_in_the_repo_is_preferred_over_the_fallback() -> None:
    # STRUCTURAL. The repo copy may carry seat-specific boundaries (LEOS
    # confidentiality, EDUOS sample-data only) that the generic fallback does
    # not, so the fallback must never win when a repo copy exists.
    source = WAKE.read_text(encoding="utf-8-sig")
    repo_line = source.index("$prompt = Join-Path $RepoRoot $PromptFile")
    fallback_line = source.index("$fallback = Join-Path $StateDir")
    assert repo_line < fallback_line


def test_the_fallback_is_branch_independent() -> None:
    # STRUCTURAL. The whole point: a prompt under the state directory cannot
    # vanish because the seat checked out a different branch.
    source = WAKE.read_text(encoding="utf-8-sig")
    assert '$fallback = Join-Path $StateDir "prompts\\$Seat-wake-prompt.md"' in source


# --- engine availability (end-to-end) --------------------------------------


def test_an_engine_not_on_path_fails_before_doing_anything(tmp_path: Path) -> None:
    # END-TO-END. "If a wake cannot reach any engine, it must say so in one
    # line and stop - not print OK."
    (tmp_path / "wake-prompt.md").write_text("do nothing", encoding="utf-8")
    result = _run_wake(tmp_path, "-Engine", "grok", env=_path_without_engines())
    assert result.returncode == 2
    assert "not on PATH" in _failure_text(tmp_path)


def test_the_engine_cannot_be_reached_path_never_reports_ok(tmp_path: Path) -> None:
    # END-TO-END. The acceptance criterion is about the WORD OK, so assert on
    # it directly rather than on the exit code alone.
    (tmp_path / "wake-prompt.md").write_text("do nothing", encoding="utf-8")
    result = _run_wake(tmp_path, "-Engine", "grok", env=_path_without_engines())
    assert "OK: wake completed" not in (result.stdout + result.stderr)


# --- no false success (structural; proven live on 2026-08-24) --------------


def test_the_wrapper_refuses_to_call_a_workless_run_ok() -> None:
    # STRUCTURAL, but the live proof is recorded: before this guard a WARRANT
    # wake logged "OK: wake completed" while the engine had declared
    # STATUS: FAILED and written nothing.
    source = WAKE.read_text(encoding="utf-8-sig")
    for guard in (
        "engine-exec-helper-rejected",
        "engine-declared-failure",
        "no-evidence-of-work",
    ):
        assert guard in source, f"missing no-false-success guard: {guard}"


def test_failure_signatures_are_matched_on_both_streams() -> None:
    # STRUCTURAL. Codex puts its exec-helper rejection on stderr and its own
    # STATUS line on stdout; reading one stream picks the wrong class.
    source = WAKE.read_text(encoding="utf-8-sig")
    assert "foreach ($f in @($TranscriptFile, $StderrFile))" in source
    assert "$engineSaid -match" in source


def test_every_failure_carries_the_exit_code_and_a_tail() -> None:
    # STRUCTURAL. "A one-line symptom is what turned a ten-minute fix into
    # two days."
    source = WAKE.read_text(encoding="utf-8-sig")
    assert "function Get-EngineTail" in source
    assert "transcript tail:" in source
    assert "stderr tail:" in source


def test_stdout_is_captured_not_only_stderr() -> None:
    # STRUCTURAL. The diagnosis lived on stdout and was being discarded.
    source = WAKE.read_text(encoding="utf-8-sig")
    assert "1>$TranscriptFile 2>$StderrFile" in source


def test_the_engine_call_does_not_pipe_native_stderr() -> None:
    # PowerShell 5.1 wraps a native command's stderr in NativeCommandError
    # records; consuming them in a pipeline under ErrorActionPreference=Stop
    # terminated the wrapper before it could log anything. Redirect, never pipe.
    source = WAKE.read_text(encoding="utf-8-sig")
    assert "Tee-Object -FilePath $TranscriptFile" not in source
    assert '$ErrorActionPreference = "Continue"' in source


# --- orphan cleanup (structural; bystander survival proven live) -----------


def test_orphan_cleanup_is_scoped_to_this_wakes_descendants() -> None:
    # STRUCTURAL. Proven live: a bystander python process survived a wake that
    # would previously have killed it. Killing a bystander is worse than the
    # orphan being cleaned up.
    source = WAKE.read_text(encoding="utf-8-sig")
    assert "function Get-DescendantIds" in source
    assert "$descendants = Get-DescendantIds -RootId $PID" in source


def test_orphan_cleanup_no_longer_scans_every_process_on_the_machine() -> None:
    source = WAKE.read_text(encoding="utf-8-sig")
    assert "Get-Process python*, py*, pytest*" not in source
