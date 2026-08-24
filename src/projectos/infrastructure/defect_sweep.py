"""The standing defect-class sweep — observe and report, never fix.

Absorbed from TradeOS ``projectos.graph.sweep`` (THREE-KERNELS-RECONCILE).
On every run it answers, for one repository: which defect classes are
OPEN, which have NO enforcing test, and whether a NEW instance has
appeared since the last sweep — by actually RUNNING each class's
enforcement test and PARSING the runner's own summary. The observed-fact
rule: a payload parsed, never an exit code trusted; unparseable output is
refused, not called green.

The sweep may only OBSERVE and REPORT. Building a missing test is a
generated assignment's job; a red enforcement test is recorded so the next
cycle carries the failure as its prompt. The sweep itself fixes nothing,
ever — it imports no fixer and writes nothing but observations.

Its output feeds the defect register (a ``last_sweep`` block of OBSERVED
fields only — declarations stay founder-owned, and the file is rewritten
only when observations actually change, so repeated sweeps are
byte-stable) and an append-only NDJSON records file, so the register stays
current without anyone remembering to update it.

Register shape (JSON)::

    {"classes": {"DC-1": {"name": ..., "source": ...,
                          "enforcement_test": "tests/test_dc1.py" | null}}}
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from projectos.domain.standing_question import PassAnswer

SWEEP_NODE = "SWEEP-DC"

#: A runner takes pytest-style args and a cwd, returns combined output text.
Runner = Callable[[Sequence[str], Path], str]


@dataclass(frozen=True, slots=True)
class ClassObservation:
    """One class, one run: only what was actually observed."""

    dc: str
    declared_test: str | None
    test_exists: bool | None  # None when no test is declared
    test_green: bool | None  # None = missing or output unparseable
    detail: str

    def observed_fields(self) -> dict[str, Any]:
        """What the register's last_sweep block records. No timestamps —
        the register only changes when the OBSERVATION changes."""
        return {
            "enforcement_test_exists": self.test_exists,
            "enforcement_green": self.test_green,
        }


@dataclass(frozen=True, slots=True)
class SweepReport:
    """The three standing answers, plus the raw observations."""

    open_classes: tuple[str, ...]
    missing_tests: tuple[str, ...]  # no declared test, or file gone
    new_instances: tuple[str, ...]  # enforcement test RED, parsed
    unknown: tuple[str, ...]  # refused to call green
    observations: tuple[ClassObservation, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "open_classes": list(self.open_classes),
            "missing_tests": list(self.missing_tests),
            "new_instances": list(self.new_instances),
            "unknown": list(self.unknown),
            "observations": [
                {
                    "dc": o.dc,
                    "declared_test": o.declared_test,
                    "test_exists": o.test_exists,
                    "test_green": o.test_green,
                    "detail": o.detail,
                }
                for o in self.observations
            ],
        }

    def standing_answer(self) -> PassAnswer:
        """The whole-repo answer to the standing question, from observations."""
        if self.new_instances:
            return PassAnswer(kind="KNOWN_CLASS", dc_class=",".join(self.new_instances))
        if self.unknown:
            return PassAnswer(
                kind="WATCH",
                watch_note="unparseable enforcement output for: " + ",".join(self.unknown),
            )
        return PassAnswer(
            kind="NO_MATCH",
            rules_checked=tuple(
                f"{o.dc}:{o.declared_test or 'NO TEST DECLARED'}" for o in self.observations
            )
            or ("register empty — no classes declared",),
        )


def parse_runner_summary(output: str) -> tuple[bool | None, str]:
    """The observed-fact reading of a test runner's output: green ONLY on a
    parsed 'N passed' with no failure token; failure tokens are red;
    anything else is refused (None), never green."""
    tail = " ".join(output.strip().splitlines()[-5:])
    if re.search(r"\b\d+ (failed|error)", tail) or "error" in tail.lower():
        return False, tail[-300:]
    match = re.search(r"\b(\d+) passed", tail)
    if match and "failed" not in tail:
        return True, f"{match.group(1)} passed (parsed from runner output)"
    return None, "runner output unparseable — refusing to call it green"


def _default_runner(args: Sequence[str], cwd: Path) -> str:
    # No -q: the host's pytest.ini may already carry one, and -qq suppresses
    # the very summary line the parser reads.
    done = subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    return done.stdout + done.stderr


def run_defect_sweep(
    *,
    repo_root: Path,
    register_path: Path,
    records_path: Path,
    runner: Runner | None = None,
) -> SweepReport:
    """Observe every registered class; report; feed register and records.

    Never fixes: declarations (name, source, instances, enforcement_test)
    are read, compared, and written back byte-identical — only the
    ``last_sweep`` observation block may differ.
    """
    run = runner or _default_runner
    register = json.loads(register_path.read_text(encoding="utf-8"))

    observations: list[ClassObservation] = []
    for dc, row in register.get("classes", {}).items():
        declared = row.get("enforcement_test")
        if declared is None:
            observations.append(
                ClassObservation(
                    dc=dc,
                    declared_test=None,
                    test_exists=None,
                    test_green=None,
                    detail="no enforcing test is declared",
                )
            )
            continue
        test_path = repo_root / declared
        if not test_path.exists():
            observations.append(
                ClassObservation(
                    dc=dc,
                    declared_test=declared,
                    test_exists=False,
                    test_green=None,
                    detail=f"declared test {declared} is GONE from the tree",
                )
            )
            continue
        green, detail = parse_runner_summary(run([declared], repo_root))
        observations.append(
            ClassObservation(
                dc=dc,
                declared_test=declared,
                test_exists=True,
                test_green=green,
                detail=detail,
            )
        )

    report = SweepReport(
        open_classes=tuple(o.dc for o in observations),
        missing_tests=tuple(
            o.dc for o in observations if o.declared_test is None or o.test_exists is False
        ),
        new_instances=tuple(o.dc for o in observations if o.test_green is False),
        unknown=tuple(
            o.dc for o in observations if o.test_exists is True and o.test_green is None
        ),
        observations=tuple(observations),
    )

    # Feed the register: observed fields only, write only on real change.
    before = json.dumps(register, sort_keys=True)
    for obs in observations:
        register["classes"][obs.dc]["last_sweep"] = obs.observed_fields()
    if json.dumps(register, sort_keys=True) != before:
        register_path.write_text(
            json.dumps(register, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    # Append-only sweep record, self-contained: readable years later with no
    # code and no chat in hand. The standing answer rides along; building it
    # through PassAnswer means a malformed answer is refused before writing.
    records_path.parent.mkdir(parents=True, exist_ok=True)
    with records_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "node": SWEEP_NODE,
                    "report": report.as_dict(),
                    "answer": report.standing_answer().as_dict(),
                },
                sort_keys=True,
            )
            + "\n"
        )
    return report
