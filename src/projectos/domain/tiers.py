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

#: The founder, always. Attempting to classify these lower raises — there is
#: no configuration that reaches this tuple.
ESCALATE_ALWAYS: tuple[str, ...] = (
    "money",
    "deploy",
    "credentials",
    "parameter_value",
    "rule_promotion",
    "legal",
    "widen_allowlist",
)

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
