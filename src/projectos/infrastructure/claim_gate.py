"""Decide whether this seat may claim, by reading LIVE claim state.

On 2026-09-03 two sessions ran the same assignment under one seat name. The
interactive session wrote its claim to the live AGENT-REPORTS folder at
04:05Z. The headless wake wrote its own at 04:08Z - it checks a STAGED
snapshot of the folder, taken at stage-in, so a claim written three minutes
earlier was simply not in what it read. At 04:10Z it moved the assignment to
DONE while the other session kept working for another seventy minutes.

**One-active-per-seat is only as strong as the folder the checker reads.**
Staging exists because the engine's sandbox cannot reach the Drive; it solved
that problem and created this one. So the check moves out of the snapshot and
into the wrapper, which can read the live folder, and it runs at the two
moments that matter: before an engine is started, and again at the instant a
claim is about to be published.

The rule when the live folder cannot be read is fixed and deliberate: **a wake
that cannot see current claims does not take work.** Yielding costs one idle
cycle. Claiming on stale evidence costs duplicated work and two writers on one
artefact.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: Consumed files are never claimable, whatever they are tagged.
RETIRED_PREFIXES = ("DONE-", "PARKED-", "SUPERSEDED-", "RPT-")


class Verdict(StrEnum):
    PROCEED = "PROCEED"  # nothing claims this assignment: take it
    DECLINE = "DECLINE"  # a live claim exists: yield
    UNAVAILABLE = "UNAVAILABLE"  # the live folder could not be read: yield
    NOTHING = "NOTHING"  # nothing tagged for this seat at all


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str
    assignment: str | None = None
    claim: str | None = None

    @property
    def may_claim(self) -> bool:
        return self.verdict is Verdict.PROCEED

    def summary(self) -> str:
        return f"{self.verdict.value}: {self.reason}"


def assignment_key(name: str, seat: str) -> str | None:
    """The part of an assignment name a claim on it must carry.

    `2026-09-03_1420_PROJECTOS_TWO-WRITERS-IMPLEMENTATION-ONLY.md` claimed by
    PROJECTOS becomes `..._PROJECTOS_CLAIM_TWO-WRITERS-IMPLEMENTATION-ONLY.md`,
    so the key is everything after the tag. Returns None when the file is not
    an assignment tagged for this seat.
    """
    stem = name[:-3] if name.endswith(".md") else name
    parts = stem.split("_")
    if len(parts) < 4 or parts[2] not in (seat, "ALL"):
        return None
    return "_".join(parts[3:])


def oldest_claimable(seat: str, inbox_dir: Path) -> str | None:
    """The same rule the wrapper and the board use, so the three never drift."""
    if not inbox_dir.is_dir():
        return None
    for path in sorted(inbox_dir.glob("*.md")):
        if path.name.startswith(RETIRED_PREFIXES):
            continue
        if assignment_key(path.name, seat) is not None:
            return path.name
    return None


def live_claim_for(
    seat: str, key: str, names: list[str], *, ignoring: frozenset[str] = frozenset()
) -> str | None:
    """The newest live claim by this seat on this assignment, if any.

    `ignoring` holds claim files that are OURS - at publish time the claim we
    are about to write is not evidence that someone else got there first.
    """
    suffix = f"_{seat}_CLAIM_{key}.md"
    matches = sorted(n for n in names if n.endswith(suffix) and n not in ignoring)
    return matches[-1] if matches else None


def live_names(reports_dir: Path) -> list[str]:
    """Filenames in the live reports folder, names only - never stat.

    Stat-ing 1700 files on a Drive mount is what made earlier listings take
    minutes; names alone come back in about two seconds.
    """
    with os.scandir(reports_dir) as it:
        return [entry.name for entry in it if entry.is_file()]


def decide(
    seat: str, reports_dir: Path, *, own_claims: frozenset[str] = frozenset()
) -> Decision:
    """May this seat claim its oldest claimable assignment right now?

    Every failure to READ the live folder is UNAVAILABLE, never PROCEED: an
    unreadable folder is exactly the moment a stale snapshot would be most
    tempting and most wrong.
    """
    try:
        if not reports_dir.is_dir():
            return Decision(
                Verdict.UNAVAILABLE,
                f"live reports folder not readable at {reports_dir}; not claiming",
            )
        assignment = oldest_claimable(seat, reports_dir / "INBOX")
        if assignment is None:
            return Decision(Verdict.NOTHING, f"nothing tagged {seat} or ALL in the INBOX")
        names = live_names(reports_dir)
    except OSError as exc:
        return Decision(
            Verdict.UNAVAILABLE, f"live reports folder could not be read ({exc}); not claiming"
        )

    key = assignment_key(assignment, seat)
    assert key is not None  # oldest_claimable only returns tagged files
    existing = live_claim_for(seat, key, names, ignoring=own_claims)
    if existing is not None:
        return Decision(
            Verdict.DECLINE,
            f"{assignment} is already claimed on the live folder by {existing}; yielding",
            assignment=assignment,
            claim=existing,
        )
    return Decision(
        Verdict.PROCEED, f"no live claim on {assignment}", assignment=assignment
    )


#: Exit codes the wrapper reads. 0 and 5 both mean "no engine needed" but for
#: different reasons, and the wrapper logs them differently.
EXIT_PROCEED, EXIT_DECLINE, EXIT_UNAVAILABLE, EXIT_NOTHING = 0, 3, 4, 5


def main(argv: list[str] | None = None) -> int:
    """`py -3.11 -m projectos.infrastructure.claim_gate <reports-dir> <SEAT> [--own NAME ...]`"""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print("usage: claim_gate <reports-dir> <SEAT> [--own CLAIMFILE ...]", file=sys.stderr)
        return EXIT_UNAVAILABLE
    own = frozenset(a for a in args[2:] if a != "--own")
    decision = decide(args[1], Path(args[0]), own_claims=own)
    print(decision.summary())
    return {
        Verdict.PROCEED: EXIT_PROCEED,
        Verdict.DECLINE: EXIT_DECLINE,
        Verdict.UNAVAILABLE: EXIT_UNAVAILABLE,
        Verdict.NOTHING: EXIT_NOTHING,
    }[decision.verdict]


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
