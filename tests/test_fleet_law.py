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


def test_a_report_citing_the_law_is_not_a_rival_law_file(tmp_path: Path) -> None:
    # 2026-08-24: every report opens by stating which law it booted from
    # ("SEAT-BOOT LAW-VERSION 9"). Eight archived reports thereby became rival
    # claimants and the resolver refused to resolve, blocking the seat's boot.
    # Citing the law is not claiming to BE the law.
    (tmp_path / "2026-08-22_1633_PROJECTOS_FLEET-RUNNING.md").write_text(
        "DONE: LAW-VERSION 9. PROJECTOS. SEAT-BOOT read.\n", encoding="utf-8"
    )
    _law(tmp_path, "SEAT-BOOT.md", 9)
    assert resolve_law(tmp_path).path.name == "SEAT-BOOT.md"


@pytest.mark.parametrize("prefix", ["RPT-", "PARKED-", "DONE-"])
def test_consumed_file_prefixes_are_retired(prefix: str, tmp_path: Path) -> None:
    # The fleet marks consumed files with these; a consumed copy of the law is
    # not the law, whatever version it still declares.
    _law(tmp_path, f"{prefix}2026-08-21_SEAT-BOOT.md", 12)
    _law(tmp_path, "SEAT-BOOT.md", 9)
    assert resolve_law(tmp_path).version == 9


def test_a_file_naming_the_law_in_prose_but_not_in_a_heading_is_ignored(
    tmp_path: Path,
) -> None:
    (tmp_path / "some-confirmation.md").write_text(
        "We confirm the SEAT-BOOT contract.\nLAW-VERSION: 9\n", encoding="utf-8"
    )
    _law(tmp_path, "SEAT-BOOT.md", 9)
    assert resolve_law(tmp_path).path.name == "SEAT-BOOT.md"


def test_the_real_fleet_folder_resolves_to_exactly_one_law() -> None:
    # The regression that mattered: this call returned "refusing to guess"
    # against the live folder and stopped the seat booting.
    live = Path("G:/My Drive/AGENT-REPORTS")
    if not live.exists():  # pragma: no cover - Drive not mounted in CI
        pytest.skip("fleet Drive folder not mounted")
    assert resolve_law(live).path.name == "SEAT-BOOT.md"
