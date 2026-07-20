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
from projectos.domain.state_machine import TRANSITIONS

#: The transition table transcribed independently from spec section 7.2, as
#: (from, event, to, allowed actors). Written out by hand on purpose: deriving the
#: expectation from `TRANSITIONS` made the test self-referential — it read the
#: answer from the same table the implementation reads, so rewiring a destination
#: produced zero failures. This literal is the external witness the frozen core
#: needs, and any divergence between it and the code is a real failure.
#:
#: `None` as the destination means "the status held before ESCALATED".
SPEC_TABLE: tuple[tuple[Status, Event, Status | None, frozenset[Actor]], ...] = (
    (Status.DRAFT, Event.CLASSIFY_OK, Status.READY, frozenset({Actor.KERNEL})),
    (Status.DRAFT, Event.CANCEL, Status.CANCELLED, frozenset({Actor.OWNER, Actor.FOUNDER})),
    (Status.READY, Event.START, Status.ACTIVE, frozenset({Actor.KERNEL})),
    (Status.READY, Event.BLOCK, Status.BLOCKED, frozenset({Actor.KERNEL})),
    (Status.READY, Event.ESCALATE, Status.ESCALATED, frozenset({Actor.KERNEL})),
    (
        Status.ACTIVE,
        Event.SUBMIT,
        Status.EVIDENCE_SUBMITTED,
        frozenset({Actor.EXECUTOR}),
    ),
    (
        Status.ACTIVE,
        Event.ESCALATE,
        Status.ESCALATED,
        frozenset({Actor.EXECUTOR, Actor.OWNER, Actor.KERNEL, Actor.FOUNDER}),
    ),
    (Status.ACTIVE, Event.CANCEL, Status.CANCELLED, frozenset({Actor.FOUNDER})),
    (
        Status.EVIDENCE_SUBMITTED,
        Event.VERIFY_START,
        Status.VERIFYING,
        frozenset({Actor.KERNEL}),
    ),
    (Status.VERIFYING, Event.ALL_CRITERIA_PASS, Status.VERIFIED, frozenset({Actor.KERNEL})),
    (Status.VERIFYING, Event.ANY_CRITERION_FAIL, Status.REJECTED, frozenset({Actor.KERNEL})),
    (Status.VERIFYING, Event.VERIFIER_ERROR, Status.REJECTED, frozenset({Actor.KERNEL})),
    (
        Status.VERIFIED,
        Event.APPROVALS_COMPLETE,
        Status.CLOSED,
        frozenset({Actor.OWNER, Actor.REVIEWER, Actor.FOUNDER, Actor.KERNEL}),
    ),
    (
        Status.VERIFIED,
        Event.REVIEW_REJECT,
        Status.REJECTED,
        frozenset({Actor.REVIEWER, Actor.FOUNDER}),
    ),
    (Status.REJECTED, Event.RESUME, Status.ACTIVE, frozenset({Actor.KERNEL})),
    (Status.BLOCKED, Event.UNBLOCK, Status.READY, frozenset({Actor.KERNEL})),
    (Status.ESCALATED, Event.FOUNDER_RESOLVE_PROCEED, None, frozenset({Actor.FOUNDER})),
    (
        Status.ESCALATED,
        Event.FOUNDER_RESOLVE_CANCEL,
        Status.CANCELLED,
        frozenset({Actor.FOUNDER}),
    ),
    (
        Status.ESCALATED,
        Event.FOUNDER_RESOLVE_RESCOPE,
        Status.CANCELLED,
        frozenset({Actor.FOUNDER}),
    ),
)

#: Rows the kernel adds beyond spec section 7.2. Listing them separately keeps the
#: table above an honest transcription of the spec, and forces any future addition
#: to be declared here rather than slipped in silently.
#:
#: Both exist because the CLI needs them and the spec's own prose implies them:
#: section 7.1 describes BLOCKED as covering "external blocker", which can arise
#: while an assignment is ACTIVE, and section 9.1 trigger 2 covers "blockers the
#: owner cannot clear", which requires escalating from BLOCKED.
KERNEL_EXTENSIONS: tuple[tuple[Status, Event, Status | None, frozenset[Actor]], ...] = (
    (Status.ACTIVE, Event.BLOCK, Status.BLOCKED, frozenset({Actor.OWNER, Actor.KERNEL})),
    (Status.BLOCKED, Event.ESCALATE, Status.ESCALATED, frozenset({Actor.OWNER, Actor.KERNEL})),
)

FULL_TABLE = SPEC_TABLE + KERNEL_EXTENSIONS
LEGAL_PAIRS = {(row[0], row[1]) for row in FULL_TABLE}


def test_implementation_table_matches_the_declared_table_exactly() -> None:
    """No row may be added to or removed from the machine silently.

    Anything the kernel implements must appear either in the spec transcription or
    in the explicitly declared extension list.
    """
    implemented = {(t.from_status, t.event) for t in TRANSITIONS}

    extra = implemented - LEGAL_PAIRS
    missing = LEGAL_PAIRS - implemented

    assert not extra, (
        "transitions in code but neither in spec 7.2 nor declared as a kernel "
        f"extension: {sorted(f'{s.value}+{e.value}' for s, e in extra)}"
    )
    assert not missing, (
        f"declared transitions absent from code: "
        f"{sorted(f'{s.value}+{e.value}' for s, e in missing)}"
    )


def test_kernel_extensions_stay_a_short_declared_list() -> None:
    """A guard against the extension list becoming a place to hide new behaviour."""
    assert len(KERNEL_EXTENSIONS) == 2


@pytest.mark.parametrize(
    "row", FULL_TABLE, ids=lambda r: f"{r[0].value}-{r[1].value}"
)
def test_each_spec_row_resolves_to_its_specified_destination(row) -> None:
    """Destination is asserted against the hand-written spec value, not the code's."""
    from_status, event, to_status, allowed = row
    prior = Status.ACTIVE if to_status is None else None
    expected = Status.ACTIVE if to_status is None else to_status

    for actor in allowed:
        target = state_machine.resolve(from_status, event, actor, prior_status=prior)
        assert target is expected, (
            f"{from_status.value} + {event.value} as {actor.value} landed in "
            f"{target.value}, spec says {expected.value}"
        )


@pytest.mark.parametrize(
    "row", FULL_TABLE, ids=lambda r: f"{r[0].value}-{r[1].value}"
)
def test_actors_outside_the_spec_column_are_refused(row) -> None:
    """The permission column is asserted against the spec, in both directions."""
    from_status, event, to_status, allowed = row
    prior = Status.ACTIVE if to_status is None else None

    for actor in set(Actor) - allowed:
        with pytest.raises(IllegalTransition, match="may not perform"):
            state_machine.resolve(from_status, event, actor, prior_status=prior)


@pytest.mark.parametrize(
    ("status", "event"),
    [pair for pair in itertools.product(Status, Event) if pair not in LEGAL_PAIRS],
    ids=lambda value: value.value if hasattr(value, "value") else str(value),
)
def test_undeclared_transitions_are_rejected(status: Status, event: Event) -> None:
    """Anything not in the spec table fails closed (INV-4)."""
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
