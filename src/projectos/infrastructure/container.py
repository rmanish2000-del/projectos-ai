"""Composition root — the one place that wires concrete implementations together.

Every collaborator is constructed here and injected downward. Nothing else in the
codebase constructs a repository, an adapter, or a clock, and there is no module
level singleton, so a caller can build a fully independent kernel over a temporary
directory without touching global state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.application.lifecycle import LifecycleService
from projectos.application.ports import Clock, IdentityProvider, RepositoryAdapter
from projectos.domain.enums import RepositoryAdapterKind
from projectos.infrastructure.adapters import LocalGitAdapter, UnavailableGitHubAdapter
from projectos.infrastructure.audit_log import NdjsonAuditLog
from projectos.infrastructure.paths import Layout, discover_repo_root
from projectos.infrastructure.repositories import (
    FileAssignmentRepository,
    FileEscalationRepository,
    FileManifestRepository,
    FilePackRepository,
)
from projectos.infrastructure.system import GitIdentityProvider, SystemClock
from projectos.infrastructure.template_binding import YamlTemplateBinder


@dataclass(frozen=True, slots=True)
class Kernel:
    """A fully wired kernel bound to one repository."""

    layout: Layout
    manifests: FileManifestRepository
    packs: FilePackRepository
    assignments: FileAssignmentRepository
    escalations: FileEscalationRepository
    audit: NdjsonAuditLog
    lifecycle: LifecycleService
    clock: Clock
    identity: IdentityProvider


def build_kernel(
    repo_root: Path | None = None,
    *,
    clock: Clock | None = None,
    identity: IdentityProvider | None = None,
    adapter: RepositoryAdapter | None = None,
) -> Kernel:
    """Wire a kernel for `repo_root` (discovered from the cwd when omitted).

    The optional parameters exist so tests and scripted callers can substitute a
    fixed clock, a known identity, or a fake adapter without patching modules.
    """
    root = (repo_root or discover_repo_root(Path.cwd())).resolve()
    layout = Layout.for_repo(root)

    manifests = FileManifestRepository(layout)
    packs = FilePackRepository(layout)
    assignments = FileAssignmentRepository(layout)
    escalations = FileEscalationRepository(layout)
    audit = NdjsonAuditLog(layout)

    resolved_clock: Clock = clock or SystemClock()
    resolved_identity: IdentityProvider = identity or GitIdentityProvider(repo_root=str(root))
    resolved_adapter: RepositoryAdapter = adapter or _build_adapter(layout, manifests, root)

    lifecycle = LifecycleService(
        manifests=manifests,
        packs=packs,
        assignments=assignments,
        escalations=escalations,
        audit=audit,
        adapter=resolved_adapter,
        templates=YamlTemplateBinder(),
        clock=resolved_clock,
        identity=resolved_identity,
    )
    return Kernel(
        layout=layout,
        manifests=manifests,
        packs=packs,
        assignments=assignments,
        escalations=escalations,
        audit=audit,
        lifecycle=lifecycle,
        clock=resolved_clock,
        identity=resolved_identity,
    )


def _build_adapter(
    layout: Layout, manifests: FileManifestRepository, root: Path
) -> RepositoryAdapter:
    """Choose the adapter the manifest asks for.

    Before a manifest exists (during `init`) the local-git adapter is the safe
    default: it needs no configuration and no credentials.
    """
    if not layout.exists():
        return LocalGitAdapter(repo_root=root)

    manifest = manifests.load()
    if manifest.repository.adapter is RepositoryAdapterKind.GITHUB:
        return UnavailableGitHubAdapter(
            owner=manifest.repository.github_owner, repo=manifest.repository.github_repo
        )
    return LocalGitAdapter(
        repo_root=root, default_branch=manifest.repository.default_branch
    )
