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
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from projectos.domain.errors import InvariantViolation
from projectos.infrastructure.fleet_clock import now_ist
from projectos.infrastructure.inbox_guard import (
    INCIDENTS_FILENAME,
    Incident,
    RefusalClass,
    record_incidents,
    unresolved,
)
from projectos.infrastructure.inbox_guard import classify as guard_classify
from projectos.infrastructure.inbox_lease import emitted_under_active_lease

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


class RegistryUnavailable(InvariantViolation):
    """The canonical enforcement registry could not be found.

    This FAILS CLOSED, unlike a missing row inside a registry that exists.
    The distinction is the whole point: a registry that is present and simply
    does not declare the parameter is a fleet that has not switched on yet,
    which is safely tolerant. A registry that cannot be found at all means we
    do not know what the fleet decided - and on 2026-08-20 that state was
    reachable from any seat, because the path was resolved relative to the
    caller's working directory. Four seats verifying from their own repo roots
    would have found no registry, silently defaulted to tolerant, and acted on
    unsigned assignments while the fleet believed itself enforcing.
    """


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
    kbhit = getattr(msvcrt, "kbhit", None)
    getwche = getattr(msvcrt, "getwche", None)
    if not callable(kbhit) or not callable(getwche):
        try:
            return input()
        except (EOFError, KeyboardInterrupt):
            return ""
    import time as _time

    deadline = _time.monotonic() + timeout_seconds
    typed: list[str] = []
    while _time.monotonic() < deadline:
        if not kbhit():
            _time.sleep(0.05)
            continue
        char = getwche()
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


#: Only files named like an assignment are ever auto-signed. A stray note,
#: a draft, a synced conflict copy: none of them get fleet authority.
ASSIGNMENT_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}_[A-Z][A-Z0-9-]*_.+\.md$")

#: Per-sweep ceiling. The largest legitimate burst observed is a handful of
#: assignments issued together, so 5 covers real work; beyond it a runaway
#: writer is THROTTLED and, more importantly, ANNOUNCED — the cap-hit is
#: logged loudly rather than hundreds of files being authorised in silence.
AUTO_SIGN_CAP = 5

#: Instant kill switch: create this file and the next sweep does nothing.
#: A file, not a service stop, so it works with no privileges and reverses
#: by deleting it.
AUTO_SIGN_BRAKE = Path.home() / ".projectos" / "auto-sign.OFF"

#: Machine-local audit log, beside the keyring — never in a repo, never on
#: Drive. This is the record that replaces the founder's read-the-list step.
AUTO_SIGN_LOG = Path.home() / ".projectos" / "auto-sign.log"


@dataclass(frozen=True, slots=True)
class AutoSignResult:
    """One sweep, fully described."""

    braked: bool = False
    signed: tuple[str, ...] = ()
    suspect: tuple[str, ...] = ()  # present-but-wrong stamps: incidents
    skipped_name: tuple[str, ...] = ()  # not assignment-shaped
    deferred: tuple[str, ...] = ()  # over the per-sweep cap
    refused: tuple[str, ...] = ()  # guard or lease refusals: incidents, not noise

    def summary(self) -> str:
        parts = [f"signed={len(self.signed)}"]
        if self.suspect:
            parts.append(f"TAMPERED={len(self.suspect)}")
        if self.deferred:
            parts.append(f"CAP-HIT deferred={len(self.deferred)}")
        if self.skipped_name:
            parts.append(f"skipped-not-assignment={len(self.skipped_name)}")
        return " ".join(parts)


def auto_sign_once(
    inbox_dir: Path,
    keyring: dict[str, bytes],
    *,
    require_lease: bool,
    cap: int = AUTO_SIGN_CAP,
    brake_path: Path | None = None,
    log_path: Path | None = None,
    drive_dir: Path | None = None,
    stamp: str = "",
    now: datetime | None = None,
) -> AutoSignResult:
    """One auto-sign sweep of the INBOX (assignment AUTO-SIGNER).

    Signs newly-arrived UNSIGNED assignment files with the fleet key so work
    the founder directs from his phone stops silently stalling. The trade is
    deliberate and bounded: it removes the human read-the-list step, and what
    replaces it is this function's audit trail — every signature recorded
    locally and on Drive where he can read it from the same phone.

    Bounds, all enforced here rather than trusted to a caller: this directory
    only (no recursion), assignment-named files only, never a second stamp on
    an already-signed file, never a repair of a tampered one (that is an
    incident: logged loudly, left refused), and never more than `cap` in one
    sweep.
    """
    brake = brake_path or AUTO_SIGN_BRAKE
    if brake.exists():
        return AutoSignResult(braked=True)
    if not inbox_dir.is_dir():
        raise InvariantViolation(f"auto-sign: {inbox_dir} is not a directory")
    # Checked up front, not inside the candidate loop. Validating it lazily
    # meant an empty INBOX swept "successfully" with the lease fence asked for
    # and never applied - "enforce the lease but I cannot find it" must fail
    # closed on every sweep, not only on sweeps that happen to have work.
    if require_lease and drive_dir is None:
        raise InvariantViolation(
            "auto-sign: require_lease needs drive_dir to find the writer lease"
        )

    candidates: list[Path] = []
    suspect: list[str] = []
    skipped: list[str] = []
    for path in sorted(inbox_dir.glob("*.md")):
        if not ASSIGNMENT_NAME.match(path.name):
            skipped.append(path.name)
            continue
        verdict = verify_text(path.read_text(encoding="utf-8"), keyring, name=str(path))
        if verdict.authentic:
            continue  # already signed: never stamped twice
        if "no AUTH stamp" in verdict.reason:
            candidates.append(path)
        else:
            suspect.append(f"{path.name} :: {verdict.reason}")

    deferred = [p.name for p in candidates[cap:]]
    signed: list[str] = []
    refused: list[str] = []
    incidents: list[Incident] = []
    moment = now if now is not None else now_ist()

    for path in candidates[:cap]:
        text = path.read_text(encoding="utf-8")

        # Question two, after "is this assignment-shaped": is this the KIND of
        # thing the signer may vouch for at all? Being genuine is not being
        # authorised, so a file that binds the law or asks for a founder-only
        # act is refused BEFORE the key ever touches it.
        guard_verdict = guard_classify(text, path.name)
        if not guard_verdict.may_sign:
            refused.append(guard_verdict.line(path.name))
            incidents.append(
                Incident(
                    at=moment.isoformat(timespec="seconds"),
                    name=path.name,
                    refusal=guard_verdict.refusal.value if guard_verdict.refusal else "REFUSED",
                    reason=guard_verdict.reason,
                )
            )
            continue

        # Question three: was this emitted by whoever holds the INBOX writer
        # lease? A second concurrent orchestrator cannot know the active lease
        # id, so this is what makes "you are second" detectable at all.
        if require_lease:
            assert drive_dir is not None  # validated before the loop
            ok, why = emitted_under_active_lease(text, drive_dir, now=moment)
            if not ok:
                refused.append(f"{RefusalClass.NO_LEASE_EVIDENCE.value} {path.name} - {why}")
                incidents.append(
                    Incident(
                        at=moment.isoformat(timespec="seconds"),
                        name=path.name,
                        refusal=RefusalClass.NO_LEASE_EVIDENCE.value,
                        reason=why,
                    )
                )
                continue

        path.write_text(sign_text(text, keyring), encoding="utf-8")
        signed.append(path.name)

    # A tampered stamp was already an incident in prose; make it one on the
    # record too, so it survives the next quiet sweep like every other.
    incidents += [
        Incident(
            at=moment.isoformat(timespec="seconds"),
            name=item.split(" :: ")[0],
            refusal=RefusalClass.TAMPERED_STAMP.value,
            reason=item,
        )
        for item in suspect
    ]

    result = AutoSignResult(
        signed=tuple(signed),
        suspect=tuple(suspect),
        skipped_name=tuple(skipped),
        deferred=tuple(deferred),
        refused=tuple(refused),
    )
    if drive_dir is not None and incidents:
        record_incidents(drive_dir, incidents)
    _write_auto_sign_trail(result, stamp, log_path or AUTO_SIGN_LOG, drive_dir)
    return result


def _write_auto_sign_trail(
    result: AutoSignResult, stamp: str, log_path: Path, drive_dir: Path | None
) -> None:
    """The audit trail: append-only locally and on Drive, plus a liveness
    marker. A stopped watcher shows as a stale marker rather than silence."""
    lines = [f"{stamp} auto-signed: {name}" for name in result.signed]
    lines += [f"{stamp} TAMPERED STAMP, LEFT REFUSED: {item}" for item in result.suspect]
    if result.deferred:
        lines.append(
            f"{stamp} CAP HIT ({len(result.deferred)} deferred to the next sweep) - "
            f"an unusual burst, check who is writing: {', '.join(result.deferred)}"
        )
    if lines:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(lines) + "\n")
    if drive_dir is None:
        return
    if lines:  # phone-readable audit, appended only when something happened
        drive_log = drive_dir / "AUTO-SIGN-LOG.md"
        header = (
            ""
            if drive_log.exists()
            else "# AUTO-SIGN LOG - signatures made on the founder's behalf\n\n"
        )
        with drive_log.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(header + "\n".join(lines) + "\n")
    # Liveness marker, rewritten every sweep: freshness IS the signal. But
    # rewriting it was ALSO how an unresolved incident disappeared - the next
    # quiet sweep overwrote the only place a refusal was visible. So the status
    # now reads the persistent incident record and carries it forward: the
    # marker refreshes, and refreshing it no longer erases anything.
    open_incidents = unresolved(drive_dir)
    last_signed = result.signed[-1] if result.signed else "none this sweep"
    attempted = list(result.signed) + [line.split(" - ")[0] for line in result.refused]
    last_attempted = attempted[-1] if attempted else "none"
    classes = sorted({line.split(" ", 1)[0] for line in result.refused})
    header = "HEALTHY" if not open_incidents else f"ATTENTION - {len(open_incidents)} unresolved"

    recovery = "nothing to clear" if not open_incidents else f"see {INCIDENTS_FILENAME}"
    status = [
        f"# AUTO-SIGN STATUS - {header}",
        "",
        f"last swept:      {stamp} IST",
        f"last signed:     {last_signed}",
        f"last attempted:  {last_attempted}",
        f"refusal classes: {', '.join(classes) if classes else 'none this sweep'}",
        f"unresolved:      {len(open_incidents)}",
        f"recovery state:  {recovery}",
        "",
        f"sweep summary: {result.summary()}",
        "",
        "A stamp much older than a few minutes means the watcher is STOPPED.",
        f"Kill switch: create {AUTO_SIGN_BRAKE}",
    ]
    if open_incidents:
        status += ["", "## unresolved incidents (carried forward, not re-detected)"]
        status += [f"- {i.at} `{i.name}` - {i.refusal}: {i.reason}" for i in open_incidents]
    (drive_dir / "AUTO-SIGN-STATUS.md").write_text(
        "\n".join(status) + "\n", encoding="utf-8", newline="\n"
    )


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
    if len(args) != 2 or args[0] not in ("sign", "verify", "batch-sign", "auto-sign"):
        print(
            "usage: python -m projectos.infrastructure.inbox_auth "
            "{sign|verify|batch-sign|auto-sign} PATH [--vouch]"
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

    if command == "auto-sign":
        from projectos.infrastructure.fleet_clock import now_ist

        result = auto_sign_once(
            target,
            keyring,
            # The fence follows the declared transition mode, not a hardcoded
            # True: see LEASE_ENFORCEMENT_PARAM for why it ships tolerant.
            require_lease=resolve_lease_enforcement() == MODE_ENFORCING,
            drive_dir=target.parent,
            stamp=now_ist().strftime("%Y-%m-%d %H:%M"),
        )
        if result.braked:
            print("auto-sign: BRAKE FILE PRESENT - did nothing")
            return 0
        print(f"auto-sign: {result.summary()}")
        for name in result.signed:
            print(f"  signed: {name}")
        for item in result.suspect:
            print(f"  TAMPERED, left refused: {item}")
        for item in result.refused:
            print(f"  REFUSED (incident recorded): {item}")
        # A tampered stamp is an incident: exit nonzero so a scheduled run
        # surfaces it rather than logging into the void.
        return 1 if result.suspect else 0

    if command == "sign":
        signed = sign_text(target.read_text(encoding="utf-8"), keyring)
        target.write_text(signed, encoding="utf-8")
        print(f"signed: {target.name} [key {signing_key(keyring)[0]}]")
        return 0

    verdict = verify_file(target, keyring)
    try:
        mode = resolve_enforcement_canonical()
    except RegistryUnavailable as exc:
        # Fail closed and say so. Silence here is what let four seats run
        # tolerant while the fleet believed itself enforcing.
        print(verdict.report_line())
        print(f"REGISTRY UNAVAILABLE: {exc} -> REFUSE")
        return 2
    act = should_act(verdict, mode)
    print(verdict.report_line())
    print(f"mode={mode} -> {'ACT' if act else 'REFUSE'}")
    return 0 if act else 2


#: The registry the CLI consults for the transition switch. Kept as a
#: repo-relative fragment only for joining onto the canonical root below -
#: it is never opened relative to the caller's working directory.
PARAMETER_REGISTRY_FILE = "docs/parameter_registry.json"

#: Override for a legitimately relocated registry (packaged installs, a test
#: fixture). It must still POINT AT A FILE THAT EXISTS: an override naming a
#: missing file fails closed exactly like a missing canonical one, so this can
#: never become the quiet route back to tolerant.
PARAMETER_REGISTRY_ENV = "PROJECTOS_PARAMETER_REGISTRY"


def canonical_registry_path() -> Path:
    """Where the enforcement registry lives, regardless of the caller's cwd.

    Derived from THIS MODULE's location, not from the process working
    directory, so a seat verifying from its own repo root reads the same
    registry as a seat verifying from ProjectOS. That is the entire fix: the
    answer to "is the fleet enforcing" must not depend on which folder the
    question was asked from.
    """
    override = os.environ.get(PARAMETER_REGISTRY_ENV)
    if override:
        return Path(override)
    # inbox_auth.py -> infrastructure -> projectos -> src -> <repo root>
    return Path(__file__).resolve().parents[3] / PARAMETER_REGISTRY_FILE


#: Registry key for the writer-lease transition switch. Same shape, and the
#: same reason, as INBOX-AUTH-ENFORCEMENT: a fence that is correct but not yet
#: fed will refuse everything. No orchestrator emits a LEASE line today, so
#: turning this on before they do would stop the fleet taking work at all -
#: which is automation disablement wearing a security badge. It ships
#: TOLERANT; Chat flips it once the issuers stamp their output.
LEASE_ENFORCEMENT_PARAM = "INBOX-LEASE-ENFORCEMENT"


def resolve_lease_enforcement() -> str:
    """Tolerant or enforcing for the writer lease. Founder/Chat-flipped only.

    Reads the same canonical registry as the stamp switch, so it inherits the
    fail-closed behaviour when the registry itself cannot be found.
    """
    path = canonical_registry_path()
    if not path.exists():
        raise RegistryUnavailable(
            f"enforcement registry not found at {path} - refusing to guess "
            "whether the writer lease is enforced"
        )
    try:
        declared = json.loads(path.read_text(encoding="utf-8")).get("parameters", {})
    except json.JSONDecodeError:
        return MODE_TOLERANT
    row = declared.get(LEASE_ENFORCEMENT_PARAM)
    if row is None:
        return MODE_TOLERANT
    value = str(row.get("value", "")).strip().lower()
    if value not in (MODE_TOLERANT, MODE_ENFORCING):
        raise KeyUnavailable(
            f"{LEASE_ENFORCEMENT_PARAM} declares {row.get('value')!r}, which is "
            f"neither {MODE_TOLERANT!r} nor {MODE_ENFORCING!r}"
        )
    return value


def resolve_enforcement_canonical() -> str:
    """The enforcement mode, resolved canonically and failing closed.

    Raises RegistryUnavailable when the registry cannot be found at all.
    Callers must treat that as REFUSE, never as tolerant.
    """
    path = canonical_registry_path()
    if not path.exists():
        raise RegistryUnavailable(
            f"enforcement registry not found at {path} - refusing to guess "
            "whether the fleet is enforcing"
        )
    return resolve_enforcement(path)

if __name__ == "__main__":  # pragma: no cover - exercised via tests calling main()
    raise SystemExit(main())
