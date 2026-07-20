"""State machine tests (spec section 7.2).

The table is the frozen core, so these tests assert it exhaustively: every legal
transition is reachable, and every combination absent from the table is rejected.
That second assertion is the important one — it is what stops a future edit from
quietly widening the machine.
"""

from __future__ import annotations

import itertools

import pytest

from projectos.domain import state_machine
from projectos.domain.enums import Actor, Event, Status
from projectos.domain.errors import IllegalTransition
from projectos.domain.state_machine import PRIOR_STATE, TRANSITIONS

LEGAL_PAIRS = {(t.from_status, t.event) for t in TRANSITIONS}


@pytest.mark.parametrize(
    "transition", TRANSITIONS, ids=lambda t: f"{t.from_status.value}-{t.event.value}"
)
def test_every_declared_transition_resolves(transition) -> None:
    actor = next(iter(transition.allowed_actors))
    prior = Status.ACTIVE if transition.to_status == PRIOR_STATE else None

    target = state_machine.resolve(
        transition.from_status, transition.event, actor, prior_status=prior
    )

    expected = Status.ACTIVE if transition.to_status == PRIOR_STATE else transition.to_status
    assert target is expected


@pytest.mark.parametrize(
    ("status", "event"),
    [pair for pair in itertools.product(Status, Event) if pair not in LEGAL_PAIRS],
    ids=lambda value: value.value if hasattr(value, "value") else str(value),
)
def test_undeclared_transitions_are_rejected(status: Status, event: Event) -> None:
    """Anything not in the table fails closed (INV-4)."""
    with pytest.raises(IllegalTransition):
        state_machine.resolve(status, event, Actor.KERNEL)


def test_actor_permission_is_enforced() -> None:
    """Only the founder may cancel an ACTIVE assignment (spec 7.2)."""
    with pytest.raises(IllegalTransition, match="may not perform"):
        state_machine.resolve(Status.ACTIVE, Event.CANCEL, Actor.OWNER)

    assert (
        state_machine.resolve(Status.ACTIVE, Event.CANCEL, Actor.FOUNDER) is Status.CANCELLED
    )


def test_terminal_states_have_no_outgoing_transitions() -> None:
    assert state_machine.legal_events(Status.CLOSED) == ()
    assert state_machine.legal_events(Status.CANCELLED) == ()


def test_founder_proceed_requires_a_recorded_prior_status() -> None:
    """Resolving to 'prior state' with no escalation in history fails closed."""
    with pytest.raises(IllegalTransition, match="no prior status"):
        state_machine.resolve(Status.ESCALATED, Event.FOUNDER_RESOLVE_PROCEED, Actor.FOUNDER)


def test_verifier_error_and_criterion_failure_both_reject() -> None:
    """INV-4: an adapter error is never distinguishable from failure in outcome."""
    for event in (Event.ANY_CRITERION_FAIL, Event.VERIFIER_ERROR):
        assert state_machine.resolve(Status.VERIFYING, event, Actor.KERNEL) is Status.REJECTED


def test_only_the_kernel_decides_verification_outcomes() -> None:
    for actor in (Actor.EXECUTOR, Actor.OWNER, Actor.FOUNDER, Actor.REVIEWER):
        with pytest.raises(IllegalTransition):
            state_machine.resolve(Status.VERIFYING, Event.ALL_CRITERIA_PASS, actor)
