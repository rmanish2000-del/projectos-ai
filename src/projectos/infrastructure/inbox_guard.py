"""What the auto-signer must refuse to authenticate, and the incident record.

The auto-signer exists so work the founder directs from his phone stops
stalling: it stamps assignment-shaped files with the fleet key on his behalf.
That convenience has a sharp edge. On 2026-08-21 an assignment-shaped file
asking for a founder-only credential act reached the INBOX and was later
cancelled as `UNAUTHORIZED-FOUNDER-CREDENTIAL-ACT`. Had the signer stamped it
first, the fleet would have carried a genuinely authenticated instruction to
do something no seat may do - and **being genuine is not being authorised**.

So the signer needs a second question after "is this assignment-shaped": *is
this the KIND of thing I may vouch for at all?* Two kinds are refused here:
files that amend or bind the fleet law, and files that request a founder-only
act as executable work.

**A refusal is not a deletion and not a verdict on the file.** It means the
AUTO-SIGNER will not vouch for it; a human may still read it and sign it
deliberately. That asymmetry is why this errs toward refusing: a false
positive costs one human signature, a false negative puts the fleet's own key
behind an act nobody authorised.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: Persistent incident record on Drive. Append-only, and NOT rewritten by a
#: later healthy sweep - the whole point is that a quiet sweep must not erase
#: an unresolved incident.
INCIDENTS_FILENAME = "AUTO-SIGN-INCIDENTS.md"

#: Machine-readable companion, so "is anything unresolved" is a question code
#: can answer rather than a human parsing prose.
INCIDENTS_STATE_FILENAME = "auto-sign-incidents.json"


class RefusalClass(StrEnum):
    """Why the auto-signer would not vouch for a file."""

    LAW_BINDING = "LAW_BINDING"
    FOUNDER_ONLY_ACT = "FOUNDER_ONLY_ACT"
    NO_LEASE_EVIDENCE = "NO_LEASE_EVIDENCE"
    TAMPERED_STAMP = "TAMPERED_STAMP"
    MALFORMED = "MALFORMED"


#: Filename markers that put a file in law-amending territory. The law is
#: amended in batches by Chat or COWORK through a deliberate act; it is never
#: something the signer should authenticate on a sweep.
LAW_NAME_MARKERS: tuple[str, ...] = ("AMENDMENT", "SEAT-BOOT", "LAW-VERSION")

#: Body phrases that assert the file changes or binds the law.
LAW_BODY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bthis (?:file )?amends\b", re.IGNORECASE),
    re.compile(r"\bamend(?:s|ment to)? the (?:fleet )?law\b", re.IGNORECASE),
    re.compile(r"\bbinds? (?:all|every) seats?\b", re.IGNORECASE),
    re.compile(r"\bLAW-VERSION\s*[:=]?\s*\d+\s*(?:->|→|becomes|bump)", re.IGNORECASE),
    re.compile(r"\bsupersedes? (?:the )?(?:current )?law\b", re.IGNORECASE),
)

#: Imperative requests for a founder-only act. Deliberately phrased as
#: REQUESTS - an assignment that merely says "do not create a credential" is
#: describing a boundary, not asking to cross it, and must not be refused for
#: naming the thing it forbids.
FOUNDER_ONLY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(?:give|send|provide|paste|share|print|echo|reveal|tell)\b[^.\n]{0,40}"
            r"\b(?:passphrase|password|api[- ]?key|secret key|private key|token)\b",
            re.IGNORECASE,
        ),
        "asks for a credential to be disclosed",
    ),
    (
        re.compile(
            r"\b(?:rotate|generate|create|issue|revoke)\b[^.\n]{0,30}"
            r"\b(?:credential|api[- ]?key|signing key|passphrase)\b",
            re.IGNORECASE,
        ),
        "asks for a credential act",
    ),
    (
        re.compile(
            r"\b(?:merge|deploy|publish|release)\b[^.\n]{0,30}"
            r"\b(?:PR|pull request|to production|publicly)\b",
            re.IGNORECASE,
        ),
        "asks for a merge, deploy or publish",
    ),
    (
        re.compile(
            r"\b(?:transfer|wire|send|pay|withdraw)\b[^.\n]{0,30}"
            r"(?:\b(?:money|funds|rupees|INR|USD)\b|[$₹]\s?\d)",
            re.IGNORECASE,
        ),
        "asks for money to move",
    ),
)


#: Words that turn a founder-only phrase into a BOUNDARY rather than a request.
#: Every assignment this fleet issues lists what may not be done, in the same
#: vocabulary as doing it - "Do not create, rotate, request or expose a
#: credential" is a fence, not a demand, and a guard that cannot tell the two
#: apart refuses the very assignments that are most careful.
PROHIBITION_MARKERS: tuple[str, ...] = (
    "do not",
    "don't",
    "never",
    "must not",
    "may not",
    "no new",
    "without",
    "refuse",
    "forbidden",
    "not permitted",
    "cannot",
    "prohibited",
)


def is_prohibition(line: str) -> bool:
    """True when this line forbids the act rather than asking for it."""
    lowered = line.lower()
    return any(marker in lowered for marker in PROHIBITION_MARKERS)


@dataclass(frozen=True)
class GuardVerdict:
    """Whether the auto-signer may vouch for this file, and why not."""

    may_sign: bool
    refusal: RefusalClass | None = None
    reason: str = ""

    def line(self, name: str) -> str:
        if self.may_sign:
            return f"OK {name}"
        return f"{self.refusal.value if self.refusal else 'REFUSED'} {name} - {self.reason}"


def classify(text: str, name: str) -> GuardVerdict:
    """Decide whether the auto-signer may vouch for this file.

    Checked in order of how badly a wrong signature would land: binding the
    law first, then founder-only acts.
    """
    upper_name = name.upper()
    if any(marker in upper_name for marker in LAW_NAME_MARKERS):
        return GuardVerdict(
            False,
            RefusalClass.LAW_BINDING,
            f"filename claims law scope ({upper_name}); the law is amended "
            "deliberately in batches, never by a signer sweep",
        )
    for pattern in LAW_BODY_PATTERNS:
        if pattern.search(text):
            return GuardVerdict(
                False,
                RefusalClass.LAW_BINDING,
                "body asserts it amends or binds fleet law",
            )
    for line in text.splitlines():
        if is_prohibition(line):
            continue
        for pattern, why in FOUNDER_ONLY_PATTERNS:
            if pattern.search(line):
                return GuardVerdict(False, RefusalClass.FOUNDER_ONLY_ACT, why)
    return GuardVerdict(True)


@dataclass(frozen=True)
class Incident:
    """One refusal, kept until somebody resolves it."""

    at: str
    name: str
    refusal: str
    reason: str
    resolved: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "at": self.at,
            "name": self.name,
            "refusal": self.refusal,
            "reason": self.reason,
            "resolved": self.resolved,
        }


def load_incidents(reports_dir: Path) -> list[Incident]:
    """Every recorded incident, including the ones already resolved."""
    path = reports_dir / INCIDENTS_STATE_FILENAME
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # A corrupt state file must not read as "nothing is wrong".
        return [
            Incident(
                at="unknown",
                name=INCIDENTS_STATE_FILENAME,
                refusal=RefusalClass.MALFORMED.value,
                reason="incident state file is unreadable; treat as unresolved",
            )
        ]
    return [
        Incident(
            at=str(row.get("at", "")),
            name=str(row.get("name", "")),
            refusal=str(row.get("refusal", "")),
            reason=str(row.get("reason", "")),
            resolved=bool(row.get("resolved", False)),
        )
        for row in raw
    ]


def unresolved(reports_dir: Path) -> list[Incident]:
    return [i for i in load_incidents(reports_dir) if not i.resolved]


def record_incidents(
    reports_dir: Path, new: list[Incident]
) -> list[Incident]:
    """Append incidents and rewrite both records. Never drops an unresolved one.

    The prose file is regenerated from the full state rather than appended to,
    so it can never disagree with the machine-readable record - but it is
    regenerated from EVERY incident, resolved and not, so regeneration is not
    a way for an unresolved incident to vanish.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    existing = load_incidents(reports_dir)
    seen = {(i.at, i.name, i.refusal) for i in existing}
    combined = existing + [i for i in new if (i.at, i.name, i.refusal) not in seen]

    (reports_dir / INCIDENTS_STATE_FILENAME).write_text(
        json.dumps([i.as_dict() for i in combined], indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    open_ones = [i for i in combined if not i.resolved]
    lines = [
        "# AUTO-SIGN INCIDENTS - files the signer refused to vouch for",
        "",
        f"**{len(open_ones)} unresolved** of {len(combined)} recorded.",
        "",
        "A refusal is not a deletion: the file is still there and a human may",
        "sign it deliberately. What the signer will not do is put the fleet key",
        "behind it automatically.",
        "",
    ]
    for incident in reversed(combined):
        mark = "resolved" if incident.resolved else "UNRESOLVED"
        lines.append(
            f"- [{mark}] {incident.at} `{incident.name}` - "
            f"{incident.refusal}: {incident.reason}"
        )
    (reports_dir / INCIDENTS_FILENAME).write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )
    return combined
