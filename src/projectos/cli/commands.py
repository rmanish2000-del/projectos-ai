"""Command handlers. Each maps 1:1 onto a kernel operation (spec section 2.2).

Handlers do three things and nothing more: translate arguments into domain values,
call the kernel, and render the result. Any rule they appear to apply is one the
kernel already decided.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from projectos.cli import formatting
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
    RuleFailure,
    ValidationError,
)
from projectos.domain.escalation import EscalationOption
from projectos.domain.evidence import CompletionClaim, EvidenceRef
from projectos.domain.ids import AssignmentId, EscalationId
from projectos.infrastructure.container import Kernel, build_kernel
from projectos.infrastructure.paths import Layout, discover_repo_root
from projectos.infrastructure.scaffold import build_manifest, scaffold
from projectos.infrastructure.system import StaticIdentityProvider
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


def cmd_next(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    lifecycle = kernel.lifecycle

    active = lifecycle.active()
    if active is not None:
        print(formatting.heading("ALREADY ACTIVE"))
        print(formatting.assignment_summary(active))
        print()
        print("  INV-1 permits one active assignment. Finish, block, or cancel it first.")
        return int(ExitCode.OK)

    result = lifecycle.generate_next()

    if result.escalation is not None:
        print(formatting.heading("NEXT UNDETERMINED — FOUNDER DECISION REQUIRED"))
        print(formatting.escalation_summary(result.escalation))
        return int(ExitCode.ESCALATION_REQUIRED)

    assert result.assignment is not None
    candidate = result.assignment

    if args.dry_run:
        print(formatting.heading("NEXT (dry run)"))
        print(formatting.assignment_summary(candidate))
        print(f"    Source    {result.decision.source}")
        return int(ExitCode.OK)

    if candidate.status is Status.REJECTED:
        # A rejected assignment is still the next thing to do; resuming carries its
        # rejection reasons into the fresh briefing (spec 7.2, REJECTED -> ACTIVE).
        resumed, briefing = lifecycle.resume(candidate.id)
        print(formatting.heading("RESUMED AFTER REJECTION"))
        print(formatting.assignment_summary(resumed))
        print()
        print(formatting.briefing_block(briefing.render()))
        return int(ExitCode.OK)

    if candidate.status is not Status.READY:
        print(formatting.heading("NEXT ASSIGNMENT NOT YET READY"))
        print(formatting.assignment_summary(candidate))
        if candidate.status is Status.DRAFT:
            print()
            print("  Classification is deferred; see `projectos history` for the reason.")
        return int(ExitCode.OK)

    started, briefing = lifecycle.start(candidate.id)
    print(formatting.heading("STARTED"))
    print(formatting.assignment_summary(started))
    print(f"    Source    {result.decision.source}")
    print()
    print(formatting.briefing_block(briefing.render()))
    return int(ExitCode.OK)


# -- verify -------------------------------------------------------------------


def cmd_verify(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    lifecycle = kernel.lifecycle
    assignment_id = _resolve_assignment_id(kernel, args.assignment)

    # A claim only stages evidence for verification; it never decides anything.
    outcome = lifecycle.verify(assignment_id, _load_claim(assignment_id, args.report))
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


def cmd_complete(args: argparse.Namespace) -> int:
    kernel = _kernel(args)
    lifecycle = kernel.lifecycle
    assignment_id = _resolve_assignment_id(kernel, args.assignment)
    role = Role(args.role)

    if args.attest:
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
        escalation = lifecycle.escalate(
            trigger=EscalationTrigger(args.trigger),
            summary=args.summary,
            options=_parse_options(args.option),
            assignment_id=AssignmentId.parse(args.assignment) if args.assignment else None,
            recommendation=args.recommend,
        )
        print(formatting.heading(f"ESCALATION OPENED  {escalation.id}"))
        print(formatting.escalation_summary(escalation))
        return int(ExitCode.ESCALATION_REQUIRED)

    escalation, assignment = lifecycle.resolve(
        EscalationId.parse(args.escalation),
        args.decision,
        FounderDecision(args.outcome),
    )
    print(formatting.heading(f"RESOLVED  {escalation.id}"))
    print(f"  Decision  {args.decision}  ({args.outcome})")
    if assignment is not None:
        print()
        print(formatting.assignment_summary(assignment))
    return int(ExitCode.OK)


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
        kernel.audit.verify()  # raises AuditChainBroken, halting the kernel
        entries = kernel.audit.read_all()
        print(formatting.heading("AUDIT CHAIN"))
        print(f"  {len(entries)} entries verified — hash chain intact (INV-5).")
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
