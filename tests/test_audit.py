"""Audit hash-chain tests (spec section 8.5, INV-5).

The chain's purpose is to make hand-edits detectable, so these tests tamper in each
of the ways an editor realistically would — change a field, drop an entry, append a
forged one, reorder — and assert each is caught.
"""

from __future__ import annotations

import pytest

from projectos.domain.audit import GENESIS_HASH, AuditEntry, seal_next, verify_chain
from projectos.domain.errors import AuditChainBroken


def entry(sequence: int, event: str = "test_event") -> AuditEntry:
    return AuditEntry(
        sequence=sequence,
        timestamp=f"2026-07-20T09:0{sequence}:00Z",
        event=event,
        actor="founder@example.test",
    )


def chain_of(length: int) -> tuple[AuditEntry, ...]:
    entries: list[AuditEntry] = []
    previous: AuditEntry | None = None
    for index in range(1, length + 1):
        previous = seal_next(entry(index), previous)
        entries.append(previous)
    return tuple(entries)


def test_first_entry_chains_from_genesis() -> None:
    first = seal_next(entry(1), None)
    assert first.prev_hash == GENESIS_HASH
    assert first.sequence == 1


def test_intact_chain_verifies() -> None:
    verify_chain(chain_of(5))


def test_empty_chain_verifies() -> None:
    """A fresh repository has no entries; that is valid, not broken."""
    verify_chain(())


def test_modified_payload_is_detected() -> None:
    entries = list(chain_of(3))
    from dataclasses import replace

    entries[1] = replace(entries[1], reason="edited after the fact")

    with pytest.raises(AuditChainBroken, match="has been modified"):
        verify_chain(tuple(entries))


def test_removed_entry_is_detected() -> None:
    """Deleting a middle entry breaks the sequence contiguity of the tail."""
    entries = list(chain_of(4))
    del entries[2]

    with pytest.raises(AuditChainBroken, match="sequence break"):
        verify_chain(tuple(entries))


def test_reordered_entries_are_detected() -> None:
    entries = list(chain_of(3))
    entries[0], entries[1] = entries[1], entries[0]

    # Swapping the first two makes entry at position 1 carry sequence 2: caught by
    # the sequence check. `match=` pins which check fired so removing it is caught.
    with pytest.raises(AuditChainBroken, match="sequence break"):
        verify_chain(tuple(entries))


def test_forged_appended_entry_is_detected() -> None:
    """An entry sealed against the wrong predecessor breaks the chain.

    Sealing against entry 1 rather than entry 2 also renumbers the forgery to
    sequence 2, so the sequence check catches it before the hash check does —
    either way it never verifies.
    """
    entries = list(chain_of(2))
    entries.append(seal_next(entry(3, "forged"), entries[0]))  # wrong parent

    with pytest.raises(AuditChainBroken, match="sequence break"):
        verify_chain(tuple(entries))


def test_hash_is_stable_across_equal_payloads() -> None:
    """Canonical serialisation: the same logical entry always hashes identically."""
    assert seal_next(entry(1), None).hash == seal_next(entry(1), None).hash


def test_hash_covers_every_payload_field() -> None:
    """Changing any covered field changes the hash."""
    from dataclasses import replace

    base = seal_next(entry(1), None)
    for field, value in (
        ("event", "other"),
        ("actor", "someone@else.test"),
        ("assignment_id", "A-0002"),
        ("reason", "different"),
        ("to_status", "closed"),
    ):
        mutated = replace(base, **{field: value})
        assert mutated.compute_hash() != base.hash, f"{field} is not covered by the hash"
