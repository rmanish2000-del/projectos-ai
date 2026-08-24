"""Narrowly-scoped applier for privileged FLEET task changes.

The problem it solves: registering or enabling a fleet wake needs elevation,
so today it waits for the founder to be at the laptop. The tempting fix is a
privileged service that runs whatever a signed file tells it to. That trades a
scheduling delay for a remote-code-execution path, and a signed instruction is
still only proof of ORIGIN - being genuine is not being authorised.

So this applier is built the other way round. **A manifest may only NAME a
task and an operation. It can never carry a command.** Every executable,
argument, path, principal and trigger comes from the repo-reviewed catalogue
`docs/fleet_tasks.json`, which changes only through an ordinary reviewed
commit. The worst a forged-but-valid manifest can achieve is re-applying a
definition that is already in the repo and already reviewed.

What it will not do, ever, from a manifest: run an arbitrary command, touch a
task outside the FLEET namespace, delete or disable anything, widen a
principal, or interrupt a task that is running.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from projectos.infrastructure.fleet_clock import now_ist
from projectos.infrastructure.inbox_auth import AUTH_PREFIX

#: The only namespace this applier will ever touch. Not configurable, and
#: never taken from the manifest: a manifest that could name its own namespace
#: could name the Windows namespace.
FLEET_TASK_PATH = "\\FLEET\\"

#: Repo-reviewed task definitions. The manifest names a key in here; it never
#: supplies a value.
CATALOGUE_FILE = "docs/fleet_tasks.json"

#: Kill switch, in the shape already proven by the auto-signer: a file, no
#: privileges needed, reversed by deleting it. When present the applier
#: applies nothing but KEEPS REPORTING, so a stopped applier is visibly
#: stopped rather than merely silent.
APPLIER_BRAKE = Path.home() / ".projectos" / "fleet-applier.OFF"

#: Append-only local audit log: every refusal and every dry run.
APPLIER_AUDIT = Path.home() / ".projectos" / "fleet-applier-audit.jsonl"

#: Manifest ids already applied, so a replayed manifest is refused rather than
#: silently re-applied.
APPLIER_LEDGER = Path.home() / ".projectos" / "fleet-applier-applied.jsonl"


class Op(StrEnum):
    """The complete set of operations a manifest may request."""

    REGISTER = "register"  # (re-)apply a reviewed definition
    ENABLE = "enable"  # enable an existing fleet wake
    REPORT = "report"  # read task state, change nothing


class Verdict(StrEnum):
    """What the applier decided about one requested operation."""

    ALLOW = "ALLOW"
    REFUSE_BRAKE = "REFUSE_BRAKE"
    REFUSE_MALFORMED = "REFUSE_MALFORMED"
    REFUSE_UNKNOWN_OP = "REFUSE_UNKNOWN_OP"
    REFUSE_UNKNOWN_TASK = "REFUSE_UNKNOWN_TASK"
    REFUSE_NON_FLEET = "REFUSE_NON_FLEET"
    REFUSE_SMUGGLED_FIELD = "REFUSE_SMUGGLED_FIELD"
    REFUSE_DIGEST_MISMATCH = "REFUSE_DIGEST_MISMATCH"
    REFUSE_DESTRUCTIVE = "REFUSE_DESTRUCTIVE"
    REFUSE_REPLAY = "REFUSE_REPLAY"


#: Keys that would let a manifest describe WHAT to run rather than WHICH
#: reviewed thing to run. Their mere presence is a refusal - not ignored,
#: because silently dropping a field the caller believed was honoured is how a
#: privilege boundary rots.
SMUGGLED_KEYS: frozenset[str] = frozenset(
    {
        "execute",
        "arguments",
        "command",
        "path",
        "working_directory",
        "user",
        "userid",
        "principal",
        "runlevel",
        "logon",
        "trigger",
        "start",
        "interval",
        "duration",
        "task_path",
        "script",
    }
)

#: Operations that destroy or stop automation. Named explicitly so the refusal
#: says WHY, rather than falling through to "unknown operation".
DESTRUCTIVE_OPS: frozenset[str] = frozenset(
    {"delete", "unregister", "disable", "stop", "remove", "change"}
)


class ManifestInvalid(ValueError):
    """The manifest could not be parsed, or is not schema-valid."""


@dataclass(frozen=True)
class TaskDefinition:
    """One reviewed task, exactly as the repo declares it."""

    name: str
    execute: str
    arguments: str
    user: str
    logon: str
    runlevel: str
    start: str
    interval: str
    duration: str

    def digest(self) -> str:
        """Stable digest of the reviewed definition.

        A manifest may pin this. If the repo's definition has changed since
        the manifest was written, the pin no longer matches and the operation
        is refused rather than applying something its issuer never saw.
        """
        payload = json.dumps(
            {
                "name": self.name,
                "execute": self.execute,
                "arguments": self.arguments,
                "user": self.user,
                "logon": self.logon,
                "runlevel": self.runlevel,
                "start": self.start,
                "interval": self.interval,
                "duration": self.duration,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def render_action(self) -> str:
        """Exactly what would be registered, for a dry run to show a human."""
        return f"{self.execute} {self.arguments}".strip()


@dataclass(frozen=True)
class Outcome:
    """One requested operation, and what the applier decided about it."""

    op: str
    task: str
    verdict: Verdict
    reason: str
    rendered: str = ""

    @property
    def allowed(self) -> bool:
        return self.verdict is Verdict.ALLOW

    def line(self) -> str:
        return f"{self.verdict.value} {self.op}:{self.task} - {self.reason}"


@dataclass(frozen=True)
class Manifest:
    """A parsed, schema-valid manifest. Parsing proves shape, not authority."""

    manifest_id: str
    issued_at: str
    operations: tuple[Mapping[str, Any], ...] = ()

    def digest(self) -> str:
        payload = json.dumps(
            {
                "manifest_id": self.manifest_id,
                "issued_at": self.issued_at,
                "operations": [dict(sorted(o.items())) for o in self.operations],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_catalogue(path: Path) -> dict[str, TaskDefinition]:
    """The reviewed task definitions, keyed by task name."""
    try:
        # utf-8-sig: the catalogue is generated by PowerShell, which writes a BOM.
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestInvalid(f"catalogue unreadable at {path}: {exc}") from exc

    catalogue: dict[str, TaskDefinition] = {}
    for row in raw.get("tasks", []):
        try:
            defn = TaskDefinition(
                name=str(row["name"]),
                execute=str(row["execute"]),
                arguments=str(row["arguments"]),
                user=str(row["user"]),
                logon=str(row["logon"]),
                runlevel=str(row["runlevel"]),
                start=str(row["start"]),
                interval=str(row["interval"]),
                duration=str(row["duration"]),
            )
        except KeyError as exc:
            raise ManifestInvalid(f"catalogue row missing {exc}") from exc
        catalogue[defn.name] = defn
    return catalogue


def strip_stamp(text: str) -> str:
    """The manifest body without its AUTH stamp line.

    A manifest has to be two things at once: JSON the applier can parse, and a
    stamped document `inbox_auth` can verify. The stamp is a trailing line, so
    the body is everything above it - and the applier must drop exactly the
    line the verifier drops, or the bytes that were signed and the bytes that
    were parsed are not the same bytes.
    """
    kept = [line for line in text.splitlines() if not line.startswith(AUTH_PREFIX)]
    return "\n".join(kept)


def parse_manifest(text: str) -> Manifest:
    """Parse and schema-check a manifest. Raises ManifestInvalid."""
    try:
        raw = json.loads(strip_stamp(text))
    except json.JSONDecodeError as exc:
        raise ManifestInvalid(f"not JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ManifestInvalid("manifest must be a JSON object")

    for required in ("manifest_id", "issued_at", "operations"):
        if required not in raw:
            raise ManifestInvalid(f"missing required field {required!r}")

    ops = raw["operations"]
    if not isinstance(ops, list) or not ops:
        raise ManifestInvalid("operations must be a non-empty list")
    for entry in ops:
        if not isinstance(entry, dict):
            raise ManifestInvalid("each operation must be an object")

    return Manifest(
        manifest_id=str(raw["manifest_id"]),
        issued_at=str(raw["issued_at"]),
        operations=tuple(ops),
    )


def already_applied(manifest_id: str, ledger: Path) -> bool:
    """True if this manifest id has been applied before (a replay)."""
    if not ledger.exists():
        return False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("manifest_id") == manifest_id:
            return True
    return False


def judge_operation(
    entry: Mapping[str, Any],
    catalogue: Mapping[str, TaskDefinition],
) -> Outcome:
    """Decide one operation against the reviewed catalogue."""
    raw_op = str(entry.get("op", "")).strip().lower()
    task = str(entry.get("task", "")).strip()

    smuggled = sorted(k for k in entry if k.lower() in SMUGGLED_KEYS)
    if smuggled:
        return Outcome(
            raw_op,
            task,
            Verdict.REFUSE_SMUGGLED_FIELD,
            f"manifest supplied {', '.join(smuggled)} - definitions come from "
            f"{CATALOGUE_FILE}, never from the manifest",
        )

    if raw_op in DESTRUCTIVE_OPS:
        return Outcome(
            raw_op,
            task,
            Verdict.REFUSE_DESTRUCTIVE,
            "this applier never deletes, disables or stops automation",
        )
    if raw_op not in set(Op):
        return Outcome(
            raw_op, task, Verdict.REFUSE_UNKNOWN_OP, "operation not permitted"
        )
    if not task:
        return Outcome(raw_op, task, Verdict.REFUSE_MALFORMED, "no task named")

    # A task name carrying a path separator is trying to leave the namespace.
    if "\\" in task or "/" in task:
        return Outcome(
            raw_op,
            task,
            Verdict.REFUSE_NON_FLEET,
            "only bare task names inside the FLEET namespace are addressable",
        )

    defn = catalogue.get(task)
    if defn is None:
        return Outcome(
            raw_op,
            task,
            Verdict.REFUSE_UNKNOWN_TASK,
            f"not a reviewed task in {CATALOGUE_FILE}",
        )

    pinned = entry.get("expect_digest")
    if pinned is not None and str(pinned) != defn.digest():
        return Outcome(
            raw_op,
            task,
            Verdict.REFUSE_DIGEST_MISMATCH,
            "reviewed definition has changed since the manifest was written",
        )

    return Outcome(
        raw_op,
        task,
        Verdict.ALLOW,
        f"reviewed definition {defn.digest()[:12]}",
        rendered=defn.render_action(),
    )


def plan(
    manifest: Manifest,
    catalogue: Mapping[str, TaskDefinition],
    *,
    brake_path: Path | None = None,
    ledger: Path | None = None,
) -> list[Outcome]:
    """Decide every operation in a manifest. Changes nothing.

    This is the whole decision surface. Applying is a separate, elevated step
    that may only execute operations this function returned as ALLOW.
    """
    brake = brake_path if brake_path is not None else APPLIER_BRAKE
    if brake.exists():
        return [
            Outcome(
                str(entry.get("op", "")),
                str(entry.get("task", "")),
                Verdict.REFUSE_BRAKE,
                f"kill switch present: {brake}",
            )
            for entry in manifest.operations
        ]

    led = ledger if ledger is not None else APPLIER_LEDGER
    if already_applied(manifest.manifest_id, led):
        return [
            Outcome(
                str(entry.get("op", "")),
                str(entry.get("task", "")),
                Verdict.REFUSE_REPLAY,
                f"manifest {manifest.manifest_id} was already applied",
            )
            for entry in manifest.operations
        ]

    return [judge_operation(entry, catalogue) for entry in manifest.operations]


def audit(
    outcomes: list[Outcome], manifest: Manifest, *, log: Path | None = None
) -> None:
    """Append one row per decision. Refusals and dry runs alike."""
    path = log if log is not None else APPLIER_AUDIT
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = now_ist()
    with path.open("a", encoding="utf-8") as handle:
        for outcome in outcomes:
            handle.write(
                json.dumps(
                    {
                        "at": stamp.isoformat(timespec="seconds"),
                        "manifest_id": manifest.manifest_id,
                        "manifest_digest": manifest.digest(),
                        "op": outcome.op,
                        "task": outcome.task,
                        "verdict": outcome.verdict.value,
                        "reason": outcome.reason,
                    },
                    ensure_ascii=True,
                )
                + "\n"
            )


def status_markdown(
    outcomes: list[Outcome],
    manifest: Manifest | None,
    *,
    braked: bool,
    task_health: Mapping[str, str] | None = None,
) -> str:
    """Phone-readable status for Drive.

    Leads with the two things a glance must answer: is the applier stopped,
    and did the last sweep change anything.
    """
    stamp = now_ist().strftime("%Y-%m-%d %H:%M IST")
    head = "STOPPED (kill switch present)" if braked else "running"
    allowed = sum(1 for outcome in outcomes if outcome.allowed)
    refused = len(outcomes) - allowed

    lines = [
        "# FLEET-APPLIER status",
        "",
        f"**{head}** - last sweep {stamp}",
        "",
        f"- last manifest: {manifest.manifest_id if manifest else 'none'}",
        f"- digest: {manifest.digest()[:16] if manifest else '-'}",
        f"- allowed: {allowed} - refused: {refused}",
        "",
        "## last sweep",
    ]
    if outcomes:
        lines.extend(f"- {outcome.line()}" for outcome in outcomes)
    else:
        lines.append("- nothing requested")

    if task_health:
        lines += ["", "## task health"]
        lines += [f"- {name}: {state}" for name, state in sorted(task_health.items())]

    lines += [
        "",
        "A sweep that refuses everything is not a fault: the applier is a fence,",
        "and a fence that never says no is not doing anything.",
        "",
        "If this timestamp stops advancing, the applier itself is down - that is",
        "the liveness signal, and silence here is the alarm.",
    ]
    return "\n".join(lines) + "\n"


def canonical_catalogue_path() -> Path:
    """Where the reviewed catalogue lives, regardless of the caller's cwd.

    Same lesson as the enforcement registry: a privileged component must not
    read its allow-list from whatever directory it happened to be started in.
    """
    return Path(__file__).resolve().parents[3] / CATALOGUE_FILE


def main(argv: list[str] | None = None) -> int:
    """Dry-run entry point. Decides and reports; it NEVER applies.

    Applying is a separate elevated step that may only execute operations
    this run returned as ALLOW. Keeping the decision unprivileged means the
    fence can be tested, and is tested, without any privilege at all.
    """
    import sys

    from projectos.infrastructure.inbox_auth import (
        KeyUnavailable,
        load_keyring,
        verify_text,
    )

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: fleet_applier <manifest.json> [--status <dir>]", file=sys.stderr)
        return 2

    manifest_path = Path(args[0])
    status_dir = Path(args[args.index("--status") + 1]) if "--status" in args else None

    braked = APPLIER_BRAKE.exists()

    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"REFUSE: manifest unreadable: {exc}", file=sys.stderr)
        return 2

    # A privileged applier requires a VALID stamp in every mode. Unlike an
    # INBOX assignment, there is no pre-adoption tolerance here: an unsigned
    # instruction to a privileged component is simply not an instruction.
    try:
        keyring = load_keyring()
    except KeyUnavailable as exc:
        print(f"REFUSE: {exc}", file=sys.stderr)
        return 2
    verdict = verify_text(text, keyring, name=manifest_path.name)
    if not verdict.authentic:
        print(f"REFUSE: {verdict.report_line()}", file=sys.stderr)
        return 2

    try:
        manifest = parse_manifest(text)
        catalogue = load_catalogue(canonical_catalogue_path())
    except ManifestInvalid as exc:
        print(f"REFUSE: {exc}", file=sys.stderr)
        return 2

    outcomes = plan(manifest, catalogue)
    audit(outcomes, manifest)

    for outcome in outcomes:
        print(outcome.line())
        if outcome.allowed and outcome.rendered:
            print(f"    would apply: {outcome.rendered}")

    if status_dir is not None:
        status_dir.mkdir(parents=True, exist_ok=True)
        (status_dir / "FLEET-APPLIER-STATUS.md").write_text(
            status_markdown(outcomes, manifest, braked=braked), encoding="utf-8"
        )

    refused = [o for o in outcomes if not o.allowed]
    print(f"DRY RUN: {len(outcomes) - len(refused)} allowed, {len(refused)} refused")
    return 0 if not refused else 2


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
