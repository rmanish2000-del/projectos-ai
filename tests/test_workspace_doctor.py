"""P9 — Workspace doctor.

Deterministic, read-only diagnostics over the same read-model P8 status interprets,
re-presented as named checks with safe remediation. These tests cover the healthy,
warning-only, and failure outcomes; each required diagnostic; deterministic ordering;
that every suggested action references only verified, non-destructive commands; the
project-focused run; strict read-only behavior; and P7/P8 non-regression.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from projectos.cli.main import main
from projectos.domain.errors import ExitCode, NotFoundError
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import add_project, init_project_kernel
from projectos.infrastructure.workspace_doctor import (
    CHECK_AUDIT_INTEGRITY,
    CHECK_CONFIGURED_PACKS,
    CHECK_KERNEL_INITIALISED,
    CHECK_PROJECT_FOCUS,
    CHECK_REPOSITORY_METADATA,
    CHECK_WORKSPACE_MANIFEST,
    Diagnostic,
    DiagnosticResult,
    DoctorReport,
    Outcome,
    build_report,
    render_report,
)
from projectos.infrastructure.workspace_handoff import build_handoff
from projectos.infrastructure.workspace_status import Condition, build_status

FOUNDER_ID = "founder@example.com"
FOUNDER_NAME = "Founder"

_RESULT_RANK = {
    DiagnosticResult.FAIL: 0,
    DiagnosticResult.WARN: 1,
    DiagnosticResult.PASS: 2,
    DiagnosticResult.SKIP: 3,
}

#: Every ProjectOS command a remediation action is allowed to reference — each one
#: verified to exist in the CLI. A suggestion outside this set is a bug.
_VERIFIED_COMMANDS = (
    "projectos workspace init-project",
    "projectos workspace status",
    "projectos pack validate",
    "projectos history --verify",
)
_DESTRUCTIVE_TOKENS = (
    "rm ",
    " -rf",
    "--force",
    "delete",
    "reset",
    "git push",
    "rmtree",
    "--fix",
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def initialise(workspace: Path, name: str) -> Path:
    return init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )


def corrupt_audit(repo: Path) -> None:
    audit_dir = Layout.for_repo(repo).audit_dir
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "2026-07.ndjson").write_text("{ not valid json\n", encoding="utf-8")


def diagnostics_for(report: DoctorReport, check: str) -> list[Diagnostic]:
    return [d for d in report.diagnostics if d.check == check]


# -- healthy ------------------------------------------------------------------


def test_fully_healthy_workspace(workspace: Path) -> None:
    # Re-register the sole project with repository metadata, then initialise it, so
    # every check passes: initialised, repo declared, pack available, chain intact.
    add_project(
        workspace,
        name="ExampleProject",
        project_id="example-project",
        repository_remote="git@example.com:acme/example.git",
        repository_branch="main",
        force=True,
    )
    initialise(workspace, "ExampleProject")

    report = build_report(workspace)

    assert report.outcome is Outcome.PASS
    assert report.failed == 0
    assert report.warned == 0
    assert "[PASS]" in render_report(report)


# -- warning-only -------------------------------------------------------------


def test_warning_only_workspace(workspace: Path) -> None:
    report = build_report(workspace)  # ExampleProject uninitialised, no repo

    assert report.outcome is Outcome.WARN
    assert report.failed == 0
    assert report.warned >= 1


# -- invalid workspace manifest ----------------------------------------------


def test_invalid_workspace_manifest_fails(workspace: Path) -> None:
    (workspace / "Workspace.yaml").write_text(
        "schema_version: 9\nworkspace:\n  name: Broken\n", encoding="utf-8"
    )

    report = build_report(workspace)

    assert report.outcome is Outcome.FAIL
    manifest = diagnostics_for(report, CHECK_WORKSPACE_MANIFEST)
    assert len(manifest) == 1
    assert manifest[0].result is DiagnosticResult.FAIL
    assert manifest[0].action is not None


def test_invalid_project_manifest_fails(workspace: Path) -> None:
    """A malformed project manifest fails resolution, surfaced through the folded
    workspace-manifest check."""
    add_project(workspace, name="Alpha", project_id="alpha")
    (workspace / "Projects" / "Alpha" / "project.yaml").write_text(
        "schema_version: 9\nproject:\n  id: alpha\n  name: Alpha\n", encoding="utf-8"
    )

    report = build_report(workspace)

    assert report.outcome is Outcome.FAIL
    assert diagnostics_for(report, CHECK_WORKSPACE_MANIFEST)[0].result is DiagnosticResult.FAIL


# -- missing pack -------------------------------------------------------------


def test_missing_pack_warns(workspace: Path) -> None:
    import shutil

    shutil.rmtree(workspace / "Shared" / "Packs" / "legal")

    report = build_report(workspace)
    packs = diagnostics_for(report, CHECK_CONFIGURED_PACKS)

    assert any(
        d.result is DiagnosticResult.WARN and "legal" in d.explanation for d in packs
    )


# -- uninitialised project ----------------------------------------------------


def test_uninitialised_project_warns_with_init_action(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    report = build_report(workspace)
    alpha = next(
        d
        for d in diagnostics_for(report, CHECK_KERNEL_INITIALISED)
        if d.scope == "alpha"
    )

    assert alpha.result is DiagnosticResult.WARN
    assert "projectos workspace init-project Alpha" in (alpha.action or "")


# -- repository metadata ------------------------------------------------------


def test_repository_metadata_warning(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")  # no repository

    report = build_report(workspace)
    alpha = next(
        d
        for d in diagnostics_for(report, CHECK_REPOSITORY_METADATA)
        if d.scope == "alpha"
    )

    assert alpha.result is DiagnosticResult.WARN


def test_repository_metadata_pass_when_declared(workspace: Path) -> None:
    add_project(
        workspace, name="Alpha", project_id="alpha", repository_remote="git@x:a.git"
    )

    report = build_report(workspace)
    alpha = next(
        d
        for d in diagnostics_for(report, CHECK_REPOSITORY_METADATA)
        if d.scope == "alpha"
    )

    assert alpha.result is DiagnosticResult.PASS


# -- audit integrity ----------------------------------------------------------


def test_audit_integrity_failure(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    repo = initialise(workspace, "Alpha")
    corrupt_audit(repo)

    report = build_report(workspace)
    alpha = next(
        d for d in diagnostics_for(report, CHECK_AUDIT_INTEGRITY) if d.scope == "alpha"
    )

    assert report.outcome is Outcome.FAIL
    assert alpha.result is DiagnosticResult.FAIL
    assert "history --verify" in (alpha.action or "")


def test_audit_check_skipped_when_uninitialised(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    report = build_report(workspace)
    alpha = next(
        d for d in diagnostics_for(report, CHECK_AUDIT_INTEGRITY) if d.scope == "alpha"
    )

    assert alpha.result is DiagnosticResult.SKIP  # neutral — no chain to verify


# -- unresolved focus ---------------------------------------------------------


def test_unresolved_project_focus_fails(workspace: Path) -> None:
    report = build_report(workspace, project="ghost")

    assert report.outcome is Outcome.FAIL
    focus = diagnostics_for(report, CHECK_PROJECT_FOCUS)[0]
    assert focus.result is DiagnosticResult.FAIL
    assert focus.action is not None


# -- deterministic ordering ---------------------------------------------------


def test_diagnostics_ordered_fail_warn_pass_skip(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    repo = initialise(workspace, "Alpha")
    corrupt_audit(repo)

    report = build_report(workspace)
    ranks = [_RESULT_RANK[d.result] for d in report.diagnostics]

    assert ranks == sorted(ranks)  # failures first, then warnings, passes, skips


def test_output_is_deterministic(workspace: Path) -> None:
    add_project(workspace, name="Zeta", project_id="zeta")
    add_project(workspace, name="Alpha", project_id="alpha")

    first = render_report(build_report(workspace))
    second = render_report(build_report(workspace))

    assert first == second


def test_projects_ordered_by_identifier_within_a_result(workspace: Path) -> None:
    add_project(workspace, name="Zeta", project_id="zeta")
    add_project(workspace, name="Alpha", project_id="alpha")

    report = build_report(workspace)
    # Among the WARN kernel-initialised checks, projects appear in id order.
    warn_scopes = [
        d.scope
        for d in diagnostics_for(report, CHECK_KERNEL_INITIALISED)
        if d.result is DiagnosticResult.WARN
    ]
    assert warn_scopes == sorted(warn_scopes)


# -- remediation safety -------------------------------------------------------


def _referenced_commands(report: DoctorReport) -> list[str]:
    commands: list[str] = []
    for diagnostic in report.diagnostics:
        if diagnostic.action:
            commands += re.findall(r"`(projectos [^`]+)`", diagnostic.action)
    return commands


def test_every_suggested_command_is_verified(workspace: Path) -> None:
    # A workspace exercising every action-bearing diagnostic at once.
    add_project(workspace, name="Alpha", project_id="alpha")  # uninitialised + no repo
    repo_b = initialise(workspace, "ExampleProject")
    corrupt_audit(repo_b)  # audit failure → history --verify action
    import shutil

    shutil.rmtree(workspace / "Shared" / "Packs" / "software")

    report = build_report(workspace)
    commands = _referenced_commands(report)

    assert commands  # there is at least one suggestion to validate
    for command in commands:
        assert any(command.startswith(v) for v in _VERIFIED_COMMANDS), command


def test_no_suggested_action_is_destructive(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    repo = initialise(workspace, "ExampleProject")
    corrupt_audit(repo)

    report = build_report(workspace, project=None)
    for diagnostic in report.diagnostics:
        if diagnostic.action:
            low = diagnostic.action.lower()
            assert not any(tok in low for tok in _DESTRUCTIVE_TOKENS), diagnostic.action


# -- project-focused ----------------------------------------------------------


def test_project_focused_doctor_narrows_to_the_target(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    report = build_report(workspace, project="alpha")

    assert report.focus == "alpha"
    project_scopes = {d.scope for d in report.diagnostics if d.scope != "workspace"}
    assert project_scopes == {"alpha"}  # ExampleProject not diagnosed


# -- read-only ----------------------------------------------------------------


def test_doctor_changes_nothing_on_disk(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    initialise(workspace, "Alpha")
    before = snapshot(workspace)

    build_report(workspace)
    build_report(workspace, project="alpha")

    assert snapshot(workspace) == before


def test_missing_workspace_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(NotFoundError):
        build_report(tmp_path / "nope")


# -- P7/P8 non-regression -----------------------------------------------------


def test_doctor_reuses_status_projects(workspace: Path) -> None:
    """Doctor derives from the P8/P7 read-model — its project scopes match status,
    and status/handoff still behave unchanged."""
    add_project(workspace, name="Alpha", project_id="alpha")
    add_project(workspace, name="Beta", project_id="beta")

    report = build_report(workspace)
    doctor_projects = {d.scope for d in report.diagnostics if d.scope != "workspace"}
    status_ids = {p.project_id for p in build_status(workspace).projects}
    handoff_ids = {p.project_id for p in build_handoff(workspace).projects}

    assert doctor_projects == status_ids == handoff_ids
    # P8 status still classifies the same workspace as a warning (uninitialised).
    assert build_status(workspace).condition is Condition.WARNING


# -- CLI ----------------------------------------------------------------------


def test_cli_doctor_ok_when_operational(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")

    code = main(["workspace", "doctor", "--workspace", str(workspace)])

    assert code == int(ExitCode.OK)  # warnings are still operational


def test_cli_doctor_failure_exit_code(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    repo = initialise(workspace, "Alpha")
    corrupt_audit(repo)

    code = main(["workspace", "doctor", "--workspace", str(workspace)])

    assert code == int(ExitCode.ESCALATION_REQUIRED)


def test_cli_doctor_is_read_only(workspace: Path) -> None:
    add_project(workspace, name="Alpha", project_id="alpha")
    before = snapshot(workspace)

    main(["workspace", "doctor", "--workspace", str(workspace)])

    assert snapshot(workspace) == before
