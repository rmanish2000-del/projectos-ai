"""Project manifest model (spec section 5).

Immutable. Construction validates the cross-field rules the JSON Schema cannot
express (founder membership, v0.1 manual-approval requirement).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from projectos.domain.enums import ExecutorType, RepositoryAdapterKind, WorkflowMode
from projectos.domain.errors import ValidationError

#: Kernel-level governed triggers. Packs may ADD to this set, never remove
#: (spec section 5 validation rules, section 7.3).
KERNEL_GOVERNED_TRIGGERS: frozenset[str] = frozenset(
    {
        "frozen_architecture",
        "research_mathematics",
        "risk_model",
        "legal_filing",
        "security_boundary",
        "breaking_contract",
    }
)


@dataclass(frozen=True, slots=True)
class Identity:
    """A human identity. `id` is the value recorded in approvals."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class PackRequirement:
    name: str
    version: str


@dataclass(frozen=True, slots=True)
class RepositoryConfig:
    adapter: RepositoryAdapterKind
    remote: str = "origin"
    default_branch: str = "main"
    github_owner: str | None = None
    github_repo: str | None = None

    def __post_init__(self) -> None:
        if self.adapter is RepositoryAdapterKind.GITHUB and not (
            self.github_owner and self.github_repo
        ):
            raise ValidationError(
                "repository.config.github.owner and .repo are required for the github adapter"
            )


@dataclass(frozen=True, slots=True)
class WorkflowConfig:
    default_mode: WorkflowMode = WorkflowMode.FAST
    governed_triggers: frozenset[str] = KERNEL_GOVERNED_TRIGGERS

    def __post_init__(self) -> None:
        missing = KERNEL_GOVERNED_TRIGGERS - self.governed_triggers
        if missing:
            raise ValidationError(
                "workflow.governed_triggers may add to but never remove kernel triggers",
                detail=f"Missing kernel triggers: {', '.join(sorted(missing))}",
            )


@dataclass(frozen=True, slots=True)
class ApprovalsConfig:
    """v0.1 pins both to `manual`; the kernel has no merge or deploy code path."""

    merge: str = "manual"
    deploy: str = "manual"

    def __post_init__(self) -> None:
        for label, value in (("merge", self.merge), ("deploy", self.deploy)):
            if value != "manual":
                raise ValidationError(
                    f"approvals.{label} must be 'manual' in schema v1, got {value!r}"
                )


@dataclass(frozen=True, slots=True)
class Manifest:
    schema_version: int
    project_id: str
    project_name: str
    description: str
    founder: Identity
    owners: tuple[Identity, ...]
    repository: RepositoryConfig
    packs: tuple[PackRequirement, ...] = ()
    agents: tuple[ExecutorType, ...] = (
        ExecutorType.COWORK,
        ExecutorType.CODE,
        ExecutorType.HUMAN,
    )
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    approvals: ApprovalsConfig = field(default_factory=ApprovalsConfig)
    hash_algorithm: str = "sha256"

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValidationError(f"Unsupported manifest schema_version {self.schema_version}")
        if not self.owners:
            raise ValidationError("manifest.owners must list at least one owner")
        if not self.is_owner(self.founder.id):
            raise ValidationError(
                "manifest.project.founder must also appear in manifest.owners",
                detail=f"Founder {self.founder.id!r} is not an owner.",
            )
        if self.hash_algorithm != "sha256":
            raise ValidationError("audit.hash_algorithm must be 'sha256' in schema v1")

    def is_owner(self, identity_id: str) -> bool:
        return any(owner.id == identity_id for owner in self.owners)

    def is_founder(self, identity_id: str) -> bool:
        return identity_id == self.founder.id
