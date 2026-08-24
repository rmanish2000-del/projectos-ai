"""The action fence — AUTO / PROPOSE / ESCALATE, allow-listed.

Absorbed from TradeOS ``projectos.graph.tiers`` (THREE-KERNELS-RECONCILE):
the one piece of that pack the kernel had no equivalent for. The state
machine gates WHO may fire a transition; this fence gates WHAT an
autonomous loop may do unprompted.

Every action carries a kind, and its tier decides who acts:

* ``AUTO``     — a loop may do it unprompted. Membership is an allow-list:
  a kind not listed is never AUTO, whatever it claims about itself.
* ``PROPOSE``  — a loop may prepare it and present it; a human starts it.
* ``ESCALATE`` — the founder, always. Not configurable downward.

The ESCALATE-ALWAYS set is structural, not preference: money, deploys,
credentials, any parameter value, rule promotion, legal surfaces, and —
the self-referential one — widening this very allow-list. A fence a loop
can widen for itself is a gate wearing a fence's label.

Widening AUTO is a founder act: the new kind must appear in
``AUTHORISED_ALLOWLIST_CHANGES`` with a date and the founder's reason, in
the same commit. The enforcement test pins AUTO membership against that
register and fails the build otherwise.

The kinds here are domain-neutral (constitution: no domain vocabulary in
the core). A domain's own kinds — trading, publishing, anything — belong
in that project's pack-level fence, layered on top of this one; unknown
kinds ESCALATE here, so the layering fails closed.
"""

from __future__ import annotations

from projectos.domain.errors import InvariantViolation

TIER_AUTO = "AUTO"
TIER_PROPOSE = "PROPOSE"
TIER_ESCALATE = "ESCALATE"

#: The complete AUTO surface. Read-only observation and self-verification —
#: nothing here moves money, mutates state another component depends on, or
#: words a human will rely on without review.
AUTO_ALLOWLIST: tuple[str, ...] = (
    "read_file",
    "run_tests",
    "run_gate",
    "compute_report",
    "write_ledger",
    "retry_failed_gate",
    "defect_sweep",
)

#: Prepared by a loop, started by a human.
PROPOSE_ALLOWLIST: tuple[str, ...] = (
    "draft_commit",
    "draft_document",
    "draft_parameter_proposal",
    "draft_assignment",
)

#: THE ESCALATE TIER, v2 — ratified by the founder 2026-08-18 ~00:05 IST
#: ("ratified", after the eight entries were rendered to him verbatim).
#: Canonical source: DOCS/ESCALATE-TIER-V2.md (COWORK, 2026-08-17). Carried
#: character-for-character by assignment ESCALATE-V2-RATIFIED-CARRY-TO-
#: DOMAIN-TIERS: fixes I-36 / DC-7; closes that document's DC-3 two-copies
#: window. Labels are the verb phrases as written. NO ninth entry, no
#: removal, no rewording — any change is a new founder ratification.
ESCALATE_TIER_V2: tuple[tuple[str, str], ...] = (
    (
        "TRANSMITTING AN ORDER",
        "Sending an instruction to a broker to open, close, modify or cancel a "
        "position, in a live or a paper account. Composing, storing, logging or "
        "displaying an order is not transmission; the boundary is the network "
        "call that leaves this system.",
    ),
    (
        "SETTING A DECIDED-AGAINST VALUE",
        "Setting or changing a value the system compares to when deciding "
        "whether to act: anything in the declaration register, and any "
        "threshold, cap, floor or tolerance a gate or a signal tests against. "
        "A function argument, config key or variable no decision is taken "
        "against is not one; the boundary is whether changing it would change "
        "what the system does, not whether it is called a parameter.",
    ),
    (
        "MOVING MONEY",
        "Committing, spending, refunding or transferring money, or creating an "
        "obligation to. Measuring, estimating, reporting or forecasting cost "
        "is not; the boundary is whether a balance changes.",
    ),
    (
        "EXPOSING SOMETHING OUTSIDE THE FLEET",
        "Making code, content or a service reachable by anyone outside this "
        "fleet — including a preview or staging URL a stranger with the link "
        "can open, and including publishing a package to a registry. Running "
        "it locally, or on a host only this fleet can reach, is not; the "
        "boundary is reachability by a third party, not the word used for the "
        "command.",
    ),
    (
        "GRANTING AN AUTHORISATION",
        "Authenticating as the founder, or creating, rotating, storing or "
        "first-time authorising a credential the founder holds. Using a "
        "connector or session the founder has already authorised for this "
        "seat is not; the boundary is whether a new authorisation is being "
        "granted, not whether a request carries a credential.",
    ),
    (
        "BINDING A RULE ON ANOTHER SEAT",
        "Making a rule binding on a seat other than your own, or amending one "
        "that already binds. Proposing a rule, describing an existing one, or "
        "recording how one was applied is not; the boundary is whether "
        "another seat would be obliged by it. Nothing about marketing, "
        "pricing or a promotional window is on this list.",
    ),
    (
        "ASSERTING A LEGAL POSITION",
        "Stating a legal conclusion, or accepting a legal obligation on the "
        "entity's behalf. Reading, quoting or summarising a published term — "
        "with its source, its date, and the standing note that it is our "
        "reading and not a legal opinion — is not; the boundary is whether a "
        "reader could rely on it as advice.",
    ),
    (
        "WIDENING THE FLEET'S ALLOW-LIST",
        "Adding a tool, network destination or capability a seat did not "
        "previously have. The broker IP whitelist is a different object with "
        "a different owner and is not this entry; say which allow-list you "
        "mean, always.",
    ),
)

#: Machine kind-slugs, mapped to the v2 entry each belongs to. The slugs are
#: lookup keys for `tier_of`; the ENTRIES above are the ratified law. Legacy
#: slugs from the v1 fence stay listed as aliases of their v2 entry so no
#: existing caller's kind silently drops out of the bypass-raise — they are
#: aliases of the eight, not a ninth entry.
ESCALATE_KINDS: dict[str, str] = {
    "transmit_order": "TRANSMITTING AN ORDER",
    "orders": "TRANSMITTING AN ORDER",  # legacy alias
    "decided_against_value": "SETTING A DECIDED-AGAINST VALUE",
    "parameter_value": "SETTING A DECIDED-AGAINST VALUE",  # legacy alias
    "money": "MOVING MONEY",
    "expose_outside_fleet": "EXPOSING SOMETHING OUTSIDE THE FLEET",
    "deploy": "EXPOSING SOMETHING OUTSIDE THE FLEET",  # legacy alias
    "grant_authorisation": "GRANTING AN AUTHORISATION",
    "credentials": "GRANTING AN AUTHORISATION",  # legacy alias
    "login": "GRANTING AN AUTHORISATION",  # legacy alias
    "bind_rule_on_seat": "BINDING A RULE ON ANOTHER SEAT",
    "rule_promotion": "BINDING A RULE ON ANOTHER SEAT",  # legacy alias
    "assert_legal_position": "ASSERTING A LEGAL POSITION",
    "legal": "ASSERTING A LEGAL POSITION",  # legacy alias
    "widen_allowlist": "WIDENING THE FLEET'S ALLOW-LIST",
}

#: The founder, always. Attempting to classify these lower raises — there is
#: no configuration that reaches this tuple. Derived from the kind map so the
#: two can never disagree.
ESCALATE_ALWAYS: tuple[str, ...] = tuple(ESCALATE_KINDS)

#: Founder register for AUTO-list changes: (kind, date, founder_reason).
#: Appending here is the WRITTEN ACT that authorises a widening; the test
#: pins AUTO_ALLOWLIST's exact membership against this register.
_ABSORPTION = "THREE-KERNELS-RECONCILE absorption, founder 'go' 2026-08-13"

AUTHORISED_ALLOWLIST_CHANGES: tuple[tuple[str, str, str], ...] = (
    ("read_file", "2026-08-13", f"initial neutral fence — {_ABSORPTION}"),
    ("run_tests", "2026-08-13", f"initial neutral fence — {_ABSORPTION}"),
    ("run_gate", "2026-08-13", f"initial neutral fence — {_ABSORPTION}"),
    ("compute_report", "2026-08-13", f"initial neutral fence — {_ABSORPTION}"),
    ("write_ledger", "2026-08-13", f"initial neutral fence — {_ABSORPTION}"),
    ("retry_failed_gate", "2026-08-13", f"loop-back edge, ceiling-bound — {_ABSORPTION}"),
    ("defect_sweep", "2026-08-13", f"observe-and-report only — {_ABSORPTION}"),
)


class EscalationBypass(InvariantViolation):
    """Code tried to classify an ESCALATE-ALWAYS kind lower. Always raises."""


def tier_of(kind: str) -> str:
    """The tier for an action kind. Unknown kinds ESCALATE — the fence
    fails closed, never open."""
    if kind in ESCALATE_ALWAYS:
        return TIER_ESCALATE
    if kind in AUTO_ALLOWLIST:
        return TIER_AUTO
    if kind in PROPOSE_ALLOWLIST:
        return TIER_PROPOSE
    return TIER_ESCALATE


def require_tier(kind: str, claimed: str) -> str:
    """Validate a claimed tier against the looked-up one.

    Claiming AUTO or PROPOSE for an ESCALATE-ALWAYS kind raises rather than
    returns: a bypass attempt is an invariant violation, not a configuration.
    """
    actual = tier_of(kind)
    if kind in ESCALATE_ALWAYS and claimed != TIER_ESCALATE:
        raise EscalationBypass(
            f"{kind!r} is ESCALATE-ALWAYS; claiming {claimed!r} is a bypass "
            "attempt, not a configuration"
        )
    return actual
