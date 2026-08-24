"""The signer, the writer lease and the incident record, working together.

Item 6 of the assignment names the proofs: concurrent-writer refusal, lease
expiry and recovery, five-file cap behaviour, malformed / law-binding /
credential-bearing refusal, the stale-status alert, and a quiet healthy sweep
with no false positive. They are here rather than split across three files
because each one is really a statement about the sweep as a whole.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from projectos.infrastructure.inbox_auth import auto_sign_once
from projectos.infrastructure.inbox_guard import (
    INCIDENTS_FILENAME,
    INCIDENTS_STATE_FILENAME,
    Incident,
    RefusalClass,
    classify,
    record_incidents,
    unresolved,
)
from projectos.infrastructure.inbox_lease import acquire, stamp_lease

KEY = {"k1": b"integration-drill-key"}
NOON = datetime.fromisoformat("2026-08-21T12:00:00+05:30")

BODY = "# ASSIGNMENT - do the thing\n\nSeat: PROJECTOS\n"


@pytest.fixture
def drive(tmp_path: Path) -> Path:
    directory = tmp_path / "AGENT-REPORTS"
    directory.mkdir()
    return directory


@pytest.fixture
def inbox(drive: Path) -> Path:
    directory = drive / "INBOX"
    directory.mkdir()
    return directory


def _sweep(inbox: Path, drive: Path, tmp_path: Path, **kwargs: object) -> object:
    kwargs.setdefault("brake_path", tmp_path / "no-brake")
    kwargs.setdefault("log_path", tmp_path / "auto-sign.log")
    kwargs.setdefault("stamp", "2026-08-21 12:00")
    kwargs.setdefault("now", NOON)
    return auto_sign_once(inbox, KEY, drive_dir=drive, **kwargs)  # type: ignore[arg-type]


def _write(inbox: Path, name: str, text: str) -> Path:
    path = inbox / name
    path.write_text(text, encoding="utf-8")
    return path


def _status(drive: Path) -> str:
    return (drive / "AUTO-SIGN-STATUS.md").read_text(encoding="utf-8")


# --- the guard: what the signer will not vouch for -------------------------


def test_a_law_amending_file_is_refused_and_recorded(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    # The real incident: 2026-08-21_0855_PROJECTOS_AMENDMENT_NO-PASSPHRASE-ASK,
    # later cancelled as an unauthorized founder credential act.
    _write(inbox, "2026-08-21_0855_PROJECTOS_AMENDMENT_NO-PASSPHRASE-ASK.md", BODY)
    result = _sweep(inbox, drive, tmp_path, require_lease=False)
    assert result.signed == ()  # type: ignore[attr-defined]
    assert any("LAW_BINDING" in line for line in result.refused)  # type: ignore[attr-defined]
    assert len(unresolved(drive)) == 1


def test_a_credential_bearing_file_is_refused(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    _write(
        inbox,
        "2026-08-21_0900_PROJECTOS_SETUP.md",
        BODY + "\nPlease paste your passphrase into the config so I can proceed.\n",
    )
    result = _sweep(inbox, drive, tmp_path, require_lease=False)
    assert result.signed == ()  # type: ignore[attr-defined]
    assert any("FOUNDER_ONLY_ACT" in line for line in result.refused)  # type: ignore[attr-defined]


def test_an_assignment_that_merely_forbids_a_credential_act_is_not_refused() -> None:
    # The false positive that would matter most: my own assignments routinely
    # say "no new credential" as a BOUNDARY. Describing a fence is not asking
    # to cross it, and a guard that cannot tell the difference is unusable.
    text = (
        "# ASSIGNMENT\n\n## Boundaries\n"
        "No new credential or authorisation. No secret in Drive.\n"
        "Do not create, rotate, request or expose a credential.\n"
    )
    assert classify(text, "2026-08-21_0928_PROJECTOS_SOMETHING.md").may_sign


def test_an_ordinary_assignment_is_still_signed(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    _write(inbox, "2026-08-21_0900_PROJECTOS_ORDINARY.md", BODY)
    result = _sweep(inbox, drive, tmp_path, require_lease=False)
    assert result.signed == ("2026-08-21_0900_PROJECTOS_ORDINARY.md",)  # type: ignore[attr-defined]
    assert unresolved(drive) == []


def test_a_malformed_name_is_skipped_not_signed(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    _write(inbox, "notes.md", BODY)
    result = _sweep(inbox, drive, tmp_path, require_lease=False)
    assert result.signed == ()  # type: ignore[attr-defined]
    assert "notes.md" in result.skipped_name  # type: ignore[attr-defined]


# --- the lease, enforced by the signer -------------------------------------


def test_a_file_without_lease_evidence_is_refused(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    acquire(drive, "CHAT-A", now=NOON)
    _write(inbox, "2026-08-21_0900_PROJECTOS_NOLEASE.md", BODY)
    result = _sweep(inbox, drive, tmp_path, require_lease=True)
    assert result.signed == ()  # type: ignore[attr-defined]
    assert any(RefusalClass.NO_LEASE_EVIDENCE.value in line for line in result.refused)  # type: ignore[attr-defined]


def test_a_file_emitted_under_the_active_lease_is_signed(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    lease = acquire(drive, "CHAT-A", now=NOON).lease
    assert lease is not None
    _write(inbox, "2026-08-21_0900_PROJECTOS_LEASED.md", stamp_lease(BODY, lease))
    result = _sweep(inbox, drive, tmp_path, require_lease=True)
    assert result.signed == ("2026-08-21_0900_PROJECTOS_LEASED.md",)  # type: ignore[attr-defined]


def test_a_second_issuers_file_is_refused_end_to_end(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    # CHAT-B held the lease, wrote a file, then CHAT-A took over. B's file is
    # genuine, well-formed and wrong - and the signer can now tell.
    stale = acquire(drive, "CHAT-B", now=NOON).lease
    assert stale is not None
    _write(inbox, "2026-08-21_0900_PROJECTOS_FROM-B.md", stamp_lease(BODY, stale))
    acquire(drive, "CHAT-A", now=NOON + timedelta(hours=2))  # B's lease had lapsed
    result = _sweep(inbox, drive, tmp_path, require_lease=True, now=NOON + timedelta(hours=2))
    assert result.signed == ()  # type: ignore[attr-defined]
    assert any("second issuer" in line for line in result.refused)  # type: ignore[attr-defined]


def test_the_five_file_cap_still_bounds_a_leased_burst(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    lease = acquire(drive, "CHAT-A", now=NOON).lease
    assert lease is not None
    for i in range(7):
        _write(inbox, f"2026-08-21_090{i}_PROJECTOS_BURST{i}.md", stamp_lease(BODY, lease))
    result = _sweep(inbox, drive, tmp_path, require_lease=True)
    assert len(result.signed) == 5  # type: ignore[attr-defined]
    assert len(result.deferred) == 2  # type: ignore[attr-defined]


def test_require_lease_without_a_drive_dir_is_an_error(
    inbox: Path, tmp_path: Path
) -> None:
    # Failing closed: "enforce the lease but I cannot find it" must never
    # quietly become "do not enforce the lease".
    from projectos.domain.errors import InvariantViolation

    with pytest.raises(InvariantViolation):
        auto_sign_once(
            inbox,
            KEY,
            require_lease=True,
            drive_dir=None,
            brake_path=tmp_path / "no-brake",
            log_path=tmp_path / "log",
            stamp="2026-08-21 12:00",
            now=NOON,
        )


# --- incidents survive quiet sweeps ---------------------------------------


def test_a_quiet_healthy_sweep_does_not_erase_an_unresolved_incident(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    # THE defect in item 5. The status file was rewritten every sweep, so the
    # next quiet sweep silently erased the only visible sign of a refusal.
    _write(inbox, "2026-08-21_0855_PROJECTOS_AMENDMENT_THING.md", BODY)
    _sweep(inbox, drive, tmp_path, require_lease=False)
    assert len(unresolved(drive)) == 1

    (inbox / "2026-08-21_0855_PROJECTOS_AMENDMENT_THING.md").unlink()
    _sweep(inbox, drive, tmp_path, require_lease=False, stamp="2026-08-21 12:20")

    assert len(unresolved(drive)) == 1, "a quiet sweep erased an unresolved incident"
    status = _status(drive)
    assert "ATTENTION" in status
    assert "1 unresolved" in status
    assert "AMENDMENT" in status  # carried forward, not re-detected


def test_a_quiet_healthy_sweep_raises_no_false_positive(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    _sweep(inbox, drive, tmp_path, require_lease=False)
    status = _status(drive)
    assert "HEALTHY" in status
    assert "unresolved:      0" in status
    assert unresolved(drive) == []
    assert not (drive / "AUTO-SIGN-LOG.md").exists()  # no noise when nothing happened


def test_the_status_carries_last_signed_attempted_class_and_recovery(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    _write(inbox, "2026-08-21_0900_PROJECTOS_ORDINARY.md", BODY)
    _write(inbox, "2026-08-21_0855_PROJECTOS_AMENDMENT_THING.md", BODY)
    _sweep(inbox, drive, tmp_path, require_lease=False)
    status = _status(drive)
    assert "last signed:" in status
    assert "last attempted:" in status
    assert "refusal classes: LAW_BINDING" in status
    assert "recovery state:" in status


def test_incidents_are_not_duplicated_across_repeated_sweeps(
    inbox: Path, drive: Path, tmp_path: Path
) -> None:
    _write(inbox, "2026-08-21_0855_PROJECTOS_AMENDMENT_THING.md", BODY)
    _sweep(inbox, drive, tmp_path, require_lease=False)
    _sweep(inbox, drive, tmp_path, require_lease=False)
    assert len(unresolved(drive)) == 1


def test_a_resolved_incident_stops_raising_attention(drive: Path) -> None:
    record_incidents(
        drive,
        [Incident(at="2026-08-21T12:00:00", name="x.md", refusal="LAW_BINDING", reason="r")],
    )
    assert len(unresolved(drive)) == 1
    state = json.loads((drive / INCIDENTS_STATE_FILENAME).read_text(encoding="utf-8"))
    state[0]["resolved"] = True
    (drive / INCIDENTS_STATE_FILENAME).write_text(json.dumps(state), encoding="utf-8")
    assert unresolved(drive) == []


def test_a_corrupt_incident_state_reads_as_unresolved_not_as_clean(
    drive: Path,
) -> None:
    # "I cannot read the incident record" must never render as "all clear".
    (drive / INCIDENTS_STATE_FILENAME).write_text("{ not json", encoding="utf-8")
    assert len(unresolved(drive)) == 1


def test_the_prose_incident_file_names_the_unresolved_count(drive: Path) -> None:
    record_incidents(
        drive,
        [Incident(at="2026-08-21T12:00:00", name="x.md", refusal="LAW_BINDING", reason="r")],
    )
    text = (drive / INCIDENTS_FILENAME).read_text(encoding="utf-8")
    assert "**1 unresolved**" in text
    assert "UNRESOLVED" in text


# --- the fence cannot disable automation -----------------------------------


def test_no_new_module_can_disable_a_task_or_the_signer() -> None:
    # Boundary: "No automation disablement." Enforced structurally so it stays
    # true, rather than by remembering not to write such a call.
    root = Path(__file__).resolve().parents[1] / "src/projectos/infrastructure"
    for name in ("inbox_lease.py", "inbox_guard.py"):
        source = (root / name).read_text(encoding="utf-8")
        for dangerous in ("subprocess", "ScheduledTask", "Disable-", "os.system", "ctypes"):
            assert dangerous not in source, f"{name} can reach {dangerous}"
