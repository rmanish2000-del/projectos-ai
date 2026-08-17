"""INBOX authenticity — the trust boundary on the instruction channel.

Every seat takes instructions from files in one Drive folder with no way to
tell an assignment written by an issuer from a file that simply appeared
(assignment INBOX-TRUST-BOUNDARY). This module closes the authenticity half:
a legitimate assignment carries an HMAC-SHA256 stamp computed with a key
that NEVER lives in the folder, and a seat verifies it offline before
acting.

Why HMAC and not the alternatives (Q1, recorded where the code lives):

* A plaintext shared secret in the file leaks by design — anyone who can
  write to the folder can read it, so the first hostile reader owns the
  channel. An HMAC stamp reveals nothing about the key.
* A manifest of expected filenames anchors nowhere — it would live in the
  same unguarded folder, so whoever can write a rogue file can write its
  manifest row too. Same folder, same trust, no boundary.
* A hash chain gives tamper-evidence for history, not authenticity of the
  newest entry: with the genesis and head in the untrusted folder, an
  attacker rebuilds the whole chain. It also authenticates continuity,
  not origin, which is the wrong question here.

HMAC's trust anchor is the KEY, distributed once out-of-band by the founder
and held per-machine OUTSIDE the synced folder (an environment variable or
a local key file). Verification is pure computation on file content — no
network beyond Drive, per the constraint.

Everything fails closed. No key means NOTHING authenticates (refusing to
verify is not the same as passing). A missing or wrong stamp is REFUSED,
and the refusal is written to a report file — a rejected instruction that
nobody hears about is an invisible one.

Tier still binds (scope item 3): authenticity is a different question from
authority. An authenticated file asking for an ESCALATE-ALWAYS act is still
refused by the fence — nothing in this module raises a file's tier, and a
test pins that the fence does not consult authenticity at all.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from pathlib import Path

from projectos.domain.errors import InvariantViolation

#: The stamp line a legitimate assignment carries (conventionally last).
AUTH_PREFIX = "AUTH: HMAC-SHA256 "

#: Environment variable holding the key (wins over the key file).
KEY_ENV_VAR = "PROJECTOS_INBOX_KEY"

#: Fallback key file — deliberately under the user profile, never under a
#: synced folder and never in a repository.
KEY_FILE = Path.home() / ".projectos" / "inbox.key"

VERDICT_AUTHENTIC = "AUTHENTIC"
VERDICT_REFUSED = "REFUSED"


class KeyUnavailable(InvariantViolation):
    """No signing key could be found. Nothing authenticates without it —
    refusing to verify is not the same as a file passing verification."""


@dataclass(frozen=True, slots=True)
class AuthVerdict:
    """One file's authenticity decision, with the reason on the record."""

    path: str
    verdict: str
    reason: str

    @property
    def authentic(self) -> bool:
        return self.verdict == VERDICT_AUTHENTIC

    def report_line(self) -> str:
        return f"{self.verdict}: {Path(self.path).name} — {self.reason}"


def load_key(*, env: str | None = None, key_file: Path | None = None) -> bytes:
    """The key, from the environment or the local key file. Absent = raise."""
    value = env if env is not None else os.environ.get(KEY_ENV_VAR, "")
    if value.strip():
        return value.strip().encode("utf-8")
    source = key_file or KEY_FILE
    if source.exists():
        content = source.read_text(encoding="utf-8").strip()
        if content:
            return content.encode("utf-8")
    raise KeyUnavailable(
        "no INBOX signing key is available",
        detail=(
            f"Set {KEY_ENV_VAR} or write {KEY_FILE}. Without the key nothing "
            "can be verified, and unverifiable is REFUSED, not passed."
        ),
    )


def _canonical_body(text: str) -> tuple[str, str | None]:
    """Split content into (canonical body, stamp hex or None).

    Line endings are normalised because the Drive round-trip and editors
    rewrite them; a signature that breaks on CRLF would train people to
    ignore refusals. The stamp line itself is excluded from the signed body.
    """
    stamp: str | None = None
    kept: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith(AUTH_PREFIX) and stamp is None:
            stamp = line[len(AUTH_PREFIX) :].strip().lower()
            continue
        kept.append(line)
    return "\n".join(kept).strip() + "\n", stamp


def _mac(body: str, key: bytes) -> str:
    return hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_text(text: str, key: bytes) -> str:
    """Return the text with its AUTH stamp appended (replacing any old one)."""
    body, _ = _canonical_body(text)
    return f"{body}{AUTH_PREFIX}{_mac(body, key)}\n"


def verify_text(text: str, key: bytes, *, name: str = "<text>") -> AuthVerdict:
    """Decide one file's authenticity. Never raises for content reasons —
    every content problem is a REFUSED verdict with its reason stated."""
    body, stamp = _canonical_body(text)
    if stamp is None:
        return AuthVerdict(
            path=name,
            verdict=VERDICT_REFUSED,
            reason="no AUTH stamp — an unstamped file in the instruction "
            "channel is an arbitrary file",
        )
    expected = _mac(body, key)
    if not hmac.compare_digest(stamp, expected):
        return AuthVerdict(
            path=name,
            verdict=VERDICT_REFUSED,
            reason="stamp does not match the content — either the body was "
            "altered after signing or the stamp was not made with the "
            "fleet key",
        )
    return AuthVerdict(path=name, verdict=VERDICT_AUTHENTIC, reason="stamp verifies")


def verify_file(path: Path, key: bytes) -> AuthVerdict:
    return verify_text(path.read_text(encoding="utf-8"), key, name=str(path))


def refuse_and_report(verdict: AuthVerdict, reports_dir: Path, *, stamp: str) -> Path | None:
    """Write a refusal to the reports folder. Returns the report path, or
    None when the verdict needs no report.

    Refusal is only half the rule; the other half is that somebody hears it.
    `stamp` is the caller's fleet-clock filename stamp — this module does not
    read the clock itself so the two concerns stay separately testable.
    """
    if verdict.authentic:
        return None
    reports_dir.mkdir(parents=True, exist_ok=True)
    target = reports_dir / f"{stamp}_PROJECTOS_AUTH-REFUSAL.md"
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(verdict.report_line() + "\n")
    return target
