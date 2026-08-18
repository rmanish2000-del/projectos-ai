"""Register count renderer — counts are rendered, never authored.

Spec: REGISTER-COUNT-CHECK-PROPOSAL.md (COWORK, 2026-08-15). A number that
was typed can be wrong; a number that is rendered cannot. Markers like
``{{count:DC-1}}`` replace count literals; this module parses the instance
rows (``| **I-nn** | ...`` under ``## DC-n`` headings), renders every
marker, and FAILS the build on: an unknown marker · a duplicate or missing
instance id · a class with no instances · any surviving bare count literal
in a sentence containing "instances", "classes" or "of the".

Marker keys: ``instances`` (total) · ``classes`` · ``DC-n`` / ``DC-NAME``
(one class; ids may be numbered or word-named, e.g. ``DC-CLAIM``) ·
``enforcement:<text>`` (ranked-table rows whose enforcement cell contains
<text>). Suffix ``|words`` spells the number out (``seven``), because the
register's own voice spells small numbers; ``|Words`` capitalises it for a
sentence-opening position (``Seven``).

Exit codes, per the scanner convention: 0 clean · 1 failures · 2 register
file not found (louder than a finding).
"""

from __future__ import annotations

import itertools
import re
import sys
from pathlib import Path

# Class ids are DC-<word>: numbered (DC-1) or named (DC-CLAIM, appended by
# AIW ruling 2, 2026-08-18 — its class id carries a word, not a number).
_CLASS_HEAD = re.compile(r"^## (DC-\w+)\b")
# An instance row's first cell is the BOLD id (`| **I-33** | ...`), optionally
# decorated (`| **I-27** ⭑ |`). A plain `I-33` in a first cell is a cross-
# reference to an instance, not the instance itself — the live register uses
# exactly that distinction in its secondary-class mapping table.
_INSTANCE_ROW = re.compile(r"^\|\s*\*\*(I-\d+)\*\*[^|]*\|")
_RANKED_ROW = re.compile(r"^\|[^|]*\|\s*\*{0,2}`?(DC-\w+)`?[^|]*\|[^|]*\|([^|]*)\|")
_MARKER = re.compile(r"\{\{count:([^}|]+)(\|[wW]ords)?\}\}")
_ONES = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_WORD_NUMBER = re.compile(
    r"\b(?:(?:" + "|".join(_TENS) + r")(?:-(?:" + "|".join(_ONES[1:10]) + r"))?"
    r"|" + "|".join(_ONES[1:]) + r")\b",
    re.IGNORECASE,
)
_TRIGGERS = ("instances", "classes", "of the")
_NOT_A_COUNT = re.compile(r"I-\d+|DC-\w+|\d{4}-\d{2}-\d{2}|§\s?\d+|\bv\d+\b|\b\d{1,2}:\d{2}\b")


def _words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens - 2] + (f"-{_ONES[ones]}" if ones else "") if n < 100 else str(n)


def parse(text: str) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Instance ids per class (rows under each ## DC-n), and the ranked
    table's enforcement cell per class."""
    classes: dict[str, list[str]] = {}
    enforcement: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        if head := _CLASS_HEAD.match(line):
            current = head.group(1)
            classes.setdefault(current, [])
        elif row := _INSTANCE_ROW.match(line):
            if current is not None:
                classes[current].append(row.group(1))
        elif (ranked := _RANKED_ROW.match(line)) and ranked.group(1) not in enforcement:
            enforcement[ranked.group(1)] = ranked.group(2).strip().lower()
    return classes, enforcement


def counts(classes: dict[str, list[str]], enforcement: dict[str, str]) -> dict[str, int]:
    table = {dc: len(ids) for dc, ids in classes.items()}
    table["instances"] = sum(table.values())
    table["classes"] = len(classes)
    return table


def audit(text: str) -> list[str]:
    """Every failure in the source, each one named. Empty list = clean."""
    classes, _ = parse(text)
    failures = [f"class {dc} has no instances" for dc, ids in classes.items() if not ids]
    all_ids = [i for ids in classes.values() for i in ids]
    duplicates = sorted({x for x in all_ids if all_ids.count(x) > 1})
    failures += [f"duplicate instance id {i}" for i in duplicates]
    numbers = sorted(int(i.split("-")[1]) for i in set(all_ids))
    failures += [
        f"instance id gap: I-{p:02d} -> I-{n:02d}"
        for p, n in itertools.pairwise(numbers)
        if n != p + 1
    ]
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not any(t in line.lower() for t in _TRIGGERS):
            continue
        bare = _NOT_A_COUNT.sub("", _MARKER.sub("", line))
        if re.search(r"\b\d{1,3}\b", bare) or _WORD_NUMBER.search(bare):
            failures.append(
                f"line {lineno}: bare count literal in a counting sentence: {line.strip()[:80]}"
            )
    return failures


def render(text: str) -> str:
    """Render every marker from the rows. Raises ValueError on an unknown
    key — an unrenderable marker is a wrong count waiting to be typed."""
    classes, enforcement = parse(text)
    table = counts(classes, enforcement)

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key.startswith("enforcement:"):
            needle = key.split(":", 1)[1].strip().lower()
            value = sum(1 for cell in enforcement.values() if needle in cell)
        elif key in table:
            value = table[key]
        else:
            raise ValueError(f"unknown marker key {key!r}")
        if not match.group(2):
            return str(value)
        spelled = _words(value)
        # `|Words` capitalises, because a rendered word can open a sentence.
        return spelled[0].upper() + spelled[1:] if match.group(2) == "|Words" else spelled

    return _MARKER.sub(_sub, text)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: python -m projectos.infrastructure.register_render FILE [OUT]")
        return 2
    source = Path(args[0])
    if not source.exists():
        print(f"register not found: {source}")
        return 2
    text = source.read_text(encoding="utf-8")
    failures = audit(text)
    try:
        rendered = render(text)
    except ValueError as exc:
        failures.append(str(exc))
        rendered = None
    for failure in failures:
        print(f"FAIL: {failure}")
    if failures:
        return 1
    if len(args) > 1 and rendered is not None:
        Path(args[1]).write_text(rendered, encoding="utf-8", newline="\n")
    print("register renders clean")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via tests calling main()
    raise SystemExit(main())
