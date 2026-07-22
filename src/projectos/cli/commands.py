"""Command handlers. Each maps 1:1 onto a kernel operation (spec section 2.2).

Handlers do three things and nothing more: translate arguments into domain values,
call the kernel, and render the result. Any rule they appear to apply is one the
kernel already decided.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from projectos.application import validation_service
from projectos.cli import formatting
from projectos.domain.assignment import Assignment
from projectos.domain.audit import AuditEntry
from projectos.domain.enums import (
    EscalationTrigger,
    EvidenceClass,
    FounderDecision,
    RepositoryAdapterKind,
    Role,
    Status,
)
from projectos.domain.errors import (
    ExitCode,
    NotFoundError,
    ProjectOSError,
    RuleFailure,
    ValidationError,
)
from projectos.domain.escalation import EscalationOption
from projectos.domain.evidence import CompletionClaim, EvidenceRef
from projectos.domain.ids import AssignmentId, EscalationId
from projectos.domain.pack import Pack
from projectos.infrastructure.container import Kernel, build_kernel
from projectos.infrastructure.pack_loading import load_pack_from_directory
from projectos.infrastructure.paths import Layout, discover_repo_root
from projectos.infrastructure.scaffold import build_manifest, scaffold
from projectos.infrastructure.system import StaticIdentityProvider
from projectos.infrastructure.template_binding import YamlTemplateBinder
from projectos.infrastructure.yaml_io import read_yaml


def _kernel(args: argparse.Namespace) -> Kernel:
    identity = StaticIdentityProvider(args.identity) if args.identity else None
    return build_kernel(args.repo, identity=identity)


def _resolve_assignment_id(kernel: Kernel, raw: str | None) -> AssignmentId:
    """Explicit id wins; otherwise operate on the assignment currently in flight."""
    if raw:
        return AssignmentId.parse(raw)
    return kernel.lifecycle.require_current().id


# -- init ---------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    root = (args.repo or discover_repo_root(Path.cwd())).resolve()
    layout = Layout.for_repo(root)

    manifest = build_manifest(
        project_id=args.project_id,
        project_name=args.name,
        description=args.description,
        founder_id=args.founder_id,
        founder_name=args.founder_name,
        adapter=RepositoryAdapterKind(args.adapter),
        default_branch=args.default_branch,
        github_owner=args.github_owner,
        github_repo=args.github_repo,
    )
    scaffold(layout, manifest, force=args.force)

    print(formatting.project_summary(manifest))
    print()
    print(f"  Initialised {layout.root}")
    print("  Next: projectos status")
    return int(ExitCode.OK)


# -- workspace ----------------------------------------------------------------


def cmd_workspace(args: argparse.Namespace) -> int:
    """Workspace tooling. Dispatches on the workspace subcommand."""
    if args.workspace_command == "init":
        return _cmd_workspace_init(args)
    if args.workspace_command == "add-project":
        return _cmd_workspace_add_project(args)
    if args.workspace_command == "init-project":
        return _cmd_workspace_init_project(args)
    if args.workspace_command == "list":
        return _cmd_workspace_list(args)
    if args.workspace_command == "discover":
        return _cmd_workspace_discover(args)
    if args.workspace_command == "handoff":
        return _cmd_workspace_handoff(args)
    if args.workspace_command == "status":
        return _cmd_workspace_status(args)
    if args.workspace_command == "doctor":
        return _cmd_workspace_doctor(args)
    if args.workspace_command == "queue":
        return _cmd_workspace_queue(args)
    if args.workspace_command == "next":
        return _cmd_workspace_next(args)
    if args.workspace_command == "assignment":
        return _cmd_workspace_assignment(args)
    raise ValidationError(f"Unknown workspace command {args.workspace_command!r}")


def _cmd_workspace_init(args: argparse.Namespace) -> int:
    """`workspace init <path>` — bootstrap a local-first workspace (P3).

    Idempotent: creates whatever is missing and preserves existing files, so a
    second run is a visible no-op rather than a corruption.
    """
    from projectos.infrastructure.workspace import bootstrap_workspace

    root = Path(args.path).resolve()
    result = bootstrap_workspace(root, name=args.name, force=args.force)

    title = "WORKSPACE CREATED" if result.is_fresh else "WORKSPACE UPDATED (idempotent)"
    print(formatting.heading(f"{title}  {result.root}"))
    print(f"  created: {len(result.created)}    kept: {len(result.kept)}")
    if result.created:
        print()
        print("  new:")
        for path in result.created:
            print(f"    + {path}")
    if result.kept and not result.is_fresh:
        print()
        print(
            f"  preserved {len(result.kept)} existing item(s) — "
            "re-run with --force to overwrite."
        )
    print()
    print(f"  Workspace manifest: {result.root / 'Workspace.yaml'}")
    return int(ExitCode.OK)


def _cmd_workspace_add_project(args: argparse.Namespace) -> int:
    """`workspace add-project <name>` — register a project (P4.2). Idempotent."""
    from projectos.infrastructure.workspace_bridge import add_project

    project_dir = add_project(
        Path(args.workspace),
        name=args.name,
        pack=args.pack,
        project_id=args.project_id,
        description=args.description,
        repository_path=args.repo,
        repository_remote=args.repo_remote,
        repository_branch=args.repo_branch,
        force=args.force,
    )
    print(formatting.heading(f"PROJECT REGISTERED  {args.name}"))
    print(f"  pack        {args.pack}")
    if args.repo:
        print(f"  repository  {Path(args.repo).resolve()}")
    if args.repo_remote:
        print(f"  remote      {args.repo_remote}")
    print(f"  manifest    {project_dir / 'project.yaml'}")
    print()
    print(f"  Next: projectos workspace init-project {args.name} "
          "--founder-id <id> --founder-name <name>")
    return int(ExitCode.OK)


def _cmd_workspace_init_project(args: argparse.Namespace) -> int:
    """`workspace init-project <name>` — scaffold the project's kernel (P4.2)."""
    from projectos.infrastructure.workspace_bridge import init_project_kernel

    repo = init_project_kernel(
        Path(args.workspace),
        name=args.name,
        founder_id=args.founder_id,
        founder_name=args.founder_name,
        force=args.force,
    )
    print(formatting.heading(f"PROJECT KERNEL READY  {args.name}"))
    print(f"  repository  {repo}")
    print(f"  state       {repo / '.projectos'}")
    print()
    print(f"  Next: projectos --repo {repo} next")
    return int(ExitCode.OK)


def _cmd_workspace_list(args: argparse.Namespace) -> int:
    """`workspace list` — registered projects and their status (P4.2). Read-only."""
    from projectos.infrastructure.workspace_bridge import list_projects

    statuses = list_projects(Path(args.workspace))
    print(formatting.heading(f"WORKSPACE PROJECTS  ({len(statuses)})"))
    if not statuses:
        print("  none registered — `projectos workspace add-project <name>`")
        return int(ExitCode.OK)
    for status in statuses:
        active = status.active_assignment or "—"
        state = "initialised" if status.initialised else "not initialised"
        print(f"  {status.name}  ({status.project_id})")
        print(f"    pack        {status.pack or '—'}")
        print(f"    repository  {status.repository}")
        print(f"    kernel      {state}    active assignment: {active}")
    return int(ExitCode.OK)


def _open_workspace_project(args: argparse.Namespace) -> tuple[str, str, Kernel]:
    """Resolve exactly one registered project and open its kernel through the bridge.

    Shared by the workspace commands that operate on a single project's kernel
    (`next`, `assignment`). Returns ``(workspace_name, project_id, kernel)``. Fails
    closed on a missing/malformed workspace (via `resolve_workspace`), an unresolved
    project, or an uninitialised kernel (via `open_project_kernel`).
    """
    from projectos.infrastructure.workspace_bridge import open_project_kernel
    from projectos.infrastructure.workspace_manifest import resolve_workspace

    workspace_root = Path(args.workspace)
    workspace = resolve_workspace(workspace_root)
    resolved = workspace.by_id(args.project) or workspace.by_name(args.project)
    if resolved is None:
        known = ", ".join(sorted(p.project_id for p in workspace.projects)) or "none"
        raise NotFoundError(
            f"Project {args.project!r} is not registered in this workspace",
            detail=f"Known project identifiers: {known}.",
        )
    kernel = open_project_kernel(workspace_root, resolved.ref.name)
    return workspace.manifest.name, resolved.project_id, kernel


def _cmd_workspace_next(args: argparse.Namespace) -> int:
    """`workspace next --project <id|name>` — generate the next assignment for one
    resolved project through the existing per-project next path (P11).

    Workspace-level orchestration only: resolve exactly one project, open its kernel
    through the existing bridge, and delegate to :func:`run_next` — the same
    generation path `projectos next` uses. No new generator, persistence, or state.
    Fails closed on an unresolved project or an uninitialised kernel; every other
    guard (active slot, escalation, pack loading, integrity) is enforced unchanged
    inside the lifecycle.
    """
    workspace_name, project_id, kernel = _open_workspace_project(args)

    print(formatting.heading(f"WORKSPACE NEXT  {workspace_name}  →  {project_id}"))
    run = run_next(kernel, dry_run=False)
    if run.assignment is not None:
        print(f"    Persisted {kernel.layout.assignment_file(str(run.assignment.id))}")
    return run.exit_code


def _cmd_workspace_assignment(args: argparse.Namespace) -> int:
    """`workspace assignment <action> --project <id|name> [--assignment <id>]`.

    Operate one selected project's assignment through the existing lifecycle
    transitions, from the workspace, without entering the project repository.

    Supported actions — `show`, `block`, `unblock` (P12), `verify` (P13),
    `complete` (P14), `escalate`/`resolve` (P15) — each delegate to the exact
    canonical path the per-project commands use: `kernel.assignments.get` (read),
    `kernel.lifecycle.block`, `kernel.lifecycle.unblock`, :func:`run_verify`
    (`projectos verify`), :func:`run_complete` (`projectos complete`),
    :func:`run_escalate` and :func:`run_resolve` (`projectos founder escalate`/
    `resolve`). Every guard (INV-6 audit integrity, evidence and verifier contracts,
    the VERIFIED-state and §8.6.2 authority requirements for approval, the **founder-
    only** authority for resolution (spec 9.2), the ESCALATE/FOUNDER_RESOLVE legal
    transitions, dependency-closure, persistence, audit logging) is enforced unchanged
    inside the lifecycle service — nothing is reimplemented here. Mutation stays inside
    the selected project's kernel.

    `resolve` targets an escalation by `--escalation` id (not an assignment) and is
    founder-only; every other action operates on the selected or in-flight assignment.

    Fails closed on an unresolved workspace/project, an uninitialised kernel, a missing
    assignment (`get` raises `NotFoundError`), missing/invalid evidence or a verifier
    error (`RuleFailure`), an unverified assignment, an unauthorized actor, incomplete
    approvals, a non-founder resolution attempt, an illegal source status, a malformed
    reason/summary/resolution, an integrity failure, or malformed state — every case
    raised by the reused contracts.
    """
    workspace_name, project_id, kernel = _open_workspace_project(args)
    header = formatting.heading(
        f"WORKSPACE ASSIGNMENT  {workspace_name}  →  {project_id}"
    )

    # `resolve` targets an escalation (not an assignment), so it is handled before the
    # in-flight-assignment resolution the other actions share.
    if args.action == "resolve":
        if not args.escalation:
            raise ValidationError("`workspace assignment resolve` requires --escalation")
        if not args.decision:
            raise ValidationError("`workspace assignment resolve` requires --decision")
        print(header)
        return run_resolve(
            kernel,
            EscalationId.parse(args.escalation),
            args.decision,
            FounderDecision(args.outcome),
        )

    assignment_id = _resolve_assignment_id(kernel, args.assignment)

    if args.action == "show":
        assignment = kernel.assignments.get(assignment_id)
        print(header)
        print(formatting.assignment_summary(assignment))
        if assignment.status is Status.VERIFIED:
            print(f"    Approvals {kernel.lifecycle.approval_status(assignment).describe()}")
        return int(ExitCode.OK)

    if args.action == "verify":
        print(header)
        return run_verify(kernel, assignment_id, report_path=args.report)

    if args.action == "complete":
        print(header)
        return run_complete(
            kernel, assignment_id, role=Role(args.role), attest=args.attest
        )

    if args.action == "escalate":
        if not args.summary.strip():
            raise ValidationError(
                "`workspace assignment escalate` requires --summary",
                detail="A decision-ready escalation states the decision the founder must make.",
            )
        print(header)
        return run_escalate(
            kernel,
            trigger=EscalationTrigger(args.trigger),
            summary=args.summary,
            options=_parse_options(args.option),
            assignment_id=assignment_id,
            recommendation=args.recommend,
        )

    if args.action == "block":
        if not args.reason.strip():
            raise ValidationError(
                "`workspace assignment block` requires --reason",
                detail="A blocker without a stated cause cannot be cleared by anyone else.",
            )
        assignment = kernel.lifecycle.block(assignment_id, args.reason)
    else:  # unblock (argparse restricts `action` to the supported choices)
        assignment = kernel.lifecycle.unblock(assignment_id)

    print(header)
    print(f"    Assignment {assignment_id}")
    print(f"    Action     {args.action}")
    print(f"    Status     {assignment.status.value.upper()}")
    if args.action == "block":
        print(f"    Reason     {args.reason}")
    return int(ExitCode.OK)


def _cmd_workspace_queue(args: argparse.Namespace) -> int:
    """`workspace queue` — read-only assignment queue inspection (P10).

    Partitions each project's persisted assignments into active / ready / blocked /
    completed / other. Read-only. Returns ESCALATION_REQUIRED when any project's
    state could not be read, otherwise OK.
    """
    from projectos.infrastructure.workspace_queue import build_queue, render_queue

    queue = build_queue(Path(args.workspace), project=args.project)
    print(render_queue(queue))

    if queue.has_failures:
        return int(ExitCode.ESCALATION_REQUIRED)
    return int(ExitCode.OK)


def _cmd_workspace_doctor(args: argparse.Namespace) -> int:
    """`workspace doctor` — read-only diagnostics with remediation (P9).

    Returns ESCALATION_REQUIRED when the overall outcome is a failure, otherwise OK
    (a warning is still operational). Makes no changes.
    """
    from projectos.infrastructure.workspace_doctor import Outcome, build_report, render_report

    report = build_report(Path(args.workspace), project=args.project)
    print(render_report(report))

    if report.outcome is Outcome.FAIL:
        return int(ExitCode.ESCALATION_REQUIRED)
    return int(ExitCode.OK)


def _cmd_workspace_status(args: argparse.Namespace) -> int:
    """`workspace status` — concise, read-only operational status (P8).

    Returns ESCALATION_REQUIRED when the overall condition is a failure (unsafe to
    operate), otherwise OK — a warning condition is still operational. Makes no
    changes.
    """
    from projectos.infrastructure.workspace_status import Condition, build_status, render_status

    status = build_status(Path(args.workspace), project=args.project)
    print(render_status(status))

    if status.condition is Condition.FAILURE:
        return int(ExitCode.ESCALATION_REQUIRED)
    return int(ExitCode.OK)


def _cmd_workspace_handoff(args: argparse.Namespace) -> int:
    """`workspace handoff` — deterministic, read-only session context (P7).

    Renders the canonical handoff and returns ESCALATION_REQUIRED when any project's
    integrity or state could not be verified, so a scripted session can branch on it;
    otherwise OK. Makes no changes.
    """
    from projectos.infrastructure.workspace_handoff import build_handoff, render_handoff

    handoff = build_handoff(Path(args.workspace), project=args.project)
    print(render_handoff(handoff))

    if any(project.failure is not None for project in handoff.projects):
        return int(ExitCode.ESCALATION_REQUIRED)
    return int(ExitCode.OK)


def _cmd_workspace_discover(args: argparse.Namespace) -> int:
    """`workspace discover` — find, validate, and classify projects (P6).

    Report-only by default and under `--dry-run`; `--register` (without `--dry-run`)
    registers valid, unregistered projects. Never overwrites an existing registration.
    """
    from projectos.infrastructure.workspace_discovery import (
        DiscoveryStatus,
        discover_workspace,
    )

    report = discover_workspace(
        Path(args.workspace), register=args.register, dry_run=args.dry_run
    )

    mode = "REGISTER" if not report.dry_run else "DRY RUN"
    print(formatting.heading(f"WORKSPACE DISCOVER  {report.root}  [{mode}]"))
    print(
        f"  scanned {report.scanned}    valid {len(report.valid)}    "
        f"registered {len(report.already_registered)}    "
        f"unregistered {len(report.unregistered)}    "
        f"duplicates {len(report.duplicates)}    invalid {len(report.invalid)}"
    )

    if report.projects:
        print()
        symbol = {
            DiscoveryStatus.REGISTERED: "=",
            DiscoveryStatus.UNREGISTERED: "+",
            DiscoveryStatus.DUPLICATE_IDENTIFIER: "!",
            DiscoveryStatus.DUPLICATE_REPOSITORY: "!",
            DiscoveryStatus.INVALID: "x",
        }
        for project in report.projects:
            tag = " (registered now)" if project.registered_now else ""
            ident = project.project_id or "—"
            print(
                f"  {symbol[project.status]} {project.rel_path}  "
                f"[{project.status.value}]  id={ident}{tag}"
            )
            if project.conflicts_with is not None:
                print(f"      conflicts with {project.conflicts_with}")
            if project.error is not None:
                print(f"      {project.error}")

    print()
    if not report.dry_run:
        print(f"  Registered {len(report.newly_registered)} project(s) this run.")
    elif report.unregistered:
        print(
            f"  {len(report.unregistered)} unregistered — re-run with --register to add them."
        )
    else:
        print("  Nothing to register.")
    return int(ExitCode.OK)


# -- validate -----------------------------------------------------------------


def cmd_validate(args: argparse.Namespace) -> int:
    """Manifest, packs, and state schema check (spec 13).

    Read-only: the handler loads, delegates to the application service, and renders.
    It applies no rules of its own.
    """
    kernel = _kernel(args)
    manifest = kernel.manifests.load()

    # Packs are read *without* the loader's fail-closed enforcement, so an
    # incompatible pack becomes a reported finding alongside everything else
    # rather than aborting the run at the first problem. The kernel's own loading
    # path still enforces; this is a report, and a report should be complete.
    loaded: list[tuple[Pack, str | None]] = []
    findings: list[validation_service.Finding] = []
    for requirement in manifest.packs:
        directory = kernel.layout.packs_dir / requirement.name
        try:
            loaded.append((load_pack_from_directory(directory), requirement.version))
        except ProjectOSError as exc:
            findings.append(
                validation_service.Finding(
                    validation_service.Severity.ERROR,
                    "pack.unreadable",
                    exc.message,
                    f"pack {requirement.name!r}",
                    exc.detail or "",
                )
            )

    report = validation_service.validate_project(
        manifest=manifest,
        packs=tuple(loaded),
        assignments=kernel.assignments.list_all(),
        binder=YamlTemplateBinder(),
    ).merged_with(validation_service.ValidationReport(findings=tuple(findings)))

    # Secret scanning runs on every state read (spec 14.1); reaching this point
    # means every file under .projectos/ was scanned clean while being loaded.
    report = report.merged_with(
        validation_service.ValidationReport(checked=("secret scan of all state files",))
    )
    return _render_validation(report, title=f"VALIDATE  {manifest.project_id}")


# -- pack ---------------------------------------------------------------------


def cmd_pack(args: argparse.Namespace) -> int:
    """`pack validate <path>` — validate a pack without installing it (spec 13)."""
    path = Path(args.path).resolve()
    pack = load_pack_from_directory(path)

    report = validation_service.validate_pack(pack, binder=YamlTemplateBinder())
    return _render_validation(report, title=f"PACK VALIDATE  {pack.name} v{pack.version}")


def _render_validation(report: validation_service.ValidationReport, *, title: str) -> int:
    """Turn a structured report into output and an exit code, at the boundary."""
    print(formatting.heading(title))
    for item in report.checked:
        print(f"  checked: {item}")

    if report.findings:
        print()
        for finding in report.findings:
            print(finding.describe())

    print()
    if report.ok:
        warnings = f" ({len(report.warnings)} warning(s))" if report.warnings else ""
        print(f"  VALID{warnings}")
        return int(ExitCode.OK)

    print(f"  INVALID — {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    return int(ExitCode.INVARIANT_ERROR)


# -- status -------------------------------------------------------------------


def cmd_status(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    lifecycle = kernel.lifecycle

    print(formatting.project_summary(lifecycle.manifest))
    print()

    current = lifecycle.current()
    print(formatting.heading("CURRENT ASSIGNMENT"))
    if current is None:
        print("  none — run `projectos next`")
    else:
        print(formatting.assignment_summary(current))
        if current.status is Status.VERIFIED:
            print(f"    Approvals {lifecycle.approval_status(current).describe()}")

    blocked = lifecycle.blocked()
    if blocked:
        print()
        print(formatting.heading("BLOCKED"))
        for assignment in blocked:
            print(formatting.assignment_summary(assignment))

    escalations = lifecycle.open_escalations()
    if escalations:
        print()
        print(formatting.heading("OPEN FOUNDER DECISIONS"))
        for escalation in escalations:
            print(formatting.escalation_summary(escalation))

    if args.brief and current is not None:
        from projectos.domain.routing import brief

        print()
        print(formatting.briefing_block(brief(current).render()))

    # An open escalation is a state the founder must act on, so it is reported
    # through the exit code as well as the output.
    return int(ExitCode.ESCALATION_REQUIRED if escalations else ExitCode.OK)


# -- next ---------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NextRun:
    """The outcome of one next-assignment flow: an exit code plus the assignment it
    acted on (generated/resumed/started), or ``None`` when none was (already active,
    or a founder decision is required)."""

    exit_code: int
    assignment: Assignment | None


def run_next(kernel: Kernel, *, dry_run: bool = False) -> NextRun:
    """The canonical next-assignment flow — the single generation path shared by
    `projectos next` and `projectos workspace next`.

    It enforces INV-1 (one active assignment), invokes `lifecycle.generate_next()`
    exactly once, and activates the result exactly as `next` always has. All
    persistence, audit logging, classification, and escalation happen inside the
    lifecycle; this function only orchestrates and renders.
    """
    lifecycle = kernel.lifecycle

    active = lifecycle.active()
    if active is not None:
        print(formatting.heading("ALREADY ACTIVE"))
        print(formatting.assignment_summary(active))
        print()
        print("  INV-1 permits one active assignment. Finish, block, or cancel it first.")
        return NextRun(int(ExitCode.OK), None)

    result = lifecycle.generate_next()

    if result.escalation is not None:
        print(formatting.heading("NEXT UNDETERMINED — FOUNDER DECISION REQUIRED"))
        print(formatting.escalation_summary(result.escalation))
        return NextRun(int(ExitCode.ESCALATION_REQUIRED), None)

    assert result.assignment is not None
    candidate = result.assignment

    if dry_run:
        print(formatting.heading("NEXT (dry run)"))
        print(formatting.assignment_summary(candidate))
        print(f"    Source    {result.decision.source}")
        return NextRun(int(ExitCode.OK), candidate)

    if candidate.status is Status.REJECTED:
        # A rejected assignment is still the next thing to do; resuming carries its
        # rejection reasons into the fresh briefing (spec 7.2, REJECTED -> ACTIVE).
        resumed, briefing = lifecycle.resume(candidate.id)
        print(formatting.heading("RESUMED AFTER REJECTION"))
        print(formatting.assignment_summary(resumed))
        print()
        print(formatting.briefing_block(briefing.render()))
        return NextRun(int(ExitCode.OK), resumed)

    if candidate.status is not Status.READY:
        print(formatting.heading("NEXT ASSIGNMENT NOT YET READY"))
        print(formatting.assignment_summary(candidate))
        if candidate.status is Status.DRAFT:
            print()
            print("  Classification is deferred; see `projectos history` for the reason.")
        return NextRun(int(ExitCode.OK), candidate)

    started, briefing = lifecycle.start(candidate.id)
    print(formatting.heading("STARTED"))
    print(formatting.assignment_summary(started))
    print(f"    Source    {result.decision.source}")
    print()
    print(formatting.briefing_block(briefing.render()))
    return NextRun(int(ExitCode.OK), started)


def cmd_next(args: argparse.Namespace) -> int:
    return run_next(_kernel(args), dry_run=args.dry_run).exit_code


# -- verify -------------------------------------------------------------------


def run_verify(
    kernel: Kernel, assignment_id: AssignmentId, *, report_path: Path | None
) -> int:
    """The canonical verification flow — the single evidence-verification path shared
    by `projectos verify` and `projectos workspace assignment verify`.

    It invokes `lifecycle.verify()` exactly once (which guards INV-6 integrity,
    ingests the claim, runs the verifier against repository evidence, transitions, and
    persists + audits), renders the canonical report, and raises `RuleFailure` when
    the evidence does not pass. Nothing here evaluates evidence or decides a verdict.
    """
    lifecycle = kernel.lifecycle

    # A claim only stages evidence for verification; it never decides anything.
    outcome = lifecycle.verify(assignment_id, _load_claim(assignment_id, report_path))
    print(formatting.verification_report(outcome.report))

    if outcome.report.passed:
        print()
        print(f"  {assignment_id} is VERIFIED. "
              f"{lifecycle.approval_status(outcome.assignment).describe()}")
        print(f"  Record approval with: projectos complete {assignment_id} --role ...")
        return int(ExitCode.OK)

    raise RuleFailure(
        f"{assignment_id} REJECTED: "
        f"{len(outcome.report.failures)} of {len(outcome.report.results)} criteria failed",
        detail="Fix the gaps above, then run `projectos verify` again.",
    )


def cmd_verify(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    assignment_id = _resolve_assignment_id(kernel, args.assignment)
    return run_verify(kernel, assignment_id, report_path=args.report)


def _load_claim(assignment_id: AssignmentId, report_path: Path | None) -> CompletionClaim:
    """Parse a completion report into a claim.

    Untrusted input (spec 14.5): parsed against a strict shape, never executed. An
    absent report yields an empty claim, which verifies exactly as harshly — the
    repository decides either way.
    """
    if report_path is None:
        return CompletionClaim(
            assignment_id=str(assignment_id), summary="completion claimed via CLI"
        )

    raw = read_yaml(report_path)
    if not isinstance(raw, dict):
        raise ValidationError(f"{report_path} must contain a YAML mapping")

    evidence: list[EvidenceRef] = []
    for item in raw.get("evidence", []) or []:
        if not isinstance(item, dict) or "class" not in item or "reference" not in item:
            raise ValidationError(
                f"{report_path}: each evidence item needs 'class' and 'reference'",
                detail=f"Valid classes: {', '.join(c.value for c in EvidenceClass)}",
            )
        evidence.append(
            EvidenceRef(
                evidence_class=EvidenceClass(item["class"]),
                reference=str(item["reference"]),
                note=item.get("note"),
            )
        )

    return CompletionClaim(
        assignment_id=str(assignment_id),
        summary=str(raw.get("summary", "completion claimed")),
        evidence=tuple(evidence),
    )


# -- complete -----------------------------------------------------------------


def run_complete(
    kernel: Kernel, assignment_id: AssignmentId, *, role: Role, attest: bool
) -> int:
    """The canonical completion flow — the single approval/attestation path shared by
    `projectos complete` and `projectos workspace assignment complete`.

    With ``attest`` it records a human attestation; otherwise it records an approval
    and the lifecycle auto-CLOSEs once the workflow mode's required roles are
    satisfied. Both delegate to `lifecycle.attest` / `lifecycle.approve`, which enforce
    INV-6 integrity, the VERIFIED-state requirement, §8.6.2 authority, the legal
    transition, and persistence + audit. Nothing here decides authority or closure.
    """
    lifecycle = kernel.lifecycle

    if attest:
        lifecycle.attest(assignment_id, role)
        print(f"  Attestation recorded for {assignment_id} as {role.value}.")
        print("  Run `projectos verify` to re-evaluate the criteria.")
        return int(ExitCode.OK)

    assignment, status = lifecycle.approve(assignment_id, role)

    if assignment.status is Status.CLOSED:
        print(formatting.heading(f"CLOSED  {assignment_id}"))
        print(formatting.assignment_summary(assignment))
        print()
        print("  Run `projectos next` to generate the successor.")
        return int(ExitCode.OK)

    print(f"  Approval recorded for {assignment_id} as {role.value}.")
    print(f"  {status.describe()}")
    return int(ExitCode.OK)


def cmd_complete(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    assignment_id = _resolve_assignment_id(kernel, args.assignment)
    return run_complete(kernel, assignment_id, role=Role(args.role), attest=args.attest)


# -- block --------------------------------------------------------------------


def cmd_block(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    lifecycle = kernel.lifecycle
    assignment_id = _resolve_assignment_id(kernel, args.assignment)

    if args.unblock:
        assignment = lifecycle.unblock(assignment_id)
        print(f"  {assignment_id} → {assignment.status.value.upper()} (dependencies restored)")
        return int(ExitCode.OK)

    if not args.reason.strip():
        raise ValidationError(
            "`projectos block` requires --reason",
            detail="A blocker without a stated cause cannot be cleared by anyone else.",
        )

    assignment = lifecycle.block(assignment_id, args.reason)
    print(f"  {assignment_id} → {assignment.status.value.upper()}")
    print(f"  Reason: {args.reason}")
    print(f"  Clear with: projectos block {assignment_id} --unblock")
    return int(ExitCode.OK)


# -- founder ------------------------------------------------------------------


def run_escalate(
    kernel: Kernel,
    *,
    trigger: EscalationTrigger,
    summary: str,
    options: tuple[EscalationOption, ...],
    assignment_id: AssignmentId | None,
    recommendation: str | None,
) -> int:
    """The canonical escalation flow — the single path shared by `projectos founder
    escalate` and `projectos workspace assignment escalate`.

    It calls `lifecycle.escalate()` exactly once (which guards INV-6 integrity,
    validates the ESCALATE transition before any write, persists the escalation, and
    freezes the scoped assignment to ESCALATED). Nothing here creates an escalation
    type or decides authority.
    """
    escalation = kernel.lifecycle.escalate(
        trigger=trigger,
        summary=summary,
        options=options,
        assignment_id=assignment_id,
        recommendation=recommendation,
    )
    print(formatting.heading(f"ESCALATION OPENED  {escalation.id}"))
    print(formatting.escalation_summary(escalation))
    return int(ExitCode.ESCALATION_REQUIRED)


def run_resolve(
    kernel: Kernel, escalation_id: EscalationId, decision: str, outcome: FounderDecision
) -> int:
    """The canonical resolution flow — the single **founder-only** path shared by
    `projectos founder resolve` and `projectos workspace assignment resolve`.

    It calls `lifecycle.resolve()` exactly once (which guards INV-6 integrity, enforces
    that the acting identity is the founder (spec 9.2), validates the decision against
    the escalation's options, persists the resolution, and re-drives the state
    machine). Nothing here fabricates founder identity or a decision.
    """
    escalation, assignment = kernel.lifecycle.resolve(escalation_id, decision, outcome)
    print(formatting.heading(f"RESOLVED  {escalation.id}"))
    print(f"  Decision  {decision}  ({outcome.value})")
    if assignment is not None:
        print()
        print(formatting.assignment_summary(assignment))
    return int(ExitCode.OK)


def cmd_founder(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    lifecycle = kernel.lifecycle

    if args.founder_command == "list":
        escalations = lifecycle.open_escalations()
        print(formatting.heading("OPEN FOUNDER DECISIONS"))
        if not escalations:
            print("  none — the founder queue is empty")
            return int(ExitCode.OK)
        for escalation in escalations:
            print(formatting.escalation_summary(escalation))
            print()
        return int(ExitCode.ESCALATION_REQUIRED)

    if args.founder_command == "escalate":
        return run_escalate(
            kernel,
            trigger=EscalationTrigger(args.trigger),
            summary=args.summary,
            options=_parse_options(args.option),
            assignment_id=AssignmentId.parse(args.assignment) if args.assignment else None,
            recommendation=args.recommend,
        )

    return run_resolve(
        kernel,
        EscalationId.parse(args.escalation),
        args.decision,
        FounderDecision(args.outcome),
    )


def _parse_options(raw_options: list[str]) -> tuple[EscalationOption, ...]:
    """Parse `ID|DESCRIPTION|CONSEQUENCE` triples.

    The consequence is mandatory here as well as in the domain, so the CLI cannot
    be used to open an escalation the founder would have to think about from
    scratch (spec 9.3).
    """
    options: list[EscalationOption] = []
    for raw in raw_options:
        parts = [part.strip() for part in raw.split("|")]
        if len(parts) != 3 or not all(parts):
            raise ValidationError(
                f"Malformed --option {raw!r}",
                detail="Expected ID|DESCRIPTION|CONSEQUENCE with all three parts present.",
            )
        options.append(EscalationOption(parts[0], parts[1], parts[2]))
    return tuple(options)


# -- history ------------------------------------------------------------------


def cmd_history(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    entries: tuple[AuditEntry, ...]

    if args.verify:
        # Chain integrity AND agreement with the state files: a chain that verifies
        # in isolation can still be missing its tail.
        report = kernel.lifecycle.verify_integrity()
        print(formatting.heading("AUDIT CHAIN"))
        print(f"  {report.describe()}.")
        print("  Hash chain intact and consistent with state files (INV-5, INV-6).")
        return int(ExitCode.OK)

    if args.assignment:
        entries = kernel.audit.for_assignment(AssignmentId.parse(args.assignment))
        if not entries:
            raise NotFoundError(f"No audit entries for {args.assignment}")
    else:
        entries = kernel.audit.read_all()

    shown = entries[-args.limit :] if args.limit > 0 else entries
    print(formatting.heading(f"HISTORY  ({len(shown)} of {len(entries)} entries)"))
    for entry in shown:
        print(formatting.audit_line(entry))
    return int(ExitCode.OK)
