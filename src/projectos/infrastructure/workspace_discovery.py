"""Workspace discovery & auto-registration (P6).

Registration (P4.2) is intentional: a human runs `workspace add-project` for each
project. Discovery is the standard onboarding mechanism that scales it — it walks
the workspace's `Projects/` area, validates every candidate it finds, classifies
each against what is already registered, and (only when asked) registers the valid,
unregistered ones. Two projects placed side by side that would collide on identifier
or repository are reported as duplicates rather than silently registered.

Three properties are load-bearing, matching the rest of the Workspace Runtime:

* **Deterministic.** Candidates are walked in sorted order, the walk is depth-bounded
  (never infinite), and ignore rules skip VCS/tooling directories. The same tree
  produces the same report every time.
* **Safe by default.** Discovery never changes workspace state unless
  ``register=True``. A dry run — and the default — only reads and reports.
* **Idempotent & non-destructive.** Registration appends missing entries to
  `Workspace.yaml` and never overwrites an existing registration or a discovered
  project's own `project.yaml`. Re-running after a register is a visible no-op.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from projectos.domain.errors import NotFoundError, ProjectOSError
from projectos.infrastructure.workspace import WorkspaceLayout
from projectos.infrastructure.workspace_bridge import register_project_ref
from projectos.infrastructure.workspace_manifest import (
    ProjectManifest,
    ProjectRepository,
    load_project_manifest,
    load_workspace_manifest,
)

#: The manifest file that marks a directory as a candidate project.
PROJECT_MANIFEST = "project.yaml"

#: Directories never descended into during discovery. Any name starting with a dot
#: is also skipped, so this list is only the dotless tooling/vendor directories.
DEFAULT_IGNORE: frozenset[str] = frozenset(
    {
        "node_modules",
        "venv",
        "__pycache__",
        "site-packages",
        "dist",
        "build",
    }
)

#: Depth bound for the walk, so discovery can never recurse infinitely. Candidates
#: conventionally sit at `Projects/<name>` (depth 1); the extra headroom tolerates a
#: shallow grouping directory without walking into a project's own contents.
DEFAULT_MAX_DEPTH = 4


class DiscoveryStatus(StrEnum):
    """The classification of one discovered candidate. Exactly one applies."""

    REGISTERED = "registered"
    UNREGISTERED = "unregistered"
    INVALID = "invalid"
    DUPLICATE_IDENTIFIER = "duplicate-identifier"
    DUPLICATE_REPOSITORY = "duplicate-repository"


@dataclass(frozen=True, slots=True)
class DiscoveredProject:
    """One candidate found on disk, with its validation result and classification."""

    name: str
    """The directory name — used as the workspace registration name."""
    rel_path: str
    """Path relative to the workspace root, posix-style (e.g. `Projects/Alpha`)."""
    path: Path
    """Absolute path to the candidate's directory."""
    status: DiscoveryStatus
    project_id: str | None = None
    manifest: ProjectManifest | None = None
    error: str | None = None
    """A human-readable validation error when ``status`` is INVALID; else ``None``."""
    conflicts_with: str | None = None
    """For a duplicate, the rel_path (or registered name) that already owns the id
    or repository this candidate collides with."""
    registered_now: bool = False
    """True when this run registered the candidate (register mode only)."""


@dataclass(frozen=True, slots=True)
class DiscoveryReport:
    """The outcome of a discovery run — a complete, countable account."""

    root: Path
    projects: tuple[DiscoveredProject, ...] = ()
    dry_run: bool = True
    registered: bool = False
    """Whether registration was requested for this run."""

    @property
    def scanned(self) -> int:
        return len(self.projects)

    @property
    def valid(self) -> tuple[DiscoveredProject, ...]:
        return tuple(p for p in self.projects if p.status is not DiscoveryStatus.INVALID)

    @property
    def already_registered(self) -> tuple[DiscoveredProject, ...]:
        return tuple(p for p in self.projects if p.status is DiscoveryStatus.REGISTERED)

    @property
    def unregistered(self) -> tuple[DiscoveredProject, ...]:
        return tuple(
            p for p in self.projects if p.status is DiscoveryStatus.UNREGISTERED
        )

    @property
    def duplicates(self) -> tuple[DiscoveredProject, ...]:
        return tuple(
            p
            for p in self.projects
            if p.status
            in (
                DiscoveryStatus.DUPLICATE_IDENTIFIER,
                DiscoveryStatus.DUPLICATE_REPOSITORY,
            )
        )

    @property
    def invalid(self) -> tuple[DiscoveredProject, ...]:
        return tuple(p for p in self.projects if p.status is DiscoveryStatus.INVALID)

    @property
    def newly_registered(self) -> tuple[DiscoveredProject, ...]:
        return tuple(p for p in self.projects if p.registered_now)


def discover_workspace(
    workspace_root: Path,
    *,
    register: bool = False,
    dry_run: bool = True,
    max_depth: int = DEFAULT_MAX_DEPTH,
    ignore: frozenset[str] = DEFAULT_IGNORE,
) -> DiscoveryReport:
    """Discover, validate, and classify projects under a workspace's `Projects/` area.

    When ``register`` is true and ``dry_run`` is false, valid unregistered candidates
    are registered in `Workspace.yaml`; every other mode only reports. Returns a
    :class:`DiscoveryReport` regardless.
    """
    workspace_root = workspace_root.resolve()
    layout = WorkspaceLayout.at(workspace_root)
    if not layout.manifest.is_file():
        raise NotFoundError(
            f"No workspace at {workspace_root}",
            detail="Run `projectos workspace init` first.",
        )

    manifest = load_workspace_manifest(layout.manifest)
    registered_paths = {ref.path for ref in manifest.projects}

    # Seed the "claimed" sets from already-registered projects so a fresh candidate
    # that collides with one of them is reported as a duplicate. A registered
    # project whose manifest is unreadable simply contributes no claim — it is still
    # registered, which is all that matters here.
    claimed_ids: dict[str, str] = {}
    claimed_repos: dict[str, str] = {}
    for ref in manifest.projects:
        try:
            registered = load_project_manifest(
                (workspace_root / ref.path / PROJECT_MANIFEST).resolve()
            )
        except ProjectOSError:
            continue
        claimed_ids.setdefault(registered.id, ref.name)
        repo_key = _repository_key(registered.repository, workspace_root, ref.path)
        if repo_key is not None:
            claimed_repos.setdefault(repo_key, ref.name)

    discovered: list[DiscoveredProject] = []
    do_register = register and not dry_run
    for path in _walk_candidates(layout.projects_dir, max_depth=max_depth, ignore=ignore):
        rel_path = path.relative_to(workspace_root).as_posix()
        project = _classify(
            path=path,
            rel_path=rel_path,
            registered_paths=registered_paths,
            claimed_ids=claimed_ids,
            claimed_repos=claimed_repos,
            workspace_root=workspace_root,
        )
        if do_register and project.status is DiscoveryStatus.UNREGISTERED:
            register_project_ref(layout, name=project.name, rel_path=project.rel_path)
            registered_paths.add(project.rel_path)
            project = _replace_registered(project)
        discovered.append(project)

    return DiscoveryReport(
        root=workspace_root,
        projects=tuple(discovered),
        dry_run=not do_register,
        registered=register,
    )


# -- classification -----------------------------------------------------------


def _classify(
    *,
    path: Path,
    rel_path: str,
    registered_paths: set[str],
    claimed_ids: dict[str, str],
    claimed_repos: dict[str, str],
    workspace_root: Path,
) -> DiscoveredProject:
    """Validate one candidate and classify it, updating the claim sets in place.

    Order of precedence: invalid (cannot be trusted) → already registered → duplicate
    identifier → duplicate repository → unregistered. A newly accepted unregistered
    candidate claims its identifier and repository so a later copy is caught.
    """
    name = path.name

    try:
        manifest = load_project_manifest(path / PROJECT_MANIFEST)
    except ProjectOSError as exc:
        return DiscoveredProject(
            name=name,
            rel_path=rel_path,
            path=path,
            status=DiscoveryStatus.INVALID,
            error=exc.render(),
        )

    if rel_path in registered_paths:
        return DiscoveredProject(
            name=name,
            rel_path=rel_path,
            path=path,
            status=DiscoveryStatus.REGISTERED,
            project_id=manifest.id,
            manifest=manifest,
        )

    if manifest.id in claimed_ids:
        return DiscoveredProject(
            name=name,
            rel_path=rel_path,
            path=path,
            status=DiscoveryStatus.DUPLICATE_IDENTIFIER,
            project_id=manifest.id,
            manifest=manifest,
            conflicts_with=claimed_ids[manifest.id],
        )

    repo_key = _repository_key(manifest.repository, workspace_root, rel_path)
    if repo_key is not None and repo_key in claimed_repos:
        return DiscoveredProject(
            name=name,
            rel_path=rel_path,
            path=path,
            status=DiscoveryStatus.DUPLICATE_REPOSITORY,
            project_id=manifest.id,
            manifest=manifest,
            conflicts_with=claimed_repos[repo_key],
        )

    claimed_ids[manifest.id] = rel_path
    if repo_key is not None:
        claimed_repos[repo_key] = rel_path
    return DiscoveredProject(
        name=name,
        rel_path=rel_path,
        path=path,
        status=DiscoveryStatus.UNREGISTERED,
        project_id=manifest.id,
        manifest=manifest,
    )


def _replace_registered(project: DiscoveredProject) -> DiscoveredProject:
    """Return a copy of an unregistered candidate marked registered this run."""
    return DiscoveredProject(
        name=project.name,
        rel_path=project.rel_path,
        path=project.path,
        status=DiscoveryStatus.REGISTERED,
        project_id=project.project_id,
        manifest=project.manifest,
        registered_now=True,
    )


def _repository_key(
    repository: ProjectRepository | None, workspace_root: Path, rel_path: str
) -> str | None:
    """A stable identity for a project's repository, for duplicate detection.

    A declared remote is the strongest identity; otherwise the resolved local path
    is used. A project that declares no repository at all has no key, so two such
    projects never collide on repository (they may still collide on identifier).
    """
    if repository is None:
        return None
    if repository.remote:
        return f"remote:{repository.remote}"
    if repository.path:
        return f"path:{Path(repository.path).resolve().as_posix()}"
    return None


# -- walk ---------------------------------------------------------------------


def _walk_candidates(
    projects_root: Path, *, max_depth: int, ignore: frozenset[str]
) -> Iterator[Path]:
    """Yield candidate project directories under `projects_root`, deepest-bounded.

    A directory containing `project.yaml` is a candidate and a boundary: the walk
    yields it and does not descend into it (a project's own contents are not scanned
    for nested projects). Directories are visited in sorted order for determinism;
    dot-directories and ``ignore`` names are skipped; the walk stops at ``max_depth``.
    """
    if not projects_root.is_dir():
        return
    yield from _walk(projects_root, depth=1, max_depth=max_depth, ignore=ignore)


def _walk(
    directory: Path, *, depth: int, max_depth: int, ignore: frozenset[str]
) -> Iterator[Path]:
    for child in sorted(
        (c for c in directory.iterdir() if c.is_dir()), key=lambda c: c.name
    ):
        if child.name.startswith(".") or child.name in ignore:
            continue
        if (child / PROJECT_MANIFEST).is_file():
            yield child  # project boundary — do not descend further
        elif depth < max_depth:
            yield from _walk(
                child, depth=depth + 1, max_depth=max_depth, ignore=ignore
            )
