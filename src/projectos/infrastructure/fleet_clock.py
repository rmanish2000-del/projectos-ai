"""Fleet time — observed, never believed (assignment FLEET-CLOCK).

Three participants have now been caught getting the time silently wrong:
WARRANT by 5.5 hours (``TZ='Asia/Kolkata' date`` returned GMT with no tzdata
and no error), Chat by 64 minutes (a filename stamp against the real Drive
write time), and Chat three times over by stamping from an assumed clock.
One class: a value believed rather than observed — DC-1, applied to the one
value the whole fleet orders itself by.

**The single source of fleet time is the host system clock, read as an aware
UTC instant and converted once to IST by a FIXED +05:30 offset.**

Why a fixed offset and not ``ZoneInfo("Asia/Kolkata")``: the named-timezone
lookup is exactly what failed WARRANT. A missing tzdata makes it return the
wrong answer with no error, and a dependency that fails silently is worse
than no dependency. India has no DST, so +05:30 is a constant, not an
approximation. tzdata is still consulted when present — but only as a
CROSS-CHECK that can raise, never as the source. Its absence is fine; its
disagreement is a fault.

Everything here fails closed. If the clock cannot be established the helper
RAISES: a wrong timestamp is worse than a missing one, because a wrong one
sorts.

Usage — one function, no options, no timezone argument::

    from projectos.infrastructure.fleet_clock import stamp_for_filename
    name = f"{stamp_for_filename()}_PROJECTOS_MY-ASSIGNMENT.md"
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone

from projectos.domain.errors import InvariantViolation

#: India Standard Time as a fixed offset. India observes no DST, so this is a
#: constant — no database lookup, nothing to be silently absent.
IST_OFFSET = timedelta(hours=5, minutes=30)
IST = timezone(IST_OFFSET, "IST")

#: A clock reporting a time before this is not slow, it is unset — the dead-RTC
#: and fresh-container cases both land near the epoch. Raising here is the whole
#: point: an unset clock otherwise produces a plausible-looking sortable lie.
CLOCK_FLOOR = datetime(2025, 1, 1, tzinfo=UTC)

#: Filename stamps carry minute resolution, so a stamp is up to 59s older than
#: the write it names even on a perfect clock. Any tolerance below this is
#: measuring truncation, not skew.
STAMP_RESOLUTION_SECONDS = 60

#: PROPOSED, NOT IN FORCE. A tolerance is a parameter value, and parameter
#: values are ESCALATE-ALWAYS (domain.tiers) — a founder act, not this module's
#: to set. Nothing here defaults to it: `check_stamp_skew` requires the caller
#: to pass a tolerance explicitly, so this constant is a recommendation you have
#: to reach for deliberately. See the FLEET-CLOCK report for the reasoning.
PROPOSED_SKEW_TOLERANCE_SECONDS = 120

FILENAME_STAMP_FORMAT = "%Y-%m-%d_%H%M"
REPORT_STAMP_FORMAT = "%Y-%m-%d %H:%M"


class ClockUnavailable(InvariantViolation):
    """The time could not be established. Never degrades into a guess."""


def _system_utc() -> datetime:
    return datetime.now(UTC)


def _cross_check_offset(instant: datetime) -> None:
    """Consult tzdata if it is here. Absence is fine — we do not depend on it.
    Disagreement raises: it means the offset rule changed or the data is bad,
    and either way this module's constant can no longer be trusted."""
    try:
        from zoneinfo import ZoneInfo

        zone = ZoneInfo("Asia/Kolkata")
    except Exception:
        return
    observed = instant.astimezone(zone).utcoffset()
    if observed != IST_OFFSET:
        raise ClockUnavailable(
            "tzdata disagrees with the fixed IST offset",
            detail=(
                f"Asia/Kolkata reports {observed} where this module holds "
                f"{IST_OFFSET}. The constant is no longer safe; do not stamp "
                "anything until this is resolved."
            ),
        )


def now_ist(clock: Callable[[], datetime] = _system_utc) -> datetime:
    """The one way to get fleet time. Aware IST, or an exception.

    Raises ClockUnavailable if the clock returns a naive datetime (an instant
    with no offset cannot be converted, only guessed at), a time before
    CLOCK_FLOOR (the clock is unset, not merely wrong), or a time whose offset
    tzdata contradicts.
    """
    try:
        instant = clock()
    except Exception as exc:
        raise ClockUnavailable("the system clock could not be read", detail=str(exc)) from exc

    if not isinstance(instant, datetime):
        raise ClockUnavailable(f"the clock returned {type(instant).__name__}, not a datetime")
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ClockUnavailable(
            "the clock returned a naive datetime",
            detail=(
                "An instant with no offset cannot be converted to IST, only "
                "guessed at. This is the WARRANT failure: a timezone requested "
                "and silently ignored."
            ),
        )

    utc_instant = instant.astimezone(UTC)
    if utc_instant < CLOCK_FLOOR:
        raise ClockUnavailable(
            "the system clock is unset",
            detail=(
                f"reported {utc_instant.isoformat()}, before the floor "
                f"{CLOCK_FLOOR.isoformat()}. An unset clock produces a "
                "plausible-looking timestamp that sorts wrongly forever."
            ),
        )

    _cross_check_offset(utc_instant)
    return utc_instant.astimezone(IST)


def stamp_for_filename(clock: Callable[[], datetime] = _system_utc) -> str:
    """`YYYY-MM-DD_HHMM` in IST, for report and assignment filenames."""
    return now_ist(clock).strftime(FILENAME_STAMP_FORMAT)


def stamp_for_report(clock: Callable[[], datetime] = _system_utc) -> str:
    """`YYYY-MM-DD HH:MM IST` for the header line of a report."""
    return f"{now_ist(clock).strftime(REPORT_STAMP_FORMAT)} IST"


@dataclass(frozen=True, slots=True)
class SkewCheck:
    """One filename stamp measured against when the file was actually written."""

    stamp: str
    skew_seconds: float
    tolerance_seconds: int
    within_tolerance: bool

    def describe(self) -> str:
        verdict = "within" if self.within_tolerance else "EXCEEDS"
        return (
            f"{self.stamp}: {self.skew_seconds:.0f}s from the observed write "
            f"time, {verdict} the {self.tolerance_seconds}s tolerance"
        )


def parse_filename_stamp(stamp: str) -> datetime:
    """Read a `YYYY-MM-DD_HHMM` stamp as an aware IST instant."""
    try:
        naive = datetime.strptime(stamp, FILENAME_STAMP_FORMAT)
    except ValueError as exc:
        raise ClockUnavailable(f"{stamp!r} is not a {FILENAME_STAMP_FORMAT} stamp") from exc
    return naive.replace(tzinfo=IST)


def check_stamp_skew(stamp: str, written_at: datetime, *, tolerance_seconds: int) -> SkewCheck:
    """Is a filename's claimed time close enough to when it was really written?

    `tolerance_seconds` is required and has no default: a tolerance is a
    parameter value, which is ESCALATE-ALWAYS. This function will not invent
    one, and refuses a tolerance below the stamp's own minute resolution
    because that measures truncation rather than skew.
    """
    if tolerance_seconds < STAMP_RESOLUTION_SECONDS:
        raise ClockUnavailable(
            f"a tolerance of {tolerance_seconds}s is below the "
            f"{STAMP_RESOLUTION_SECONDS}s stamp resolution",
            detail=(
                "Filename stamps carry minutes, so a correct stamp is already "
                "up to 59s behind its write. A tighter tolerance reports "
                "truncation as a defect."
            ),
        )
    if written_at.tzinfo is None or written_at.utcoffset() is None:
        raise ClockUnavailable(
            "the observed write time is naive",
            detail="An unanchored write time cannot be compared, only assumed equal.",
        )

    claimed = parse_filename_stamp(stamp)
    skew = abs((written_at - claimed).total_seconds())
    return SkewCheck(
        stamp=stamp,
        skew_seconds=skew,
        tolerance_seconds=tolerance_seconds,
        within_tolerance=skew <= tolerance_seconds,
    )
