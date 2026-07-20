"""The `.projectos/` directory layout (spec section 2.3).

One place defines where everything lives, so the portability guarantee holds:
deleting `.projectos/` removes ProjectOS with zero residue because nothing is
written anywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECTOS_DIR = ".projectos"


@dataclass(frozen=True, slots=True)
class Layout:
    root: Path

    @classmethod
    def for_repo(cls, repo_root: Path) -> Layout:
        return cls(repo_root.resolve() / PROJECTOS_DIR)

    @property
    def repo_root(self) -> Path:
        return self.root.parent

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.yaml"

    @property
    def packs_dir(self) -> Path:
        return self.root / "packs"

    @property
    def assignments_dir(self) -> Path:
        return self.root / "assignments"

    @property
    def active_pointer(self) -> Path:
        return self.root / "active.yaml"

    @property
    def escalations_dir(self) -> Path:
        return self.root / "escalations"

    @property
    def audit_dir(self) -> Path:
        return self.root / "audit"

    def assignment_file(self, assignment_id: str) -> Path:
        return self.assignments_dir / f"{assignment_id}.yaml"

    def escalation_file(self, escalation_id: str) -> Path:
        return self.escalations_dir / f"{escalation_id}.yaml"

    def exists(self) -> bool:
        return self.manifest.is_file()

    def ensure_directories(self) -> None:
        for directory in (
            self.root,
            self.packs_dir,
            self.assignments_dir,
            self.escalations_dir,
            self.audit_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


def discover_repo_root(start: Path) -> Path:
    """Walk upward to the nearest directory containing `.projectos/`.

    Falls back to `start` so `init` can run in a directory that has none yet.
    """
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / PROJECTOS_DIR).is_dir():
            return candidate
    return current
