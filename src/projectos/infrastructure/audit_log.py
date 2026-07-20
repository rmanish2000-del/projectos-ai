"""NDJSON audit log with monthly rotation (spec section 8.5).

One JSON object per line, appended and never rewritten. Files rotate monthly
(`2026-07.ndjson`) but the hash chain runs continuously across files, so rotation
is a filing convenience and not a chain boundary — a tamperer cannot start a fresh
file to escape verification.
"""

from __future__ import annotations

import json
from pathlib import Path

from projectos.domain.audit import AuditEntry, verify_chain
from projectos.domain.enums import Role
from projectos.domain.errors import ValidationError
from projectos.domain.evidence import ApprovalRecord
from projectos.domain.ids import AssignmentId
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.validation import validate

#: Audit events that record a human decision rather than a state transition.
APPROVAL_EVENTS: frozenset[str] = frozenset({"approval_recorded", "attestation_recorded"})


class NdjsonAuditLog:
    def __init__(self, layout: Layout) -> None:
        self._layout = layout

    # -- writing ---------------------------------------------------------------

    def append(self, entry: AuditEntry) -> AuditEntry:
        path = self._file_for(entry.timestamp)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry.to_dict(), sort_keys=True, ensure_ascii=False)
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
        return entry

    def _file_for(self, timestamp: str) -> Path:
        # ISO-8601 timestamps sort lexicographically, so the first seven characters
        # are the rotation key.
        month = timestamp[:7] if len(timestamp) >= 7 else "unknown"
        return self._layout.audit_dir / f"{month}.ndjson"

    # -- reading ---------------------------------------------------------------

    def read_all(self) -> tuple[AuditEntry, ...]:
        directory = self._layout.audit_dir
        if not directory.is_dir():
            return ()
        entries: list[AuditEntry] = []
        for path in sorted(directory.glob("*.ndjson")):
            entries.extend(self._read_file(path))
        # Sequence, not filename, defines order: it is the field the chain verifies.
        return tuple(sorted(entries, key=lambda e: e.sequence))

    @staticmethod
    def _read_file(path: Path) -> list[AuditEntry]:
        entries: list[AuditEntry] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"Malformed audit entry at {path}:{number}", detail=str(exc)
                ) from exc
            validate(raw, "audit_entry.schema.json", source=f"{path}:{number}")
            entries.append(AuditEntry.from_dict(raw))
        return entries

    def last(self) -> AuditEntry | None:
        entries = self.read_all()
        return entries[-1] if entries else None

    def verify(self) -> None:
        """Re-walk the chain. Raises AuditChainBroken, which halts the kernel."""
        verify_chain(self.read_all())

    # -- projections -----------------------------------------------------------

    def approvals_for(self, assignment_id: AssignmentId) -> tuple[ApprovalRecord, ...]:
        """Approvals and attestations recorded against one assignment.

        Derived from the log rather than stored separately, so an approval cannot
        exist without a corresponding hash-chained entry.
        """
        wanted = str(assignment_id)
        records: list[ApprovalRecord] = []
        for entry in self.read_all():
            if entry.event not in APPROVAL_EVENTS or entry.assignment_id != wanted:
                continue
            role_value = str(entry.data.get("role", ""))
            if role_value not in {role.value for role in Role}:
                continue
            records.append(
                ApprovalRecord(
                    assignment_id=wanted,
                    role=Role(role_value),
                    actor=str(entry.data.get("actor", entry.actor)),
                    decision=str(entry.data.get("decision", "approved")),
                    timestamp=entry.timestamp,
                )
            )
        return tuple(records)

    def for_assignment(self, assignment_id: AssignmentId) -> tuple[AuditEntry, ...]:
        wanted = str(assignment_id)
        return tuple(e for e in self.read_all() if e.assignment_id == wanted)
