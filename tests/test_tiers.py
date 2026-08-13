"""The action fence: AUTO / PROPOSE / ESCALATE (THREE-KERNELS-RECONCILE).

The enforcement test for the fence itself: AUTO membership is pinned
against the founder register, ESCALATE-ALWAYS cannot be classified lower,
and unknown kinds fail closed to ESCALATE.
"""

from __future__ import annotations

import pytest

from projectos.domain import tiers
from projectos.domain.errors import InvariantViolation


class TestTierLookup:
    def test_auto_kinds_are_auto(self) -> None:
        for kind in tiers.AUTO_ALLOWLIST:
            assert tiers.tier_of(kind) == tiers.TIER_AUTO

    def test_propose_kinds_are_propose(self) -> None:
        for kind in tiers.PROPOSE_ALLOWLIST:
            assert tiers.tier_of(kind) == tiers.TIER_PROPOSE

    def test_escalate_always_kinds_escalate(self) -> None:
        for kind in tiers.ESCALATE_ALWAYS:
            assert tiers.tier_of(kind) == tiers.TIER_ESCALATE

    def test_unknown_kind_fails_closed_to_escalate(self) -> None:
        assert tiers.tier_of("launch_missiles") == tiers.TIER_ESCALATE
        assert tiers.tier_of("") == tiers.TIER_ESCALATE

    def test_escalate_always_wins_over_any_listing(self) -> None:
        # Even if a kind were ever listed in two places, ESCALATE_ALWAYS is
        # checked first: the strictest tier wins.
        assert tiers.tier_of("widen_allowlist") == tiers.TIER_ESCALATE


class TestRequireTier:
    def test_valid_claim_returns_actual(self) -> None:
        assert tiers.require_tier("read_file", tiers.TIER_AUTO) == tiers.TIER_AUTO

    def test_claiming_auto_for_escalate_always_raises(self) -> None:
        with pytest.raises(tiers.EscalationBypass):
            tiers.require_tier("money", tiers.TIER_AUTO)

    def test_claiming_propose_for_escalate_always_raises(self) -> None:
        with pytest.raises(tiers.EscalationBypass):
            tiers.require_tier("widen_allowlist", tiers.TIER_PROPOSE)

    def test_wrong_but_non_bypass_claim_returns_actual(self) -> None:
        # A too-strict claim is corrected, not raised: only claiming DOWN
        # from ESCALATE-ALWAYS is a bypass.
        assert tiers.require_tier("read_file", tiers.TIER_ESCALATE) == tiers.TIER_AUTO

    def test_bypass_is_an_invariant_violation(self) -> None:
        # The fence speaks the kernel's error language: a bypass attempt maps
        # to exit code 2, like every other invariant break.
        assert issubclass(tiers.EscalationBypass, InvariantViolation)


class TestFounderRegister:
    def test_auto_membership_is_pinned_to_the_register(self) -> None:
        """Widening AUTO without a founder register entry fails the build.

        This is the fence's own enforcement test: every AUTO kind must have
        a written founder act, and every registered act must still be on the
        list (a silent removal is as unaudited as a silent addition).
        """
        registered = {kind for kind, _date, _reason in tiers.AUTHORISED_ALLOWLIST_CHANGES}
        assert set(tiers.AUTO_ALLOWLIST) == registered

    def test_register_entries_carry_date_and_reason(self) -> None:
        for kind, date, reason in tiers.AUTHORISED_ALLOWLIST_CHANGES:
            assert kind
            assert len(date) == 10
            assert date[4] == "-"
            assert date[7] == "-"
            assert reason.strip()

    def test_the_three_tiers_are_disjoint(self) -> None:
        auto = set(tiers.AUTO_ALLOWLIST)
        propose = set(tiers.PROPOSE_ALLOWLIST)
        escalate = set(tiers.ESCALATE_ALWAYS)
        assert not auto & propose
        assert not auto & escalate
        assert not propose & escalate
