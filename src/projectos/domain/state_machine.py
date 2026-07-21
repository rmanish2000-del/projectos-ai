"""Deterministic assignment state machine (spec section 7.2).

The transition table is exhaustive and closed: anything not listed is illegal and
fails closed (INV-4). The machine is a pure function of (status, event, actor) — it
performs no I/O, reads no clock, and holds no state, so the same inputs always
produce the same transition.

`ESCALATED -> prior state` is expressed as a sentinel target resolved by the
caller, because the destination depends on the assignment's own history rather
than on the table.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.enums import Actor, Event, Status
from projectos.domain.errors import IllegalTransition

#: Sentinel target meaning "return to the status held before ESCALATED".
PRIOR_STATE: str = "__prior__"


@dataclass(frozen=True, slots=True)
class Transition:
    from_status: Status
    event: Event
    to_status: Status | str
    allowed_actors: frozenset[Actor]
    note: str = ""

    def permits(self, actor: Actor) -> bool:
        return actor in self.allowed_actors


_K = frozenset
_KERNEL = _K({Actor.KERNEL})
_FOUNDER = _K({Actor.FOUNDER})
_OWNER_OR_FOUNDER = _K({Actor.OWNER, Actor.FOUNDER})

#: The exhaustive transition table. Sourced directly from spec section 7.2 —
#: rows here and rows there must correspond one to one.
TRANSITIONS: tuple[Transition, ...] = (
    Transition(Status.DRAFT, Event.CLASSIFY_OK, Status.READY, _KERNEL, "deps CLOSED, no block"),
    Transition(Status.DRAFT, Event.CANCEL, Status.CANCELLED, _OWNER_OR_FOUNDER),
    Transition(Status.READY, Event.START, Status.ACTIVE, _KERNEL, "enforces INV-1"),
    Transition(Status.READY, Event.BLOCK, Status.BLOCKED, _KERNEL),
    Transition(Status.READY, Event.ESCALATE, Status.ESCALATED, _KERNEL),
    Transition(Status.ACTIVE, Event.SUBMIT, Status.EVIDENCE_SUBMITTED, _K({Actor.EXECUTOR})),
    Transition(
        Status.ACTIVE,
        Event.ESCALATE,
        Status.ESCALATED,
        _K({Actor.EXECUTOR, Actor.OWNER, Actor.KERNEL}),
    ),
    Transition(Status.ACTIVE, Event.CANCEL, Status.CANCELLED, _FOUNDER, "founder only"),
    Transition(Status.ACTIVE, Event.BLOCK, Status.BLOCKED, _K({Actor.OWNER, Actor.KERNEL})),
    Transition(Status.EVIDENCE_SUBMITTED, Event.VERIFY_START, Status.VERIFYING, _KERNEL),
    Transition(Status.VERIFYING, Event.ALL_CRITERIA_PASS, Status.VERIFIED, _KERNEL),
    Transition(Status.VERIFYING, Event.ANY_CRITERION_FAIL, Status.REJECTED, _KERNEL),
    Transition(Status.VERIFYING, Event.VERIFIER_ERROR, Status.REJECTED, _KERNEL, "fail closed"),
    Transition(
        Status.VERIFIED,
        Event.APPROVALS_COMPLETE,
        Status.CLOSED,
        _K({Actor.OWNER, Actor.REVIEWER, Actor.FOUNDER}),
    ),
    Transition(
        Status.VERIFIED,
        Event.REVIEW_REJECT,
        Status.REJECTED,
        _K({Actor.REVIEWER, Actor.FOUNDER}),
    ),
    Transition(Status.REJECTED, Event.RESUME, Status.ACTIVE, _KERNEL, "reasons attached"),
    Transition(Status.BLOCKED, Event.UNBLOCK, Status.READY, _KERNEL, "deps restored"),
    Transition(Status.BLOCKED, Event.ESCALATE, Status.ESCALATED, _K({Actor.OWNER, Actor.KERNEL})),
    Transition(Status.ESCALATED, Event.FOUNDER_RESOLVE_PROCEED, PRIOR_STATE, _FOUNDER),
    Transition(Status.ESCALATED, Event.FOUNDER_RESOLVE_CANCEL, Status.CANCELLED, _FOUNDER),
    Transition(
        Status.ESCALATED,
        Event.FOUNDER_RESOLVE_RESCOPE,
        Status.CANCELLED,
        _FOUNDER,
        "CANCELLED + new DRAFT issued by caller",
    ),
)

_TABLE: dict[tuple[Status, Event], Transition] = {
    (transition.from_status, transition.event): transition for transition in TRANSITIONS
}


def lookup(status: Status, event: Event) -> Transition:
    """Return the transition for (status, event) or raise IllegalTransition."""
    transition = _TABLE.get((status, event))
    if transition is None:
        legal = sorted(e.value for (s, e) in _TABLE if s is status)
        raise IllegalTransition(
            f"Illegal transition: {event.value} is not permitted from {status.value}",
            detail=(
                f"Legal events from {status.value}: {', '.join(legal) or 'none (terminal state)'}"
            ),
        )
    return transition


def resolve(
    status: Status, event: Event, actor: Actor, *, prior_status: Status | None = None
) -> Status:
    """Resolve the destination status, enforcing the actor permission column.

    `prior_status` is required only for founder-proceed resolutions, where the
    destination is the assignment's pre-escalation status.
    """
    transition = lookup(status, event)
    if not transition.permits(actor):
        allowed = ", ".join(sorted(a.value for a in transition.allowed_actors))
        raise IllegalTransition(
            f"Actor {actor.value!r} may not perform {event.value} from {status.value}",
            detail=f"Allowed actors: {allowed}",
        )
    if transition.to_status == PRIOR_STATE:
        if prior_status is None:
            raise IllegalTransition(
                f"Cannot resolve {event.value}: no prior status recorded before escalation",
                detail="The assignment history contains no transition into ESCALATED.",
            )
        return prior_status
    assert isinstance(transition.to_status, Status)
    return transition.to_status


def legal_events(status: Status) -> tuple[Event, ...]:
    """Every event legal from `status`. Used by `status` output and by tests that
    assert the table stays exhaustive."""
    return tuple(sorted((e for (s, e) in _TABLE if s is status), key=lambda e: e.value))
