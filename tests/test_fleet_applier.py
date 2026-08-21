"""Tests for the privileged FLEET task applier.

The applier's entire value is what it REFUSES, so most of these are red paths.
The governing idea under test: a manifest may name a task and an operation and
nothing else. Every command, path and principal comes from the repo-reviewed
catalogue, so a validly signed manifest still cannot introduce a new command.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from projectos.infrastructure.fleet_applier import (
    CATALOGUE_FILE,
    Manifest,
    ManifestInvalid,
    Outcome,
    TaskDefinition,
    Verdict,
    already_applied,
    audit,
    judge_operation,
    load_catalogue,
    parse_manifest,
    plan,
    status_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def catalogue() -> dict[str, TaskDefinition]:
    return {
        "WAKE-EDUOS": TaskDefinition(
            name="WAKE-EDUOS",
            execute="wscript.exe",
            arguments="//B //Nologo C:\\ProjectOS-AI\\scripts\\run-hidden.vbs powershell -File x",
            user="rmani",
            logon="Interactive",
            runlevel="Limited",
            start="2026-08-20T09:16:00",
            interval="PT20M",
            duration="PT10H",
        )
    }


@pytest.fixture
def no_brake(tmp_path: Path) -> Path:
    return tmp_path / "absent.OFF"


@pytest.fixture
def empty_ledger(tmp_path: Path) -> Path:
    return tmp_path / "applied.jsonl"


def _manifest(*operations: dict[str, object], mid: str = "M-1") -> Manifest:
    return Manifest(manifest_id=mid, issued_at="2026-08-21T09:00:00", operations=operations)


# --- the reviewed catalogue is the only source of definitions --------------


def test_the_real_repo_catalogue_loads() -> None:
    # Asserts the shipped file is well-formed, because a
    # catalogue that cannot be read is an applier that cannot refuse safely.
    loaded = load_catalogue(REPO_ROOT / CATALOGUE_FILE)
    assert loaded, "reviewed catalogue is empty"
    assert all(defn.execute for defn in loaded.values())


def test_rendering_is_deterministic() -> None:
    loaded = load_catalogue(REPO_ROOT / CATALOGUE_FILE)
    first = {name: defn.digest() for name, defn in loaded.items()}
    again = load_catalogue(REPO_ROOT / CATALOGUE_FILE)
    second = {name: defn.digest() for name, defn in again.items()}
    assert first == second


def test_a_known_task_is_allowed(catalogue: dict[str, TaskDefinition]) -> None:
    outcome = judge_operation({"op": "register", "task": "WAKE-EDUOS"}, catalogue)
    assert outcome.verdict is Verdict.ALLOW
    assert outcome.rendered.startswith("wscript.exe")


def test_the_rendered_action_comes_from_the_catalogue_not_the_manifest(
    catalogue: dict[str, TaskDefinition],
) -> None:
    outcome = judge_operation({"op": "register", "task": "WAKE-EDUOS"}, catalogue)
    assert outcome.rendered == catalogue["WAKE-EDUOS"].render_action()


# --- red paths -------------------------------------------------------------


def test_an_unknown_task_is_refused(catalogue: dict[str, TaskDefinition]) -> None:
    outcome = judge_operation({"op": "register", "task": "WAKE-NOWHERE"}, catalogue)
    assert outcome.verdict is Verdict.REFUSE_UNKNOWN_TASK


def test_an_unknown_operation_is_refused(catalogue: dict[str, TaskDefinition]) -> None:
    outcome = judge_operation({"op": "elevate", "task": "WAKE-EDUOS"}, catalogue)
    assert outcome.verdict is Verdict.REFUSE_UNKNOWN_OP


@pytest.mark.parametrize("op", ["delete", "unregister", "disable", "stop", "remove"])
def test_destructive_operations_are_refused_by_name(
    op: str, catalogue: dict[str, TaskDefinition]
) -> None:
    # Refused as DESTRUCTIVE rather than merely UNKNOWN, so the log says why.
    outcome = judge_operation({"op": op, "task": "WAKE-EDUOS"}, catalogue)
    assert outcome.verdict is Verdict.REFUSE_DESTRUCTIVE


@pytest.mark.parametrize(
    "field",
    ["execute", "arguments", "command", "user", "runlevel", "trigger", "task_path"],
)
def test_a_manifest_cannot_smuggle_a_definition_field(
    field: str, catalogue: dict[str, TaskDefinition]
) -> None:
    # The attack this applier exists to stop: a validly signed file that also
    # says WHAT to run. Presence alone refuses - it is never quietly ignored.
    outcome = judge_operation(
        {"op": "register", "task": "WAKE-EDUOS", field: "calc.exe"}, catalogue
    )
    assert outcome.verdict is Verdict.REFUSE_SMUGGLED_FIELD
    assert field in outcome.reason


@pytest.mark.parametrize(
    "task", ["\\Microsoft\\Windows\\Defender", "..\\OTHER", "FLEET/WAKE-EDUOS"]
)
def test_a_task_name_cannot_leave_the_fleet_namespace(
    task: str, catalogue: dict[str, TaskDefinition]
) -> None:
    outcome = judge_operation({"op": "register", "task": task}, catalogue)
    assert outcome.verdict is Verdict.REFUSE_NON_FLEET


def test_a_stale_digest_pin_is_refused(catalogue: dict[str, TaskDefinition]) -> None:
    # The issuer signed against a definition that has since changed in the
    # repo. Applying the new one would apply something they never reviewed.
    outcome = judge_operation(
        {"op": "register", "task": "WAKE-EDUOS", "expect_digest": "0" * 64}, catalogue
    )
    assert outcome.verdict is Verdict.REFUSE_DIGEST_MISMATCH


def test_a_matching_digest_pin_is_allowed(catalogue: dict[str, TaskDefinition]) -> None:
    outcome = judge_operation(
        {
            "op": "register",
            "task": "WAKE-EDUOS",
            "expect_digest": catalogue["WAKE-EDUOS"].digest(),
        },
        catalogue,
    )
    assert outcome.verdict is Verdict.ALLOW


def test_a_missing_task_name_is_malformed(catalogue: dict[str, TaskDefinition]) -> None:
    assert judge_operation({"op": "register"}, catalogue).verdict is Verdict.REFUSE_MALFORMED


# --- manifest-level gates --------------------------------------------------


def test_the_kill_switch_refuses_every_operation(
    tmp_path: Path, catalogue: dict[str, TaskDefinition], empty_ledger: Path
) -> None:
    brake = tmp_path / "fleet-applier.OFF"
    brake.write_text("stop", encoding="utf-8")
    outcomes = plan(
        _manifest({"op": "register", "task": "WAKE-EDUOS"}),
        catalogue,
        brake_path=brake,
        ledger=empty_ledger,
    )
    assert [o.verdict for o in outcomes] == [Verdict.REFUSE_BRAKE]


def test_a_replayed_manifest_is_refused(
    tmp_path: Path, catalogue: dict[str, TaskDefinition], no_brake: Path
) -> None:
    ledger = tmp_path / "applied.jsonl"
    ledger.write_text(json.dumps({"manifest_id": "M-1"}) + "\n", encoding="utf-8")
    outcomes = plan(
        _manifest({"op": "register", "task": "WAKE-EDUOS"}, mid="M-1"),
        catalogue,
        brake_path=no_brake,
        ledger=ledger,
    )
    assert [o.verdict for o in outcomes] == [Verdict.REFUSE_REPLAY]


def test_a_fresh_manifest_id_is_not_a_replay(
    tmp_path: Path, catalogue: dict[str, TaskDefinition], no_brake: Path
) -> None:
    ledger = tmp_path / "applied.jsonl"
    ledger.write_text(json.dumps({"manifest_id": "M-1"}) + "\n", encoding="utf-8")
    outcomes = plan(
        _manifest({"op": "register", "task": "WAKE-EDUOS"}, mid="M-2"),
        catalogue,
        brake_path=no_brake,
        ledger=ledger,
    )
    assert outcomes[0].verdict is Verdict.ALLOW


def test_already_applied_is_false_for_a_missing_ledger(tmp_path: Path) -> None:
    assert not already_applied("M-1", tmp_path / "never.jsonl")


def test_one_bad_operation_does_not_authorise_the_others(
    catalogue: dict[str, TaskDefinition], no_brake: Path, empty_ledger: Path
) -> None:
    outcomes = plan(
        _manifest(
            {"op": "register", "task": "WAKE-EDUOS"},
            {"op": "register", "task": "WAKE-EDUOS", "execute": "calc.exe"},
        ),
        catalogue,
        brake_path=no_brake,
        ledger=empty_ledger,
    )
    assert [o.verdict for o in outcomes] == [
        Verdict.ALLOW,
        Verdict.REFUSE_SMUGGLED_FIELD,
    ]


# --- schema ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "not json at all",
        "[]",
        '"a string"',
        json.dumps({"issued_at": "x", "operations": [{"op": "report"}]}),
        json.dumps({"manifest_id": "M", "operations": [{"op": "report"}]}),
        json.dumps({"manifest_id": "M", "issued_at": "x"}),
        json.dumps({"manifest_id": "M", "issued_at": "x", "operations": []}),
        json.dumps({"manifest_id": "M", "issued_at": "x", "operations": ["register"]}),
    ],
)
def test_malformed_manifests_are_rejected(text: str) -> None:
    with pytest.raises(ManifestInvalid):
        parse_manifest(text)


def test_a_well_formed_manifest_parses() -> None:
    manifest = parse_manifest(
        json.dumps(
            {
                "manifest_id": "M-1",
                "issued_at": "2026-08-21T09:00:00",
                "operations": [{"op": "report", "task": "WAKE-EDUOS"}],
            }
        )
    )
    assert manifest.manifest_id == "M-1"
    assert len(manifest.digest()) == 64


# --- observability ---------------------------------------------------------


def test_every_decision_is_audited_including_refusals(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    manifest = _manifest({"op": "register", "task": "WAKE-EDUOS"})
    outcomes = [
        Outcome("register", "WAKE-EDUOS", Verdict.ALLOW, "ok"),
        Outcome("delete", "WAKE-EDUOS", Verdict.REFUSE_DESTRUCTIVE, "no"),
    ]
    audit(outcomes, manifest, log=log)
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [r["verdict"] for r in rows] == ["ALLOW", "REFUSE_DESTRUCTIVE"]
    assert all(r["manifest_id"] == "M-1" for r in rows)


def test_the_audit_log_is_append_only(tmp_path: Path) -> None:
    log = tmp_path / "audit.jsonl"
    manifest = _manifest({"op": "report", "task": "WAKE-EDUOS"})
    outcome = [Outcome("report", "WAKE-EDUOS", Verdict.ALLOW, "ok")]
    audit(outcome, manifest, log=log)
    audit(outcome, manifest, log=log)
    assert len(log.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_status_says_stopped_when_braked() -> None:
    text = status_markdown([], None, braked=True)
    assert "STOPPED" in text
    assert "last sweep" in text


def test_status_counts_allowed_and_refused() -> None:
    text = status_markdown(
        [
            Outcome("register", "A", Verdict.ALLOW, "ok"),
            Outcome("delete", "B", Verdict.REFUSE_DESTRUCTIVE, "no"),
        ],
        _manifest({"op": "register", "task": "A"}),
        braked=False,
    )
    assert "allowed: 1" in text
    assert "refused: 1" in text


def test_status_carries_a_liveness_signal() -> None:
    # The applier's own silence must be visible: if the timestamp stops
    # advancing, that is the alarm.
    assert "liveness" in status_markdown([], None, braked=False)
