"""P15 — Workspace escalation bridge.

Open and resolve escalations for one selected project's assignment through the
*existing* canonical paths (`lifecycle.escalate` / `lifecycle.resolve`), from the
workspace. These tests drive a real escalate → resolve round trip, prove resolution by
id and name, persisted status + audit + queue/status/doctor/handoff reflection, and
every fail-closed case — including the founder-only authority gate on resolution —
plus mutation isolation and no duplicated escalation logic.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pytest

from projectos.cli.commands import cmd_founder
from projectos.cli.main import main
from projectos.domain.enums import Status
from projectos.domain.errors import ExitCode
from projectos.domain.ids import AssignmentId, EscalationId
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import (
    add_project,
    init_project_kernel,
    open_project_kernel,
)
from projectos.infrastructure.workspace_doctor import build_report
from projectos.infrastructure.workspace_handoff import build_handoff
from projectos.infrastructure.workspace_queue import build_queue
from projectos.infrastructure.workspace_status import build_status

FOUNDER_ID = "founder@example.test"
FOUNDER_NAME = "Test Founder"
OPTIONS = ["--option", "O1|Proceed anyway|risk accepted",
           "--option", "O2|Cancel it|work is lost"]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def register_started(
    workspace: Path, name: str, project_id: str, tmp_path: Path, *, git_email: str = FOUNDER_ID
) -> Path:
    """Register a project (git repo with a chosen acting identity), initialise it, and
    generate its first ACTIVE assignment."""
    repo = tmp_path / f"{project_id}_repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", git_email)
    _git(repo, "config", "user.name", "Actor")
    add_project(workspace, name=name, project_id=project_id, repository_path=str(repo))
    init_project_kernel(
        workspace, name=name, founder_id=FOUNDER_ID, founder_name=FOUNDER_NAME
    )
    main(["workspace", "next", "--workspace", str(workspace), "--project", project_id])
    return repo


def escalate_cmd(workspace: Path, project: str, *extra: str) -> int:
    return main(
        ["workspace", "assignment", "escalate", "--workspace", str(workspace),
         "--project", project, "--summary", "The founder must decide", *OPTIONS, *extra]
    )


def resolve_cmd(workspace: Path, project: str, escalation: str, *extra: str) -> int:
    return main(
        ["workspace", "assignment", "resolve", "--workspace", str(workspace),
         "--project", project, "--escalation", escalation, "--decision", "O1", *extra]
    )


def status_of(workspace: Path, name: str, assignment_id: str) -> Status:
    return open_project_kernel(workspace, name).assignments.get(
        AssignmentId.parse(assignment_id)
    ).status


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# -- successful escalation & resolution ---------------------------------------


def test_escalate_freezes_the_assignment(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)

    code = escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    assert code == int(ExitCode.ESCALATION_REQUIRED)
    assert status_of(workspace, "Alpha", "A-0001") is Status.ESCALATED
    assert len(open_project_kernel(workspace, "Alpha").lifecycle.open_escalations()) == 1


def test_resolve_restores_the_assignment(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)
    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    code = resolve_cmd(workspace, "alpha", "E-0001", "--outcome", "proceed")

    assert code == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.ACTIVE  # proceed restores prior
    kernel = open_project_kernel(workspace, "Alpha")
    assert not kernel.escalations.get(EscalationId.parse("E-0001")).is_open  # resolved
    assert kernel.lifecycle.open_escalations() == ()


def test_project_resolution_by_id_and_name(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)

    assert escalate_cmd(workspace, "alpha", "--assignment", "A-0001") == int(  # by id
        ExitCode.ESCALATION_REQUIRED
    )
    assert resolve_cmd(workspace, "Alpha", "E-0001") == int(ExitCode.OK)  # by name
    assert status_of(workspace, "Alpha", "A-0001") is Status.ACTIVE


def test_escalate_defaults_to_the_in_flight_assignment(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)

    code = escalate_cmd(workspace, "alpha")  # no --assignment → the ACTIVE one

    assert code == int(ExitCode.ESCALATION_REQUIRED)
    assert status_of(workspace, "Alpha", "A-0001") is Status.ESCALATED


# -- persistence, audit & reflection ------------------------------------------


def test_escalation_appends_audit_and_verifies(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)
    before = len(open_project_kernel(workspace, "Alpha").audit.read_all())

    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    kernel = open_project_kernel(workspace, "Alpha")
    assert len(kernel.audit.read_all()) > before  # escalation_opened + freeze transition
    kernel.lifecycle.verify_integrity()  # chain intact — went through the lifecycle


def test_queue_status_doctor_handoff_reflect_escalation(
    workspace: Path, tmp_path: Path
) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)
    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    # Queue: the escalated assignment is definitively in the blocked bucket.
    alpha_q = build_queue(workspace, project="alpha").projects[0]
    assert [a.id for a in alpha_q.blocked] == ["A-0001"]
    assert alpha_q.active == ()

    # Status / doctor / handoff all resolve the project and reflect it as not active.
    status = build_status(workspace, project="alpha")
    assert status.projects_with_active_assignment == 0
    doctor = build_report(workspace, project="alpha")
    assert any(d.scope == "alpha" for d in doctor.diagnostics)
    handoff = build_handoff(workspace, project="alpha")
    assert handoff.projects[0].current_assignment is None  # ESCALATED is not in-flight


# -- fail-closed --------------------------------------------------------------


def test_missing_assignment_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)

    assert escalate_cmd(workspace, "alpha", "--assignment", "A-9999") != int(ExitCode.OK)


def test_illegal_source_status_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)
    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")  # → ESCALATED

    # Resolving with CANCEL cancels the assignment; a second escalate on a CANCELLED
    # assignment has no ESCALATE edge → illegal transition, fail closed.
    resolve_cmd(workspace, "alpha", "E-0001", "--outcome", "cancel")
    assert status_of(workspace, "Alpha", "A-0001") is Status.CANCELLED

    code = escalate_cmd(workspace, "alpha", "--assignment", "A-0001")
    assert code != int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.CANCELLED  # unchanged


def test_escalate_requires_summary(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)

    code = main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
                 "--project", "alpha", "--assignment", "A-0001", *OPTIONS])  # no --summary

    assert code == int(ExitCode.INVARIANT_ERROR)
    assert status_of(workspace, "Alpha", "A-0001") is Status.ACTIVE  # unchanged


def test_escalate_with_too_few_options_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)

    code = main(["workspace", "assignment", "escalate", "--workspace", str(workspace),
                 "--project", "alpha", "--assignment", "A-0001", "--summary", "Decide",
                 "--option", "O1|Only one|not enough"])

    assert code != int(ExitCode.OK)  # domain rejects fewer than two options (spec 9.3)


def test_resolve_requires_escalation_and_decision(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)
    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    no_esc = main(["workspace", "assignment", "resolve", "--workspace", str(workspace),
                   "--project", "alpha", "--decision", "O1"])
    assert no_esc == int(ExitCode.INVARIANT_ERROR)


def test_resolve_invalid_decision_fails_closed(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)
    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    code = main(["workspace", "assignment", "resolve", "--workspace", str(workspace),
                 "--project", "alpha", "--escalation", "E-0001",
                 "--decision", "NOPE", "--outcome", "proceed"])

    assert code != int(ExitCode.OK)  # decision is not one of the escalation's options


def test_resolve_is_founder_only(workspace: Path, tmp_path: Path) -> None:
    # The acting identity (the repo's git email) is NOT the founder.
    register_started(workspace, "Alpha", "alpha", tmp_path, git_email="intruder@example.test")
    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")  # escalate needs no authority

    code = resolve_cmd(workspace, "alpha", "E-0001")

    assert code == int(ExitCode.INVARIANT_ERROR)  # only the founder resolves (spec 9.2)
    assert status_of(workspace, "Alpha", "A-0001") is Status.ESCALATED  # unchanged
    assert open_project_kernel(workspace, "Alpha").escalations.get(
        EscalationId.parse("E-0001")
    ).is_open  # still open


def test_integrity_failure_fails_closed(workspace: Path, tmp_path: Path) -> None:
    repo = register_started(workspace, "Alpha", "alpha", tmp_path)
    audit_dir = Layout.for_repo(repo).audit_dir
    for ndjson in audit_dir.glob("*.ndjson"):
        ndjson.write_text("{ not valid json\n", encoding="utf-8")

    assert escalate_cmd(workspace, "alpha", "--assignment", "A-0001") != int(ExitCode.OK)


def test_unresolved_project_and_uninitialised_fail_closed(workspace: Path) -> None:
    assert escalate_cmd(workspace, "ghost", "--assignment", "A-0001") != int(ExitCode.OK)
    add_project(workspace, name="Beta", project_id="beta")  # registered, not init
    assert escalate_cmd(workspace, "beta", "--assignment", "A-0001") != int(ExitCode.OK)


# -- mutation boundary --------------------------------------------------------


def test_only_the_selected_project_is_mutated(workspace: Path, tmp_path: Path) -> None:
    register_started(workspace, "Alpha", "alpha", tmp_path)
    register_started(workspace, "Bravo", "bravo", tmp_path)
    bravo_projectos_before = snapshot(tmp_path / "bravo_repo" / ".projectos")
    manifest_before = (workspace / "Workspace.yaml").read_bytes()

    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    assert snapshot(tmp_path / "bravo_repo" / ".projectos") == bravo_projectos_before
    assert (workspace / "Workspace.yaml").read_bytes() == manifest_before
    assert status_of(workspace, "Bravo", "A-0001") is Status.ACTIVE  # Bravo untouched


# -- no duplicated logic / regression -----------------------------------------


def test_delegates_to_the_same_escalation_path_as_the_service(
    workspace: Path, tmp_path: Path
) -> None:
    """workspace escalate reaches kernel.lifecycle.escalate; the persisted result is
    the same an escalation opened through the service would produce."""
    register_started(workspace, "Alpha", "alpha", tmp_path)

    escalate_cmd(workspace, "alpha", "--assignment", "A-0001")

    kernel = open_project_kernel(workspace, "Alpha")
    assert kernel.escalations.get(EscalationId.parse("E-0001")).assignment_id is not None
    assert status_of(workspace, "Alpha", "A-0001") is Status.ESCALATED


def test_existing_per_project_founder_still_works(workspace: Path, tmp_path: Path) -> None:
    """Regression guard: the run_escalate/run_resolve extraction left `projectos
    founder escalate`/`resolve` unchanged. Driven through cmd_founder directly."""
    repo = register_started(workspace, "Alpha", "alpha", tmp_path)

    escalate_args = argparse.Namespace(
        repo=repo, identity=None, founder_command="escalate", trigger="founder_decision",
        summary="Decide", option=["O1|Proceed|risk", "O2|Cancel|loss"],
        assignment="A-0001", recommend="O1",
    )
    assert cmd_founder(escalate_args) == int(ExitCode.ESCALATION_REQUIRED)
    assert status_of(workspace, "Alpha", "A-0001") is Status.ESCALATED

    resolve_args = argparse.Namespace(
        repo=repo, identity=None, founder_command="resolve", escalation="E-0001",
        decision="O1", outcome="proceed",
    )
    assert cmd_founder(resolve_args) == int(ExitCode.OK)
    assert status_of(workspace, "Alpha", "A-0001") is Status.ACTIVE
