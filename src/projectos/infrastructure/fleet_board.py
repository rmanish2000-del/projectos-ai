"""One file that tells the truth about where every seat stands.

The founder disabled the whole fleet on 2026-08-31 and was right to: nine
seats waking every twenty minutes is roughly 650 wakes a day, and there was
no single place showing who was doing what. It felt like a black box because
it was one - the evidence existed, but only as 900 lines of per-seat log and
1300 files in a reports folder.

This renders that into one board: a header saying what today has cost, then
one line per seat saying what it is doing, when it last ran, how it went, and
whether it is stuck and why. **One file that tells the truth beats a hundred
that repeat it.** It is rewritten in place, never appended, so it cannot
become the noise it exists to replace.

Every field is read from a primary source, never from another report:
seat and repository from the reviewed task catalogue, last wake and result
from the seat's own local log, consecutive failures from its backoff file,
current assignment from the INBOX itself, and engine sessions from the usage
log the wrapper writes when it actually starts an engine.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from projectos.infrastructure.fleet_clock import now_ist

#: The board lives at the top of the reports folder, one fixed name.
BOARD_FILENAME = "FLEET-BOARD.md"

#: The wrapper's own record of sessions that actually reached an engine.
USAGE_FILENAME = "FLEET-USAGE.md"

#: Consumed files never count as work waiting for a seat.
RETIRED_PREFIXES = ("DONE-", "PARKED-", "SUPERSEDED-", "RPT-")

#: `-RepoRoot <path>` out of a task action, quoted or bare.
REPO_ROOT_RE = re.compile(r'-RepoRoot\s+(?:"([^"]+)"|(\S+))')

#: `-Seat <NAME>`. The seat's real name comes from here, NOT from stripping
#: WAKE- off the task name: the restocker's task is WAKE-CHAT-RESTOCK but its
#: seat is CHAT-AUTO-RESTOCK, so the derived name found no log and the board
#: reported "never" for a seat that had been running.
SEAT_RE = re.compile(r'-Seat\s+(?:"([^"]+)"|(\S+))')

#: `-File <path>\scripts\wake.ps1`. Used to recover the repository when a
#: task omits -RepoRoot and relies on the wrapper's default, as the PROJECTOS
#: and restocker tasks do.
WAKE_FILE_RE = re.compile(r'-File\s+(?:"([^"]+)"|(\S+))')

#: A wrapper log line: `2026-09-01 14:38:02 [SEAT] MESSAGE`.
LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) \[([^\]]+)\] (.*)$")


@dataclass(frozen=True)
class SeatRow:
    """Everything the board says about one seat."""

    seat: str
    repo: str
    assignment: str
    last_wake: str
    last_result: str
    consecutive_failures: int
    blocked: str

    def line(self) -> str:
        blocked = self.blocked or "-"
        return (
            f"| {self.seat} | {self.repo} | {self.assignment} | {self.last_wake} "
            f"| {self.last_result} | {self.consecutive_failures} | {blocked} |"
        )


def seat_repos(catalogue_path: Path) -> dict[str, str]:
    """Seat -> repository root, from the reviewed task catalogue.

    The catalogue is the same file the applier treats as its allow-list, so
    the board and the applier can never disagree about which seats exist.
    """
    try:
        raw = json.loads(catalogue_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}

    found: dict[str, str] = {}
    for row in raw.get("tasks", []):
        name = str(row.get("name", ""))
        if not name.startswith("WAKE-"):
            continue  # AUTO-SIGN and friends are not seats
        args = str(row.get("arguments", ""))

        seat_match = SEAT_RE.search(args)
        seat = (
            (seat_match.group(1) or seat_match.group(2))
            if seat_match
            else name[len("WAKE-") :]
        )

        repo_match = REPO_ROOT_RE.search(args)
        if repo_match:
            repo = repo_match.group(1) or repo_match.group(2)
        else:
            # No -RepoRoot: the task relies on the wrapper's default, so
            # recover the root from the wake script it points at.
            file_match = WAKE_FILE_RE.search(args)
            script = (file_match.group(1) or file_match.group(2)) if file_match else ""
            repo = str(Path(script).parent.parent) if script else "-"
        found[seat] = repo
    return found


def claimable_for(seat: str, inbox_dir: Path) -> str:
    """The oldest INBOX file tagged for this seat or ALL, or 'idle'.

    Deliberately the same rule the wrapper uses to decide whether to start an
    engine, so the board never claims a seat has work the wrapper would skip.
    """
    if not inbox_dir.is_dir():
        return "idle"
    for path in sorted(inbox_dir.glob("*.md")):
        if path.name.startswith(RETIRED_PREFIXES):
            continue
        parts = path.stem.split("_")
        if len(parts) < 4:
            continue
        if parts[2] in (seat, "ALL"):
            return path.name
    return "idle"


def _log_lines(log_path: Path) -> list[tuple[str, str, str]]:
    """(date, time, message) for every well-formed line in a seat log."""
    if not log_path.exists():
        return []
    out: list[tuple[str, str, str]] = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LOG_LINE_RE.match(line.strip())
        if match:
            out.append((match.group(1), match.group(2), match.group(4)))
    return out


def _summarise(message: str) -> str:
    """The outcome word for a log message, short enough to scan."""
    if message.startswith("OK: wake completed"):
        return "OK"
    if message.startswith("SKIP-EMPTY"):
        return "skip (nothing tagged)"
    if message.startswith("SKIP:"):
        return "skip (locked/backoff)"
    if message.startswith("WAKE-FAILURE"):
        return "FAILED: " + message.split("WAKE-FAILURE:", 1)[-1].strip()[:60]
    return message[:60]


def backoff_state(state_dir: Path, seat: str) -> tuple[int, str]:
    """(consecutive failures, blocked reason) from the seat's backoff file."""
    path = state_dir / f"wake-{seat}.backoff.json"
    if not path.exists():
        return 0, ""
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return 0, "backoff file unreadable"
    consecutive = int(raw.get("consecutive", 0) or 0)
    until = raw.get("next_eligible")
    klass = str(raw.get("last_class", "") or "")
    blocked = f"{klass} until {str(until)[:16]}" if until and consecutive else ""
    return consecutive, blocked


def seat_row(seat: str, repo: str, reports_dir: Path, state_dir: Path) -> SeatRow:
    lines = _log_lines(state_dir / f"wake-{seat}.log")
    if lines:
        date, time, message = lines[-1]
        last_wake, last_result = f"{date} {time[:5]}", _summarise(message)
    else:
        last_wake, last_result = "never", "-"
    consecutive, blocked = backoff_state(state_dir, seat)
    return SeatRow(
        seat=seat,
        repo=repo,
        assignment=claimable_for(seat, reports_dir / "INBOX"),
        last_wake=last_wake,
        last_result=last_result,
        consecutive_failures=consecutive,
        blocked=blocked,
    )


def todays_counts(
    reports_dir: Path, state_dir: Path, seats: list[str], *, today: str
) -> tuple[int, int, int]:
    """(wakes today, engine sessions today, skips today), all measured.

    A "wake" is any run that reached the wrapper's logging; an "engine
    session" is one line in the usage log, which the wrapper writes only when
    it has actually started an engine. The gap between the two is the saving.
    """
    wakes = skips = 0
    for seat in seats:
        for date, _, message in _log_lines(state_dir / f"wake-{seat}.log"):
            if date != today:
                continue
            wakes += 1
            if message.startswith(("SKIP-EMPTY", "SKIP:")):
                skips += 1

    sessions = 0
    usage = reports_dir / USAGE_FILENAME
    if usage.exists():
        sessions = sum(
            1
            for line in usage.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.startswith(today)
        )
    return wakes, sessions, skips


def render_board(reports_dir: Path, state_dir: Path, catalogue_path: Path) -> str:
    """The whole board, ready to write."""
    stamp = now_ist()
    today = stamp.strftime("%Y-%m-%d")
    repos = seat_repos(catalogue_path)
    rows = [seat_row(s, r, reports_dir, state_dir) for s, r in sorted(repos.items())]
    wakes, sessions, skips = todays_counts(
        reports_dir, state_dir, sorted(repos), today=today
    )

    working = [r for r in rows if r.assignment != "idle"]
    stuck = [r for r in rows if r.consecutive_failures]

    return "\n".join(
        [
            "# FLEET BOARD",
            "",
            f"**{stamp.strftime('%Y-%m-%d %H:%M IST')}** - "
            f"{len(rows)} seats - {len(working)} with work - {len(stuck)} stuck",
            "",
            f"**Today: {wakes} wakes - {sessions} engine sessions actually spent "
            f"- {skips} skipped free.**",
            "",
            "| Seat | Repo | Assignment | Last wake | Last result | Fails | Blocked |",
            "|---|---|---|---|---|---|---|",
            *[r.line() for r in rows],
            "",
            "Rewritten in place by every wake that starts an engine. A wake that",
            "finds nothing tagged for its seat exits without writing anything at",
            "all, so if this timestamp is old the fleet has simply been quiet -",
            "check the task states before assuming it is broken.",
            "",
        ]
    )


def write_board(reports_dir: Path, state_dir: Path, catalogue_path: Path) -> Path:
    path = reports_dir / BOARD_FILENAME
    path.write_text(
        render_board(reports_dir, state_dir, catalogue_path),
        encoding="utf-8",
        newline="\n",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    """`py -3.11 -m projectos.infrastructure.fleet_board [reports-dir]`."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    reports = Path(args[0]) if args else Path(r"G:\My Drive\AGENT-REPORTS")
    state = Path.home() / ".projectos"
    catalogue = Path(__file__).resolve().parents[3] / "docs" / "fleet_tasks.json"
    try:
        print(write_board(reports, state, catalogue))
    except OSError as exc:
        # A board that cannot be written must never fail a wake.
        print(f"fleet-board: could not write: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
