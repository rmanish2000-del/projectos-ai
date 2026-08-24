"""Workspace bootstrap generator (P3).

A *workspace* is the local-first directory that holds many ProjectOS projects, the
shared assets they draw on, and a home for the kernel itself. It is a layer *above*
the per-repository `.projectos/` that ProjectOS Core manages, and it is pure
scaffolding: this module lays down a directory tree and starter files, and does not
touch the kernel, its domain, or its state machine.

Two properties are load-bearing:

* **Local-first.** Only the local filesystem is written. No network, no service.
* **Idempotent.** Running the bootstrap twice never corrupts an existing workspace:
  directories are created if missing, and an existing file is preserved (never
  overwritten) unless `force` is set. Every action is reported as created or kept,
  so a second run is visibly a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: The default pack skeletons a fresh workspace ships with (P3 scope).
DEFAULT_PACKS: tuple[str, ...] = (
    "rapid-build",
    "software",
    "trading",
    "renewable",
    "legal",
    "website",
    "documentation",
)

#: The starter files every pack skeleton contains. YAML files carry a minimal valid
#: body so they parse; markdown files carry a heading. They are intentionally
#: skeletal — a starting point for the pack author, not a finished pack.
PACK_FILES: tuple[str, ...] = (
    "README.md",
    "project_rules.yaml",
    "assignment_rules.md",
    "quality_gates.yaml",
    "deployment.md",
)

#: Shared subdirectories under `Shared/`.
SHARED_DIRS: tuple[str, ...] = (
    "Packs",
    "Templates",
    "Policies",
    "Prompts",
    "Knowledge",
)

EXAMPLE_PROJECT = "ExampleProject"

#: The one pack that ships loadable (a valid pack.yaml + templates), so a project
#: can be created from it. `rapid-build` is the fast, minimal domain: define a task,
#: then build it, both FAST (owner closes).
RAPID_BUILD = "rapid-build"

RAPID_BUILD_PACK_YAML = """# rapid-build pack — declarative, loadable by the ProjectOS kernel.
schema_version: 1
name: rapid-build
version: 0.1.0
domain: generic
requires_projectos: ">=0.1.0,<0.2.0"
pipeline:
  - phase: foundation
    templates:
      - define-task
      - build-task
"""

RAPID_BUILD_TEMPLATES: dict[str, str] = {
    "define-task": """# rapid-build assignment template — kernel issues id, state, origin.
title: Define the task
work_type: specification
executor: cowork
objective: >
  State the task, its scope, and its machine-verifiable acceptance criteria.
stopping_point: Stop when the task definition is committed. Do not build yet.
acceptance_criteria:
  - id: AC-1
    statement: A task definition exists at docs/TASK.md.
    verify:
      type: file_exists
      path: docs/TASK.md
evidence_required:
  - commit
""",
    "build-task": """# rapid-build assignment template — kernel issues id, state, origin.
title: Build the defined task
work_type: implementation
executor: code
objective: >
  Implement the task defined by the preceding assignment, and commit it.
stopping_point: Stop after the change is committed.
acceptance_criteria:
  - id: AC-1
    statement: The build is committed.
    verify:
      type: commit_exists
      message_pattern: "(?i)build|implement"
evidence_required:
  - commit
""",
}

#: Marker file so an otherwise-empty directory is tracked by git and survives a
#: clone. Named `.gitkeep` by convention.
GITKEEP = ".gitkeep"


@dataclass(frozen=True, slots=True)
class WorkspaceLayout:
    """The paths a workspace owns, all derived from its root."""

    root: Path

    @classmethod
    def at(cls, root: Path) -> WorkspaceLayout:
        return cls(root.resolve())

    @property
    def manifest(self) -> Path:
        return self.root / "Workspace.yaml"

    @property
    def projectos_dir(self) -> Path:
        return self.root / "ProjectOS"

    @property
    def shared_dir(self) -> Path:
        return self.root / "Shared"

    @property
    def packs_dir(self) -> Path:
        return self.shared_dir / "Packs"

    @property
    def projects_dir(self) -> Path:
        return self.root / "Projects"

    def pack_dir(self, name: str) -> Path:
        return self.packs_dir / name

    def project_dir(self, name: str) -> Path:
        return self.projects_dir / name

    def exists(self) -> bool:
        return self.manifest.is_file()


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """What the bootstrap did, so a caller can report and prove idempotency."""

    root: Path
    created: tuple[str, ...] = field(default=())
    kept: tuple[str, ...] = field(default=())

    @property
    def is_fresh(self) -> bool:
        """True when nothing pre-existed — a first bootstrap."""
        return not self.kept


class _Writer:
    """Records every file/dir touched as created or kept, so the result is a
    faithful account and a re-run is provably a no-op."""

    def __init__(self, root: Path, *, force: bool) -> None:
        self._root = root
        self._force = force
        self.created: list[str] = []
        self.kept: list[str] = []

    def _rel(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()

    def dir(self, path: Path) -> None:
        existed = path.is_dir()
        path.mkdir(parents=True, exist_ok=True)
        (self.kept if existed else self.created).append(self._rel(path) + "/")

    def file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not self._force:
            self.kept.append(self._rel(path))
            return
        path.write_text(content, encoding="utf-8", newline="\n")
        self.created.append(self._rel(path))


def bootstrap_workspace(
    root: Path, *, name: str | None = None, force: bool = False
) -> BootstrapResult:
    """Create (or complete) a workspace at `root`. Idempotent.

    `name` defaults to the root directory's name. `force` overwrites the generated
    starter files; without it, existing files are preserved so a second run cannot
    clobber the author's edits.
    """
    root = root.resolve()
    layout = WorkspaceLayout.at(root)
    workspace_name = name or root.name
    writer = _Writer(root, force=force)

    writer.dir(root)
    writer.dir(layout.projectos_dir)
    writer.file(layout.projectos_dir / "README.md", _PROJECTOS_README)
    writer.dir(layout.shared_dir)
    for subdir in SHARED_DIRS:
        writer.dir(layout.shared_dir / subdir)
        writer.file(layout.shared_dir / subdir / GITKEEP, "")

    for pack in DEFAULT_PACKS:
        _write_pack_skeleton(writer, layout.pack_dir(pack), pack)

    writer.dir(layout.projects_dir)
    _write_example_project(writer, layout)

    # The manifest is written last so its project/pack lists reflect what exists.
    writer.file(layout.manifest, _workspace_manifest(workspace_name))

    return BootstrapResult(
        root=root, created=tuple(writer.created), kept=tuple(writer.kept)
    )


def _write_pack_skeleton(writer: _Writer, pack_dir: Path, name: str) -> None:
    writer.dir(pack_dir)
    writer.file(pack_dir / "README.md", _pack_readme(name))
    writer.file(pack_dir / "project_rules.yaml", _pack_project_rules(name))
    writer.file(pack_dir / "assignment_rules.md", _pack_assignment_rules(name))
    writer.file(pack_dir / "quality_gates.yaml", _pack_quality_gates(name))
    writer.file(pack_dir / "deployment.md", _pack_deployment(name))
    writer.dir(pack_dir / "templates")
    writer.file(pack_dir / "templates" / GITKEEP, "")

    # rapid-build ships as a *loadable* ProjectOS pack — a valid pack.yaml and
    # bindable templates — so a project can be created from it. The other packs
    # remain skeletons until a pack author fills them in.
    if name == RAPID_BUILD:
        writer.file(pack_dir / "pack.yaml", RAPID_BUILD_PACK_YAML)
        for template_name, body in RAPID_BUILD_TEMPLATES.items():
            writer.file(pack_dir / "templates" / f"{template_name}.yaml", body)


def _write_example_project(writer: _Writer, layout: WorkspaceLayout) -> None:
    project_dir = layout.project_dir(EXAMPLE_PROJECT)
    writer.dir(project_dir)
    writer.file(project_dir / "project.yaml", _example_project_yaml())


# -- file bodies (skeletal, valid) -------------------------------------------


_PROJECTOS_README = """# ProjectOS

Home for the ProjectOS orchestration kernel within this workspace. Each project
under `../Projects/` manages its own `.projectos/` state; this directory is a
placeholder for workspace-level ProjectOS assets.
"""


def _workspace_manifest(name: str) -> str:
    packs = "\n".join(
        f"    - name: {pack}\n      path: Shared/Packs/{pack}" for pack in DEFAULT_PACKS
    )
    return f"""# ProjectOS workspace manifest — schema v1. Local-first; edit freely.
schema_version: 1
workspace:
  name: {name}
projectos: ProjectOS
shared:
  packs: Shared/Packs
  templates: Shared/Templates
  policies: Shared/Policies
  prompts: Shared/Prompts
  knowledge: Shared/Knowledge
packs:
{packs}
projects:
  - name: {EXAMPLE_PROJECT}
    path: Projects/{EXAMPLE_PROJECT}
"""


def _example_project_yaml() -> str:
    return f"""# Sample project registration — schema v1.
schema_version: 1
project:
  id: example-project
  name: {EXAMPLE_PROJECT}
  description: A sample project registered in the workspace.
pack: rapid-build
"""


def _pack_readme(name: str) -> str:
    return f"""# {name} pack

Starter skeleton for the `{name}` project pack. Declarative YAML only — no
executable code. Fill in the rules, quality gates, and templates below, then
register the pack in `Workspace.yaml`.
"""


def _pack_project_rules(name: str) -> str:
    return f"""# {name}: project rules — schema v1.
schema_version: 1
pack: {name}
rules: []
"""


def _pack_assignment_rules(name: str) -> str:
    return f"""# {name}: assignment rules

Describe how assignments are shaped for the `{name}` domain — default executors,
work types, and stopping-point conventions.
"""


def _pack_quality_gates(name: str) -> str:
    return f"""# {name}: quality gates — schema v1.
schema_version: 1
pack: {name}
gates: []
"""


def _pack_deployment(name: str) -> str:
    return f"""# {name}: deployment

Deployment notes for the `{name}` domain. ProjectOS never deploys automatically;
this documents the manual steps a human performs.
"""
