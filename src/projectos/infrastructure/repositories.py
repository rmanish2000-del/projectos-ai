"""File-backed implementations of the application ports.

The repository *is* the database (decision D-1): every value lives in a YAML file
under `.projectos/`, so `git log` is a second witness to the audit chain.

These classes hold no cached state between calls. Reading from disk each time is
cheap at v0.1 scale and removes a whole class of bug where the kernel decides from
a stale snapshot.
"""

from __future__ import annotations

from projectos.application.validation_service import Severity, check_pack_compatibility
from projectos.domain.assignment import Assignment
from projectos.domain.errors import NotFoundError, ValidationError
from projectos.domain.escalation import Escalation
from projectos.domain.ids import (
    FIRST_ASSIGNMENT_ID,
    FIRST_ESCALATION_ID,
    AssignmentId,
    EscalationId,
)
from projectos.domain.manifest import Manifest
from projectos.domain.pack import Pack, PackSet
from projectos.infrastructure.pack_loading import load_pack_from_directory
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.serialization import (
    assignment_from_dict,
    assignment_to_dict,
    escalation_from_dict,
    escalation_to_dict,
    manifest_from_dict,
    manifest_to_dict,
    require_mapping,
)
from projectos.infrastructure.yaml_io import read_yaml, write_yaml

MANIFEST_HEADER = "ProjectOS project manifest — schema v1. Managed by the kernel."
ASSIGNMENT_HEADER = (
    "ProjectOS assignment — schema v1. KERNEL-MANAGED: do not hand-edit. "
    "Edits break audit validation and halt the kernel (INV-6)."
)
ESCALATION_HEADER = "ProjectOS escalation — schema v1. Resolution is founder-only."
ACTIVE_HEADER = "ProjectOS active-assignment pointer — derived from assignment status."


class FileManifestRepository:
    def __init__(self, layout: Layout) -> None:
        self._layout = layout

    def exists(self) -> bool:
        return self._layout.manifest.is_file()

    def load(self) -> Manifest:
        if not self.exists():
            raise NotFoundError(
                f"No ProjectOS manifest at {self._layout.manifest}",
                detail="Run `projectos init` to scaffold this repository.",
            )
        raw = require_mapping(read_yaml(self._layout.manifest), source=str(self._layout.manifest))
        return manifest_from_dict(raw, source=str(self._layout.manifest))

    def save(self, manifest: Manifest) -> None:
        write_yaml(self._layout.manifest, manifest_to_dict(manifest), header=MANIFEST_HEADER)


class FilePackRepository:
    """Loads packs named by the manifest, in manifest order (last wins)."""

    def __init__(self, layout: Layout) -> None:
        self._layout = layout

    def load_all(self, manifest: Manifest) -> PackSet:
        """Load every pack the manifest requires, enforcing compatibility.

        Compatibility is checked here, on the single loading path, rather than only
        in the validation commands. `pack validate` is then a report on the same
        rules the loader applies, and there is no route into the kernel — including
        activation — that reaches a pack whose version was never checked.
        """
        packs: list[Pack] = []
        for requirement in manifest.packs:
            pack = self._load_one(requirement.name)
            self._enforce_compatibility(pack, requirement.version)
            packs.append(pack)
        return PackSet(tuple(packs))

    @staticmethod
    def _enforce_compatibility(pack: Pack, constraint: str | None) -> None:
        """Fail closed on an incompatible pack (spec 10.2)."""
        findings = check_pack_compatibility(pack, declared_constraint=constraint)
        blocking = [f for f in findings if f.severity is Severity.ERROR]
        if not blocking:
            return
        first = blocking[0]
        raise ValidationError(
            f"Pack {pack.name!r} is not compatible: {first.message}",
            detail="\n".join(
                filter(None, [first.hint, "Run `projectos validate` for the full report."])
            ),
        )

    def _load_one(self, name: str) -> Pack:
        directory = self._layout.packs_dir / name
        pack_file = directory / "pack.yaml"
        if not pack_file.is_file():
            raise ValidationError(
                f"Manifest requires pack {name!r} but {pack_file} is missing",
                detail="An unresolvable pack halts the kernel (spec 10.2, fail closed).",
            )
        # One loader for both paths, so `pack validate` and pack loading can never
        # disagree about how a pack is read.
        return load_pack_from_directory(directory)


class FileAssignmentRepository:
    def __init__(self, layout: Layout) -> None:
        self._layout = layout

    def list_all(self) -> tuple[Assignment, ...]:
        directory = self._layout.assignments_dir
        if not directory.is_dir():
            return ()
        assignments = [
            assignment_from_dict(
                require_mapping(read_yaml(path), source=str(path)), source=str(path)
            )
            for path in sorted(directory.glob("A-*.yaml"))
        ]
        return tuple(sorted(assignments, key=lambda a: a.id))

    def get(self, assignment_id: AssignmentId) -> Assignment:
        path = self._layout.assignment_file(str(assignment_id))
        if not path.is_file():
            raise NotFoundError(f"No assignment {assignment_id}")
        return assignment_from_dict(
            require_mapping(read_yaml(path), source=str(path)), source=str(path)
        )

    def save(self, assignment: Assignment) -> None:
        write_yaml(
            self._layout.assignment_file(str(assignment.id)),
            assignment_to_dict(assignment),
            header=ASSIGNMENT_HEADER,
        )

    def next_id(self) -> AssignmentId:
        existing = self.list_all()
        if not existing:
            return FIRST_ASSIGNMENT_ID
        return max(a.id for a in existing).next()

    def active(self) -> Assignment | None:
        for assignment in self.list_all():
            if assignment.occupies_active_slot:
                return assignment
        return None

    def set_active(self, assignment_id: AssignmentId | None) -> None:
        write_yaml(
            self._layout.active_pointer,
            {"active": str(assignment_id) if assignment_id else None},
            header=ACTIVE_HEADER,
        )


class FileEscalationRepository:
    def __init__(self, layout: Layout) -> None:
        self._layout = layout

    def list_all(self) -> tuple[Escalation, ...]:
        directory = self._layout.escalations_dir
        if not directory.is_dir():
            return ()
        escalations = [
            escalation_from_dict(
                require_mapping(read_yaml(path), source=str(path)), source=str(path)
            )
            for path in sorted(directory.glob("E-*.yaml"))
        ]
        return tuple(sorted(escalations, key=lambda e: e.id))

    def get(self, escalation_id: EscalationId) -> Escalation:
        path = self._layout.escalation_file(str(escalation_id))
        if not path.is_file():
            raise NotFoundError(f"No escalation {escalation_id}")
        return escalation_from_dict(
            require_mapping(read_yaml(path), source=str(path)), source=str(path)
        )

    def save(self, escalation: Escalation) -> None:
        write_yaml(
            self._layout.escalation_file(str(escalation.id)),
            escalation_to_dict(escalation),
            header=ESCALATION_HEADER,
        )

    def next_id(self) -> EscalationId:
        existing = self.list_all()
        if not existing:
            return FIRST_ESCALATION_ID
        return max(e.id for e in existing).next()
