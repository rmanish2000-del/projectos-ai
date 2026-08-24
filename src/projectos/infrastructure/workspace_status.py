"""Workspace status — concise, deterministic, read-only operational view (P8).

Where the P7 handoff *reports* a workspace's full context, this module *interprets*
it: is the workspace safe to operate, what is incomplete, and what is broken. It is a
thin interpretation layer over the same read-model — it calls :func:`build_handoff`
for collection and never re-reads the workspace itself, so there is one collection
path shared by both commands.

Severity is the load-bearing idea:

* **failure** — invalid or broken state that makes operation unsafe: a malformed
  workspace/project manifest, a broken audit chain, an unresolved project focus.
* **warning** — valid but incomplete: an uninitialised project kernel, a configured
  pack whose directory is missing, a project whose pack is unavailable.
* **healthy** — valid and operational: nothing failing, nothing incomplete.

Read-only and deterministic throughout: no mutation, no network, stable ordering,
no timestamps. A malformed manifest is *reported as a failure condition* rather than
crashing the command, so `status` always prints a status.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from projectos.domain.errors import NotFoundError, ProjectOSError
from projectos.infrastructure.workspace import WorkspaceLayout
from projectos.infrastructure.workspace_handoff import (
    AssignmentInfo,
    Handoff,
    ProjectHandoff,
    build_handoff,
)


class Condition(StrEnum):
    """The workspace's overall operational condition."""

    HEALTHY = "healthy"
    WARNING = "warning"
    FAILURE = "failure"


class Severity(StrEnum):
    """The severity of a single actionable problem."""

    WARNING = "warning"
    FAILURE = "failure"


class IntegrityState(StrEnum):
    """A project's audit-chain integrity state, at a glance."""

    VERIFIED = "verified"
    FAILED = "failed"
    NOT_INITIALISED = "not-initialised"


@dataclass(frozen=True, slots=True)
class Problem:
    """One actionable problem, attributed to a scope and graded by severity."""

    severity: Severity
    scope: str
    """`"workspace"` or a project's stable identifier."""
    message: str


@dataclass(frozen=True, slots=True)
class PackStatus:
    """A configured pack and whether its directory is present on disk."""

    name: str
    path: str
    available: bool


@dataclass(frozen=True, slots=True)
class ProjectStatusLine:
    """One project's operational status, in stable-identifier order."""

    project_id: str
    name: str
    initialised: bool
    active_assignment: AssignmentInfo | None
    has_repository: bool
    pack: str | None
    pack_available: bool
    integrity: IntegrityState


@dataclass(frozen=True, slots=True)
class WorkspaceStatus:
    """The concise, deterministic operational status of a workspace."""

    condition: Condition
    workspace_name: str
    workspace_root: Path
    focus: str | None
    packs: tuple[PackStatus, ...]
    projects: tuple[ProjectStatusLine, ...]
    problems: tuple[Problem, ...]

    @property
    def registered_projects(self) -> int:
        return len(self.projects)

    @property
    def initialised_projects(self) -> int:
        return sum(1 for p in self.projects if p.initialised)

    @property
    def projects_with_active_assignment(self) -> int:
        return sum(1 for p in self.projects if p.active_assignment is not None)

    @property
    def available_packs(self) -> int:
        return sum(1 for p in self.packs if p.available)

    @property
    def integrity_failures(self) -> int:
        return sum(1 for p in self.projects if p.integrity is IntegrityState.FAILED)

    @property
    def warnings(self) -> int:
        return sum(1 for p in self.problems if p.severity is Severity.WARNING)


def build_status(workspace_root: Path, *, project: str | None = None) -> WorkspaceStatus:
    """Assemble a workspace's operational status. Read-only.

    Collection is delegated to :func:`build_handoff` (the shared P7 read-model);
    this function only derives severity, counts, pack availability, and the problem
    list. A missing workspace is a precondition failure (fail-closed); a *malformed*
    workspace/project manifest, or an unresolved ``project`` focus, is reported as a
    ``FAILURE`` condition rather than crashing the command.
    """
    workspace_root = workspace_root.resolve()
    layout = WorkspaceLayout.at(workspace_root)
    if not layout.manifest.is_file():
        raise NotFoundError(
            f"No workspace at {workspace_root}",
            detail="Run `projectos workspace init` first.",
        )

    try:
        handoff = build_handoff(workspace_root)  # full workspace; focus handled below
    except ProjectOSError as exc:
        return _failure_status(workspace_root, layout, exc.render())

    focus = _resolve_focus(handoff, project)
    problems: list[Problem] = []

    packs = _pack_statuses(handoff)
    available_pack_names = {p.name for p in packs if p.available}
    for pack in packs:
        if not pack.available:
            problems.append(
                Problem(
                    Severity.WARNING,
                    "workspace",
                    f"configured pack {pack.name!r} path is missing: {pack.path}",
                )
            )

    if project is not None and focus is None:
        problems.append(
            Problem(
                Severity.FAILURE,
                "workspace",
                f"project focus {project!r} does not resolve to a registered project",
            )
        )

    projects = tuple(
        _project_line(p, available_pack_names, problems) for p in handoff.projects
    )

    condition = _condition(problems)
    return WorkspaceStatus(
        condition=condition,
        workspace_name=handoff.workspace_name,
        workspace_root=workspace_root,
        focus=focus,
        packs=packs,
        projects=projects,
        problems=tuple(problems),
    )


def _resolve_focus(handoff: Handoff, project: str | None) -> str | None:
    if project is None:
        return None
    match = next(
        (p for p in handoff.projects if project in (p.project_id, p.name)), None
    )
    return match.project_id if match is not None else None


def _pack_statuses(handoff: Handoff) -> tuple[PackStatus, ...]:
    return tuple(
        PackStatus(
            name=pack.name,
            path=pack.path,
            available=(handoff.workspace_root / pack.path).is_dir(),
        )
        for pack in handoff.packs
    )


def _project_line(
    project: ProjectHandoff, available_pack_names: set[str], problems: list[Problem]
) -> ProjectStatusLine:
    pack_available = project.pack is not None and project.pack in available_pack_names
    if project.failure is not None:
        integrity = IntegrityState.FAILED
    elif project.initialised:
        integrity = IntegrityState.VERIFIED
    else:
        integrity = IntegrityState.NOT_INITIALISED

    if integrity is IntegrityState.FAILED:
        problems.append(
            Problem(
                Severity.FAILURE,
                project.project_id,
                f"audit integrity failure: {project.failure}",
            )
        )
    if not project.initialised:
        problems.append(
            Problem(Severity.WARNING, project.project_id, "project kernel not initialised")
        )
    if project.pack is None:
        problems.append(
            Problem(Severity.WARNING, project.project_id, "project declares no pack")
        )
    elif not pack_available:
        problems.append(
            Problem(
                Severity.WARNING,
                project.project_id,
                f"pack {project.pack!r} is not available in the workspace",
            )
        )

    return ProjectStatusLine(
        project_id=project.project_id,
        name=project.name,
        initialised=project.initialised,
        active_assignment=project.current_assignment,
        has_repository=not project.repository.is_empty,
        pack=project.pack,
        pack_available=pack_available,
        integrity=integrity,
    )


def _condition(problems: list[Problem]) -> Condition:
    if any(p.severity is Severity.FAILURE for p in problems):
        return Condition.FAILURE
    if any(p.severity is Severity.WARNING for p in problems):
        return Condition.WARNING
    return Condition.HEALTHY


def _failure_status(
    workspace_root: Path, layout: WorkspaceLayout, message: str
) -> WorkspaceStatus:
    """A status for a workspace that could not be resolved — malformed manifest state.

    The name is read directly from the raw manifest so the report still identifies
    the workspace; if even that is unreadable, the root directory name is used.
    """
    name = _best_effort_name(layout) or workspace_root.name
    return WorkspaceStatus(
        condition=Condition.FAILURE,
        workspace_name=name,
        workspace_root=workspace_root,
        focus=None,
        packs=(),
        projects=(),
        problems=(Problem(Severity.FAILURE, "workspace", message),),
    )


def _best_effort_name(layout: WorkspaceLayout) -> str | None:
    try:
        from projectos.infrastructure.yaml_io import read_yaml

        raw = read_yaml(layout.manifest)
    except ProjectOSError:
        return None
    if isinstance(raw, dict):
        workspace = raw.get("workspace")
        if isinstance(workspace, dict):
            name = workspace.get("name")
            if isinstance(name, str):
                return name
    return None


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_status(status: WorkspaceStatus) -> str:
    """Render a status as deterministic, human-readable text. Pure function."""
    lines: list[str] = []
    lines.append(f"WORKSPACE STATUS  {status.workspace_name}  [{status.condition.value.upper()}]")
    lines.append(_RULE)
    lines.append(f"  root      {status.workspace_root}")
    lines.append(f"  focus     {status.focus or 'none'}")
    lines.append("")
    lines.append(
        f"  registered {status.registered_projects}    "
        f"initialised {status.initialised_projects}    "
        f"active {status.projects_with_active_assignment}    "
        f"packs {status.available_packs}/{len(status.packs)}    "
        f"integrity-failures {status.integrity_failures}    "
        f"warnings {status.warnings}"
    )

    lines.append("")
    lines.append(f"PROJECTS  ({len(status.projects)})")
    if not status.projects:
        lines.append("  none registered")
    for project in status.projects:
        lines.extend(_render_project(project, status.focus))

    lines.append("")
    lines.append(f"PROBLEMS  ({len(status.problems)})")
    if not status.problems:
        lines.append("  none — workspace is healthy")
    for problem in status.problems:
        lines.append(
            f"  [{problem.severity.value.upper()}] {problem.scope}: {problem.message}"
        )

    return "\n".join(lines)


def _render_project(project: ProjectStatusLine, focus: str | None) -> list[str]:
    marker = " *" if focus is not None and project.project_id == focus else ""
    state = "initialised" if project.initialised else "not-initialised"
    if project.active_assignment is not None:
        a = project.active_assignment
        assignment = f"{a.id} [{a.status}]"
    else:
        assignment = "none"
    repo = "yes" if project.has_repository else "none"
    pack = project.pack or "none"
    if project.pack is not None:
        pack += "" if project.pack_available else " (unavailable)"
    return [
        f"  {project.project_id}{marker}",
        f"    kernel      {state}    integrity {project.integrity.value}",
        f"    assignment  {assignment}",
        f"    repository  {repo}    pack {pack}",
    ]
