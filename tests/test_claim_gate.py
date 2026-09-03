"""Tests for the live claim gate.

The three paths the assignment names, plus the matching rules that make them
mean anything. These encode 2026-09-03: a headless wake read a staged snapshot,
missed a claim written three minutes earlier to the live folder, claimed the
same assignment, and moved it to DONE under a session still working on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.infrastructure.claim_gate import (
    EXIT_DECLINE,
    EXIT_NOTHING,
    EXIT_PROCEED,
    EXIT_UNAVAILABLE,
    Verdict,
    assignment_key,
    decide,
    live_claim_for,
    main,
    oldest_claimable,
)

ASSIGNMENT = "2026-09-03_1420_PROJECTOS_TWO-WRITERS-IMPLEMENTATION-ONLY.md"


@pytest.fixture
def reports(tmp_path: Path) -> Path:
    directory = tmp_path / "AGENT-REPORTS"
    (directory / "INBOX").mkdir(parents=True)
    (directory / "INBOX" / ASSIGNMENT).write_text("# assignment\n", encoding="utf-8")
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
