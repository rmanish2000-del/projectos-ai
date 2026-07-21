"""Repository adapters (spec section 11).

Adapters never import one another and never make verification decisions. Each one
declares its capabilities honestly; the kernel fails a rule closed when the
capability it needs is absent.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.errors import UnsupportedCapability
from projectos.domain.evidence import EvidenceRule, RepositoryFact
from projectos.infrastructure.adapters.local_git import LocalGitAdapter


@dataclass(frozen=True, slots=True)
class UnavailableGitHubAdapter:
    """Placeholder for the GitHub adapter, which lands in phase P4.

    It declares no capabilities and raises on every query. That is deliberate: a
    manifest configured for `github` today fails closed with an actionable message
    instead of silently degrading to local-git and producing weaker evidence than
    the acceptance criteria asked for.
    """

    owner: str | None = None
    repo: str | None = None

    def capabilities(self) -> dict[str, bool]:
        return {"pr": False, "ci": False, "artifacts": False}

    def query(self, rule: EvidenceRule) -> RepositoryFact:
        raise UnsupportedCapability(
            f"The github adapter is not implemented in this phase; cannot evaluate "
            f"{rule.type.value}",
            detail=(
                "Set repository.adapter to 'local_git' in .projectos/manifest.yaml, or "
                "wait for the GitHub adapter (spec section 16, phase P4)."
            ),
        )


__all__ = ["LocalGitAdapter", "UnavailableGitHubAdapter"]
