"""Identifier value objects.

Assignment and escalation identifiers are kernel-issued, monotonically increasing
and zero-padded (`A-0001`, `E-0001`). They are values, not strings: parsing is
total and rejects anything outside the format, so a malformed id can never reach
the state machine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Self

from projectos.domain.errors import ValidationError


@dataclass(frozen=True, order=True, slots=True)
class SequentialId:
    """Base for `<PREFIX>-NNNN` identifiers. Subclasses only set the prefix."""

    prefix: ClassVar[str] = ""
    width: ClassVar[int] = 4

    number: int

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValidationError(f"{type(self).__name__} must be >= 1, got {self.number}")

    @classmethod
    def parse(cls, raw: str) -> Self:
        match = re.match(rf"^{cls.prefix}-(\d{{{cls.width}}})$", raw.strip())
        if match is None:
            raise ValidationError(
                f"Malformed identifier {raw!r}",
                detail=f"Expected {cls.prefix}-NNNN with {cls.width} digits.",
            )
        return cls(int(match.group(1)))

    def next(self) -> Self:
        return type(self)(self.number + 1)

    def __str__(self) -> str:
        return f"{self.prefix}-{self.number:0{self.width}d}"


@dataclass(frozen=True, order=True, slots=True)
class AssignmentId(SequentialId):
    prefix: ClassVar[str] = "A"


@dataclass(frozen=True, order=True, slots=True)
class EscalationId(SequentialId):
    prefix: ClassVar[str] = "E"


FIRST_ASSIGNMENT_ID = AssignmentId(1)
FIRST_ESCALATION_ID = EscalationId(1)
