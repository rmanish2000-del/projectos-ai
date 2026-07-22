"""Workspace next-action planner — deterministic, read-only recommendation (P16).

The first planning layer above the workspace command surface. It reads one selected
project's *persisted* ProjectOS state and recommends exactly one safe next operational
action — or reports that a founder decision or external input is required. It
**recommends only; it never executes** a transition, and it invents no assignment ids,
evidence, roles, identities, or decisions.

Every recommendation is grounded in existing contracts:

* Resolution and the kernel come from the existing workspace bridge
  (`resolve_workspace` → `open_project_kernel`).
* The project's situation is read through the canonical lifecycle accessors
  (`current`, `open_escalations`, `verify_integrity`, `assignments.list_all`) — the
  same reads the queue, status, doctor, and handoff commands use.
* Transition legality is taken from :func:`state_machine.legal_events`, never a
  hand-written rule table: a transition-based command is only suggested when its
  underlying event is legal from the assignment's current status.
* Every suggested command is one that already exists in the CLI, always with the
  explicit `--project` selector, never destructive, and with required human inputs
  shown as clearly-labelled placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from projectos.domain import state_machine
from projectos.domain.assignment import Assignment
from projectos.domain.enums import Event, Status
from projectos.domain.errors import NotFoundError, ProjectOSError
from projectos.infrastructure.container import Kernel
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace_bridge import open_project_kernel, project_repository
from projectos.infrastructure.workspace_manifest import ResolvedProject, resolve_workspace


class Category(StrEnum):
    """The single recommendation category a plan returns."""

    RUN_COMMAND = "run-command"
    FOUNDER_DECISION_REQUIRED = "founder-decision-required"
    EXTERNAL_INPUT_REQUIRED = "external-input-required"
    BLOCKED = "blocked"
    COMPLETE = "complete"


class ActionKind(StrEnum):
    """A fully-determined, non-authority operation the plan executor (P17) may run.

    Only recommendations that need no unresolved placeholders and no external input
    carry a :class:`PlannedAction`; every other recommendation leaves ``action`` None
    and is not executable. This is the *single* source of truth for what is safe to
    execute — the executor reads it rather than parsing the command string.
    """

    GENERATE_NEXT = "generate-next"  # the canonical `workspace next` operation
    UNBLOCK = "unblock"  # `lifecycle.unblock` for a concrete blocked assignment


@dataclass(frozen=True, slots=True)
class PlannedAction:
    """The typed operation behind an executable recommendation (never a shell string)."""

    kind: ActionKind
    assignment_id: str | None = None
    """The concrete assignment id for UNBLOCK; None for GENERATE_NEXT."""


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Exactly one recommended next action."""

    category: Category
    reason: str
    command: str | None = None
    """A verified existing command, with any required inputs as `<LABELLED>` placeholders."""
    required_inputs: tuple[str, ...] = ()
    action: PlannedAction | None = None
    """The executable typed operation, set only for a fully-determined safe action
    (P17). ``None`` means the recommendation is advisory only and not auto-executable."""


@dataclass(frozen=True, slots=True)
class Plan:
    """The deterministic next-action plan for one selected project."""

    workspace_name: str
    project_id: str
    situation: str
    recommendation: Recommendation

    @property
    def is_blocked(self) -> bool:
        return self.recommendation.category is Category.BLOCKED


def build_plan(workspace_root: Path, *, project: str) -> Plan:
    """Recommend one safe next action for `project`. Strictly read-only.

    Fails closed on an unresolved workspace/project (raises); every other situation —
    uninitialised kernel, integrity failure, open escalation, or any assignment status
    — is reported as a recommendation, never raised.
    """
    workspace_root = workspace_root.resolve()
    workspace = resolve_workspace(workspace_root)
    resolved = workspace.by_id(project) or workspace.by_name(project)
    if resolved is None:
        known = ", ".join(sorted(p.project_id for p in workspace.projects)) or "none"
        raise NotFoundError(
            f"Project {project!r} is not registered in this workspace",
            detail=f"Known project identifiers: {known}.",
        )

    name = workspace.manifest.name
    project_id = resolved.project_id
    repo = project_repository(workspace_root, resolved.manifest, resolved.ref.path)

    # -- uninitialised kernel: recommend the existing scaffold command ---------
    if not Layout.for_repo(repo).exists():
        return Plan(
            workspace_name=name,
            project_id=project_id,
            situation="project kernel not initialised",
            recommendation=Recommendation(
                category=Category.RUN_COMMAND,
                reason="the project has no `.projectos/` kernel yet",
                command=(
                    f"projectos workspace init-project {resolved.ref.name} "
                    "--founder-id <FOUNDER_ID> --founder-name <FOUNDER_NAME>"
                ),
                required_inputs=("the founder identity and display name",),
            ),
        )

    kernel = open_project_kernel(workspace_root, resolved.ref.name)
    return _plan_for_kernel(name, project_id, kernel, workspace_root, resolved)


def _plan_for_kernel(
    name: str,
    project_id: str,
    kernel: Kernel,
    workspace_root: Path,
    resolved: ResolvedProject,
) -> Plan:
    # -- integrity: a broken chain / unreadable state is unsafe to operate on --
    try:
        kernel.lifecycle.verify_integrity()
    except ProjectOSError as exc:
        return _plan(
            name, project_id, "audit integrity could not be verified",
            Recommendation(
                Category.BLOCKED,
                reason=f"integrity failure — do not operate: {exc.render()}",
                command=f"projectos workspace doctor --project {project_id}",
            ),
        )

    # -- an open escalation is a pending founder decision ----------------------
    escalations = kernel.lifecycle.open_escalations()
    if escalations:
        escalation = min(escalations, key=lambda e: str(e.id))
        return _plan(
            name, project_id, f"open escalation {escalation.id}: {escalation.summary}",
            Recommendation(
                Category.FOUNDER_DECISION_REQUIRED,
                reason=f"escalation {escalation.id} awaits a founder decision (spec 9.2)",
                command=(
                    f"projectos workspace assignment resolve --project {project_id} "
                    f"--escalation {escalation.id} --decision <OPTION_ID> "
                    "--outcome <proceed|cancel|rescope>"
                ),
                required_inputs=(
                    "the founder's decision (an option id) and outcome",
                    "the acting identity must be the project's founder",
                ),
            ),
        )

    # -- an in-flight assignment (ACTIVE/…/VERIFIED/REJECTED) ------------------
    current = kernel.lifecycle.current()
    if current is not None:
        return _plan(name, project_id, _summary(current), _for_inflight(current, project_id))

    # -- nothing in flight: examine the persisted assignment set --------------
    assignments = kernel.assignments.list_all()
    return _plan(
        name, project_id, _idle_summary(assignments),
        _for_idle(assignments, project_id, kernel, workspace_root, resolved),
    )


# -- in-flight status → recommendation (grounded in legal_events) -------------


def _for_inflight(assignment: Assignment, project_id: str) -> Recommendation:
    status = assignment.status
    aid = str(assignment.id)

    if status is Status.VERIFIED and _legal(status, Event.APPROVALS_COMPLETE):
        return Recommendation(
            Category.RUN_COMMAND,
            reason=f"{aid} is VERIFIED and awaits approval to close",
            command=(
                f"projectos workspace assignment complete --project {project_id} "
                f"--assignment {aid} --role owner"
            ),
            required_inputs=(
                "the acting identity must be authorized for the role "
                "(reviewed/governed modes need a reviewer / founder too)",
            ),
        )

    if status is Status.REJECTED and _legal(status, Event.RESUME):
        return Recommendation(
            Category.RUN_COMMAND,
            reason=f"{aid} was REJECTED; resuming carries the reasons into a fresh briefing",
            command=f"projectos workspace next --project {project_id}",
            required_inputs=("fix the failed acceptance criteria before re-verifying",),
        )

    if status in (Status.EVIDENCE_SUBMITTED, Status.VERIFYING) and _legal(
        status, Event.VERIFY_START
    ):
        return Recommendation(
            Category.RUN_COMMAND,
            reason=f"{aid} has evidence submitted; run verification against the repository",
            command=(
                f"projectos workspace assignment verify --project {project_id} "
                f"--assignment {aid}"
            ),
        )

    if status is Status.ACTIVE:  # SUBMIT is the forward event, but the work is external
        return Recommendation(
            Category.EXTERNAL_INPUT_REQUIRED,
            reason=f"{aid} is ACTIVE — the acceptance criteria need implementation and evidence",
            command=(
                f"projectos workspace assignment verify --project {project_id} "
                f"--assignment {aid}"
            ),
            required_inputs=(
                "implement the assignment and commit the evidence its criteria require, "
                "then verify",
            ),
        )

    # Any other in-flight status: recommend inspecting it (read-only, always safe).
    return Recommendation(
        Category.EXTERNAL_INPUT_REQUIRED,
        reason=f"{aid} is {status.value}; inspect it to determine the next step",
        command=(
            f"projectos workspace assignment show --project {project_id} --assignment {aid}"
        ),
    )


# -- idle (no in-flight assignment) → recommendation --------------------------


def _for_idle(
    assignments: tuple[Assignment, ...],
    project_id: str,
    kernel: Kernel,
    workspace_root: Path,
    resolved: ResolvedProject,
) -> Recommendation:
    blocked = _first(assignments, Status.BLOCKED)
    if blocked is not None and _legal(Status.BLOCKED, Event.UNBLOCK):
        return Recommendation(
            Category.RUN_COMMAND,
            reason=f"{blocked.id} is BLOCKED; unblock it once its dependencies are CLOSED",
            command=(
                f"projectos workspace assignment unblock --project {project_id} "
                f"--assignment {blocked.id}"
            ),
            required_inputs=("all blocking dependencies must be CLOSED",),
            action=PlannedAction(ActionKind.UNBLOCK, assignment_id=str(blocked.id)),
        )

    ready = _first(assignments, Status.READY)
    if ready is not None and _legal(Status.READY, Event.START):
        return Recommendation(
            Category.RUN_COMMAND,
            reason=f"{ready.id} is READY; `next` starts it",
            command=f"projectos workspace next --project {project_id}",
            action=PlannedAction(ActionKind.GENERATE_NEXT),
        )

    draft = _first(assignments, Status.DRAFT)
    if draft is not None:
        return Recommendation(
            Category.EXTERNAL_INPUT_REQUIRED,
            reason=f"{draft.id} is DRAFT — classification was deferred; inspect the reason",
            command=f"projectos workspace assignment show --project {project_id} "
            f"--assignment {draft.id}",
            required_inputs=("resolve the deferred classification (see `history`)",),
        )

    # No non-terminal assignment. A closed one means that assignment is complete.
    latest_closed = _latest(assignments, Status.CLOSED)
    if latest_closed is not None:
        return Recommendation(
            Category.COMPLETE,
            reason=f"{latest_closed.id} is CLOSED — no further action for it",
            command=f"projectos workspace next --project {project_id}",
            required_inputs=("`next` generates the successor, if the pack pipeline has one",),
        )

    # Truly nothing to act on yet: generate the first/next assignment.
    if not _pack_installed(kernel, resolved):
        pack = resolved.manifest.pack or "the configured pack"
        return Recommendation(
            Category.EXTERNAL_INPUT_REQUIRED,
            reason=f"the pack {pack!r} is not installed in the kernel; generation cannot run",
            command=f"projectos workspace doctor --project {project_id}",
            required_inputs=(f"restore the {pack} pack under the project kernel",),
        )
    return Recommendation(
        Category.RUN_COMMAND,
        reason="no assignment exists yet; `next` generates the first",
        command=f"projectos workspace next --project {project_id}",
        action=PlannedAction(ActionKind.GENERATE_NEXT),
    )


# -- helpers ------------------------------------------------------------------


def _legal(status: Status, event: Event) -> bool:
    """Ground a recommendation in the canonical transition table (never a local rule)."""
    return event in state_machine.legal_events(status)


def _first(assignments: tuple[Assignment, ...], status: Status) -> Assignment | None:
    matches = sorted((a for a in assignments if a.status is status), key=lambda a: str(a.id))
    return matches[0] if matches else None


def _latest(assignments: tuple[Assignment, ...], status: Status) -> Assignment | None:
    matches = sorted((a for a in assignments if a.status is status), key=lambda a: str(a.id))
    return matches[-1] if matches else None


def _pack_installed(kernel: Kernel, resolved: ResolvedProject) -> bool:
    pack = resolved.manifest.pack
    if pack is None:
        return True  # nothing configured to be missing
    return (kernel.layout.packs_dir / pack / "pack.yaml").is_file()


def _summary(assignment: Assignment) -> str:
    return f"{assignment.id} {assignment.status.value.upper()} — {assignment.title}"


def _idle_summary(assignments: tuple[Assignment, ...]) -> str:
    if not assignments:
        return "no assignments"
    return f"{len(assignments)} assignment(s), none in flight"


def _plan(
    name: str, project_id: str, situation: str, recommendation: Recommendation
) -> Plan:
    return Plan(
        workspace_name=name,
        project_id=project_id,
        situation=situation,
        recommendation=recommendation,
    )


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_plan(plan: Plan) -> str:
    """Render a plan as deterministic, human-readable text. Pure function."""
    rec = plan.recommendation
    lines = [
        f"WORKSPACE PLAN  {plan.workspace_name}  →  {plan.project_id}",
        _RULE,
        f"  situation       {plan.situation}",
        f"  recommendation  {rec.category.value.upper()}",
        f"  reason          {rec.reason}",
    ]
    if rec.command is not None:
        lines.append(f"  command         {rec.command}")
    if rec.required_inputs:
        lines.append("  required input:")
        lines.extend(f"    - {item}" for item in rec.required_inputs)
    return "\n".join(lines)
