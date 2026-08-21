"""Tests for the single-writer INBOX lease.

These encode 2026-08-21, when two Chat surfaces issued into one INBOX in the
same hour and two PROJECTOS surfaces claimed the same assignment seven minutes
apart. Neither second writer broke a rule; nothing could tell them they were
second.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from projectos.infrastructure.inbox_lease import (
    DEFAULT_TTL,
    LEASE_FILENAME,
    LeaseError,
    acquire,
    declared_lease_id,
    emitted_under_active_lease,
    read_lease,
    release,
    renew,
    stamp_lease,
)

NOON = datetime.fromisoformat("2026-08-21T12:00:00+05:30")


@pytest.fixture
def reports(tmp_path: Path) -> Path:
    directory = tmp_path / "AGENT-REPORTS"
    directory.mkdir()
    return directory


# --- acquiring -------------------------------------------------------------


def test_a_free_inbox_grants_the_lease(reports: Path) -> None:
    decision = acquire(reports, "CHAT-A", now=NOON)
    assert decision.granted
    assert decision.lease is not None
    assert decision.lease.holder == "CHAT-A"
    assert (reports / LEASE_FILENAME).exists()


def test_a_second_concurrent_writer_is_refused(reports: Path) -> None:
    # The whole point. CHAT-B is not doing anything wrong - it simply must be
    # told it is second, and by whom, and for how long.
    acquire(reports, "CHAT-A", now=NOON)
    decision = acquire(reports, "CHAT-B", now=NOON + timedelta(minutes=5))
    assert decision.refused
    assert "CHAT-A" in decision.reason
    assert "proposal" in decision.reason  # told what to do instead


def test_the_refusal_names_the_holder_and_the_expiry(reports: Path) -> None:
    granted = acquire(reports, "CHAT-A", now=NOON).lease
    assert granted is not None
    decision = acquire(reports, "CHAT-B", now=NOON)
    assert granted.expires_at in decision.reason


def test_the_holder_reacquiring_renews_rather_than_being_refused(reports: Path) -> None:
    first = acquire(reports, "CHAT-A", now=NOON)
    second = acquire(reports, "CHAT-A", now=NOON + timedelta(minutes=5))
    assert second.granted
    assert second.reason == "lease renewed"
    assert first.lease is not None
    assert second.lease is not None
    assert second.lease.expires_at > first.lease.expires_at


# --- expiry and recovery ---------------------------------------------------


def test_an_expired_lease_frees_the_inbox(reports: Path) -> None:
    # Recovery is by expiry, so a surface that dies without releasing blocks
    # the INBOX for a bounded time and needs no founder act to clear.
    acquire(reports, "CHAT-A", now=NOON)
    decision = acquire(reports, "CHAT-B", now=NOON + DEFAULT_TTL + timedelta(seconds=1))
    assert decision.granted
    assert decision.lease is not None
    assert decision.lease.holder == "CHAT-B"


def test_the_ttl_is_bounded(reports: Path) -> None:
    lease = acquire(reports, "CHAT-A", now=NOON).lease
    assert lease is not None
    span = datetime.fromisoformat(lease.expires_at) - NOON
    assert timedelta(0) < span <= timedelta(hours=1)


def test_an_expired_lease_is_not_renewed_behind_the_new_holders_back(
    reports: Path,
) -> None:
    # A stalled surface waking up must not resume writing into an INBOX that
    # someone else has legitimately taken over.
    acquire(reports, "CHAT-A", now=NOON)
    later = NOON + DEFAULT_TTL + timedelta(minutes=1)
    acquire(reports, "CHAT-B", now=later)
    decision = renew(reports, "CHAT-A", now=later + timedelta(minutes=1))
    assert decision.refused
    assert "CHAT-B" in decision.reason


def test_renewing_without_a_lease_is_refused(reports: Path) -> None:
    assert renew(reports, "CHAT-A", now=NOON).refused


def test_only_the_holder_may_release(reports: Path) -> None:
    acquire(reports, "CHAT-A", now=NOON)
    assert release(reports, "CHAT-B", now=NOON).refused
    assert (reports / LEASE_FILENAME).exists()
    assert release(reports, "CHAT-A", now=NOON).granted
    assert not (reports / LEASE_FILENAME).exists()


def test_a_corrupt_lease_file_raises_rather_than_reading_as_unheld(
    reports: Path,
) -> None:
    # Unreadable must never mean "free": that would hand the INBOX to a second
    # writer at the exact moment the coordination record is broken.
    (reports / LEASE_FILENAME).write_text("{ not json", encoding="utf-8")
    with pytest.raises(LeaseError):
        read_lease(reports)


def test_no_secret_is_written_into_the_lease(reports: Path) -> None:
    acquire(reports, "CHAT-A", now=NOON)
    raw = json.loads((reports / LEASE_FILENAME).read_text(encoding="utf-8"))
    assert set(raw) == {"holder", "lease_id", "issued_at", "expires_at"}


# --- emission evidence -----------------------------------------------------


def test_a_file_stamped_under_the_active_lease_is_accepted(reports: Path) -> None:
    lease = acquire(reports, "CHAT-A", now=NOON).lease
    assert lease is not None
    text = stamp_lease("# ASSIGNMENT\nbody\n", lease)
    ok, why = emitted_under_active_lease(text, reports, now=NOON)
    assert ok, why


def test_a_file_with_no_lease_line_is_refused(reports: Path) -> None:
    acquire(reports, "CHAT-A", now=NOON)
    ok, why = emitted_under_active_lease("# ASSIGNMENT\nbody\n", reports, now=NOON)
    assert not ok
    assert "no LEASE line" in why


def test_a_file_from_the_second_issuer_is_refused(reports: Path) -> None:
    # CHAT-B wrote its file believing it held the INBOX; its lease id is not
    # the active one, which is precisely how "second" becomes detectable.
    stale = acquire(reports, "CHAT-B", now=NOON).lease
    assert stale is not None
    text = stamp_lease("# ASSIGNMENT\nbody\n", stale)
    release(reports, "CHAT-B", now=NOON)
    acquire(reports, "CHAT-A", now=NOON)
    ok, why = emitted_under_active_lease(text, reports, now=NOON)
    assert not ok
    assert "second issuer" in why


def test_a_file_stamped_under_an_expired_lease_is_refused(reports: Path) -> None:
    lease = acquire(reports, "CHAT-A", now=NOON).lease
    assert lease is not None
    text = stamp_lease("# ASSIGNMENT\nbody\n", lease)
    ok, why = emitted_under_active_lease(
        text, reports, now=NOON + DEFAULT_TTL + timedelta(minutes=1)
    )
    assert not ok
    assert "expired" in why


def test_evidence_is_refused_when_no_lease_is_active(reports: Path) -> None:
    lease = acquire(reports, "CHAT-A", now=NOON).lease
    assert lease is not None
    text = stamp_lease("# ASSIGNMENT\nbody\n", lease)
    release(reports, "CHAT-A", now=NOON)
    ok, why = emitted_under_active_lease(text, reports, now=NOON)
    assert not ok
    assert "no lease is active" in why


def test_stamping_is_idempotent_in_shape(reports: Path) -> None:
    lease = acquire(reports, "CHAT-A", now=NOON).lease
    assert lease is not None
    text = stamp_lease("# ASSIGNMENT\nbody", lease)
    assert declared_lease_id(text) == lease.lease_id
    assert text.endswith("\n")


def test_a_refused_issuer_writes_a_proposal_not_an_assignment(reports: Path) -> None:
    from projectos.infrastructure.inbox_auth import ASSIGNMENT_NAME
    from projectos.infrastructure.inbox_lease import write_proposal

    acquire(reports, "CHAT-A", now=NOON)
    refused = acquire(reports, "CHAT-B", now=NOON)
    assert refused.refused

    path = write_proposal(
        reports,
        holder="CHAT-B",
        subject="restock the WARRANT pool",
        body="- WARRANT has no pool items left",
        now=NOON,
        active=refused.lease,
    )
    assert path.exists()
    # The load-bearing property: it can never be mistaken for claimable work.
    assert not ASSIGNMENT_NAME.match(path.name)
    assert "not an assignment" in path.read_text(encoding="utf-8")


def test_the_proposal_names_who_held_the_lease(reports: Path) -> None:
    from projectos.infrastructure.inbox_lease import write_proposal

    acquire(reports, "CHAT-A", now=NOON)
    refused = acquire(reports, "CHAT-B", now=NOON)
    path = write_proposal(
        reports, holder="CHAT-B", subject="s", body="b", now=NOON, active=refused.lease
    )
    assert "CHAT-A" in path.read_text(encoding="utf-8")
