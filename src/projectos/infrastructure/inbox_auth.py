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
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from projectos.domain.errors import InvariantViolation

#: The stamp line a legitimate assignment carries (conventionally last).
#: The value is versioned from day one: ``AUTH: HMAC-SHA256 k1:<hex>``.
#: A fleet living on one eternal key must not be a thing we built on purpose.
AUTH_PREFIX = "AUTH: HMAC-SHA256 "

#: Environment variable holding the keyring (wins over the key file).
#: Format: comma-separated ``id:secret`` entries, e.g. ``k1:abc...,k2:def...``.
KEY_ENV_VAR = "PROJECTOS_INBOX_KEY"

#: Fallback keyring file — deliberately under the user profile, never under a
#: synced folder and never in a repository. One ``id:secret`` entry per line;
#: blank lines and ``#`` comments ignored. THE LAST ENTRY IS THE SIGNING KEY —
#: rotation appends the new key, so "newest last" is the written convention.
KEY_FILE = Path.home() / ".projectos" / "inbox.key"

VERDICT_AUTHENTIC = "AUTHENTIC"
VERDICT_REFUSED = "REFUSED"

#: Rotation, as a procedure rather than a crisis (amendment item 2):
#:   1. Founder generates k2 and APPENDS ``k2:<hex>`` to every seat's keyring
#:      (env var or key file). k1 stays listed.
#:   2. New assignments are signed with k2 automatically — the signing key is
#:      the last-listed entry, and k2 now is.
#:   3. Seats accept BOTH: verification selects the key by the id carried in
#:      the stamp, so k1-stamped files still verify while any remain live.
#:   4. Founder RETIRES k1 by deleting its line — a written act on the keyring,
#:      after which k1 stamps refuse with the unknown-id reason.
#: A seat reports WHICH key verified a file: the verdict carries key_id and
#: report_line() prints it.


class KeyUnavailable(InvariantViolation):
    """No signing key could be found. Nothing authenticates without it —
    refusing to verify is not the same as a file passing verification."""


@dataclass(frozen=True, slots=True)
class AuthVerdict:
    """One file's authenticity decision, with the reason on the record."""

    path: str
    verdict: str
    reason: str
    key_id: str | None = None  # which key verified (or was named by) the stamp

    @property
    def authentic(self) -> bool:
        return self.verdict == VERDICT_AUTHENTIC

    def report_line(self) -> str:
        which = f" [key {self.key_id}]" if self.key_id else ""
        return f"{self.verdict}{which}: {Path(self.path).name} — {self.reason}"


def _parse_keyring_entries(entries: list[str], *, source: str) -> dict[str, bytes]:
    ring: dict[str, bytes] = {}
    for raw in entries:
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        key_id, sep, secret = entry.partition(":")
        key_id, secret = key_id.strip(), secret.strip()
        if not sep or not key_id or not secret or any(c.isspace() for c in key_id):
            raise KeyUnavailable(
                f"malformed keyring entry in {source}",
                detail="Each entry is 'id:secret' with a non-empty, space-free id.",
            )
        ring[key_id] = secret.encode("utf-8")
    return ring


def load_keyring(*, env: str | None = None, key_file: Path | None = None) -> dict[str, bytes]:
    """The keyring, from the environment or the local key file. Absent = raise.

    Returns id -> key in listed order; the LAST entry is the signing key.
    """
    value = env if env is not None else os.environ.get(KEY_ENV_VAR, "")
    if value.strip():
        ring = _parse_keyring_entries(value.split(","), source=KEY_ENV_VAR)
        if ring:
            return ring
    source = key_file or KEY_FILE
    if source.exists():
        ring = _parse_keyring_entries(
            source.read_text(encoding="utf-8").splitlines(), source=str(source)
        )
        if ring:
            return ring
    raise KeyUnavailable(
        "no INBOX signing keyring is available",
        detail=(
            f"Set {KEY_ENV_VAR} (comma-separated id:secret) or write {KEY_FILE} "
            "(one id:secret per line, newest last). Without a keyring nothing "
            "can be verified, and unverifiable is REFUSED, not passed."
        ),
    )


def signing_key(keyring: dict[str, bytes]) -> tuple[str, bytes]:
    """The active signing key: the last-listed entry, by the rotation
    convention that a new key is appended."""
    key_id = next(reversed(keyring))
    return key_id, keyring[key_id]


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
            stamp = line[len(AUTH_PREFIX) :].strip()
            continue
        kept.append(line)
    return "\n".join(kept).strip() + "\n", stamp


def _mac(body: str, key: bytes) -> str:
    return hmac.new(key, body.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_text(text: str, keyring: dict[str, bytes], *, key_id: str | None = None) -> str:
    """Return the text with its versioned AUTH stamp appended (replacing any
    old one). Signs with the last-listed key unless `key_id` names another."""
    body, _ = _canonical_body(text)
    if key_id is None:
        key_id, key = signing_key(keyring)
    else:
        if key_id not in keyring:
            raise KeyUnavailable(f"cannot sign with unknown key id {key_id!r}")
        key = keyring[key_id]
    return f"{body}{AUTH_PREFIX}{key_id}:{_mac(body, key)}\n"


def verify_text(text: str, keyring: dict[str, bytes], *, name: str = "<text>") -> AuthVerdict:
    """Decide one file's authenticity. Never raises for content reasons —
    every content problem is a REFUSED verdict with its reason stated.

    NO ISSUER BYPASS (amendment item 3): this function sees content and keys,
    nothing else. There is no filename, author, issuer or folder parameter,
    so no path can skip verification for a "trusted" source — a Chat-issued
    assignment authenticates exactly like any other file or not at all.
    """
    body, stamp = _canonical_body(text)
    if stamp is None:
        return AuthVerdict(
            path=name,
            verdict=VERDICT_REFUSED,
            reason="no AUTH stamp — an unstamped file in the instruction "
            "channel is an arbitrary file",
        )
    key_id, sep, mac_hex = stamp.partition(":")
    mac_hex = mac_hex.strip().lower()
    if not sep or not key_id or not mac_hex:
        return AuthVerdict(
            path=name,
            verdict=VERDICT_REFUSED,
            reason="stamp carries no key id — the format is "
            "'AUTH: HMAC-SHA256 <id>:<hex>' and an unversioned stamp is "
            "not a valid stamp",
        )
    key = keyring.get(key_id)
    if key is None:
        return AuthVerdict(
            path=name,
            verdict=VERDICT_REFUSED,
            key_id=key_id,
            reason=f"stamp names key {key_id!r}, which this seat does not "
            "hold — either a rotation this machine has not received, or a "
            "forgery",
        )
    if not hmac.compare_digest(mac_hex, _mac(body, key)):
        return AuthVerdict(
            path=name,
            verdict=VERDICT_REFUSED,
            key_id=key_id,
            reason="stamp does not match the content — either the body was "
            "altered after signing or the stamp was not made with the "
            "fleet key",
        )
    return AuthVerdict(
        path=name, verdict=VERDICT_AUTHENTIC, key_id=key_id, reason="stamp verifies"
    )


def verify_file(path: Path, keyring: dict[str, bytes]) -> AuthVerdict:
    return verify_text(path.read_text(encoding="utf-8"), keyring, name=str(path))


#: Registry key for the transition switch (INBOX-KEY-GENERATION item 4).
ENFORCEMENT_PARAM = "INBOX-AUTH-ENFORCEMENT"

MODE_TOLERANT = "tolerant"
MODE_ENFORCING = "enforcing"


def resolve_enforcement(registry_path: Path) -> str:
    """The transition switch: tolerant or enforcing. Founder-flipped only.

    Tolerant is the default — including when the registry or the row is
    absent — because the failure direction is inverted here: an enforcing
    seat with no ordered declaration would refuse every legitimate unsigned
    assignment, which is a seat deciding fleet policy on its own. A
    DECLARED value that is neither known mode is a config error and raises.
    """
    if not registry_path.exists():
        return MODE_TOLERANT
    try:
        declared = json.loads(registry_path.read_text(encoding="utf-8")).get("parameters", {})
    except json.JSONDecodeError:
        return MODE_TOLERANT
    row = declared.get(ENFORCEMENT_PARAM)
    if row is None:
        return MODE_TOLERANT
    value = str(row.get("value", "")).strip().lower()
    if value not in (MODE_TOLERANT, MODE_ENFORCING):
        raise KeyUnavailable(
            f"{ENFORCEMENT_PARAM} declares {row.get('value')!r}, which is neither "
            f"{MODE_TOLERANT!r} nor {MODE_ENFORCING!r}"
        )
    return value


def should_act(verdict: AuthVerdict, mode: str) -> bool:
    """May a seat act on this file, given the transition mode?

    The asymmetry is deliberate: an ABSENT stamp in tolerant mode is a
    legitimate pre-adoption file and may be acted on (the absence is still
    reported); a PRESENT-BUT-WRONG stamp is refused in EVERY mode, because a
    stamp that does not verify is evidence of tampering or a wrong key, and
    no transition excuses that.
    """
    if verdict.authentic:
        return True
    if mode == MODE_ENFORCING:
        return False
    return "no AUTH stamp" in verdict.reason


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


def _ask_console(prompt: str, timeout_seconds: int = 120) -> str:
    """Read one confirmation line from the REAL console input buffer.

    Why not input(): the founder's batch-sign hung at the prompt — in
    ConPTY-backed panes (embedded terminals), sys.stdin reports isatty=True
    yet typed keys never reach the child's stdin pipe, so input() blocks
    forever with no echo. msvcrt reads the console buffer directly (getwche
    echoes each key), and the timeout guarantees the tool can NEVER hang:
    on timeout it returns empty, which the caller treats as decline.
    """
    print(prompt, end="", flush=True)
    try:
        import msvcrt
    except ImportError:  # non-Windows: plain input is fine there
        try:
            return input()
        except (EOFError, KeyboardInterrupt):
            return ""
    import time as _time

    deadline = _time.monotonic() + timeout_seconds
    typed: list[str] = []
    while _time.monotonic() < deadline:
        if not msvcrt.kbhit():
            _time.sleep(0.05)
            continue
        char = msvcrt.getwche()
        if char in ("\r", "\n"):
            print()
            return "".join(typed)
        if char == "\x03":  # Ctrl+C
            print()
            return ""
        if char == "\x08":  # backspace
            if typed:
                typed.pop()
                print(" \b", end="", flush=True)
            continue
        typed.append(char)
    print("\n(no input within the timeout - treating as decline; "
          "use --vouch for the non-interactive path)")
    return ""


def batch_sign(
    inbox_dir: Path,
    keyring: dict[str, bytes],
    *,
    ask: Callable[[str], str] = _ask_console,
    vouch: bool = False,
) -> int:
    """ONE vouching act over the INBOX (assignment BATCH-SIGN).

    Lists every currently unsigned file with its title, asks for one explicit
    confirmation, then stamps them all. It is an authorization, not a rubber
    stamp: the founder sees exactly what he vouches for before anything is
    signed, a declined confirmation stamps NOTHING, and no file outside the
    named directory is ever touched (top level only, no recursion).

    A file whose stamp is PRESENT BUT WRONG is never quietly re-signed —
    tampering evidence is reported, not papered over.

    Exit codes: 0 all candidates stamped · 1 something needs attention (a
    bad-stamp file present, or a write failed — each named) · 3 declined,
    nothing stamped.
    """
    if not inbox_dir.is_dir():
        print(f"BLOCKED: {inbox_dir} is not a directory")
        return 2
    unsigned: list[Path] = []
    suspect: list[AuthVerdict] = []
    for path in sorted(inbox_dir.glob("*.md")):
        verdict = verify_text(path.read_text(encoding="utf-8"), keyring, name=str(path))
        if verdict.authentic:
            continue
        if "no AUTH stamp" in verdict.reason:
            unsigned.append(path)
        else:
            suspect.append(verdict)

    for verdict in suspect:
        print(f"NOT SIGNING (needs eyes, not a stamp): {verdict.report_line()}")
    if not unsigned:
        print("nothing unsigned to stamp")
        return 1 if suspect else 0

    print(f"About to vouch for {len(unsigned)} file(s):")
    for number, path in enumerate(unsigned, start=1):
        first = path.read_text(encoding="utf-8").splitlines()
        title = first[0].strip() if first else "(empty file)"
        print(f"  {number:2d}. {path.name} - {title[:90]}")
    if vouch:
        # The flag IS the deliberate act (--vouch): same listing shown, no
        # console read to go wrong. Built after the interactive prompt hung
        # at the founder's terminal (BATCH-SIGN-FIXED).
        print(f"--vouch given: stamping all {len(unsigned)} listed files")
    else:
        answer = ask(
            f"Type SIGN to stamp ALL {len(unsigned)} listed files; anything else aborts: "
        )
        if answer.strip() != "SIGN":
            print("declined - nothing stamped")
            return 3

    failures = 0
    for path in unsigned:
        try:
            path.write_text(sign_text(path.read_text(encoding="utf-8"), keyring), encoding="utf-8")
            print(f"signed: {path.name} [key {signing_key(keyring)[0]}]")
        except OSError as exc:
            failures += 1
            print(f"FAILED to stamp {path.name}: {exc}")
    return 1 if (failures or suspect) else 0


def main(argv: list[str] | None = None) -> int:
    """`python -m projectos.infrastructure.inbox_auth {sign|verify|batch-sign} PATH`.

    sign       — stamp FILE in place with the fleet key. Prints one status
                 line; NEVER the key.
    verify     — print the verdict line and the transition mode's decision.
                 Exit 0 when the seat may act, 2 when it must refuse.
    batch-sign — list every unsigned file in DIR, confirm once, stamp all
                 (the founder's one vouching act; see batch_sign).
    """
    args = list(sys.argv[1:] if argv is None else argv)
    vouch = "--vouch" in args
    args = [a for a in args if a != "--vouch"]
    if len(args) != 2 or args[0] not in ("sign", "verify", "batch-sign"):
        print(
            "usage: python -m projectos.infrastructure.inbox_auth "
            "{sign|verify|batch-sign} PATH [--vouch]"
        )
        return 2
    command, target = args[0], Path(args[1])
    try:
        keyring = load_keyring()
    except KeyUnavailable as exc:
        print(f"BLOCKED: {exc.message}")
        return 2

    if command == "batch-sign":
        return batch_sign(target, keyring, vouch=vouch)

    if command == "sign":
        signed = sign_text(target.read_text(encoding="utf-8"), keyring)
        target.write_text(signed, encoding="utf-8")
        print(f"signed: {target.name} [key {signing_key(keyring)[0]}]")
        return 0

    verdict = verify_file(target, keyring)
    mode = resolve_enforcement(Path(PARAMETER_REGISTRY_FILE))
    act = should_act(verdict, mode)
    print(verdict.report_line())
    print(f"mode={mode} -> {'ACT' if act else 'REFUSE'}")
    return 0 if act else 2


#: The registry the CLI consults for the transition switch, relative to the
#: working directory (the seat's repo root).
PARAMETER_REGISTRY_FILE = "docs/parameter_registry.json"

if __name__ == "__main__":  # pragma: no cover - exercised via tests calling main()
    raise SystemExit(main())
