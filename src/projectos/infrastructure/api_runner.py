"""Spend governor for the droplet API seat runner (P0d).

The runner exists because every desktop subscription is exhausted while the
droplet holds separately funded API credit: OpenAI $100, xAI $10, auto-reload
deliberately OFF so a runaway stops at the balance instead of billing onward.

This module is the part that must be right BEFORE money moves. It answers one
question — may this run spend, and from which pool — and it answers it the same
way every time, in a form that can be tested on a laptop with no network and no
keys. The transport (which HTTP endpoint, which model) is deliberately not here:
a governor that cannot be tested without spending money is a governor nobody
tests.

Design rulings encoded here, all from the P0d assignment:

* Spend order is FIXED, OpenAI before xAI. $100 against $10 - burning the small
  pool first leaves no fallback for the fallback.
* Spending is a LAST RESORT. If a chat seat holds the item, is likely to take
  it, or has already reported on it, the runner does not spend. The skip is
  LOGGED, because a silent skip and a silent failure look identical.
* A day where the runner spends nothing and nothing stalled is the runner
  working perfectly. Nothing in here treats a zero-spend day as a fault.
* Cost is logged per run as a proxy, readable from a phone. Claude's limit ran
  out mid-day on 2026-08-19 with no warning; invisible cost is how that happens.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from projectos.infrastructure.fleet_clock import now_ist

# ---------------------------------------------------------------------------
# Pools and order
# ---------------------------------------------------------------------------

#: Fixed spend order. Not configurable, and not sorted by anything at runtime:
#: the ordering IS the ruling. Draining the $10 pool first would leave the
#: fallback with no fallback.
SPEND_ORDER: tuple[str, ...] = ("openai", "xai")

#: Funded balances at the time of writing, in USD. These are a starting point
#: for the ledger, not a live reading - the authority is the vendor's own
#: balance, and auto-reload is OFF so the hard stop exists regardless of what
#: this file believes.
FUNDED_USD: dict[str, Decimal] = {
    "openai": Decimal("100.00"),
    "xai": Decimal("10.00"),
}

# ---------------------------------------------------------------------------
# Caps
# ---------------------------------------------------------------------------

#: Per-run ceiling. One assignment run should not cost more than this; at
#: $0.50 the OpenAI pool alone buys ~200 runs, which is far more than eight
#: seats need in a day. The number matters less than its role: it is the
#: blast radius of a single bug. A prompt that loops on itself burns at most
#: one run before the day cap notices.
PER_RUN_CAP_USD = Decimal("0.50")

#: Per-day ceiling across ALL pools and ALL seats. $5 gives roughly twenty days
#: of runway on OpenAI alone while leaving the xAI pool untouched as a genuine
#: fallback. It is deliberately far below what eight seats firing thirty times
#: a day COULD spend: the runner is the last resort, so a day that approaches
#: this cap means the chat seats have stopped working and that is the thing to
#: look at, not the cap.
PER_DAY_CAP_USD = Decimal("5.00")

#: Never spend a pool to zero. Below this the pool is treated as empty, so
#: there is always a reserve to diagnose with rather than discovering the
#: balance is gone at the moment something urgent needs it.
POOL_RESERVE_USD = Decimal("1.00")

#: Kill switch, in the auto-signer's proven shape: a FILE, so it needs no
#: privileges, works when nothing else does, and reverses by deleting it.
API_RUNNER_BRAKE = Path.home() / ".projectos" / "api-runner.OFF"

#: Machine-local cost ledger. One JSON object per line, appended, never
#: rewritten - a ledger that can be edited in place is not a ledger.
COST_LEDGER = Path.home() / ".projectos" / "api-runner-cost.jsonl"


class Decision(StrEnum):
    """Why this run may or may not spend."""

    SPEND = "SPEND"
    SKIP_HELD = "SKIP_HELD"  # a chat seat holds it: deliberate, not a failure
    SKIP_DONE = "SKIP_DONE"  # already reported on
    BLOCKED_BRAKE = "BLOCKED_BRAKE"
    BLOCKED_DAY_CAP = "BLOCKED_DAY_CAP"
    BLOCKED_NO_POOL = "BLOCKED_NO_POOL"


@dataclass(frozen=True)
class SpendRuling:
    """One decision, fully described, including the ones that cost nothing."""

    decision: Decision
    pool: str | None = None
    reason: str = ""

    @property
    def may_spend(self) -> bool:
        return self.decision is Decision.SPEND

    def summary(self) -> str:
        where = f" [{self.pool}]" if self.pool else ""
        return f"{self.decision.value}{where}: {self.reason}"


def spent_today(ledger: Path | None = None, *, today: str | None = None) -> Decimal:
    """Total proxy cost recorded for the current IST day.

    Reads the ledger rather than trusting an in-memory counter: the runner is
    restarted by reboots and cron, and a counter that resets on restart is a
    cap that does not exist.
    """
    path = ledger if ledger is not None else COST_LEDGER
    day = today if today is not None else now_ist().strftime("%Y-%m-%d")
    if not path.exists():
        return Decimal("0")

    total = Decimal("0")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            # A corrupt line must not silently zero the day's spend and
            # re-open the cap. Skip the line, keep counting the rest.
            continue
        if row.get("day") == day:
            try:
                total += Decimal(str(row.get("usd", "0")))
            except (ArithmeticError, ValueError):
                continue
    return total


def choose_pool(
    remaining: dict[str, Decimal],
    *,
    reserve: Decimal = POOL_RESERVE_USD,
) -> str | None:
    """First pool in the fixed order with more than the reserve left."""
    for pool in SPEND_ORDER:
        if remaining.get(pool, Decimal("0")) > reserve:
            return pool
    return None


def decide(
    *,
    item_id: str,
    held_by: str | None = None,
    already_reported: bool = False,
    remaining: dict[str, Decimal] | None = None,
    ledger: Path | None = None,
    brake_path: Path | None = None,
    day_cap: Decimal = PER_DAY_CAP_USD,
) -> SpendRuling:
    """Decide whether this item may be run for money.

    The checks are ordered cheapest-and-most-absolute first: the kill switch
    beats everything, then the reasons not to spend at all, then the budget.
    """
    brake = brake_path if brake_path is not None else API_RUNNER_BRAKE
    if brake.exists():
        return SpendRuling(Decision.BLOCKED_BRAKE, None, f"kill switch present: {brake}")

    # Last-resort discipline. These are not failures and must not read as
    # failures on the phone: they are the runner declining to duplicate a chat
    # seat, which is the cheapest correct outcome there is.
    if held_by:
        return SpendRuling(Decision.SKIP_HELD, None, f"{item_id} is held by {held_by}")
    if already_reported:
        return SpendRuling(Decision.SKIP_DONE, None, f"{item_id} already has a report")

    today_spend = spent_today(ledger)
    if today_spend >= day_cap:
        return SpendRuling(
            Decision.BLOCKED_DAY_CAP,
            None,
            f"day cap reached: {today_spend} >= {day_cap} USD",
        )

    pool = choose_pool(remaining if remaining is not None else dict(FUNDED_USD))
    if pool is None:
        return SpendRuling(
            Decision.BLOCKED_NO_POOL,
            None,
            f"every pool at or below the {POOL_RESERVE_USD} USD reserve",
        )

    return SpendRuling(
        Decision.SPEND,
        pool,
        f"{item_id} unheld, {today_spend} of {day_cap} USD spent today",
    )


def record(
    *,
    item_id: str,
    pool: str | None,
    usd: Decimal,
    decision: Decision,
    ledger: Path | None = None,
) -> None:
    """Append one line to the cost ledger, including zero-cost decisions.

    Skips are recorded too. A ledger holding only the runs that cost money
    cannot answer "did the runner do nothing because nothing needed doing, or
    because it was broken" - and that is the question worth asking.
    """
    path = ledger if ledger is not None else COST_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = now_ist()
    row = {
        "at": stamp.isoformat(timespec="seconds"),
        "day": stamp.strftime("%Y-%m-%d"),
        "item": item_id,
        "pool": pool,
        "usd": str(usd),
        "decision": decision.value,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def phone_line(ledger: Path | None = None, *, today: str | None = None) -> str:
    """One line, for the founder's phone.

    Deliberately answers the two questions a phone glance can hold: what has
    today cost, and how close is that to the cap.
    """
    spend = spent_today(ledger, today=today)
    pct = int((spend / PER_DAY_CAP_USD) * 100) if PER_DAY_CAP_USD else 0
    return f"API-RUNNER today: {spend} of {PER_DAY_CAP_USD} USD ({pct}% of day cap)"


def ledger_rows(ledger: Path | None = None) -> Iterable[dict[str, object]]:
    """Every well-formed ledger row, oldest first."""
    path = ledger if ledger is not None else COST_LEDGER
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows
