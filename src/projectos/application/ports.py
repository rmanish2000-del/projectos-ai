"""Ports the application layer depends on (Clean Architecture boundary).

These are Protocols, not base classes: the domain and application layers define
what they need, and infrastructure supplies it. Dependencies point inward only —
nothing here imports from `projectos.infrastructure` or `projectos.cli`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from projectos.domain.assignment import Assignment
from projectos.domain.audit import AuditEntry
from projectos.domain.escalation import Escalation
from projectos.domain.evidence import ApprovalRecord, EvidenceRule, RepositoryFact
from projectos.domain.ids import AssignmentId, EscalationId
from projectos.domain.manifest import Manifest
from projectos.domain.pack import PackSet


@runtime_checkable
class Clock(Protocol):
    """Time as a dependency, so tests are deterministic and no module reads the
    wall clock directly."""

    def now_iso(self) -> str: ...


@runtime_checkable
class IdentityProvider(Protocol):
    """The acting identity. v0.1 trusts local OS/git identity (spec 14.4, risk R-6)."""

    def current(self) -> str: ...


@runtime_checkable
class ManifestRepository(Protocol):
    def exists(self) -> bool: ...
    def load(self) -> Manifest: ...
    def save(self, manifest: Manifest) -> None: ...


@runtime_checkable
class PackRepository(Protocol):
    def load_all(self, manifest: Manifest) -> PackSet: ...


@runtime_checkable
class AssignmentRepository(Protocol):
    def list_all(self) -> tuple[Assignment, ...]: ...
    def get(self, assignment_id: AssignmentId) -> Assignment: ...
    def save(self, assignment: Assignment) -> None: ...
    def next_id(self) -> AssignmentId: ...
    def active(self) -> Assignment | None: ...
    def set_active(self, assignment_id: AssignmentId | None) -> None: ...


@runtime_checkable
class EscalationRepository(Protocol):
    def list_all(self) -> tuple[Escalation, ...]: ...
    def get(self, escalation_id: EscalationId) -> Escalation: ...
    def save(self, escalation: Escalation) -> None: ...
    def next_id(self) -> EscalationId: ...


@runtime_checkable
class AuditLog(Protocol):
    def append(self, entry: AuditEntry) -> AuditEntry: ...
    def read_all(self) -> tuple[AuditEntry, ...]: ...
    def last(self) -> AuditEntry | None: ...
    def verify(self) -> None: ...
    def approvals_for(self, assignment_id: AssignmentId) -> tuple[ApprovalRecord, ...]: ...


@runtime_checkable
class RepositoryAdapter(Protocol):
    """Facts only. Adapters never return verdicts (spec section 11)."""

    def capabilities(self) -> dict[str, bool]: ...

    def query(self, rule: EvidenceRule) -> RepositoryFact:
        """Answer one evidence rule with observed facts.

        Implementations raise `AdapterError` on failure rather than returning a
        negative fact, so a broken adapter is distinguishable from absent evidence.
        """
        ...
