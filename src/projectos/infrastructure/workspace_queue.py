"""Workspace assignment queue — deterministic, read-only inspection (P10).

ProjectOS Core already *is* the queue: each project's kernel persists its
assignments under `.projectos/assignments/*.yaml` with a state-machine status and an
active-slot pointer, and the lifecycle exposes `active()`, `blocked()`, and
`list_all()`. P10 adds no new store and no new state — it adds a read-only *view*
that partitions those already-persisted assignments, per project, into the buckets an
orchestrator asks about: active, ready, blocked, completed (and everything else).

It reuses the workspace read path directly: :func:`build_handoff` resolves the
workspace (and, project-first, one project), fixes the deterministic project order,
and reports each project's kernel location and initialised state; the queue then
reads that project's persisted assignments through the existing
``kernel.assignments.list_all()`` and buckets them by status.

Read-only and deterministic: no mutation, no network, projects in stable-identifier
order, assignments in id order within each bucket, no timestamps. A per-project state
fault is reported against that project rather than blanking the rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.domain.assignment import Assignment
from projectos.domain.enums import Status
from projectos.domain.errors import NotFoundError, ProjectOSError
from projectos.infrastructure.container import build_kernel
from projectos.infrastructure.workspace import WorkspaceLayout
from projectos.infrastructure.workspace_handoff import (
    AssignmentInfo,
    ProjectHandoff,
    build_handoff,
)

#: Bucket keys, in the fixed order the queue reports and renders them.
ACTIVE = "active"
READY = "ready"
BLOCKED = "blocked"
COMPLETED = "completed"
OTHER = "other"
BUCKETS: tuple[str, ...] = (ACTIVE, READY, BLOCKED, COMPLETED, OTHER)


@dataclass(frozen=True, slots=True)
class ProjectQueue:
    """One project's assignments, partitioned by state. Empty when uninitialised."""

    project_id: str
    name: str
    initialised: bool
    active: tuple[AssignmentInfo, ...] = ()
    ready: tuple[AssignmentInfo, ...] = ()
    blocked: tuple[AssignmentInfo, ...] = ()
    completed: tuple[AssignmentInfo, ...] = ()
    other: tuple[AssignmentInfo, ...] = ()
    failure: str | None = None
    """A read fault (unreadable/inconsistent state) for this project; else ``None``."""

    def bucket(self, name: str) -> tuple[AssignmentInfo, ...]:
        return {
            ACTIVE: self.active,
            READY: self.ready,
            BLOCKED: self.blocked,
            COMPLETED: self.completed,
            OTHER: self.other,
        }[name]

    @property
    def total(self) -> int:
        return sum(len(self.bucket(name)) for name in BUCKETS)


@dataclass(frozen=True, slots=True)
class WorkspaceQueue:
    """The workspace-wide assignment queue: one :class:`ProjectQueue` per project."""

    workspace_name: str
    workspace_root: Path
    focus: str | None
    projects: tuple[ProjectQueue, ...]

    def _count(self, name: str) -> int:
        return sum(len(p.bucket(name)) for p in self.projects)

    @property
    def active(self) -> int:
        return self._count(ACTIVE)

    @property
    def ready(self) -> int:
        return self._count(READY)

    @property
    def blocked(self) -> int:
        return self._count(BLOCKED)

    @property
    def completed(self) -> int:
        return self._count(COMPLETED)

    @property
    def other(self) -> int:
        return self._count(OTHER)

    @property
    def total(self) -> int:
        return sum(p.total for p in self.projects)

    @property
    def has_failures(self) -> bool:
        return any(p.failure is not None for p in self.projects)


def build_queue(workspace_root: Path, *, project: str | None = None) -> WorkspaceQueue:
    """Assemble the workspace assignment queue (or one project's, project-first).

    Read-only. Resolution and project ordering are delegated to :func:`build_handoff`
    (the shared P7 read path); the queue only reads each initialised project's
    persisted assignments and partitions them. A missing workspace or an unresolved
    project focus fails closed exactly as the handoff does.
    """
    workspace_root = workspace_root.resolve()
    layout = WorkspaceLayout.at(workspace_root)
    if not layout.manifest.is_file():
        raise NotFoundError(
            f"No workspace at {workspace_root}",
            detail="Run `projectos workspace init` first.",
        )

    handoff = build_handoff(workspace_root, project=project)
    projects = tuple(_project_queue(p) for p in handoff.projects)
    return WorkspaceQueue(
        workspace_name=handoff.workspace_name,
        workspace_root=workspace_root,
        focus=handoff.focus,
        projects=projects,
    )


def _project_queue(project: ProjectHandoff) -> ProjectQueue:
    if not project.initialised:
        return ProjectQueue(
            project_id=project.project_id, name=project.name, initialised=False
        )

    # Reading persisted assignments is read-only; an unreadable/inconsistent state
    # file raises a typed error, reported against this project (not the whole queue).
    try:
        kernel = build_kernel(Path(project.kernel_location))
        assignments = kernel.assignments.list_all()
    except ProjectOSError as exc:
        return ProjectQueue(
            project_id=project.project_id,
            name=project.name,
            initialised=True,
            failure=exc.render(),
        )

    partitioned = _partition(assignments)
    return ProjectQueue(
        project_id=project.project_id,
        name=project.name,
        initialised=True,
        active=partitioned[ACTIVE],
        ready=partitioned[READY],
        blocked=partitioned[BLOCKED],
        completed=partitioned[COMPLETED],
        other=partitioned[OTHER],
    )


def _partition(
    assignments: tuple[Assignment, ...],
) -> dict[str, tuple[AssignmentInfo, ...]]:
    """Bucket assignments by status, each bucket sorted by (zero-padded) id.

    Buckets reuse the kernel's own status semantics: `is_active_slot` (INV-1) defines
    *active*; `blocked` mirrors the lifecycle's blocked set (BLOCKED or ESCALATED);
    *completed* is the CLOSED terminal state. Everything else — draft, verified,
    rejected, cancelled — falls to *other* carrying its exact status, so the partition
    is total and nothing is silently dropped.
    """
    grouped: dict[str, list[AssignmentInfo]] = {name: [] for name in BUCKETS}
    for assignment in assignments:
        info = AssignmentInfo(
            id=str(assignment.id),
            title=assignment.title,
            status=assignment.status.value,
        )
        grouped[_bucket(assignment.status)].append(info)
    return {
        name: tuple(sorted(entries, key=lambda info: info.id))
        for name, entries in grouped.items()
    }


def _bucket(status: Status) -> str:
    if status.is_active_slot:
        return ACTIVE
    if status is Status.READY:
        return READY
    if status in (Status.BLOCKED, Status.ESCALATED):
        return BLOCKED
    if status is Status.CLOSED:
        return COMPLETED
    return OTHER


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68
_BUCKET_LABEL = {
    ACTIVE: "active",
    READY: "ready",
    BLOCKED: "blocked",
    COMPLETED: "completed",
    OTHER: "other",
}


def render_queue(queue: WorkspaceQueue) -> str:
    """Render the queue as deterministic, human-readable text. Pure function."""
    lines: list[str] = []
    lines.append(f"WORKSPACE QUEUE  {queue.workspace_name}")
    lines.append(_RULE)
    lines.append(f"  root   {queue.workspace_root}")
    lines.append(f"  focus  {queue.focus or 'none'}")
    lines.append("")
    lines.append(
        f"  projects {len(queue.projects)}    active {queue.active}    "
        f"ready {queue.ready}    blocked {queue.blocked}    "
        f"completed {queue.completed}    other {queue.other}"
    )

    lines.append("")
    lines.append(f"PROJECTS  ({len(queue.projects)})")
    if not queue.projects:
        lines.append("  none registered")
    for project in queue.projects:
        lines.extend(_render_project(project))

    return "\n".join(lines)


def _render_project(project: ProjectQueue) -> list[str]:
    lines = ["", f"  {project.project_id}  ({project.name})"]
    if project.failure is not None:
        lines.append(f"    FAILURE — {project.failure}")
        return lines
    if not project.initialised:
        lines.append("    not initialised — no queue")
        return lines
    if project.total == 0:
        lines.append("    empty — no assignments yet")
        return lines
    for name in BUCKETS:
        entries = project.bucket(name)
        label = f"{_BUCKET_LABEL[name]:<10}"
        if not entries:
            lines.append(f"    {label}(none)")
            continue
        for index, info in enumerate(entries):
            prefix = label if index == 0 else " " * 10
            lines.append(f"    {prefix}{info.id}  {info.title}  [{info.status}]")
    return lines
