"""ProjectOS CLI (spec section 13).

Each command is a thin wrapper over exactly one kernel operation. The CLI parses
arguments, calls the kernel, formats the result, and maps typed errors onto the
deterministic exit-code contract:

    0  ok
    1  rule failure (verification rejected)
    2  invariant or validation error
    3  escalation required

Deterministic exit codes are what make the CLI scriptable by agents: an executor
can branch on the code without parsing prose.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Sequence
from pathlib import Path

from projectos.cli import commands
from projectos.domain.enums import EscalationTrigger, FounderDecision, RepositoryAdapterKind, Role
from projectos.domain.errors import ExitCode, ProjectOSError

PROGRAM = "projectos"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="ProjectOS AI — repository-driven orchestration kernel (v0.1).",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=None,
        metavar="PATH",
        help="Repository root (default: discovered from the working directory).",
    )
    parser.add_argument(
        "--identity",
        default=None,
        metavar="ID",
        help="Acting identity for this command (default: git user.email).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- init ------------------------------------------------------------------
    init = subparsers.add_parser("init", help="Scaffold .projectos/ in this repository.")
    init.add_argument("--project-id", required=True, help="Kebab-case, immutable project id.")
    init.add_argument("--name", required=True, help="Human-readable project name.")
    init.add_argument("--founder-id", required=True, help="Founder identity used for approvals.")
    init.add_argument("--founder-name", required=True, help="Founder display name.")
    init.add_argument("--description", default="", help="One-line project description.")
    init.add_argument(
        "--adapter",
        choices=[kind.value for kind in RepositoryAdapterKind],
        default=RepositoryAdapterKind.LOCAL_GIT.value,
        help="Repository adapter (default: local_git).",
    )
    init.add_argument("--default-branch", default="main")
    init.add_argument("--github-owner", default=None)
    init.add_argument("--github-repo", default=None)
    init.add_argument(
        "--force", action="store_true", help="Overwrite an existing manifest."
    )

    # -- workspace -------------------------------------------------------------
    workspace = subparsers.add_parser(
        "workspace", help="Local-first multi-project workspace tooling."
    )
    workspace_subs = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_init = workspace_subs.add_parser(
        "init", help="Bootstrap a workspace directory tree (idempotent)."
    )
    workspace_init.add_argument(
        "path",
        nargs="?",
        default="Workspace",
        help="Workspace root directory (default: ./Workspace). Created if missing.",
    )
    workspace_init.add_argument(
        "--name", default=None, help="Workspace name (default: the root directory name)."
    )
    workspace_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing starter files (default: preserve them).",
    )

    ws_add = workspace_subs.add_parser(
        "add-project", help="Register a project in the workspace (idempotent)."
    )
    ws_add.add_argument("name", help="Project name.")
    ws_add.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_add.add_argument("--pack", default="rapid-build", help="Pack backing the project.")
    ws_add.add_argument("--project-id", default=None, help="Kebab-case id (default: from name).")
    ws_add.add_argument("--description", default="", help="One-line project description.")
    ws_add.add_argument(
        "--repo", default=None, help="Local path to the project's repository (optional)."
    )
    ws_add.add_argument(
        "--repo-remote",
        default=None,
        help="Repository remote URL, for a repository hosted elsewhere (optional).",
    )
    ws_add.add_argument("--repo-branch", default=None, help="Repository default branch (optional).")
    ws_add.add_argument("--force", action="store_true", help="Overwrite an existing project.yaml.")

    ws_initp = workspace_subs.add_parser(
        "init-project",
        help="Scaffold a registered project's ProjectOS kernel from its pack (idempotent).",
    )
    ws_initp.add_argument("name", help="Registered project name.")
    ws_initp.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_initp.add_argument("--founder-id", required=True, help="Founder identity for the project.")
    ws_initp.add_argument("--founder-name", required=True, help="Founder display name.")
    ws_initp.add_argument("--force", action="store_true", help="Re-initialise an existing kernel.")

    ws_list = workspace_subs.add_parser("list", help="List registered projects and status.")
    ws_list.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")

    ws_status = workspace_subs.add_parser(
        "status",
        help="Concise, read-only operational status of the workspace and its projects.",
    )
    ws_status.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_status.add_argument(
        "--project",
        default=None,
        help="Focus on one project by id or name (project-first resolution).",
    )

    ws_doctor = workspace_subs.add_parser(
        "doctor",
        help="Read-only diagnostics with safe, advisory remediation guidance.",
    )
    ws_doctor.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_doctor.add_argument(
        "--project",
        default=None,
        help="Diagnose one project by id or name (project-first resolution).",
    )

    ws_queue = workspace_subs.add_parser(
        "queue",
        help="Read-only assignment queue: active/ready/blocked/completed per project.",
    )
    ws_queue.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_queue.add_argument(
        "--project",
        default=None,
        help="Show one project's queue by id or name (project-first resolution).",
    )

    ws_next = workspace_subs.add_parser(
        "next",
        help="Generate the next assignment for one project via the existing next path.",
    )
    ws_next.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_next.add_argument(
        "--project",
        required=True,
        help="The project to generate for, by id or name (required — no auto-select).",
    )

    ws_plan = workspace_subs.add_parser(
        "plan",
        help="Recommend one safe next action for a project (read-only; recommends, never runs).",
    )
    ws_plan.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_plan.add_argument(
        "--project",
        required=True,
        help="The project to plan for, by id or name (required — no auto-select).",
    )

    ws_run = workspace_subs.add_parser(
        "run",
        help="Execute one safe planner recommendation — MUTATES only with --confirm.",
    )
    ws_run.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_run.add_argument(
        "--project",
        required=True,
        help="The project to act on, by id or name (required — no auto-select).",
    )
    ws_run.add_argument(
        "--confirm",
        action="store_true",
        help="Required to execute. Without it, the plan is shown and nothing is run.",
    )

    ws_dashboard = workspace_subs.add_parser(
        "dashboard",
        help="Aggregate the workspace read-models into one read-only founder view.",
    )
    ws_dashboard.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_dashboard.add_argument(
        "--project",
        default=None,
        help="Focus the project rows on one project by id or name (summary stays workspace-wide).",
    )

    ws_focus = workspace_subs.add_parser(
        "focus",
        help="Select the one project needing the founder's attention (read-only).",
    )
    ws_focus.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")

    ws_recommend = workspace_subs.add_parser(
        "recommend-agent",
        help="Recommend one supported agent for an assignment (read-only; invokes nothing).",
    )
    ws_recommend.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_recommend.add_argument(
        "--project",
        required=True,
        help="The project owning the assignment, by id or name (required).",
    )
    ws_recommend.add_argument(
        "--assignment",
        default=None,
        help="Assignment id (default: the assignment currently in flight).",
    )

    ws_dispatch = workspace_subs.add_parser(
        "dispatch",
        help="Print a read-only, copy-ready agent handoff package (invokes no agent).",
    )
    ws_dispatch.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_dispatch.add_argument(
        "--project",
        required=True,
        help="The project to hand off, by id or name (required — no auto-select).",
    )
    ws_dispatch.add_argument(
        "--agent",
        required=True,
        choices=["claude-code", "claude-chat", "claude-cowork"],
        help="The explicit AI worker type (required — no auto-select).",
    )
    ws_dispatch.add_argument(
        "--assignment",
        default=None,
        help="Assignment id (default: the assignment currently in flight).",
    )

    ws_assignment = workspace_subs.add_parser(
        "assignment",
        help="Operate one project's assignment via existing lifecycle transitions.",
    )
    ws_assignment.add_argument(
        "action",
        choices=["show", "verify", "complete", "escalate", "resolve", "block", "unblock"],
        help="Lifecycle action to perform on the selected assignment.",
    )
    ws_assignment.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_assignment.add_argument(
        "--project",
        required=True,
        help="The project owning the assignment, by id or name (required).",
    )
    ws_assignment.add_argument(
        "--assignment",
        default=None,
        help="Assignment id (default: the assignment currently in flight).",
    )
    ws_assignment.add_argument(
        "--reason", default="", help="Reason for `block` (required for the block action)."
    )
    ws_assignment.add_argument(
        "--report",
        type=Path,
        default=None,
        metavar="FILE",
        help="Completion report (YAML) to ingest before `verify` (same as `verify --report`).",
    )
    ws_assignment.add_argument(
        "--role",
        choices=[role.value for role in Role],
        default=Role.OWNER.value,
        help="Role for `complete` (default: owner; same as `complete --role`).",
    )
    ws_assignment.add_argument(
        "--attest",
        action="store_true",
        help="For `complete`: record a human attestation instead of an approval.",
    )
    # -- escalate (same arguments as `founder escalate`) ----------------------
    ws_assignment.add_argument(
        "--summary", default="", help="For `escalate`: the decision statement (required)."
    )
    ws_assignment.add_argument(
        "--trigger",
        choices=[trigger.value for trigger in EscalationTrigger],
        default=EscalationTrigger.FOUNDER_DECISION.value,
        help="For `escalate`: the escalation trigger (default: founder_decision).",
    )
    ws_assignment.add_argument(
        "--option",
        action="append",
        default=[],
        metavar="ID|DESCRIPTION|CONSEQUENCE",
        help="For `escalate`: repeatable; at least two are required (spec 9.3).",
    )
    ws_assignment.add_argument(
        "--recommend", default=None, help="For `escalate`: the recommended option id."
    )
    # -- resolve (founder-only; same arguments as `founder resolve`) ----------
    ws_assignment.add_argument(
        "--escalation", default=None, help="For `resolve`: the escalation id, e.g. E-0001."
    )
    ws_assignment.add_argument(
        "--decision", default=None, help="For `resolve`: option id or free-form directive."
    )
    ws_assignment.add_argument(
        "--outcome",
        choices=[outcome.value for outcome in FounderDecision],
        default=FounderDecision.PROCEED.value,
        help="For `resolve`: the founder decision outcome (default: proceed).",
    )

    ws_handoff = workspace_subs.add_parser(
        "handoff",
        help="Print a deterministic, read-only workspace handoff for a fresh session.",
    )
    ws_handoff.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_handoff.add_argument(
        "--project",
        default=None,
        help="Focus on one project by id or name (project-first resolution).",
    )

    ws_discover = workspace_subs.add_parser(
        "discover",
        help="Discover projects under the workspace and report their registration status.",
    )
    ws_discover.add_argument("--workspace", default=".", help="Workspace root (default: cwd).")
    ws_discover.add_argument(
        "--register",
        action="store_true",
        help="Register valid, unregistered projects (default: report only).",
    )
    ws_discover.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only, never change state (overrides --register).",
    )

    # -- validate --------------------------------------------------------------
    subparsers.add_parser(
        "validate", help="Validate manifest, packs, and state. Makes no changes."
    )

    # -- pack ------------------------------------------------------------------
    pack = subparsers.add_parser("pack", help="Project-pack tooling.")
    pack_subs = pack.add_subparsers(dest="pack_command", required=True)
    pack_validate = pack_subs.add_parser(
        "validate", help="Validate a pack directory without installing it."
    )
    pack_validate.add_argument("path", help="Directory containing pack.yaml.")

    # -- status ----------------------------------------------------------------
    status = subparsers.add_parser(
        "status", help="Project, active assignment, blockers, open escalations."
    )
    status.add_argument(
        "--brief", action="store_true", help="Also print the active assignment's briefing."
    )

    # -- next ------------------------------------------------------------------
    nxt = subparsers.add_parser(
        "next", help="Activate the ready assignment, or generate the successor."
    )
    nxt.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be generated without writing state.",
    )

    # -- verify ----------------------------------------------------------------
    verify = subparsers.add_parser(
        "verify", help="Verify the active assignment against repository evidence."
    )
    verify.add_argument("assignment", nargs="?", help="Assignment id (default: the active one).")
    verify.add_argument(
        "--report",
        type=Path,
        default=None,
        metavar="FILE",
        help="Completion report (YAML) to ingest before verifying.",
    )

    # -- complete --------------------------------------------------------------
    complete = subparsers.add_parser(
        "complete", help="Record an approval; closes the assignment when all are in."
    )
    complete.add_argument("assignment", nargs="?", help="Assignment id (default: the active one).")
    complete.add_argument(
        "--role",
        choices=[role.value for role in Role],
        default=Role.OWNER.value,
        help="Role approving (default: owner).",
    )
    complete.add_argument(
        "--attest",
        action="store_true",
        help="Record a human attestation instead of an approval (spec 8.2).",
    )

    # -- block -----------------------------------------------------------------
    block = subparsers.add_parser("block", help="Block an assignment, or unblock it.")
    block.add_argument("assignment", nargs="?", help="Assignment id (default: the active one).")
    block.add_argument("--reason", default="", help="Why the assignment is blocked.")
    block.add_argument(
        "--unblock",
        action="store_true",
        help="Return a BLOCKED assignment to READY once dependencies are closed.",
    )

    # -- founder ---------------------------------------------------------------
    founder = subparsers.add_parser("founder", help="Founder escalation queue.")
    founder_subs = founder.add_subparsers(dest="founder_command", required=True)

    founder_subs.add_parser("list", help="Show open escalations.")

    raise_parser = founder_subs.add_parser("escalate", help="Open a decision-ready escalation.")
    raise_parser.add_argument("--summary", required=True, help="One-paragraph decision statement.")
    raise_parser.add_argument(
        "--trigger",
        choices=[trigger.value for trigger in EscalationTrigger],
        default=EscalationTrigger.FOUNDER_DECISION.value,
    )
    raise_parser.add_argument("--assignment", default=None, help="Scope to one assignment.")
    raise_parser.add_argument(
        "--option",
        action="append",
        default=[],
        metavar="ID|DESCRIPTION|CONSEQUENCE",
        help="Repeatable; at least two are required (spec 9.3).",
    )
    raise_parser.add_argument("--recommend", default=None, help="Recommended option id.")

    resolve = founder_subs.add_parser("resolve", help="Founder-only resolution.")
    resolve.add_argument("escalation", help="Escalation id, e.g. E-0001.")
    resolve.add_argument("--decision", required=True, help="Option id or free-form directive.")
    resolve.add_argument(
        "--outcome",
        choices=[outcome.value for outcome in FounderDecision],
        default=FounderDecision.PROCEED.value,
    )

    # -- history ---------------------------------------------------------------
    history = subparsers.add_parser("history", help="Audit log (append-only, hash-chained).")
    history.add_argument("--assignment", default=None, help="Filter to one assignment.")
    history.add_argument(
        "--verify", action="store_true", help="Re-walk the hash chain and report integrity."
    )
    history.add_argument(
        "--limit", type=int, default=40, help="Most recent entries to show (default: 40)."
    )

    return parser


HANDLERS = {
    "init": commands.cmd_init,
    "workspace": commands.cmd_workspace,
    "validate": commands.cmd_validate,
    "pack": commands.cmd_pack,
    "status": commands.cmd_status,
    "next": commands.cmd_next,
    "verify": commands.cmd_verify,
    "complete": commands.cmd_complete,
    "block": commands.cmd_block,
    "founder": commands.cmd_founder,
    "history": commands.cmd_history,
}


def _force_utf8_output() -> None:
    """Print UTF-8 regardless of the console's default codepage.

    Windows consoles default to cp1252, which cannot encode the box-drawing and
    arrow characters used in the output; without this the CLI dies with a
    UnicodeEncodeError before it can print anything or return its exit code.
    `errors="replace"` keeps a genuinely limited terminal readable rather than
    fatal.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        with contextlib.suppress(ValueError, OSError):  # exotic stream types
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    _force_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)

    handler = HANDLERS[args.command]
    try:
        return int(handler(args))
    except ProjectOSError as error:
        # Typed errors carry their own exit code; nothing else decides one.
        print(f"error: {error.render()}", file=sys.stderr)
        return int(error.exit_code)
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        print("aborted", file=sys.stderr)
        return int(ExitCode.INVARIANT_ERROR)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
