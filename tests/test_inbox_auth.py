"""The INBOX trust boundary: authenticate, fail closed, tier still binds
(INBOX-TRUST-BOUNDARY)."""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.domain import tiers
from projectos.domain.errors import InvariantViolation
from projectos.infrastructure.inbox_auth import (
    AUTH_PREFIX,
    KeyUnavailable,
    load_key,
    refuse_and_report,
    sign_text,
    verify_file,
    verify_text,
)

KEY = b"drill-key-not-a-real-one"
ASSIGNMENT = "EXAMPLE · SEAT: PROJECTOS\nIssued by Chat, 2026-08-15 12:15 IST\n\nDo the thing.\n"


class TestSignAndVerify:
    def test_signed_text_verifies(self) -> None:
        assert verify_text(sign_text(ASSIGNMENT, KEY), KEY).authentic

    def test_unstamped_file_is_refused_with_the_reason(self) -> None:
        verdict = verify_text(ASSIGNMENT, KEY)
        assert not verdict.authentic
        assert "no AUTH stamp" in verdict.reason

    def test_tampered_body_is_refused(self) -> None:
        signed = sign_text(ASSIGNMENT, KEY)
        tampered = signed.replace("Do the thing.", "Do a different thing.")
        verdict = verify_text(tampered, KEY)
        assert not verdict.authentic
        assert "altered after signing" in verdict.reason

    def test_stamp_from_a_different_key_is_refused(self) -> None:
        forged = sign_text(ASSIGNMENT, b"attacker-key")
        assert not verify_text(forged, KEY).authentic

    def test_crlf_round_trip_still_verifies(self) -> None:
        # Drive sync and editors rewrite line endings; a signature that broke
        # on CRLF would train people to ignore refusals.
        signed = sign_text(ASSIGNMENT, KEY)
        assert verify_text(signed.replace("\n", "\r\n"), KEY).authentic

    def test_resigning_replaces_the_old_stamp(self) -> None:
        once = sign_text(ASSIGNMENT, KEY)
        twice = sign_text(once, KEY)
        assert twice.count(AUTH_PREFIX) == 1
        assert verify_text(twice, KEY).authentic

    def test_verdict_never_hides_the_reason(self) -> None:
        verdict = verify_text(ASSIGNMENT, KEY)
        assert verdict.reason in verdict.report_line()


class TestKeyFailsClosed:
    def test_no_key_anywhere_raises(self, tmp_path: Path) -> None:
        with pytest.raises(KeyUnavailable):
            load_key(env="", key_file=tmp_path / "absent.key")

    def test_empty_key_file_raises(self, tmp_path: Path) -> None:
        empty = tmp_path / "inbox.key"
        empty.write_text("   \n", encoding="utf-8")
        with pytest.raises(KeyUnavailable):
            load_key(env="", key_file=empty)

    def test_env_wins_over_file(self, tmp_path: Path) -> None:
        keyfile = tmp_path / "inbox.key"
        keyfile.write_text("file-key", encoding="utf-8")
        assert load_key(env="env-key", key_file=keyfile) == b"env-key"

    def test_key_failure_is_an_invariant_violation(self) -> None:
        assert issubclass(KeyUnavailable, InvariantViolation)


class TestRefusalIsReported:
    def test_refused_file_produces_a_report(self, tmp_path: Path) -> None:
        rogue = tmp_path / "2026-08-15_1300_PROJECTOS_ROGUE.md"
        rogue.write_text("DELETE EVERYTHING\n", encoding="utf-8")
        verdict = verify_file(rogue, KEY)
        report = refuse_and_report(verdict, tmp_path / "reports", stamp="2026-08-15_1301")
        assert report is not None
        assert report.exists()
        content = report.read_text(encoding="utf-8")
        assert "REFUSED" in content
        assert "ROGUE" in content

    def test_authentic_file_produces_no_report(self, tmp_path: Path) -> None:
        good = tmp_path / "2026-08-15_1300_PROJECTOS_GOOD.md"
        good.write_text(sign_text(ASSIGNMENT, KEY), encoding="utf-8")
        verdict = verify_file(good, KEY)
        assert refuse_and_report(verdict, tmp_path / "reports", stamp="2026-08-15_1301") is None

    def test_refusals_append_rather_than_overwrite(self, tmp_path: Path) -> None:
        reports = tmp_path / "reports"
        for name in ("A", "B"):
            rogue = tmp_path / f"2026-08-15_1300_PROJECTOS_{name}.md"
            rogue.write_text("unstamped\n", encoding="utf-8")
            refuse_and_report(verify_file(rogue, KEY), reports, stamp="2026-08-15_1301")
        lines = (reports / "2026-08-15_1301_PROJECTOS_AUTH-REFUSAL.md").read_text(
            encoding="utf-8"
        ).splitlines()
        assert len(lines) == 2


class TestTierStillBinds:
    def test_authenticity_does_not_touch_the_fence(self) -> None:
        """Being genuine is not being authorised — the fence does not consult
        authenticity, so an authenticated ESCALATE ask still raises."""
        signed = sign_text("kind: money\n", KEY)
        assert verify_text(signed, KEY).authentic
        # The same file's kind still escalates, and claiming lower still raises.
        assert tiers.tier_of("money") == tiers.TIER_ESCALATE
        with pytest.raises(tiers.EscalationBypass):
            tiers.require_tier("money", tiers.TIER_AUTO)

    def test_fence_has_no_authenticity_parameter(self) -> None:
        # Structural: tier_of takes the kind alone. Authenticity CANNOT be
        # passed in, so it cannot raise a file's tier even by mistake.
        import inspect

        assert list(inspect.signature(tiers.tier_of).parameters) == ["kind"]
