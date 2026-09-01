"""Tests for the fleet board.

The board's only job is to be true. A board that is merely present, or that
quietly reports "never" for a seat that has been running, is worse than no
board - it turns a black box into a black box the founder trusts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from projectos.infrastructure.fleet_board import (
    BOARD_FILENAME,
    backoff_state,
    claimable_for,
    render_board,
    seat_repos,
    todays_counts,
    write_board,
)


def _catalogue(tmp_path: Path, tasks: list[dict[str, str]]) -> Path:
    path = tmp_path / "fleet_tasks.json"
    path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    return path


def _task(name: str, args: str) -> dict[str, str]:
    return {
        "name": name,
        "execute": "wscript.exe",
        "arguments": args,
        "user": "rmani",
        "logon": "Interactive",
        "runlevel": "Limited",
        "start": "2026-09-01T09:00:00",
        "interval": "PT3H",
        "duration": "PT10H",
    }


@pytest.fixture
def reports(tmp_path: Path) -> Path:
    directory = tmp_path / "AGENT-REPORTS"
    (directory / "INBOX").mkdir(parents=True)
    return directory


@pytest.fixture
def state(tmp_path: Path) -> Path:
    directory = tmp_path / "state"
    directory.mkdir()
    return directory


# --- who the seats are ------------------------------------------------------


def test_the_seat_name_comes_from_the_task_arguments_not_the_task_name(
    tmp_path: Path,
) -> None:
    # The restocker's task is WAKE-CHAT-RESTOCK but its seat is
    # CHAT-AUTO-RESTOCK. Deriving the name by stripping WAKE- found no log and
    # the first board reported "never" for a seat that had been running.
    catalogue = _catalogue(
        tmp_path,
        [
            _task(
                "WAKE-CHAT-RESTOCK",
                "-File C:\\ProjectOS-AI\\scripts\\wake.ps1 -Seat CHAT-AUTO-RESTOCK",
            )
        ],
    )
    assert "CHAT-AUTO-RESTOCK" in seat_repos(catalogue)
    assert "CHAT-RESTOCK" not in seat_repos(catalogue)


def test_the_repo_is_recovered_when_a_task_omits_reporoot(tmp_path: Path) -> None:
    # PROJECTOS's task relies on the wrapper's default instead of passing
    # -RepoRoot, and the first board printed "-" for it.
    catalogue = _catalogue(
        tmp_path,
        [_task("WAKE-PROJECTOS", "-File C:\\ProjectOS-AI\\scripts\\wake.ps1 -Seat PROJECTOS")],
    )
    assert seat_repos(catalogue)["PROJECTOS"].endswith("ProjectOS-AI")


def test_a_quoted_reporoot_with_spaces_survives(tmp_path: Path) -> None:
    catalogue = _catalogue(
        tmp_path,
        [_task("WAKE-LEOS", '-Seat LEOS -RepoRoot "C:\\Urjadata Case - X\\LEOS"')],
    )
    assert seat_repos(catalogue)["LEOS"] == "C:\\Urjadata Case - X\\LEOS"


def test_non_seat_tasks_are_not_seats(tmp_path: Path) -> None:
    catalogue = _catalogue(
        tmp_path,
        [_task("AUTO-SIGN", "-Seat NOBODY"), _task("WAKE-WEB", "-Seat WEB")],
    )
    assert list(seat_repos(catalogue)) == ["WEB"]


# --- what each seat is doing ------------------------------------------------


def test_a_seat_with_a_tagged_file_shows_that_assignment(reports: Path) -> None:
    (reports / "INBOX" / "2026-09-01_1429_WEB_DO-THE-THING.md").write_text("x", encoding="utf-8")
    assert claimable_for("WEB", reports / "INBOX").endswith("DO-THE-THING.md")


def test_a_seat_with_nothing_is_idle(reports: Path) -> None:
    (reports / "INBOX" / "2026-09-01_1429_WEB_DO-THE-THING.md").write_text("x", encoding="utf-8")
    assert claimable_for("TRADEOS", reports / "INBOX") == "idle"


def test_an_all_tagged_file_counts_for_every_seat(reports: Path) -> None:
    (reports / "INBOX" / "2026-09-01_0800_ALL_STANDING-RULE.md").write_text("x", encoding="utf-8")
    assert claimable_for("TRADEOS", reports / "INBOX").endswith("STANDING-RULE.md")


@pytest.mark.parametrize("prefix", ["DONE-", "PARKED-", "SUPERSEDED-", "RPT-"])
def test_a_consumed_file_is_not_work(prefix: str, reports: Path) -> None:
    (reports / "INBOX" / f"{prefix}2026-09-01_1429_WEB_DONE-ALREADY.md").write_text(
        "x", encoding="utf-8"
    )
    assert claimable_for("WEB", reports / "INBOX") == "idle"


def test_the_board_uses_the_same_rule_the_wrapper_skips_on() -> None:
    # If these two ever disagree the board will show work for a seat whose
    # wake refuses to start, which is exactly the confusion it exists to end.
    wake = (Path(__file__).resolve().parents[1] / "scripts" / "wake.ps1").read_text(
        encoding="utf-8-sig"
    )
    assert "DONE-|PARKED-|SUPERSEDED-|RPT-" in wake
    assert "-eq 'ALL'" in wake


# --- how it went ------------------------------------------------------------


def test_consecutive_failures_and_the_block_reason_are_reported(state: Path) -> None:
    (state / "wake-WEB.backoff.json").write_text(
        json.dumps(
            {
                "consecutive": 3,
                "last_class": "engine-exit-1",
                "next_eligible": "2026-09-01T20:36:00+05:30",
            }
        ),
        encoding="utf-8",
    )
    count, blocked = backoff_state(state, "WEB")
    assert count == 3
    assert "engine-exit-1" in blocked


def test_a_clean_seat_reports_no_block(state: Path) -> None:
    assert backoff_state(state, "TRADEOS") == (0, "")


def test_an_unreadable_backoff_file_says_so_rather_than_reading_as_healthy(
    state: Path,
) -> None:
    (state / "wake-WEB.backoff.json").write_text("{ not json", encoding="utf-8")
    _, blocked = backoff_state(state, "WEB")
    assert "unreadable" in blocked


# --- what today cost --------------------------------------------------------


def test_skips_are_counted_and_are_not_engine_sessions(
    reports: Path, state: Path
) -> None:
    # The saving IS the gap between these two numbers, so the board has to
    # measure them from different sources: the log for wakes, the usage file
    # for sessions the wrapper actually started.
    (state / "wake-WEB.log").write_text(
        "2026-09-01 09:00:00 [WEB] SKIP-EMPTY: nothing tagged WEB or ALL\n"
        "2026-09-01 12:00:00 [WEB] SKIP-EMPTY: nothing tagged WEB or ALL\n"
        "2026-09-01 15:00:00 [WEB] OK: wake completed (engine=codex)\n",
        encoding="utf-8",
    )
    (reports / "FLEET-USAGE.md").write_text(
        "2026-09-01 | WEB | engine=codex | session #1 today\n", encoding="utf-8"
    )
    wakes, sessions, skips = todays_counts(
        reports, state, ["WEB"], today="2026-09-01"
    )
    assert (wakes, sessions, skips) == (3, 1, 2)


def test_yesterdays_lines_do_not_count_as_today(reports: Path, state: Path) -> None:
    (state / "wake-WEB.log").write_text(
        "2026-08-31 09:00:00 [WEB] OK: wake completed (engine=codex)\n", encoding="utf-8"
    )
    assert todays_counts(reports, state, ["WEB"], today="2026-09-01")[0] == 0


# --- the board itself -------------------------------------------------------


def test_the_board_reflects_real_state_after_a_wake(
    tmp_path: Path, reports: Path, state: Path
) -> None:
    catalogue = _catalogue(
        tmp_path,
        [
            _task("WAKE-WEB", "-Seat WEB -RepoRoot C:\\web"),
            _task("WAKE-TRADEOS", "-Seat TRADEOS -RepoRoot C:\\tos"),
        ],
    )
    (reports / "INBOX" / "2026-09-01_1429_WEB_DO-THE-THING.md").write_text("x", encoding="utf-8")
    (state / "wake-WEB.log").write_text(
        "2026-09-01 14:45:50 [WEB] OK: wake completed (engine=codex)\n", encoding="utf-8"
    )
    (state / "wake-TRADEOS.backoff.json").write_text(
        json.dumps(
            {"consecutive": 2, "last_class": "engine-exit-1", "next_eligible": "2026-09-01T18:00"}
        ),
        encoding="utf-8",
    )

    board = render_board(reports, state, catalogue)
    assert "DO-THE-THING.md" in board  # WEB's real assignment
    assert "| TRADEOS | C:\\tos | idle |" in board  # TRADEOS genuinely idle
    assert "2026-09-01 14:45" in board  # WEB's real last wake
    assert "engine-exit-1" in board  # TRADEOS's real block
    assert "2 seats" in board


def test_the_board_is_rewritten_in_place_not_appended(
    tmp_path: Path, reports: Path, state: Path
) -> None:
    # It exists to replace noise, so it must never become noise itself.
    catalogue = _catalogue(tmp_path, [_task("WAKE-WEB", "-Seat WEB -RepoRoot C:\\web")])
    write_board(reports, state, catalogue)
    first = (reports / BOARD_FILENAME).read_text(encoding="utf-8")
    write_board(reports, state, catalogue)
    second = (reports / BOARD_FILENAME).read_text(encoding="utf-8")
    assert second.count("# FLEET BOARD") == 1
    assert len(second) < len(first) * 2


def test_the_board_survives_a_missing_catalogue(
    tmp_path: Path, reports: Path, state: Path
) -> None:
    board = render_board(reports, state, tmp_path / "absent.json")
    assert "FLEET BOARD" in board  # renders empty rather than raising
