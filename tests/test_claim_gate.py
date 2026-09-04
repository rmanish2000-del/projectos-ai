"""Tests for the live claim gate.

The three paths the assignment names, plus the matching rules that make them
mean anything. These encode 2026-09-03: a headless wake read a staged snapshot,
missed a claim written three minutes earlier to the live folder, claimed the
same assignment, and moved it to DONE under a session still working on it.
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from projectos.infrastructure.claim_gate import (
    AUTH_PREFIX,
    DEFAULT_GRACE_SECONDS,
    EXIT_DECLINE,
    EXIT_NOTHING,
    EXIT_PROCEED,
    EXIT_UNAVAILABLE,
    EXIT_WAIT,
    Verdict,
    age_seconds,
    assignment_key,
    decide,
    is_stamped,
    live_claim_for,
    main,
    oldest_claimable,
)


def _set_age(path: Path, seconds: float) -> None:
    then = time.time() - seconds
    os.utime(path, (then, then))

ASSIGNMENT = "2026-09-03_1420_PROJECTOS_TWO-WRITERS-IMPLEMENTATION-ONLY.md"


@pytest.fixture
def reports(tmp_path: Path) -> Path:
    directory = tmp_path / "AGENT-REPORTS"
    (directory / "INBOX").mkdir(parents=True)
    target = directory / "INBOX" / ASSIGNMENT
    target.write_text("# assignment" + chr(10), encoding="utf-8")
    # Aged past the grace window on purpose. Since 2026-09-05 an unsigned file
    # written this instant is (correctly) "young: wait for the signer"; these
    # tests are about live claims, so their file must be old enough to be
    # claimable at all.
    _set_age(target, 600)
    return directory


# --- the three required paths -----------------------------------------------


def test_claim_present_means_a_second_session_declines(reports: Path) -> None:
    # THE defect. Another session's claim is on the live folder; this one
    # must yield rather than write a second claim on the same artefact.
    (reports / "2026-09-03_1551_PROJECTOS_CLAIM_TWO-WRITERS-IMPLEMENTATION-ONLY.md").write_text(
        "claimed_by: PROJECTOS\n", encoding="utf-8"
    )
    decision = decide("PROJECTOS", reports)
    assert decision.verdict is Verdict.DECLINE
    assert not decision.may_claim
    assert decision.claim is not None
    assert "1551" in decision.claim  # names WHO got there first


def test_live_read_failure_means_no_claim_with_a_stated_reason(tmp_path: Path) -> None:
    # A wake that cannot see current claims must not take work. Yielding
    # costs one idle cycle; claiming on stale evidence costs two writers.
    decision = decide("PROJECTOS", tmp_path / "not-mounted")
    assert decision.verdict is Verdict.UNAVAILABLE
    assert not decision.may_claim
    assert "not claiming" in decision.reason


def test_no_claim_means_the_normal_claim_proceeds(reports: Path) -> None:
    decision = decide("PROJECTOS", reports)
    assert decision.verdict is Verdict.PROCEED
    assert decision.may_claim
    assert decision.assignment == ASSIGNMENT


# --- matching: what counts as "a claim on this assignment" -------------------


def test_the_key_is_everything_after_the_tag() -> None:
    assert assignment_key(ASSIGNMENT, "PROJECTOS") == "TWO-WRITERS-IMPLEMENTATION-ONLY"


def test_a_file_tagged_for_another_seat_has_no_key_for_this_one() -> None:
    assert assignment_key(ASSIGNMENT, "WEB") is None


def test_an_all_tagged_file_keys_for_every_seat() -> None:
    assert assignment_key("2026-09-01_0800_ALL_STANDING-RULE.md", "WEB") == "STANDING-RULE"


def test_a_claim_on_the_superseded_version_does_not_block_the_new_one(
    reports: Path,
) -> None:
    # Real case: the earlier TWO-WRITERS-ONE-SEAT was claimed twice and blocked
    # twice. Those claims are on a different assignment and must not make the
    # IMPLEMENTATION-ONLY successor look taken.
    (reports / "2026-09-03_1330_PROJECTOS_CLAIM_TWO-WRITERS-ONE-SEAT.md").write_text(
        "x", encoding="utf-8"
    )
    assert decide("PROJECTOS", reports).verdict is Verdict.PROCEED


def test_another_seats_claim_does_not_block_this_seat(reports: Path) -> None:
    (reports / "2026-09-03_1500_WEB_CLAIM_TWO-WRITERS-IMPLEMENTATION-ONLY.md").write_text(
        "x", encoding="utf-8"
    )
    assert decide("PROJECTOS", reports).verdict is Verdict.PROCEED


def test_our_own_claim_is_not_evidence_someone_else_got_there_first(
    reports: Path,
) -> None:
    # At publish time the claim we are about to write is already in OUT and
    # may already be on Drive from a moment ago; ignoring it is what lets the
    # publish-time re-check distinguish "us" from "them".
    mine = "2026-09-03_1551_PROJECTOS_CLAIM_TWO-WRITERS-IMPLEMENTATION-ONLY.md"
    (reports / mine).write_text("x", encoding="utf-8")
    assert decide("PROJECTOS", reports, own_claims=frozenset({mine})).verdict is Verdict.PROCEED


def test_the_newest_of_several_claims_is_the_one_named() -> None:
    names = [
        "2026-09-03_1000_PROJECTOS_CLAIM_X.md",
        "2026-09-03_1551_PROJECTOS_CLAIM_X.md",
        "2026-09-03_1200_PROJECTOS_CLAIM_X.md",
    ]
    assert live_claim_for("PROJECTOS", "X", names) == "2026-09-03_1551_PROJECTOS_CLAIM_X.md"


# --- the claimable rule is the shared one ----------------------------------


def test_oldest_claimable_ignores_consumed_prefixes(reports: Path) -> None:
    (reports / "INBOX" / "DONE-2026-09-01_0900_PROJECTOS_OLD.md").write_text("x", encoding="utf-8")
    assert oldest_claimable("PROJECTOS", reports / "INBOX") == ASSIGNMENT


def test_nothing_tagged_is_reported_as_nothing_not_as_proceed(tmp_path: Path) -> None:
    reports = tmp_path / "AGENT-REPORTS"
    (reports / "INBOX").mkdir(parents=True)
    assert decide("PROJECTOS", reports).verdict is Verdict.NOTHING


def test_the_gate_uses_the_same_rule_as_the_wrapper_and_the_board() -> None:
    # Three places decide what is claimable; if they drift the board shows
    # work a wake will not start, or the gate blocks work the board says is
    # free. Pin the shared vocabulary.
    from projectos.infrastructure import claim_gate, fleet_board

    assert claim_gate.RETIRED_PREFIXES == fleet_board.RETIRED_PREFIXES


# --- the CLI the wrapper actually calls -------------------------------------


def test_exit_codes_are_distinct_and_documented(
    reports: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(reports), "PROJECTOS"]) == EXIT_PROCEED
    (reports / "2026-09-03_1551_PROJECTOS_CLAIM_TWO-WRITERS-IMPLEMENTATION-ONLY.md").write_text(
        "x", encoding="utf-8"
    )
    assert main([str(reports), "PROJECTOS"]) == EXIT_DECLINE
    assert main([str(tmp_path / "absent"), "PROJECTOS"]) == EXIT_UNAVAILABLE
    assert main([str(reports), "WEB"]) == EXIT_NOTHING
    out = capsys.readouterr().out
    assert "DECLINE" in out
    assert "UNAVAILABLE" in out


def test_own_claims_can_be_passed_on_the_command_line(reports: Path) -> None:
    mine = "2026-09-03_1551_PROJECTOS_CLAIM_TWO-WRITERS-IMPLEMENTATION-ONLY.md"
    (reports / mine).write_text("x", encoding="utf-8")
    assert main([str(reports), "PROJECTOS", "--own", mine]) == EXIT_PROCEED


# --- the unstamped trap: a grace window before any refusal ------------------

UNSIGNED = "2026-09-05_0015_PROJECTOS_FIX-THE-UNSTAMPED-TRAP.md"


@pytest.fixture
def young_unsigned(tmp_path: Path) -> Path:
    reports = tmp_path / "AGENT-REPORTS"
    (reports / "INBOX").mkdir(parents=True)
    target = reports / "INBOX" / UNSIGNED
    target.write_text("# assignment, no stamp yet" + chr(10), encoding="utf-8")
    _set_age(target, 20)
    return reports


def test_young_unsigned_means_wait_and_touch_nothing(young_unsigned: Path) -> None:
    # THE fix. The signer has not had its chances yet; the seat waits.
    target = young_unsigned / "INBOX" / UNSIGNED
    before = (target.name, target.read_bytes(), target.stat().st_mtime)
    decision = decide("PROJECTOS", young_unsigned, grace_seconds=180)
    assert decision.verdict is Verdict.WAIT_FOR_STAMP
    assert not decision.may_claim
    assert "waiting for the signer" in decision.reason
    assert (target.name, target.read_bytes(), target.stat().st_mtime) == before  # untouched


def test_old_unsigned_proceeds_so_the_engine_can_refuse_it(young_unsigned: Path) -> None:
    # By now the signer has demonstrably had several passes. The refusal
    # behaviour is unchanged - the gate merely stops standing in its way.
    _set_age(young_unsigned / "INBOX" / UNSIGNED, 600)
    assert decide("PROJECTOS", young_unsigned, grace_seconds=180).verdict is Verdict.PROCEED


def test_a_signed_file_never_waits(young_unsigned: Path) -> None:
    target = young_unsigned / "INBOX" / UNSIGNED
    target.write_text(
        "# assignment" + chr(10) + AUTH_PREFIX + "k1:" + "0" * 64 + chr(10),
        encoding="utf-8",
    )
    _set_age(target, 5)
    assert decide("PROJECTOS", young_unsigned).verdict is Verdict.PROCEED


def test_the_window_is_the_callers_not_a_hardcoded_guess(young_unsigned: Path) -> None:
    # 20s old: inside a 60s window, outside a 10s one.
    assert decide("PROJECTOS", young_unsigned, grace_seconds=60).verdict is Verdict.WAIT_FOR_STAMP
    assert decide("PROJECTOS", young_unsigned, grace_seconds=10).verdict is Verdict.PROCEED
    assert DEFAULT_GRACE_SECONDS == 180  # three signer intervals at today's PT1M


def test_clock_skew_reads_as_young_which_is_the_safe_direction(young_unsigned: Path) -> None:
    # 2026-09-04: Chat's clock ran 58 minutes ahead of the file's mtime. A
    # file that appears to come from the future must wait, not be refused.
    target = young_unsigned / "INBOX" / UNSIGNED
    future = datetime.now(UTC) - timedelta(minutes=58)  # "now" behind the write
    assert age_seconds(target, now=future) < 0
    assert decide("PROJECTOS", young_unsigned, now=future).verdict is Verdict.WAIT_FOR_STAMP


def test_age_comes_from_mtime_not_the_name(young_unsigned: Path) -> None:
    # The name says 00:15 on 09-05; the mtime is what the seat's machine saw.
    target = young_unsigned / "INBOX" / UNSIGNED
    _set_age(target, 3600)
    assert age_seconds(target) > 3000


def test_is_stamped_looks_only_for_the_stamp_line(tmp_path: Path) -> None:
    f = tmp_path / "x.md"
    f.write_text("body" + chr(10), encoding="utf-8")
    assert not is_stamped(f)
    f.write_text("body" + chr(10) + AUTH_PREFIX + "k1:abc" + chr(10), encoding="utf-8")
    assert is_stamped(f)
    assert not is_stamped(tmp_path / "absent.md")


def test_the_wait_verdict_comes_before_the_live_claim_check(young_unsigned: Path) -> None:
    # A young unsigned file at the head of the queue means WAIT even when a
    # claim on it exists - the claim check only matters once it is claimable.
    (young_unsigned / "2026-09-04_2320_PROJECTOS_CLAIM_FIX-THE-UNSTAMPED-TRAP.md").write_text(
        "x", encoding="utf-8"
    )
    assert decide("PROJECTOS", young_unsigned).verdict is Verdict.WAIT_FOR_STAMP


def test_grace_is_a_cli_flag_with_its_own_exit_code(young_unsigned: Path) -> None:
    assert main([str(young_unsigned), "PROJECTOS", "--grace", "180"]) == EXIT_WAIT
    assert main([str(young_unsigned), "PROJECTOS", "--grace", "5"]) == EXIT_PROCEED
    assert main([str(young_unsigned), "PROJECTOS", "--grace", "nope"]) == EXIT_UNAVAILABLE
