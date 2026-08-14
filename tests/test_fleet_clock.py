"""Fleet time is observed, never believed (FLEET-CLOCK).

The enforcement test for DC-1's time family: every way the clock can fail
must RAISE, because a wrong timestamp sorts and a missing one does not.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from projectos.domain.errors import InvariantViolation
from projectos.infrastructure.fleet_clock import (
    CLOCK_FLOOR,
    IST,
    IST_OFFSET,
    PROPOSED_SKEW_TOLERANCE_SECONDS,
    STAMP_RESOLUTION_SECONDS,
    ClockUnavailable,
    check_stamp_skew,
    now_ist,
    parse_filename_stamp,
    stamp_for_filename,
    stamp_for_report,
)

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

    def test_tolerance_is_required_not_defaulted(self) -> None:
        # A tolerance is a parameter value (ESCALATE-ALWAYS); this module will
        # not invent one, so the argument is keyword-only and mandatory.
        with pytest.raises(TypeError):
            check_stamp_skew(  # type: ignore[call-arg]
                "2026-08-14_1210", datetime(2026, 8, 14, 12, 10, tzinfo=IST)
            )

    def test_proposed_tolerance_is_a_proposal_not_a_default(self) -> None:
        assert PROPOSED_SKEW_TOLERANCE_SECONDS > STAMP_RESOLUTION_SECONDS

    def test_parse_returns_ist(self) -> None:
        assert parse_filename_stamp("2026-08-14_1210").utcoffset() == IST_OFFSET
