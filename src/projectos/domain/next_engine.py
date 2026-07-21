"""Automatic next-assignment generation (spec section 3.3).

Deterministic by construction: the same state plus the same pack always yields the
same successor. The engine resolves a *template reference* only — it decides what
comes next, not how it is written to disk.

Resolution order, exactly as specified:
  1. the closed assignment's explicit `next` block,
  2. the pack pipeline for the current phase,
  3. otherwise a `NEXT_UNDETERMINED` escalation.

INV-7 holds because the engine returns at most one template: there is no branch
that produces two successors.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.assignment import Assignment
from projectos.domain.enums import Status
from projectos.domain.pack import PackSet

DEFAULT_PHASE = "foundation"


@dataclass(frozen=True, slots=True)
class NextDecision:
    """Either a resolved template, or an undetermined result carrying its reason."""

    template: str | None
    source: str
    reason: str = ""

    @property
    def determined(self) -> bool:
        return self.template is not None


def decide(
    closed: Assignment | None,
    all_assignments: tuple[Assignment, ...],
    packs: PackSet,
    *,
    phase: str = DEFAULT_PHASE,
) -> NextDecision:
    """Resolve the successor for a CLOSED assignment.

    `closed` is None when bootstrapping an empty project: there is no predecessor
    to read a `next` block from, so resolution starts at the pack pipeline.
    """
    if closed is not None and closed.next is not None:
        return NextDecision(closed.next.template, "assignment.next")

    templates = packs.phase_templates(phase)
    if not templates:
        return NextDecision(
            None,
            "pack.pipeline",
            reason=(
                f"No pack declares a pipeline for phase {phase!r}. "
                f"Known phases: {', '.join(packs.phases()) or 'none'}."
            ),
        )

    consumed = _consumed_templates(all_assignments)
    for template in templates:
        if template not in consumed:
            return NextDecision(template, f"pack.pipeline[{phase}]")

    return NextDecision(
        None,
        "pack.pipeline",
        reason=(
            f"Every template in phase {phase!r} has been issued "
            f"({', '.join(templates)}). The phase is complete; declare the next phase "
            "in the pack pipeline or set an explicit `next` block."
        ),
    )


def _consumed_templates(assignments: tuple[Assignment, ...]) -> frozenset[str]:
    """Templates already turned into assignments.

    Cancelled assignments do not consume their template — a cancelled attempt
    should be reissuable, otherwise a rescope would silently skip a pipeline step.
    """
    return frozenset(
        assignment.origin_template
        for assignment in assignments
        if assignment.origin_template is not None and assignment.status is not Status.CANCELLED
    )
