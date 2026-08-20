"""Tests for the API runner's spend governor.

Every test here runs with no network, no keys and no money. That is the point:
the decision to spend is separated from the spending so it can be proven on a
laptop, and a governor nobody can test is a governor nobody tests.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from projectos.infrastructure.api_runner import (
    PER_DAY_CAP_USD,
    POOL_RESERVE_USD,
    SPEND_ORDER,
    Decision,
    choose_pool,
    decide,
    ledger_rows,
    phone_line,
    record,
    spent_today,
)


@pytest.fixture
def ledger(tmp_path):
    return tmp_path / "cost.jsonl"


@pytest.fixture
def no_brake(tmp_path):
    return tmp_path / "absent.OFF"


def _write(ledger: Path, rows: list[dict[str, str]]) -> None:
    ledger.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )


# --- the fixed order -------------------------------------------------------


def test_spend_order_is_openai_before_xai():
    # The ordering is a ruling, not a preference: $100 before $10 so the
    # fallback keeps a fallback. Guard it against a well-meaning re-sort.
    assert SPEND_ORDER == ("openai", "xai")


def test_openai_is_chosen_while_it_has_credit():
    remaining = {"openai": Decimal("100"), "xai": Decimal("10")}
    assert choose_pool(remaining) == "openai"


def test_falls_through_to_xai_only_when_openai_is_spent():
    remaining = {"openai": Decimal("0.50"), "xai": Decimal("10")}
    assert choose_pool(remaining) == "xai"


def test_reserve_means_a_pool_is_empty_before_it_reads_zero():
    # At exactly the reserve the pool is already unusable, so there is always
    # something left to diagnose with.
    remaining = {"openai": POOL_RESERVE_USD, "xai": POOL_RESERVE_USD}
    assert choose_pool(remaining) is None


# --- the reasons not to spend ---------------------------------------------


def test_kill_switch_blocks_an_otherwise_healthy_run(tmp_path, ledger):
    brake = tmp_path / "api-runner.OFF"
    brake.write_text("stop", encoding="utf-8")
    ruling = decide(item_id="ITEM-1", ledger=ledger, brake_path=brake)
    assert ruling.decision is Decision.BLOCKED_BRAKE
    assert not ruling.may_spend


def test_kill_switch_beats_every_other_consideration(tmp_path, ledger):
    # Ordering matters: the brake must not be reachable only after the
    # cheaper checks happen to pass.
    brake = tmp_path / "api-runner.OFF"
    brake.write_text("stop", encoding="utf-8")
    ruling = decide(
        item_id="ITEM-1",
        held_by="TRADEOS",
        already_reported=True,
        remaining={"openai": Decimal("0"), "xai": Decimal("0")},
        ledger=ledger,
        brake_path=brake,
    )
    assert ruling.decision is Decision.BLOCKED_BRAKE


def test_an_item_a_chat_seat_holds_is_skipped_not_spent(ledger, no_brake):
    ruling = decide(
        item_id="ITEM-1", held_by="TRADEOS", ledger=ledger, brake_path=no_brake
    )
    assert ruling.decision is Decision.SKIP_HELD
    assert not ruling.may_spend
    assert "TRADEOS" in ruling.reason


def test_an_already_reported_item_is_skipped(ledger, no_brake):
    ruling = decide(
        item_id="ITEM-1", already_reported=True, ledger=ledger, brake_path=no_brake
    )
    assert ruling.decision is Decision.SKIP_DONE


def test_day_cap_blocks_further_spending(ledger, no_brake):
    from projectos.infrastructure.fleet_clock import now_ist

    today = now_ist().strftime("%Y-%m-%d")
    _write(ledger, [{"day": today, "usd": str(PER_DAY_CAP_USD)}])
    ruling = decide(item_id="ITEM-1", ledger=ledger, brake_path=no_brake)
    assert ruling.decision is Decision.BLOCKED_DAY_CAP


def test_exhausted_pools_block(ledger, no_brake):
    ruling = decide(
        item_id="ITEM-1",
        remaining={"openai": Decimal("0"), "xai": Decimal("0")},
        ledger=ledger,
        brake_path=no_brake,
    )
    assert ruling.decision is Decision.BLOCKED_NO_POOL


def test_an_unheld_item_under_cap_may_spend_from_openai(ledger, no_brake):
    ruling = decide(item_id="ITEM-1", ledger=ledger, brake_path=no_brake)
    assert ruling.decision is Decision.SPEND
    assert ruling.pool == "openai"
    assert ruling.may_spend


# --- the ledger ------------------------------------------------------------


def test_spent_today_counts_only_today(ledger):
    from projectos.infrastructure.fleet_clock import now_ist

    today = now_ist().strftime("%Y-%m-%d")
    _write(
        ledger,
        [
            {"day": "2020-01-01", "usd": "99.00"},
            {"day": today, "usd": "0.25"},
            {"day": today, "usd": "0.25"},
        ],
    )
    assert spent_today(ledger) == Decimal("0.50")


def test_a_corrupt_line_does_not_zero_the_day_and_reopen_the_cap(ledger):
    # The dangerous failure is not a crash, it is a silently reset counter:
    # that turns a cap into a suggestion. The good rows must still count.
    from projectos.infrastructure.fleet_clock import now_ist

    today = now_ist().strftime("%Y-%m-%d")
    ledger.write_text(
        json.dumps({"day": today, "usd": "1.00"})
        + "\n{ this is not json\n"
        + json.dumps({"day": today, "usd": "1.50"})
        + "\n",
        encoding="utf-8",
    )
    assert spent_today(ledger) == Decimal("2.50")


def test_a_missing_ledger_is_zero_not_an_error(tmp_path):
    assert spent_today(tmp_path / "never-written.jsonl") == Decimal("0")


def test_skips_are_recorded_too(ledger):
    # A ledger holding only paid runs cannot distinguish "nothing needed
    # doing" from "the runner was broken all day".
    record(
        item_id="ITEM-1",
        pool=None,
        usd=Decimal("0"),
        decision=Decision.SKIP_HELD,
        ledger=ledger,
    )
    rows = list(ledger_rows(ledger))
    assert len(rows) == 1
    assert rows[0]["decision"] == "SKIP_HELD"
    assert rows[0]["usd"] == "0"


def test_recorded_spend_counts_against_the_day_cap(ledger):
    record(
        item_id="ITEM-1",
        pool="openai",
        usd=Decimal("0.40"),
        decision=Decision.SPEND,
        ledger=ledger,
    )
    assert spent_today(ledger) == Decimal("0.40")


def test_ledger_is_append_only_across_calls(ledger):
    for i in range(3):
        record(
            item_id=f"ITEM-{i}",
            pool="openai",
            usd=Decimal("0.10"),
            decision=Decision.SPEND,
            ledger=ledger,
        )
    assert len(list(ledger_rows(ledger))) == 3
    assert spent_today(ledger) == Decimal("0.30")


def test_phone_line_names_todays_spend_and_the_cap(ledger):
    record(
        item_id="ITEM-1",
        pool="openai",
        usd=Decimal("1.00"),
        decision=Decision.SPEND,
        ledger=ledger,
    )
    line = phone_line(ledger)
    assert "1.00" in line
    assert str(PER_DAY_CAP_USD) in line
    assert "%" in line


def test_a_zero_spend_day_reads_as_healthy_not_broken(ledger):
    # "A day where the runner spends nothing and nothing stalled is the runner
    # working perfectly" - so the phone line must not be alarming.
    assert "0 of" in phone_line(ledger)
