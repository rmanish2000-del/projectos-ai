"""Workspace → project-kernel bridge (P4.2).

The read-only Workspace Runtime (P4.1) resolves manifests; this module connects a
registered workspace project to an operable ProjectOS kernel. It composes existing
pieces — the workspace loaders, the `scaffold`/`build_manifest` primitives, the
pack loader, and `build_kernel` — without changing the kernel or its architecture.

Three capabilities, the minimum P5 needs:

* :func:`add_project` — register a project in `Workspace.yaml` and write its
  `project.yaml`. Writes only under the workspace. Idempotent.
* :func:`init_project_kernel` — scaffold a project's `.projectos/` in its repository
  using a workspace pack (e.g. `rapid-build`), so the kernel can run against it.
  Idempotent; never overwrites an existing `.projectos/` without `force`.
* :func:`project_status` — read-only: where the project's repository is, whether its
  kernel is initialised, and its active assignment.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from projectos.domain.enums import RepositoryAdapterKind
from projectos.domain.errors import NotFoundError, ValidationError
from projectos.infrastructure.container import Kernel, build_kernel
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.scaffold import build_manifest
from projectos.infrastructure.serialization import manifest_to_dict
from projectos.infrastructure.workspace import RAPID_BUILD, WorkspaceLayout
from projectos.infrastructure.workspace_manifest import (
    ProjectManifest,
    ResolvedProject,
    load_project_manifest,
    load_workspace_manifest,
    resolve_workspace,
)
from projectos.infrastructure.yaml_io import read_yaml, write_yaml

MANIFEST_HEADER = "ProjectOS project manifest — schema v1. Managed by the kernel."
WORKSPACE_HEADER = "ProjectOS workspace manifest — schema v1. Local-first; edit freely."
PROJECT_HEADER = "ProjectOS workspace project manifest — schema v1."


# -- registration -------------------------------------------------------------


def add_project(
    workspace_root: Path,
    *,
    name: str,
    pack: str = RAPID_BUILD,
    project_id: str | None = None,
    description: str = "",
    repository_path: str | None = None,
    repository_remote: str | None = None,
    repository_branch: str | None = None,
    force: bool = False,
) -> Path:
    """Register a project in the workspace and write its `project.yaml`.

    A project's repository may be recorded as a local `repository_path` (which the
    bridge also uses to host the kernel), or by `repository_remote` / `repository_branch`
    metadata for a repository that lives elsewhere and is not hosted by the bridge —
    the form the SensexPilot dogfood needs, so an external repository can be
    referenced without the kernel writing into it.

    Idempotent: re-registering the same name with the same details is a no-op.
    Registering a different project.yaml over an existing one requires `force`.
    Writes only under the workspace root.
    """
    workspace_root = workspace_root.resolve()
    layout = WorkspaceLayout.at(workspace_root)
    if not layout.manifest.is_file():
        raise NotFoundError(
            f"No workspace at {workspace_root}",
            detail="Run `projectos workspace init` first.",
        )

    manifest = load_workspace_manifest(layout.manifest)
    project_id = project_id or _slug(name)
    rel_path = f"Projects/{name}"

    # -- register in Workspace.yaml (append if absent) ------------------------
    existing = manifest.project(name)
    if existing is not None and existing.path != rel_path:
        raise ValidationError(
            f"Project {name!r} is already registered at {existing.path!r}",
            detail="Choose a different name; registration is by unique name.",
        )
    if existing is None:
        raw = read_yaml(layout.manifest)
        raw.setdefault("projects", []).append({"name": name, "path": rel_path})
        write_yaml(layout.manifest, raw, header=WORKSPACE_HEADER)

    # -- write Projects/<name>/project.yaml -----------------------------------
    project_dir = layout.project_dir(name)
    project_yaml = project_dir / "project.yaml"
    body: dict[str, object] = {
        "schema_version": 1,
        "project": {"id": project_id, "name": name, "description": description},
        "pack": pack,
    }
    repository = _repository_block(repository_path, repository_remote, repository_branch)
    if repository:
        body["repository"] = repository

    if project_yaml.exists() and not force:
        # Idempotent: leave an existing manifest untouched.
        return project_dir
    write_yaml(project_yaml, body, header=PROJECT_HEADER)
    return project_dir


# -- kernel bridge ------------------------------------------------------------


def project_repository(workspace_root: Path, project: ProjectManifest, ref_path: str) -> Path:
    """Resolve where a project's ProjectOS state and evidence live.

    A project's `repository.path` (if declared) is the repository the kernel runs
    against; otherwise the project's own directory in the workspace is used.
    """
    if project.repository is not None and project.repository.path:
        return Path(project.repository.path).resolve()
    return (workspace_root / ref_path).resolve()


def init_project_kernel(
    workspace_root: Path,
    *,
    name: str,
    founder_id: str,
    founder_name: str,
    force: bool = False,
) -> Path:
    """Scaffold a project's `.projectos/` from its workspace pack, so the kernel can
    operate against it. Returns the repository path. Idempotent."""
    workspace_root = workspace_root.resolve()
    resolved = _require_project(workspace_root, name)
    project = resolved.manifest
    pack_name = project.pack or RAPID_BUILD

    repo = project_repository(workspace_root, project, resolved.ref.path)
    layout = Layout.for_repo(repo)
    if layout.exists() and not force:
        return repo  # already initialised — idempotent no-op

    source_pack = WorkspaceLayout.at(workspace_root).pack_dir(pack_name)
    if not (source_pack / "pack.yaml").is_file():
        raise ValidationError(
            f"Workspace pack {pack_name!r} is not loadable (no pack.yaml at {source_pack})",
            detail="Only packs shipped with a pack.yaml (e.g. rapid-build) can back a project.",
        )

    manifest = build_manifest(
        project_id=project.id,
        project_name=project.name,
        description=project.description,
        founder_id=founder_id,
        founder_name=founder_name,
        adapter=RepositoryAdapterKind.LOCAL_GIT,
        default_branch=_default_branch(project),
        pack=pack_name,
    )

    layout.ensure_directories()
    write_yaml(layout.manifest, manifest_to_dict(manifest), header=MANIFEST_HEADER)
    _install_pack(source_pack, layout.packs_dir / pack_name)
    write_yaml(
        layout.active_pointer,
        {"active": None},
        header="ProjectOS active-assignment pointer — derived from assignment status.",
    )
    return repo


def open_project_kernel(workspace_root: Path, name: str) -> Kernel:
    """Build a kernel for a registered, initialised project."""
    workspace_root = workspace_root.resolve()
    resolved = _require_project(workspace_root, name)
    repo = project_repository(workspace_root, resolved.manifest, resolved.ref.path)
    if not Layout.for_repo(repo).exists():
        raise NotFoundError(
            f"Project {name!r} has no ProjectOS kernel at {repo}",
            detail="Run `projectos workspace init-project` first.",
        )
    return build_kernel(repo)


# -- status (read-only) -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProjectStatus:
    name: str
    project_id: str
    pack: str | None
    repository: str | None
    initialised: bool
    active_assignment: str | None


def project_status(workspace_root: Path, resolved: ResolvedProject) -> ProjectStatus:
    """Read-only status for one resolved project."""
    workspace_root = workspace_root.resolve()
    project = resolved.manifest
    repo = project_repository(workspace_root, project, resolved.ref.path)
    initialised = Layout.for_repo(repo).exists()

    active: str | None = None
    if initialised:
        active_assignment = build_kernel(repo).lifecycle.active()
        active = str(active_assignment.id) if active_assignment is not None else None

    return ProjectStatus(
        name=resolved.ref.name,
        project_id=project.id,
        pack=project.pack,
        repository=str(repo),
        initialised=initialised,
        active_assignment=active,
    )


def list_projects(workspace_root: Path) -> tuple[ProjectStatus, ...]:
    """Read-only status for every registered project (workspace → projects)."""
    workspace = resolve_workspace(workspace_root.resolve())
    return tuple(project_status(workspace.root, p) for p in workspace.projects)


def find_project(workspace_root: Path, identifier: str) -> ResolvedProject | None:
    """Look up a registered project by its identifier.

    Matches the project's own `project.id` first, then falls back to its workspace
    registration name, so either form of identifier resolves. Read-only. Delegates
    to the resolved-workspace lookups; no lookup logic is duplicated here.
    """
    workspace = resolve_workspace(workspace_root.resolve())
    return workspace.by_id(identifier) or workspace.by_name(identifier)


# -- helpers ------------------------------------------------------------------


def _require_project(workspace_root: Path, name: str) -> ResolvedProject:
    layout = WorkspaceLayout.at(workspace_root)
    if not layout.manifest.is_file():
        raise NotFoundError(f"No workspace at {workspace_root}")
    manifest = load_workspace_manifest(layout.manifest)
    ref = manifest.project(name)
    if ref is None:
        known = ", ".join(p.name for p in manifest.projects) or "none"
        raise NotFoundError(
            f"Project {name!r} is not registered in the workspace",
            detail=f"Registered projects: {known}.",
        )
    project_yaml = (workspace_root / ref.path / "project.yaml").resolve()
    if not project_yaml.is_file():
        raise ValidationError(f"Project {name!r} has no project.yaml at {project_yaml}")
    return ResolvedProject(ref, load_project_manifest(project_yaml))


def _install_pack(source: Path, destination: Path) -> None:
    """Copy a loadable workspace pack into a project's `.projectos/packs/`.

    Only the files the kernel loads (pack.yaml + templates/*.yaml) matter; copying
    the whole directory is simplest and harmless. Overwrites the destination so a
    re-init with `force` refreshes the installed pack.
    """
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _default_branch(project: ProjectManifest) -> str:
    if project.repository is not None and project.repository.default_branch:
        return project.repository.default_branch
    return "main"


def _repository_block(
    path: str | None, remote: str | None, branch: str | None
) -> dict[str, str]:
    """Assemble a project.yaml `repository` block from whichever fields are given.

    Returns an empty dict when no repository detail is supplied, so the field is
    omitted entirely (it is optional, spec P4.1).
    """
    block: dict[str, str] = {}
    if path is not None:
        block["path"] = path
    if remote is not None:
        block["remote"] = remote
    if branch is not None:
        block["default_branch"] = branch
    if block:
        block["adapter"] = "local_git"
    return block


def _slug(name: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in name.lower())
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "project"
