"""Single-writer lease for the fleet INBOX.

On 2026-08-21 two Chat surfaces issued into one INBOX in the same hour. One
correctly enforced one-active-assignment-per-seat and deleted five assignments
the other had written; separately, both a PROJECTOS laptop surface and a
PROJECTOS cloud surface claimed the same assignment seven minutes apart and
filed contradictory reports. Neither surface did anything wrong by its own
rules. **There was simply nothing that could tell a second writer it was
second.**

This module is that thing. One orchestrator holds a lease on the INBOX; a
second is refused and told to write a proposal to AGENT-REPORTS instead of an
assignment. The lease is a plain JSON file on Drive and carries NO SECRET: it
is a coordination record, not an authorisation. It stops concurrent issuance,
which is the observed failure; it is not a defence against a hostile writer
with Drive access, and it is deliberately not described as one.

Recovery is by EXPIRY, not by an override. A holder that dies without
releasing blocks the INBOX only until its bounded TTL runs out, so there is no
"break the lease" verb for a stuck orchestrator to misuse and no founder act
required to get moving again.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

#: The lease record, beside the INBOX in the fleet reports folder.
LEASE_FILENAME = "INBOX-WRITER-LEASE.json"

#: Bounded by design. Long enough that an orchestrator working through a batch
#: does not lose the lease mid-batch; short enough that a surface which dies
#: silently does not hold the INBOX shut for a working day.
DEFAULT_TTL = timedelta(minutes=30)

#: The evidence line an issued assignment carries, naming the lease it was
#: emitted under. This is not a signature and proves no identity - it proves
#: the writer knew which lease was active at the moment it wrote, which is
#: exactly the thing a second concurrent writer does not know.
LEASE_HEADER = "LEASE: "


class LeaseError(RuntimeError):
    """The lease could not be read, or an operation was refused."""


@dataclass(frozen=True)
class Lease:
    """Who currently holds the right to write assignments, and until when."""

    holder: str
    lease_id: str
    issued_at: str
    expires_at: str

    def is_expired(self, now: datetime) -> bool:
        return now >= datetime.fromisoformat(self.expires_at)

    def held_by(self, holder: str, now: datetime) -> bool:
        return self.holder == holder and not self.is_expired(now)

    def as_dict(self) -> dict[str, str]:
        return {
            "holder": self.holder,
            "lease_id": self.lease_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }

    def summary(self) -> str:
        return f"{self.holder} holds {self.lease_id} until {self.expires_at}"


@dataclass(frozen=True)
class LeaseDecision:
    """The answer to "may I write assignments right now", with its reason."""

    granted: bool
    lease: Lease | None
    reason: str

    @property
    def refused(self) -> bool:
        return not self.granted


def lease_path(reports_dir: Path) -> Path:
    return reports_dir / LEASE_FILENAME


def read_lease(reports_dir: Path) -> Lease | None:
    """The current lease, or None when there is none.

    A corrupt lease file is an error rather than a silent None: treating
    unreadable as unheld would hand the INBOX to a second writer at exactly
    the moment the coordination record is broken.
    """
    path = lease_path(reports_dir)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Lease(
            holder=str(raw["holder"]),
            lease_id=str(raw["lease_id"]),
            issued_at=str(raw["issued_at"]),
            expires_at=str(raw["expires_at"]),
        )
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise LeaseError(f"lease file unreadable at {path}: {exc}") from exc


def _write(reports_dir: Path, lease: Lease) -> None:
    path = lease_path(reports_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(lease.as_dict(), indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def acquire(
    reports_dir: Path,
    holder: str,
    *,
    now: datetime,
    ttl: timedelta = DEFAULT_TTL,
    lease_id: str | None = None,
) -> LeaseDecision:
    """Take the INBOX writer lease, or be told who already has it.

    Granted when the lease is free, expired, or already this holder's (which
    renews it). Refused when another holder's lease is live - and the refusal
    names the holder and the expiry, because "you are second" is only
    actionable if it also says who is first and for how long.
    """
    current = read_lease(reports_dir)
    if current is not None and not current.is_expired(now) and current.holder != holder:
        return LeaseDecision(
            granted=False,
            lease=current,
            reason=(
                f"INBOX writer lease is held by {current.holder} until "
                f"{current.expires_at}; write a proposal to AGENT-REPORTS "
                "instead of an assignment"
            ),
        )

    granted = Lease(
        holder=holder,
        lease_id=lease_id or uuid.uuid4().hex[:16],
        issued_at=now.isoformat(timespec="seconds"),
        expires_at=(now + ttl).isoformat(timespec="seconds"),
    )
    _write(reports_dir, granted)
    was = "renewed" if current is not None and current.holder == holder else "acquired"
    return LeaseDecision(granted=True, lease=granted, reason=f"lease {was}")


def renew(
    reports_dir: Path, holder: str, *, now: datetime, ttl: timedelta = DEFAULT_TTL
) -> LeaseDecision:
    """Extend a lease this holder still holds.

    An expired lease is NOT renewed: it is reacquired through `acquire`, which
    may find someone else already there. Silently renewing something that had
    lapsed would let a stalled surface wake up and resume writing into an
    INBOX another orchestrator had legitimately taken over.
    """
    current = read_lease(reports_dir)
    if current is None:
        return LeaseDecision(False, None, "no lease to renew")
    if not current.held_by(holder, now):
        return LeaseDecision(
            False, current, f"lease is not held by {holder} (held by {current.holder})"
        )
    return acquire(reports_dir, holder, now=now, ttl=ttl, lease_id=current.lease_id)


def release(reports_dir: Path, holder: str, *, now: datetime) -> LeaseDecision:
    """Give the lease up early. Only the holder may."""
    current = read_lease(reports_dir)
    if current is None:
        return LeaseDecision(False, None, "no lease to release")
    if current.holder != holder:
        return LeaseDecision(
            False, current, f"{holder} cannot release a lease held by {current.holder}"
        )
    lease_path(reports_dir).unlink(missing_ok=True)
    return LeaseDecision(True, None, "lease released")


def stamp_lease(text: str, lease: Lease) -> str:
    """Add the lease evidence line to an assignment about to be written."""
    body = text.rstrip("\n")
    return f"{body}\n{LEASE_HEADER}{lease.lease_id}\n"


def declared_lease_id(text: str) -> str | None:
    """The lease id an assignment claims it was emitted under, if any."""
    for line in text.splitlines():
        if line.startswith(LEASE_HEADER):
            return line[len(LEASE_HEADER) :].strip()
    return None


def emitted_under_active_lease(
    text: str, reports_dir: Path, *, now: datetime
) -> tuple[bool, str]:
    """Was this file emitted under the lease that is active right now?

    Returns the answer and the reason, so a refusal can name its class rather
    than failing as a bare False.
    """
    declared = declared_lease_id(text)
    if declared is None:
        return False, "no LEASE line: file was not emitted under any writer lease"

    current = read_lease(reports_dir)
    if current is None:
        return False, f"declares lease {declared} but no lease is active"
    if current.is_expired(now):
        return False, f"declares lease {declared} but the active lease has expired"
    if declared != current.lease_id:
        return (
            False,
            f"declares lease {declared}, but the active lease is "
            f"{current.lease_id} ({current.holder}) - written by a second issuer",
        )
    return True, f"emitted under the active lease held by {current.holder}"


#: What a refused second issuer writes instead of an assignment. A proposal is
#: inert by construction: it is not assignment-shaped, so the signer will not
#: stamp it and no seat will claim it. The second issuer still gets its
#: intent onto the record - being second should cost you the write, not the
#: idea.
PROPOSAL_PREFIX = "PROPOSAL"


def write_proposal(
    reports_dir: Path,
    *,
    holder: str,
    subject: str,
    body: str,
    now: datetime,
    active: Lease | None,
) -> Path:
    """Record a refused issuer's intent as a proposal, not an assignment.

    Deliberately NOT written into the INBOX and deliberately not
    assignment-named: the whole point of refusing the second writer is that
    its output must not become claimable work behind the lease holder's back.
    """
    stamp = now.strftime("%Y-%m-%d_%H%M")
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in subject).strip("-")
    # PROPOSAL leads the name, ahead of the date. That is not cosmetic: the
    # assignment pattern is anchored on a leading date (`^\d{4}-\d{2}-\d{2}_`),
    # so a date-first proposal IS assignment-shaped and a seat would claim it.
    # Leading with the word is what makes the file structurally unclaimable.
    path = reports_dir / f"{PROPOSAL_PREFIX}_{stamp}_{holder}_{safe}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    held = active.summary() if active is not None else "no active lease recorded"
    path.write_text(
        "\n".join(
            [
                f"# PROPOSAL from {holder} - not an assignment",
                "",
                f"Written {now.isoformat(timespec='seconds')} because the INBOX",
                f"writer lease was held elsewhere: {held}.",
                "",
                "This file is deliberately not assignment-shaped: the signer will",
                "not stamp it and no seat will claim it. It is here so the intent",
                "survives without a second issuer writing work into the queue.",
                "",
                "## Subject",
                subject,
                "",
                "## Proposed",
                body.rstrip(),
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return path
