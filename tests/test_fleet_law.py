"""Tests for resolving the fleet law by content rather than filename.

These encode the 2026-08-20 incident: LAW-VERSION 9 arrived as
`SEAT-BOOT (1).md` because Drive renamed it, the canonical `SEAT-BOOT.md`
did not exist, and every seat was told to find the law by title.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.infrastructure.fleet_law import (
    LawUnavailable,
    candidates,
    is_retired,
    resolve_law,
)


def _law(directory: Path, name: str, version: int, *, body: str = "") -> Path:
    path = directory / name
    path.write_text(f"# SEAT-BOOT\n**LAW-VERSION: {version}**\n{body}", encoding="utf-8")
    return path


def test_the_incident_a_drive_renamed_file_is_still_found(tmp_path: Path) -> None:
    # The exact shape of the outage: no SEAT-BOOT.md at all, the live law
    # wearing Drive's duplicate suffix, the predecessor already retired.
    _law(tmp_path, "SEAT-BOOT (1).md", 9)
    _law(tmp_path, "SUPERSEDED-2026-08-20_SEAT-BOOT-v8-LAW-VERSION-8.md", 8)

    law = resolve_law(tmp_path)
    assert law.version == 9
    assert law.path.name == "SEAT-BOOT (1).md"


def test_canonical_name_resolves_normally(tmp_path: Path) -> None:
    _law(tmp_path, "SEAT-BOOT.md", 9)
    assert resolve_law(tmp_path).version == 9


def test_a_superseded_file_is_never_the_law(tmp_path: Path) -> None:
    # Even when it is the only file present: retired means retired, and a
    # seat booting on a superseded law is the failure being prevented.
    _law(tmp_path, "SUPERSEDED-2026-08-19_SEAT-BOOT-v7.md", 7)
    with pytest.raises(LawUnavailable):
        resolve_law(tmp_path)


def test_a_failed_upload_is_never_the_law_even_at_a_higher_version(
    tmp_path: Path,
) -> None:
    # This file really exists in the fleet folder, labelled DO-NOT-USE, and it
    # claims v8. Version alone must not be allowed to win.
    _law(tmp_path, "FAILED-UPLOAD-2026-08-19_SEAT-BOOT-v8-DO-NOT-USE.md", 8)
    _law(tmp_path, "SEAT-BOOT.md", 7)
    assert resolve_law(tmp_path).version == 7


def test_highest_live_version_wins(tmp_path: Path) -> None:
    _law(tmp_path, "SEAT-BOOT.md", 9)
    _law(tmp_path, "SUPERSEDED-old.md", 8)
    _law(tmp_path, "SUPERSEDED-older.md", 7)
    assert resolve_law(tmp_path).version == 9


def test_a_tie_is_refused_rather_than_guessed(tmp_path: Path) -> None:
    # Two live files both claiming to be the law is precisely when guessing
    # is most tempting and most dangerous.
    _law(tmp_path, "SEAT-BOOT.md", 9)
    _law(tmp_path, "SEAT-BOOT (1).md", 9)
    with pytest.raises(LawUnavailable, match="more than one"):
        resolve_law(tmp_path)


def test_no_law_at_all_raises_rather_than_returning_none(tmp_path: Path) -> None:
    (tmp_path / "some-report.md").write_text("no version here", encoding="utf-8")
    with pytest.raises(LawUnavailable, match="no file"):
        resolve_law(tmp_path)


def test_a_passing_mention_deep_in_a_file_is_not_a_declaration(
    tmp_path: Path,
) -> None:
    # A report discussing "LAW-VERSION 12" must not outrank the actual law.
    filler = "x" * 6000
    (tmp_path / "some-report.md").write_text(
        f"# A report\n{filler}\nLAW-VERSION: 12\n", encoding="utf-8"
    )
    _law(tmp_path, "SEAT-BOOT.md", 9)
    assert resolve_law(tmp_path).version == 9


def test_emphasis_around_the_version_is_tolerated(tmp_path: Path) -> None:
    (tmp_path / "SEAT-BOOT.md").write_text(
        "# SEAT-BOOT\n**LAW-VERSION: 9**  - written by COWORK.\n", encoding="utf-8"
    )
    assert resolve_law(tmp_path).version == 9


def test_retired_prefixes_are_recognised() -> None:
    assert is_retired("SUPERSEDED-x.md")
    assert is_retired("FAILED-UPLOAD-x.md")
    assert is_retired("CANCELLED-x.md")
    assert not is_retired("SEAT-BOOT.md")
    assert not is_retired("SEAT-BOOT (1).md")


def test_candidates_excludes_retired_and_orders_by_version(tmp_path: Path) -> None:
    _law(tmp_path, "SEAT-BOOT.md", 9)
    _law(tmp_path, "older-law.md", 5)
    _law(tmp_path, "SUPERSEDED-x.md", 8)
    found = candidates(tmp_path)
    assert [f.version for f in found] == [9, 5]


def test_summary_names_version_and_file(tmp_path: Path) -> None:
    _law(tmp_path, "SEAT-BOOT.md", 9)
    assert resolve_law(tmp_path).summary() == "LAW-VERSION 9 at SEAT-BOOT.md"


def test_a_dashboard_reporting_the_version_is_not_the_law(tmp_path: Path) -> None:
    # The founder dashboard prints "LAW-VERSION: 9" as status. An earlier
    # version of this resolver treated it as a rival law file and refused to
    # resolve at all - correct caution, wrong candidate set.
    (tmp_path / "FOUNDER-FLEET-DASHBOARD-LATEST.md").write_text(
        "# Fleet dashboard\nLAW-VERSION: 9\nseats: 8\n", encoding="utf-8"
    )
    _law(tmp_path, "SEAT-BOOT.md", 9)
    law = resolve_law(tmp_path)
    assert law.path.name == "SEAT-BOOT.md"


def test_a_law_named_only_in_its_heading_still_counts(tmp_path: Path) -> None:
    (tmp_path / "fleet-law-copy.md").write_text(
        "# SEAT-BOOT - the fleet law\n**LAW-VERSION: 4**\n", encoding="utf-8"
    )
    assert resolve_law(tmp_path).version == 4


# --- assignment FIX-LAW-RESOLVER-CITATION (2026-08-22) ---------------------
# Since 2026-08-21 every seat report opens by citing the law it booted under.
# Eleven citing files tied with the genuine SEAT-BOOT.md and the resolver
# refused to boot the whole fleet. A citation must never count as a
# declaration; a genuine second declaration must still be refused.


def _citing_report(directory: Path, name: str) -> Path:
    # The real shape of the colliding files: the law cited in the first 200
    # characters and a bare LAW-VERSION line further down the head.
    path = directory / name
    path.write_text(
        "DONE: Booted PROJECTOS. LAW-VERSION 9. FLEET-STATE.md and SEAT-BOOT "
        "read. INBOX listed: nothing claimable.\n"
        "ANSWERS: none\n"
        "LAW-VERSION: 9\n"
        "STOP.\n",
        encoding="utf-8",
    )
    return path


def test_the_2026_08_22_collision_resolves_to_the_law_alone(tmp_path: Path) -> None:
    # The live incident in miniature: heartbeats and reports citing the law,
    # reports carrying SEAT-BOOT inside their FILENAME, and the one real law.
    _citing_report(tmp_path, "2026-08-21_1501_PROJECTOS_HEARTBEAT.md")
    _citing_report(tmp_path, "2026-08-21_2320_WEB_HEARTBEAT.md")
    _citing_report(tmp_path, "2026-08-21_0850_GROK_CLAIM_ITEM4-SEAT-BOOT-STRANGER-READ.md")
    _citing_report(tmp_path, "2026-08-21_0855_GROK_REPORT_ITEM4-SEAT-BOOT-STRANGER-READ.md")
    _law(tmp_path, "SEAT-BOOT.md", 9)

    law = resolve_law(tmp_path)
    assert law.path.name == "SEAT-BOOT.md"
    assert law.version == 9


def test_a_report_citing_the_law_is_not_a_candidate(tmp_path: Path) -> None:
    # "Booted under SEAT-BOOT, LAW-VERSION 9" is correct, useful phrasing and
    # must stay safe to write. The resolver sees no candidate at all here.
    _citing_report(tmp_path, "2026-08-21_0945_AIW_READ-ONLY-SOURCE-CONNECTOR.md")
    assert candidates(tmp_path) == []


def test_seat_boot_as_a_filename_substring_is_not_a_declaration(tmp_path: Path) -> None:
    # Three of the colliding files carried SEAT-BOOT inside their report
    # filenames. Only a stem that IS the law's name (plus Drive's duplicate
    # suffix) declares; a stem that contains it merely mentions it.
    _citing_report(tmp_path, "2026-08-21_1230_GROK_REPORT_ITEM4-SEAT-BOOT-FOLLOWTHROUGH.md")
    _law(tmp_path, "SEAT-BOOT.md", 9)
    found = candidates(tmp_path)
    assert [f.path.name for f in found] == ["SEAT-BOOT.md"]


def test_two_genuine_declarations_still_refuse(tmp_path: Path) -> None:
    # The CONTESTED path must survive this fix: a real fork is exactly when
    # refusing beats guessing, and a silent wrong law is worse than a stopped
    # fleet.
    _law(tmp_path, "SEAT-BOOT.md", 9)
    _law(tmp_path, "SEAT-BOOT (1).md", 9)
    _citing_report(tmp_path, "2026-08-21_1501_PROJECTOS_HEARTBEAT.md")
    with pytest.raises(LawUnavailable, match="more than one"):
        resolve_law(tmp_path)


def test_a_retired_law_file_is_still_excluded_after_the_fix(tmp_path: Path) -> None:
    _law(tmp_path, "SUPERSEDED-2026-08-20_SEAT-BOOT-v8.md", 8)
    _law(tmp_path, "SEAT-BOOT.md", 9)
    found = candidates(tmp_path)
    assert [f.path.name for f in found] == ["SEAT-BOOT.md"]
