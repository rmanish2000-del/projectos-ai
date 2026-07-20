"""State integrity verification (spec sections 8.5 and 14.6, INV-5 and INV-6).

`audit.verify()` alone proves the log is *internally* consistent. It cannot prove
the log is *complete*, because any prefix of a valid chain is itself a valid chain:
truncating the tail, or deleting the newest monthly file, leaves entries whose
sequences are contiguous and whose hashes still link. Deleting the log entirely
leaves an empty chain, which is indistinguishable from a fresh project.

The missing anchor already exists in the state files. Every transition records the
hash of the audit entry that authorised it, in `TransitionRecord.audit_ref`. Those
references are written by the kernel and are the external witness the chain needs:
if an assignment claims an audit entry that the log no longer contains, the log has
lost entries.

Verification therefore runs in both directions:

* every `audit_ref` an assignment cites must be present in the log, and
* every transition the log records for an assignment must appear in its history.

The second direction catches the reverse tamper — editing an assignment file to
drop or rewrite its history while the log stays intact.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.assignment import Assignment
from projectos.domain.audit import AuditEntry, verify_chain
from projectos.domain.errors import AuditChainBroken

#: Audit events that correspond to a recorded state transition. Other events
#: (`assignment_created`, `approval_recorded`, `classify_deferred`, …) are
#: bookkeeping and carry no history entry.
_TRANSITION_EVENTS_EXCLUDED: frozenset[str] = frozenset(
    {
        "assignment_created",
        "approval_recorded",
        "attestation_recorded",
        "classify_deferred",
        "escalation_opened",
        "escalation_resolved",
    }
)


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    entries: int
    assignments: int
    references_checked: int

    def describe(self) -> str:
        return (
            f"{self.entries} audit entries, {self.assignments} assignments, "
            f"{self.references_checked} transition references cross-checked"
        )


def verify_state(
    entries: tuple[AuditEntry, ...], assignments: tuple[Assignment, ...]
) -> IntegrityReport:
    """Verify the audit chain and its agreement with the assignment files.

    Raises :class:`AuditChainBroken` on the first inconsistency, which halts the
    kernel (INV-6).
    """
    verify_chain(entries)

    known_hashes = {entry.hash for entry in entries}
    checked = 0

    for assignment in assignments:
        for record in assignment.history:
            checked += 1
            if record.audit_ref in known_hashes:
                continue
            raise AuditChainBroken(
                f"Audit log is missing the entry that authorised a transition of "
                f"{assignment.id}",
                detail=(
                    f"{assignment.id} records {record.from_status.value} -> "
                    f"{record.to_status.value} at {record.timestamp} citing audit entry "
                    f"{record.audit_ref[:12]}…, which is not in the log. "
                    "Entries have been truncated or deleted."
                ),
            )

    _verify_no_dropped_history(entries, assignments)
    return IntegrityReport(
        entries=len(entries), assignments=len(assignments), references_checked=checked
    )


def _verify_no_dropped_history(
    entries: tuple[AuditEntry, ...], assignments: tuple[Assignment, ...]
) -> None:
    """Catch the reverse tamper: history removed from an assignment file.

    Only assignments still present are checked. A deleted assignment file is a
    different failure and is reported by the loader, not here.
    """
    by_id = {str(assignment.id): assignment for assignment in assignments}

    for entry in entries:
        if entry.assignment_id is None or entry.event in _TRANSITION_EVENTS_EXCLUDED:
            continue
        assignment = by_id.get(entry.assignment_id)
        if assignment is None:
            continue
        if any(record.audit_ref == entry.hash for record in assignment.history):
            continue
        raise AuditChainBroken(
            f"{entry.assignment_id} is missing a transition the audit log records",
            detail=(
                f"Audit entry {entry.sequence} ({entry.event}: {entry.from_status} -> "
                f"{entry.to_status}) has no matching record in the assignment's history. "
                "The assignment file has been edited by hand."
            ),
        )
