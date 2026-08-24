"""Fleet time is observed, never believed (FLEET-CLOCK).

The enforcement test for DC-1's time family: every way the clock can fail
must RAISE, because a wrong timestamp sorts and a missing one does not.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from projectos.domain.errors import InvariantViolation
from projectos.infrastructure import fleet_clock
from projectos.infrastructure.fleet_clock import (
    CLOCK_FLOOR,
    IST,
    IST_OFFSET,
    PARAMETER_REGISTRY_PATH,
    STAMP_RESOLUTION_SECONDS,
    TOLERANCE_PARAM,
    ClockUnavailable,
    NotThisSeatsCheck,
    ParameterBlocked,
    check_local_file,
    check_stamp_skew,
    now_ist,
    parse_filename_stamp,
    resolve_tolerance,
    stamp_for_filename,
    stamp_for_report,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# A known instant: 2026-08-14 06:40 UTC is 12:10 IST the same day.
KNOWN_UTC = datetime(2026, 8, 14, 6, 40, tzinfo=UTC)


def _fixed(instant: datetime) -> Callable[[], datetime]:
    return lambda: instant


class TestConversion:
    def test_converts_utc_to_ist_by_fixed_offset(self) -> None:
        result = now_ist(_fixed(KNOWN_UTC))
        assert result.hour == 12
        assert result.minute == 10
        assert result.utcoffset() == IST_OFFSET

    def test_filename_stamp_shape(self) -> None:
        assert stamp_for_filename(_fixed(KNOWN_UTC)) == "2026-08-14_1210"

    def test_report_stamp_shape(self) -> None:
        assert stamp_for_report(_fixed(KNOWN_UTC)) == "2026-08-14 12:10 IST"

    def test_accepts_an_instant_in_any_offset(self) -> None:
        # Same moment expressed in a different offset must yield the same IST.
        elsewhere = KNOWN_UTC.astimezone(timezone(timedelta(hours=-5)))
        assert stamp_for_filename(_fixed(elsewhere)) == "2026-08-14_1210"

    def test_real_clock_works_and_is_aware(self) -> None:
        # Not asserting the value - asserting the real path produces an aware
        # IST instant rather than raising on this machine.
        assert now_ist().utcoffset() == IST_OFFSET


class TestFailsClosed:
    def test_naive_datetime_raises(self) -> None:
        # The WARRANT failure: a timezone requested and silently ignored.
        with pytest.raises(ClockUnavailable):
            now_ist(_fixed(datetime(2026, 8, 14, 6, 40)))

    def test_unset_clock_raises(self) -> None:
        with pytest.raises(ClockUnavailable):
            now_ist(_fixed(datetime(1970, 1, 1, tzinfo=UTC)))

    def test_just_below_the_floor_raises(self) -> None:
        with pytest.raises(ClockUnavailable):
            now_ist(_fixed(CLOCK_FLOOR - timedelta(seconds=1)))

    def test_floor_itself_is_accepted(self) -> None:
        assert now_ist(_fixed(CLOCK_FLOOR)).utcoffset() == IST_OFFSET

    def test_clock_that_throws_raises_clock_unavailable(self) -> None:
        def broken() -> datetime:
            raise OSError("no RTC")

        with pytest.raises(ClockUnavailable):
            now_ist(broken)

    def test_non_datetime_raises(self) -> None:
        with pytest.raises(ClockUnavailable):
            now_ist(lambda: "2026-08-14T12:10")  # type: ignore[arg-type,return-value]

    def test_failure_is_an_invariant_violation(self) -> None:
        # Fails closed in the kernel's own language: exit code 2, never a pass.
        assert issubclass(ClockUnavailable, InvariantViolation)

    def test_no_failure_path_returns_a_value(self) -> None:
        """Every bad input raises; none returns a plausible-looking time."""
        bad_inputs = [
            datetime(2026, 8, 14, 6, 40),
            datetime(1970, 1, 1, tzinfo=UTC),
            CLOCK_FLOOR - timedelta(days=1),
        ]
        for value in bad_inputs:
            with pytest.raises(ClockUnavailable):
                now_ist(_fixed(value))


class TestTzdataCrossCheck:
    def test_agrees_with_tzdata_when_present(self) -> None:
        # tzdata is a cross-check, not the source: when it is here it must
        # agree, and on this machine it either agrees or is absent.
        try:
            from zoneinfo import ZoneInfo

            observed = KNOWN_UTC.astimezone(ZoneInfo("Asia/Kolkata")).utcoffset()
        except Exception:
            pytest.skip("tzdata not available - absence is fine by design")
        assert observed == IST_OFFSET

    def test_absence_of_tzdata_does_not_break_the_clock(self, monkeypatch) -> None:
        # Simulate a machine with no tzdata: the helper must still work,
        # because it does not depend on the lookup that failed WARRANT.
        import builtins

        real_import = builtins.__import__

        def no_zoneinfo(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "zoneinfo":
                raise ImportError("no tzdata here")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", no_zoneinfo)
        assert stamp_for_filename(_fixed(KNOWN_UTC)) == "2026-08-14_1210"


class TestSkewCheck:
    def test_stamp_matching_its_write_time_is_within_tolerance(self) -> None:
        written = datetime(2026, 8, 14, 12, 10, 30, tzinfo=IST)
        check = check_stamp_skew("2026-08-14_1210", written, tolerance_seconds=120)
        assert check.within_tolerance
        assert check.skew_seconds == 30

    def test_the_chat_64_minute_case_is_a_defect(self) -> None:
        written = datetime(2026, 8, 14, 13, 14, tzinfo=IST)
        check = check_stamp_skew("2026-08-14_1210", written, tolerance_seconds=120)
        assert not check.within_tolerance
        assert check.skew_seconds == 64 * 60
        assert "EXCEEDS" in check.describe()

    def test_the_warrant_five_and_a_half_hour_case_is_a_defect(self) -> None:
        # A stamp written from GMT while claiming IST lands 5.5h out.
        written = datetime(2026, 8, 14, 17, 40, tzinfo=IST)
        check = check_stamp_skew("2026-08-14_1210", written, tolerance_seconds=120)
        assert not check.within_tolerance
        assert check.skew_seconds == 5.5 * 3600

    def test_skew_is_symmetric(self) -> None:
        early = check_stamp_skew(
            "2026-08-14_1210", datetime(2026, 8, 14, 12, 0, tzinfo=IST), tolerance_seconds=600
        )
        late = check_stamp_skew(
            "2026-08-14_1210", datetime(2026, 8, 14, 12, 20, tzinfo=IST), tolerance_seconds=600
        )
        assert early.skew_seconds == late.skew_seconds == 600

    def test_compares_across_offsets(self) -> None:
        written_utc = datetime(2026, 8, 14, 6, 40, tzinfo=UTC)  # == 12:10 IST
        check = check_stamp_skew("2026-08-14_1210", written_utc, tolerance_seconds=120)
        assert check.skew_seconds == 0

    def test_naive_write_time_raises(self) -> None:
        with pytest.raises(ClockUnavailable):
            check_stamp_skew(
                "2026-08-14_1210",
                datetime(2026, 8, 14, 12, 10),
                tolerance_seconds=120,
            )

    def test_malformed_stamp_raises(self) -> None:
        with pytest.raises(ClockUnavailable):
            check_stamp_skew(
                "14-08-2026_1210", datetime(2026, 8, 14, 12, 10, tzinfo=IST), tolerance_seconds=120
            )

    def test_tolerance_below_stamp_resolution_raises(self) -> None:
        # Below 60s you are measuring minute-truncation, not skew.
        with pytest.raises(ClockUnavailable):
            check_stamp_skew(
                "2026-08-14_1210", datetime(2026, 8, 14, 12, 10, tzinfo=IST), tolerance_seconds=30
            )

    def test_declared_tolerance_is_not_a_module_default(self) -> None:
        # The founder declared 120s, but the module still holds no default:
        # the value lives in the registry and is resolved, never assumed.
        assert not hasattr(fleet_clock, "DEFAULT_TOLERANCE_SECONDS")
        assert fleet_clock.TOLERANCE_PARAM == "FLEET-CLOCK-SKEW-TOLERANCE"

    def test_tolerance_is_required_not_defaulted(self) -> None:
        # A tolerance is a parameter value (ESCALATE-ALWAYS); this module will
        # not invent one, so the argument is keyword-only and mandatory.
        with pytest.raises(TypeError):
            check_stamp_skew(  # type: ignore[call-arg]
                "2026-08-14_1210", datetime(2026, 8, 14, 12, 10, tzinfo=IST)
            )

    def test_the_declared_tolerance_clears_the_resolution_floor(self) -> None:
        # The founder's reason is the resolution argument: one minute is what
        # the stamp can express, so the value must leave slack above it.
        assert resolve_tolerance(REPO_ROOT / PARAMETER_REGISTRY_PATH) > STAMP_RESOLUTION_SECONDS

    def test_parse_returns_ist(self) -> None:
        assert parse_filename_stamp("2026-08-14_1210").utcoffset() == IST_OFFSET


class TestDeclaredTolerance:
    """The value is the founder's policy, resolved — never this module's guess."""

    def test_resolves_the_declared_value_from_the_shipped_registry(self) -> None:
        assert resolve_tolerance(REPO_ROOT / PARAMETER_REGISTRY_PATH) == 120

    def test_the_shipped_row_is_policy_declared_with_a_reason(self) -> None:
        row = json.loads((REPO_ROOT / PARAMETER_REGISTRY_PATH).read_text(encoding="utf-8"))[
            "parameters"
        ][TOLERANCE_PARAM]
        assert row["status"] == "policy_declared"
        assert row["declared_by"] == "founder"
        assert row["reason"].strip()
        # The measurement is evidence consulted, never the basis - a value
        # fitted to a distribution is a fitted parameter wearing a policy label.
        assert "resolution" in row["basis"].lower()
        assert "not the basis" in row["evidence_consulted"]["note"].lower()

    def test_missing_registry_is_blocked_not_defaulted(self, tmp_path: Path) -> None:
        with pytest.raises(ParameterBlocked):
            resolve_tolerance(tmp_path / "absent.json")

    def test_missing_key_is_blocked(self, tmp_path: Path) -> None:
        path = tmp_path / "reg.json"
        path.write_text(json.dumps({"parameters": {}}), encoding="utf-8")
        with pytest.raises(ParameterBlocked):
            resolve_tolerance(path)

    def test_non_integer_declaration_is_blocked(self, tmp_path: Path) -> None:
        path = tmp_path / "reg.json"
        path.write_text(
            json.dumps({"parameters": {TOLERANCE_PARAM: {"value": "soonish"}}}), encoding="utf-8"
        )
        with pytest.raises(ParameterBlocked):
            resolve_tolerance(path)

    def test_unreadable_registry_is_blocked(self, tmp_path: Path) -> None:
        path = tmp_path / "reg.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(ParameterBlocked):
            resolve_tolerance(path)


class TestSplitByAnchor:
    """Local files are this seat's to check. Synced files are not."""

    def test_locally_written_file_is_checked(self, tmp_path: Path) -> None:
        target = tmp_path / f"{stamp_for_filename()}_PROJECTOS_EXAMPLE.md"
        target.write_text("written now", encoding="utf-8")
        check = check_local_file(target, tolerance_seconds=120)
        # A file this machine just wrote must be within the declared tolerance;
        # if this ever fails, the local clock really has drifted.
        assert check.within_tolerance

    def test_a_stale_stamp_on_a_local_file_is_caught(self, tmp_path: Path) -> None:
        target = tmp_path / "2026-08-14_1210_PROJECTOS_STALE.md"
        target.write_text("stamped long before it was written", encoding="utf-8")
        check = check_local_file(target, tolerance_seconds=120)
        assert not check.within_tolerance

    def test_synced_file_is_refused_not_measured(self, tmp_path: Path) -> None:
        # The ruling: this seat cannot see the authoring moment for a synced
        # file, so it refuses rather than reporting sync latency as clock error.
        synced_root = tmp_path / "My Drive"
        (synced_root / "AGENT-REPORTS").mkdir(parents=True)
        target = synced_root / "AGENT-REPORTS" / "2026-08-14_1210_ALL_THING.md"
        target.write_text("synced here by the client", encoding="utf-8")
        with pytest.raises(NotThisSeatsCheck):
            check_local_file(target, tolerance_seconds=120, synced_roots=(synced_root,))

    def test_refusal_names_the_owner_of_the_other_half(self, tmp_path: Path) -> None:
        synced_root = tmp_path / "synced"
        synced_root.mkdir()
        target = synced_root / "2026-08-14_1210_ALL_THING.md"
        target.write_text("x", encoding="utf-8")
        with pytest.raises(NotThisSeatsCheck) as caught:
            check_local_file(target, tolerance_seconds=120, synced_roots=(synced_root,))
        assert "Chat-owned" in caught.value.render()

    def test_a_file_outside_the_synced_roots_is_still_checked(self, tmp_path: Path) -> None:
        synced_root = tmp_path / "synced"
        synced_root.mkdir()
        elsewhere = tmp_path / f"{stamp_for_filename()}_PROJECTOS_LOCAL.md"
        elsewhere.write_text("local", encoding="utf-8")
        assert check_local_file(
            elsewhere, tolerance_seconds=120, synced_roots=(synced_root,)
        ).within_tolerance
