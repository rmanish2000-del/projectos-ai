"""Scaffolding for `projectos init` (spec section 13).

Produces a valid `.projectos/` with a manifest and the bundled `software-core`
pack, so `init` followed by `status` works with no further editing.

The scaffold writes only under `.projectos/` (spec section 12) and never touches
project content.
"""

from __future__ import annotations

from typing import Any

from projectos.domain.enums import RepositoryAdapterKind
from projectos.domain.errors import ValidationError
from projectos.domain.manifest import (
    Identity,
    Manifest,
    PackRequirement,
    RepositoryConfig,
)
from projectos.infrastructure.paths import Layout
from projectos.infrastructure.yaml_io import write_yaml

DEFAULT_PACK = "software-core"

PACK_HEADER = "ProjectOS project pack — declarative only. No executable code (decision D-3)."
TEMPLATE_HEADER = "ProjectOS assignment template — kernel issues id, state, and origin_template."

#: The bundled pack. Deliberately small: the kernel default is FAST, and this pack
#: raises only the two things that genuinely warrant it — code work gets a
#: reviewer, and kernel/state paths are protected (risk R-7).
SOFTWARE_CORE_PACK: dict[str, Any] = {
    "schema_version": 1,
    "name": DEFAULT_PACK,
    "version": "0.1.0",
    "domain": "software",
    "requires_projectos": ">=0.1.0,<0.2.0",
    "vocabulary": {"risk_flags": ["schema_migration", "dependency_upgrade"]},
    "classification": {
        "reviewed_work_types": ["implementation", "refactor"],
        "protected_paths": [".projectos/**", "src/projectos/domain/**"],
        "governed_triggers_add": ["schema_migration"],
    },
    "escalation_triggers_add": [],
    "pipeline": [
        {
            "phase": "foundation",
            "templates": ["design-spec", "implement-kernel", "harden-and-document"],
        }
    ],
}

SOFTWARE_CORE_TEMPLATES: dict[str, dict[str, Any]] = {
    "design-spec": {
        "title": "Design the specification for the next capability",
        "work_type": "specification",
        "executor": "cowork",
        "objective": (
            "Produce a specification that states the capability, its boundaries, and its "
            "acceptance criteria in machine-verifiable terms."
        ),
        "stopping_point": (
            "Stop when the specification document is committed. Do not begin implementation."
        ),
        "acceptance_criteria": [
            {
                "id": "AC-1",
                "statement": "A specification document exists in docs/.",
                "verify": {"type": "file_exists", "path": "docs/SPEC.md"},
            }
        ],
        "evidence_required": ["commit"],
    },
    "implement-kernel": {
        "title": "Implement the specified capability",
        "work_type": "implementation",
        "executor": "code",
        "objective": (
            "Implement the capability described by the preceding specification, with tests "
            "and type checking green."
        ),
        "stopping_point": "Stop after opening the pull request. Do not merge.",
        # Acceptance criteria are verified from repository evidence (§8.3). Reviewer
        # sign-off is the separate CLOSE gate that REVIEWED mode already requires
        # (§7.3), so it must NOT also appear as an acceptance criterion: approval is
        # only recordable once an assignment is VERIFIED, and verification cannot
        # depend on the approval, or the two deadlock (P1.4 Blocker 4, §21.4).
        "acceptance_criteria": [
            {
                "id": "AC-1",
                "statement": "Implementation is committed.",
                "verify": {
                    "type": "commit_exists",
                    "message_pattern": "(?i)implement",
                },
            },
        ],
        "evidence_required": ["commit", "approval"],
    },
    "harden-and-document": {
        "title": "Harden and document the capability",
        "work_type": "document",
        "executor": "cowork",
        "objective": "Document the capability; owner sign-off closes it at CLOSE.",
        "stopping_point": "Stop when documentation is committed.",
        # As above: the CLOSE-time approval is the workflow-mode gate, not an
        # acceptance criterion. Document work is FAST, so the owner closes it.
        "acceptance_criteria": [
            {
                "id": "AC-1",
                "statement": "The README documents the capability.",
                "verify": {"type": "file_exists", "path": "README.md"},
            },
        ],
        "evidence_required": ["commit"],
    },
}


def build_manifest(
    *,
    project_id: str,
    project_name: str,
    description: str,
    founder_id: str,
    founder_name: str,
    adapter: RepositoryAdapterKind,
    default_branch: str,
    github_owner: str | None = None,
    github_repo: str | None = None,
    extra_owners: tuple[Identity, ...] = (),
    pack: str = DEFAULT_PACK,
    pack_constraint: str = ">=0.1.0 <0.2.0",
) -> Manifest:
    """Build the project manifest.

    `extra_owners` lists additional manifest-authorized identities beyond the
    founder — the pool from which reviewers are drawn (spec 8.6.2). The `init`
    command scaffolds a single-founder manifest; a project adds owners by editing
    `manifest.yaml`.

    `pack` names the project's pack (default the bundled `software-core`); the
    workspace bridge passes a workspace pack such as `rapid-build` here.
    """
    founder = Identity(id=founder_id, name=founder_name)
    owners = (founder, *(o for o in extra_owners if o.id != founder.id))
    return Manifest(
        schema_version=1,
        project_id=project_id,
        project_name=project_name,
        description=description,
        founder=founder,
        owners=owners,
        packs=(PackRequirement(pack, pack_constraint),),
        repository=RepositoryConfig(
            adapter=adapter,
            default_branch=default_branch,
            github_owner=github_owner,
            github_repo=github_repo,
        ),
    )


def scaffold(layout: Layout, manifest: Manifest, *, force: bool = False) -> None:
    """Write `.projectos/` for `manifest`.

    Refuses to overwrite an existing manifest unless `force` is set: re-running
    `init` over a live project would orphan its assignments and audit chain.
    """
    if layout.exists() and not force:
        raise ValidationError(
            f"ProjectOS is already initialised at {layout.root}",
            detail="Re-run with --force to overwrite the manifest (assignments are preserved).",
        )

    layout.ensure_directories()

    from projectos.infrastructure.repositories import MANIFEST_HEADER
    from projectos.infrastructure.serialization import manifest_to_dict

    write_yaml(layout.manifest, manifest_to_dict(manifest), header=MANIFEST_HEADER)

    pack_dir = layout.packs_dir / DEFAULT_PACK
    write_yaml(pack_dir / "pack.yaml", SOFTWARE_CORE_PACK, header=PACK_HEADER)
    for name, body in SOFTWARE_CORE_TEMPLATES.items():
        write_yaml(pack_dir / "templates" / f"{name}.yaml", body, header=TEMPLATE_HEADER)

    write_yaml(
        layout.active_pointer,
        {"active": None},
        header="ProjectOS active-assignment pointer — derived from assignment status.",
    )
