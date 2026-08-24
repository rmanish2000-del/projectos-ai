"""The enforcement registry must resolve the same from every working directory.

On 2026-08-20 the CLI opened `docs/parameter_registry.json` relative to the
process working directory. A seat verifying from its own repo root found no
registry, silently defaulted to TOLERANT, and would have acted on unsigned
assignments while the fleet believed itself enforcing. The answer to "is the
fleet enforcing" must not depend on which folder the question was asked from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from projectos.infrastructure.inbox_auth import (
    MODE_ENFORCING,
    MODE_TOLERANT,
    PARAMETER_REGISTRY_ENV,
    RegistryUnavailable,
    canonical_registry_path,
    resolve_enforcement,
    resolve_enforcement_canonical,
)


def _registry(directory: Path, mode: str) -> Path:
    path = directory / "parameter_registry.json"
    path.write_text(
        json.dumps({"parameters": {"INBOX-AUTH-ENFORCEMENT": {"value": mode}}}),
        encoding="utf-8",
    )
    return path


def test_canonical_path_is_the_same_from_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(PARAMETER_REGISTRY_ENV, raising=False)
    from_here = canonical_registry_path()
    monkeypatch.chdir(tmp_path)
    assert canonical_registry_path() == from_here


def test_canonical_path_points_into_this_repo_not_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(PARAMETER_REGISTRY_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    resolved = canonical_registry_path()
    assert resolved.name == "parameter_registry.json"
    assert tmp_path not in resolved.parents


def test_mode_is_identical_from_projectos_and_from_a_foreign_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The regression itself: same question, two directories, one answer.
    monkeypatch.delenv(PARAMETER_REGISTRY_ENV, raising=False)
    from_repo = resolve_enforcement_canonical()
    monkeypatch.chdir(tmp_path)  # stands in for C:\EduOS, C:\AI-Workspace, ...
    assert resolve_enforcement_canonical() == from_repo


def test_the_old_cwd_relative_read_really_did_fall_to_tolerant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Documents the defect rather than trusting the report of it: from a
    # foreign root the relative path resolves to nothing, and nothing was
    # read as "tolerant".
    monkeypatch.chdir(tmp_path)
    assert resolve_enforcement(Path("docs/parameter_registry.json")) == MODE_TOLERANT


def test_a_missing_registry_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PARAMETER_REGISTRY_ENV, str(tmp_path / "absent.json"))
    with pytest.raises(RegistryUnavailable, match="refusing to guess"):
        resolve_enforcement_canonical()


def test_an_override_naming_a_missing_file_is_not_a_route_back_to_tolerant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The override exists for packaged installs, not as a bypass.
    monkeypatch.setenv(PARAMETER_REGISTRY_ENV, str(tmp_path / "nope.json"))
    with pytest.raises(RegistryUnavailable):
        resolve_enforcement_canonical()


def test_an_override_naming_a_real_registry_is_honoured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(PARAMETER_REGISTRY_ENV, str(_registry(tmp_path, MODE_ENFORCING)))
    assert resolve_enforcement_canonical() == MODE_ENFORCING


def test_a_present_registry_without_the_row_stays_tolerant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Unchanged ratified semantics: a registry that exists but has not
    # declared the switch is a fleet that has not turned it on yet. Only a
    # MISSING registry fails closed.
    path = tmp_path / "parameter_registry.json"
    path.write_text(json.dumps({"parameters": {}}), encoding="utf-8")
    monkeypatch.setenv(PARAMETER_REGISTRY_ENV, str(path))
    assert resolve_enforcement_canonical() == MODE_TOLERANT


def test_the_lease_switch_ships_tolerant_so_the_fleet_keeps_taking_work() -> None:
    # A fence nothing feeds yet must not be armed. No orchestrator stamps a
    # LEASE line today, so enforcing would refuse every legitimate assignment
    # - automation disablement wearing a security badge.
    from projectos.infrastructure.inbox_auth import resolve_lease_enforcement

    assert resolve_lease_enforcement() == MODE_TOLERANT


def test_the_lease_switch_also_fails_closed_without_a_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from projectos.infrastructure.inbox_auth import resolve_lease_enforcement

    monkeypatch.setenv(PARAMETER_REGISTRY_ENV, str(tmp_path / "absent.json"))
    with pytest.raises(RegistryUnavailable):
        resolve_lease_enforcement()


def test_the_lease_switch_reads_enforcing_when_declared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from projectos.infrastructure.inbox_auth import resolve_lease_enforcement

    path = tmp_path / "parameter_registry.json"
    path.write_text(
        json.dumps({"parameters": {"INBOX-LEASE-ENFORCEMENT": {"value": "enforcing"}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv(PARAMETER_REGISTRY_ENV, str(path))
    assert resolve_lease_enforcement() == MODE_ENFORCING
