"""Founder-decision escalation model (spec section 9).

The kernel rejects an escalation without at least two options carrying
consequences. That single rule is what keeps the founder's queue short: an
escalation is a decision to make, not a thought to read.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from projectos.domain.enums import EscalationState, EscalationTrigger, FounderDecision
from projectos.domain.errors import ValidationError
from projectos.domain.ids import AssignmentId, EscalationId

MINIMUM_OPTIONS = 2


@dataclass(frozen=True, slots=True)
class EscalationOption:
    id: str
    description: str
    consequence: str

    def __post_init__(self) -> None:
        if not self.description.strip():
            raise ValidationError(f"Escalation option {self.id} must have a description")
        if not self.consequence.strip():
            raise ValidationError(
                f"Escalation option {self.id} must state its consequence",
                detail="Options without consequences are not decision-ready (spec 9.3).",
            )


@dataclass(frozen=True, slots=True)
class Resolution:
    decision: str
    decided_by: str
    decided_at: str
    outcome: FounderDecision


@dataclass(frozen=True, slots=True)
class Escalation:
    id: EscalationId
    trigger: EscalationTrigger
    summary: str
    options: tuple[EscalationOption, ...]
    schema_version: int = 1
    assignment_id: AssignmentId | None = None
    recommendation: str | None = None
    state: EscalationState = EscalationState.OPEN
    resolution: Resolution | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValidationError(f"Unsupported escalation schema_version {self.schema_version}")
        if not self.summary.strip():
            raise ValidationError(f"{self.id} must carry a decision-ready summary")
        if len(self.options) < MINIMUM_OPTIONS:
            raise ValidationError(
                f"{self.id} must offer at least {MINIMUM_OPTIONS} options",
                detail=(
                    "Escalations without options are rejected so the founder queue "
                    "carries decisions, not commentary (spec 9.3)."
                ),
            )
        option_ids = [option.id for option in self.options]
        if len(set(option_ids)) != len(option_ids):
            raise ValidationError(f"{self.id} has duplicate option ids")
        if self.recommendation is not None and self.recommendation not in option_ids:
            raise ValidationError(
                f"{self.id} recommends unknown option {self.recommendation!r}",
                detail=f"Known options: {', '.join(option_ids)}",
            )
        if self.state is EscalationState.RESOLVED and self.resolution is None:
            raise ValidationError(f"{self.id} is resolved but carries no resolution record")

    @property
    def is_open(self) -> bool:
        return self.state is EscalationState.OPEN

    @property
    def is_project_level(self) -> bool:
        """Project-level escalations block next-assignment generation (spec 9.3)."""
        return self.assignment_id is None

    def option(self, option_id: str) -> EscalationOption | None:
        for option in self.options:
            if option.id == option_id:
                return option
        return None

    def resolved(self, resolution: Resolution) -> Escalation:
        if not self.is_open:
            raise ValidationError(f"{self.id} is already resolved")
        return replace(self, state=EscalationState.RESOLVED, resolution=resolution)
