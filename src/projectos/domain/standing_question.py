"""The standing question — every PASS must say what it saw.

Absorbed from TradeOS ``projectos.graph.ledger`` (THREE-KERNELS-RECONCILE).
A green result that cannot say WHAT it checked is a claim, not evidence —
the same doctrine the rule engine applies to agents, applied to the
kernel's own automated passes.

Every PASS an automated node records must answer one standing question:
does what was observed match a known defect class (``KNOWN_CLASS``), match
nothing — with the list of rules actually checked (``NO_MATCH``) — or name
a WATCH candidate worth tracking (``WATCH``)? A PASS without its answer is
refused at construction time; it never reaches a record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from projectos.domain.errors import ValidationError

PASS_ANSWER_KINDS: tuple[str, ...] = ("KNOWN_CLASS", "NO_MATCH", "WATCH")

#: The question itself, verbatim, for surfaces that display the obligation.
STANDING_QUESTION = (
    "Does what you observed match a known defect class (DC-n), no match "
    "(with the list of rules actually checked), or a WATCH candidate worth "
    "naming?"
)


class PassWithoutAnswer(ValidationError):
    """A PASS that does not answer the standing question is not a PASS."""


@dataclass(frozen=True, slots=True)
class PassAnswer:
    """The standing question's answer, attached to every automated PASS.

    kind=KNOWN_CLASS -> ``dc_class`` names the defect class (e.g. "DC-1").
    kind=NO_MATCH    -> ``rules_checked`` lists what was actually checked.
    kind=WATCH       -> ``watch_note`` names the candidate worth watching.
    """

    kind: str
    dc_class: str | None = None
    rules_checked: tuple[str, ...] = ()
    watch_note: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in PASS_ANSWER_KINDS:
            raise PassWithoutAnswer(f"unknown answer kind {self.kind!r}")
        if self.kind == "KNOWN_CLASS" and not self.dc_class:
            raise PassWithoutAnswer("KNOWN_CLASS must name the DC-n class")
        if self.kind == "NO_MATCH" and not self.rules_checked:
            raise PassWithoutAnswer(
                "NO_MATCH must list the rules that were actually checked — "
                "'no match' without the list is 'did not look'"
            )
        if self.kind == "WATCH" and not self.watch_note:
            raise PassWithoutAnswer("WATCH must name the candidate")

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "dc_class": self.dc_class,
            "rules_checked": list(self.rules_checked),
            "watch_note": self.watch_note,
        }
