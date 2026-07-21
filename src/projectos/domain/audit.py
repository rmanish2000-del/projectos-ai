"""Append-only audit log with a SHA-256 hash chain (spec section 8.5, INV-5).

Each entry hashes its own canonical payload together with the previous entry's
hash. Editing or removing any entry breaks every hash after it, which is what makes
hand-edits to state detectable rather than merely discouraged.

Canonicalisation matters: the hash is computed over JSON with sorted keys and no
insignificant whitespace, so the same logical entry always hashes identically
regardless of how it was serialised.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any

from projectos.domain.errors import AuditChainBroken, ValidationError

#: The hash a first entry chains from. A fixed, explicit value rather than an
#: empty string, so a truncated log cannot masquerade as a fresh one.
GENESIS_HASH: str = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """One state-affecting event. `hash` is derived, never supplied by a caller."""

    sequence: int
    timestamp: str
    event: str
    actor: str
    assignment_id: str | None = None
    escalation_id: str | None = None
    from_status: str | None = None
    to_status: str | None = None
    reason: str | None = None
    evidence_refs: tuple[str, ...] = ()
    data: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = GENESIS_HASH
    hash: str = ""

    def payload(self) -> dict[str, Any]:
        """The canonical, hash-covered content of this entry (everything but `hash`)."""
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event": self.event,
            "actor": self.actor,
            "assignment_id": self.assignment_id,
            "escalation_id": self.escalation_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "data": self.data,
            "prev_hash": self.prev_hash,
        }

    def compute_hash(self) -> str:
        canonical = json.dumps(
            self.payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def sealed(self) -> AuditEntry:
        """Return this entry with its derived hash attached."""
        return replace(self, hash=self.compute_hash())

    def to_dict(self) -> dict[str, Any]:
        return {**self.payload(), "hash": self.hash}

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> AuditEntry:
        try:
            return cls(
                sequence=int(raw["sequence"]),
                timestamp=str(raw["timestamp"]),
                event=str(raw["event"]),
                actor=str(raw["actor"]),
                assignment_id=raw.get("assignment_id"),
                escalation_id=raw.get("escalation_id"),
                from_status=raw.get("from_status"),
                to_status=raw.get("to_status"),
                reason=raw.get("reason"),
                evidence_refs=tuple(raw.get("evidence_refs") or ()),
                data=dict(raw.get("data") or {}),
                prev_hash=str(raw.get("prev_hash", GENESIS_HASH)),
                hash=str(raw.get("hash", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError("Malformed audit entry", detail=str(exc)) from exc


def seal_next(entry: AuditEntry, previous: AuditEntry | None) -> AuditEntry:
    """Chain `entry` onto `previous` and seal it."""
    prev_hash = previous.hash if previous is not None else GENESIS_HASH
    sequence = previous.sequence + 1 if previous is not None else 1
    return replace(entry, sequence=sequence, prev_hash=prev_hash).sealed()


def verify_chain(entries: tuple[AuditEntry, ...]) -> None:
    """Re-walk the chain. Raises AuditChainBroken at the first inconsistency.

    Verifying the whole chain rather than only the tail is deliberate: a tamperer
    who can rewrite one entry can rewrite the tail too.
    """
    expected_prev = GENESIS_HASH
    for index, entry in enumerate(entries, start=1):
        if entry.sequence != index:
            raise AuditChainBroken(
                f"Audit sequence break at position {index}",
                detail=f"Expected sequence {index}, found {entry.sequence}.",
            )
        if entry.prev_hash != expected_prev:
            raise AuditChainBroken(
                f"Audit chain broken at entry {entry.sequence}",
                detail=(
                    f"Entry records prev_hash {entry.prev_hash[:12]}…, "
                    f"expected {expected_prev[:12]}…"
                ),
            )
        recomputed = entry.compute_hash()
        if recomputed != entry.hash:
            raise AuditChainBroken(
                f"Audit entry {entry.sequence} has been modified",
                detail=(
                    f"Stored hash {entry.hash[:12]}… does not match "
                    f"recomputed {recomputed[:12]}…"
                ),
            )
        expected_prev = entry.hash
