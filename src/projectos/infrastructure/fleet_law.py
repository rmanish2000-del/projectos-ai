"""Locate the fleet's current law file by CONTENT, not by filename.

On 2026-08-20 LAW-VERSION 9 was uploaded to the fleet AGENT-REPORTS and landed
as `SEAT-BOOT (1).md` - Google Drive's duplicate-name suffix - while the
predecessor had already been renamed `SUPERSEDED-...`. The canonical title
`SEAT-BOOT.md` therefore did not exist at all, and every seat prompt tells
seats to read the law "by folder and title". For the length of that window the
whole fleet would have woken with no law it could find.

The lesson is not "be careful uploading". It is that **a filename is not an
identifier** when the transport can rename files behind you. The law announces
its own version in its header, so that header is the authority and the filename
is only a hint. This module resolves the law the way a seat should: read every
candidate, believe the header, and refuse an ambiguous answer rather than
guessing which of two files is the law.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

#: Prefixes that mark a file as deliberately NOT the live law. These are the
#: fleet's existing conventions, observed in the reports folder: superseded
#: versions, a failed upload that was explicitly labelled DO-NOT-USE, and
#: cancelled items. A file wearing one of these is never the answer, whatever
#: version its header claims.
RETIRED_PREFIXES: tuple[str, ...] = (
    "SUPERSEDED-",
    "FAILED-UPLOAD-",
    "CANCELLED-",
    "DRAFT-",
)

#: The law states its version in its own first lines, with or without markdown
#: emphasis around it: `**LAW-VERSION: 9**`.
LAW_VERSION_RE = re.compile(r"LAW-VERSION[:\s]+\**\s*(\d+)", re.IGNORECASE)

#: How the law identifies ITSELF. Declaring a LAW-VERSION is not enough to be
#: the law: the founder dashboard reports the current version too, and an
#: early draft of this resolver duly offered the dashboard and the law as
#: rival candidates and refused to choose. A law file carries this name in its
#: filename or in its opening heading - which survives Drive's duplicate
#: suffix, since that only appends to the stem.
LAW_NAME = "SEAT-BOOT"

#: Only the head of a file is scanned. The version belongs at the top; a
#: mention of "LAW-VERSION 7" three hundred lines into a changelog is a
#: reference, not a declaration.
HEAD_BYTES = 4096


class LawUnavailable(RuntimeError):
    """No live law file could be identified, or the answer was ambiguous.

    Raised rather than returning a best guess: a seat that boots on the wrong
    law is worse off than a seat that refuses to boot and says why.
    """


@dataclass(frozen=True)
class LawFile:
    """The resolved law: where it is and what it claims to be."""

    path: Path
    version: int

    def summary(self) -> str:
        return f"LAW-VERSION {self.version} at {self.path.name}"


def _declared_version(path: Path) -> int | None:
    """The LAW-VERSION a file declares in its head, if it is a law file.

    Returns None for anything that merely mentions a version - a report, a
    dashboard, a changelog - because only the law may answer "what is the law".
    """
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:HEAD_BYTES]
    except OSError:
        return None

    identifies_as_law = LAW_NAME in path.name.upper() or LAW_NAME in head[:200].upper()
    if not identifies_as_law:
        return None

    match = LAW_VERSION_RE.search(head)
    return int(match.group(1)) if match else None


def is_retired(name: str) -> bool:
    """True if the filename marks it as explicitly not the live law."""
    return name.startswith(RETIRED_PREFIXES)


def candidates(reports_dir: Path) -> list[LawFile]:
    """Every non-retired file declaring a LAW-VERSION, highest first."""
    found: list[LawFile] = []
    for path in sorted(reports_dir.glob("*.md")):
        if is_retired(path.name):
            continue
        version = _declared_version(path)
        if version is not None:
            found.append(LawFile(path, version))
    return sorted(found, key=lambda f: f.version, reverse=True)


def resolve_law(reports_dir: Path) -> LawFile:
    """The one live law file, or an exception explaining why there isn't one."""
    found = candidates(reports_dir)
    if not found:
        raise LawUnavailable(
            f"no file in {reports_dir} declares a LAW-VERSION - "
            "the fleet has no law it can read"
        )

    top = found[0].version
    tied = [f for f in found if f.version == top]
    if len(tied) > 1:
        names = ", ".join(sorted(f.path.name for f in tied))
        raise LawUnavailable(
            f"LAW-VERSION {top} is declared by more than one live file "
            f"({names}) - refusing to guess which is the law"
        )
    return tied[0]


def main(argv: list[str] | None = None) -> int:
    """`py -3.11 -m projectos.infrastructure.fleet_law <reports-dir>`.

    Prints the resolved law and its version so a wake prompt can name the
    LAW-VERSION it actually read instead of the one it expected to find.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: fleet_law <reports-dir>", file=sys.stderr)
        return 2
    try:
        law = resolve_law(Path(args[0]))
    except LawUnavailable as exc:
        print(f"LAW UNRESOLVED: {exc}", file=sys.stderr)
        return 2
    print(law.summary())
    print(law.path)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
