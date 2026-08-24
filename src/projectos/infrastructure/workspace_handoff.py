"""Canonical workspace handoff — deterministic, read-only session context (P7).

A fresh AI coding session currently needs a hand-assembled brief before it can
continue ProjectOS work safely. This module derives that brief from committed
contracts alone: it resolves the workspace (and, project-first, a single project),
reads each project's repository metadata, pack, kernel location, current assignment,
and audit-chain integrity, and assembles them into an immutable :class:`Handoff`.

Three properties are load-bearing:

* **Read-only.** Nothing here writes, registers, generates, or reaches the network.
  It composes the existing read paths (`resolve_workspace`, `project_repository`,
  `build_kernel`, `verify_integrity`) and constructs values.
* **Deterministic.** Projects are ordered by their stable identifier; there are no
  timestamps and no environment-derived noise, so identical workspace/project state
  yields identical substantive output.
* **Fail-closed, but reporting.** A malformed workspace manifest fails closed via the
  resolver (its typed error names the offending file). A per-project state or
  integrity fault is caught and reported *against that project* rather than blanking
  the rest of the handoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.domain.errors import NotFoundError, ProjectOSError
from projectos.infrastructure.container import build_kernel
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.workspace import WorkspaceLayout
from projectos.infrastructure.workspace_bridge import project_repository
from projectos.infrastructure.workspace_manifest import (
    ProjectRepository,
    ResolvedProject,
    resolve_workspace,
)

UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class RepositoryInfo:
    """A project's declared repository metadata, verbatim from its `project.yaml`."""

    adapter: str | None = None
    remote: str | None = None
    default_branch: str | None = None
    path: str | None = None

    @property
    def is_empty(self) -> bool:
        return not any((self.adapter, self.remote, self.default_branch, self.path))


@dataclass(frozen=True, slots=True)
class AssignmentInfo:
    """The identity of the assignment a project is currently working on."""

    id: str
    title: str
    status: str


@dataclass(frozen=True, slots=True)
class ProjectHandoff:
    """One registered project's verifiable context for the handoff."""

    name: str
    """Workspace registration name (the key under `projects` in Workspace.yaml)."""
    project_id: str
    """The project's own stable identifier, from its `project.yaml`."""
    pack: str | None
    repository: RepositoryInfo
    kernel_location: str
    """Absolute path to the repository the kernel runs against."""
    initialised: bool
    """Whether a `.projectos/` kernel exists at ``kernel_location``."""
    current_assignment: AssignmentInfo | None
    integrity: str | None
    """The audit-chain integrity summary when it could be verified; else ``None``."""
    failure: str | None
    """A read fault (state or broken chain) for this project; else ``None``."""


@dataclass(frozen=True, slots=True)
class PackRef:
    """A pack the workspace configures, by name and path."""

    name: str
    path: str


@dataclass(frozen=True, slots=True)
class Handoff:
    """The canonical, deterministic workspace handoff."""

    workspace_name: str
    workspace_root: Path
    manifest_path: Path
    schema_version: int
    packs: tuple[PackRef, ...]
    projects: tuple[ProjectHandoff, ...]
    focus: str | None
    """The project id when a single project was resolved (project-first); else ``None``."""


def build_handoff(workspace_root: Path, *, project: str | None = None) -> Handoff:
    """Assemble the handoff for a workspace, or for one project (project-first).

    ``project`` matches a registered project's `project.id` first, then its
    registration name (the same resolution `find_project` uses). Read-only.
    Fail-closed on a missing workspace or an unresolvable project reference; a
    malformed project manifest fails closed inside :func:`resolve_workspace`.
    """
    workspace_root = workspace_root.resolve()
    layout = WorkspaceLayout.at(workspace_root)
    if not layout.manifest.is_file():
        raise NotFoundError(
            f"No workspace at {workspace_root}",
            detail="Run `projectos workspace init` first.",
        )

    workspace = resolve_workspace(workspace_root)

    if project is not None:
        resolved = workspace.by_id(project) or workspace.by_name(project)
        if resolved is None:
            known = ", ".join(sorted(p.project_id for p in workspace.projects)) or "none"
            raise NotFoundError(
                f"Project {project!r} is not registered in this workspace",
                detail=f"Known project identifiers: {known}.",
            )
        selected: tuple[ResolvedProject, ...] = (resolved,)
        focus = resolved.project_id
    else:
        selected = tuple(sorted(workspace.projects, key=lambda p: p.project_id))
        focus = None

    return Handoff(
        workspace_name=workspace.manifest.name,
        workspace_root=workspace_root,
        manifest_path=layout.manifest,
        schema_version=workspace.manifest.schema_version,
        packs=tuple(
            PackRef(p.name, p.path)
            for p in sorted(workspace.manifest.packs, key=lambda p: p.name)
        ),
        projects=tuple(_project_handoff(workspace_root, p) for p in selected),
        focus=focus,
    )


def _project_handoff(workspace_root: Path, resolved: ResolvedProject) -> ProjectHandoff:
    manifest = resolved.manifest
    repo = project_repository(workspace_root, manifest, resolved.ref.path)
    initialised = Layout.for_repo(repo).exists()

    current: AssignmentInfo | None = None
    integrity: str | None = None
    failure: str | None = None
    if initialised:
        # Reading persisted kernel state is read-only; a broken chain (INV-5/6) or an
        # unreadable state file raises a typed error, which we report against this
        # project rather than aborting the whole handoff.
        try:
            kernel = build_kernel(repo)
            in_flight = kernel.lifecycle.current()
            if in_flight is not None:
                current = AssignmentInfo(
                    id=str(in_flight.id),
                    title=in_flight.title,
                    status=in_flight.status.value,
                )
            integrity = kernel.lifecycle.verify_integrity().describe()
        except ProjectOSError as exc:
            failure = exc.render()

    return ProjectHandoff(
        name=resolved.ref.name,
        project_id=manifest.id,
        pack=manifest.pack,
        repository=_repository_info(manifest.repository),
        kernel_location=str(repo),
        initialised=initialised,
        current_assignment=current,
        integrity=integrity,
        failure=failure,
    )


def _repository_info(repository: ProjectRepository | None) -> RepositoryInfo:
    if repository is None:
        return RepositoryInfo()
    return RepositoryInfo(
        adapter=repository.adapter,
        remote=repository.remote,
        default_branch=repository.default_branch,
        path=repository.path,
    )


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_handoff(handoff: Handoff) -> str:
    """Render a handoff as deterministic, human-readable text.

    Pure function of its input: no clock, no environment lookup. Stable ordering
    comes from :func:`build_handoff`; this only lays the values out.
    """
    lines: list[str] = []
    lines.append(f"WORKSPACE HANDOFF  {handoff.workspace_name}")
    lines.append(_RULE)
    lines.append(f"  root            {handoff.workspace_root}")
    lines.append(f"  manifest        {handoff.manifest_path}")
    lines.append(f"  schema_version  {handoff.schema_version}")
    if handoff.focus is not None:
        lines.append(f"  focus           {handoff.focus}  (project-first resolution)")

    lines.append("")
    lines.append("CONFIGURED PACKS")
    if handoff.packs:
        for pack in handoff.packs:
            lines.append(f"  {pack.name}  ({pack.path})")
    else:
        lines.append(f"  {UNAVAILABLE} — none configured")

    lines.append("")
    lines.append(f"REGISTERED PROJECTS  ({len(handoff.projects)})")
    if not handoff.projects:
        lines.append(f"  {UNAVAILABLE} — none registered")
    for project in handoff.projects:
        lines.extend(_render_project(project))

    return "\n".join(lines)


def _render_project(project: ProjectHandoff) -> list[str]:
    lines: list[str] = ["", f"  {project.name}  ({project.project_id})"]
    lines.append(f"    pack            {project.pack or f'{UNAVAILABLE} — none'}")
    lines.extend(_render_repository(project.repository))
    lines.append(f"    kernel          {project.kernel_location}")
    state = "initialised" if project.initialised else f"{UNAVAILABLE} — not initialised"
    lines.append(f"    kernel state    {state}")

    if project.current_assignment is not None:
        a = project.current_assignment
        lines.append(f"    assignment      {a.id}  {a.title}  [{a.status}]")
    elif project.initialised and project.failure is None:
        lines.append(f"    assignment      {UNAVAILABLE} — none in flight")
    else:
        lines.append(f"    assignment      {UNAVAILABLE} — kernel not initialised")

    if project.failure is not None:
        lines.append(f"    integrity       FAILURE — {project.failure}")
    elif project.integrity is not None:
        lines.append(f"    integrity       verified — {project.integrity}")
    else:
        lines.append(f"    integrity       {UNAVAILABLE} — kernel not initialised")

    return lines


def _render_repository(repository: RepositoryInfo) -> list[str]:
    if repository.is_empty:
        return [f"    repository      {UNAVAILABLE} — none declared"]
    fields = [
        ("adapter", repository.adapter),
        ("remote", repository.remote),
        ("branch", repository.default_branch),
        ("path", repository.path),
    ]
    shown = "  ".join(f"{label}={value}" for label, value in fields if value)
    return [f"    repository      {shown}"]
