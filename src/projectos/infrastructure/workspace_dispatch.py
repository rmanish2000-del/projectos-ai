"""Agent handoff package — deterministic, read-only, copy-ready dispatch (P18).

The first AI-worker orchestration capability, and deliberately the smallest one: it
*prepares* a handoff for one explicitly-selected assignment and one explicitly-selected
worker type, and does nothing else. It **invokes no agent**, opens no network, runs no
shell, and mutates nothing.

Every value comes from an existing contract — the P7 handoff read-model supplies the
workspace/project/repository/pack/integrity context, and the assignment is read through
the kernel's own repository. Fields the assignment/pack genuinely persist are included
verbatim; every other schema field is labelled ``UNAVAILABLE`` rather than invented.
The only generated text is the *static* per-agent execution guidance, which is
ProjectOS policy — never business or domain content — and never alters the assignment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from projectos.domain.assignment import Assignment
from projectos.domain.errors import NotFoundError, ValidationError
from projectos.domain.ids import AssignmentId
from projectos.infrastructure.workspace_bridge import open_project_kernel
from projectos.infrastructure.workspace_handoff import RepositoryInfo, build_handoff

#: The dispatch package schema version — a fixed string, never a timestamp.
DISPATCH_VERSION = "projectos-handoff/1"

#: The explicitly-selectable worker types. There is no automatic selection (P18).
SUPPORTED_AGENTS: tuple[str, ...] = ("claude-code", "claude-chat", "claude-cowork")

UNAVAILABLE = "UNAVAILABLE"

#: Static, role-appropriate ProjectOS execution guidance. Not generated, not
#: domain-specific, and never a substitute for the assignment's own instructions.
_AGENT_GUIDANCE: dict[str, tuple[str, ...]] = {
    "claude-code": (
        "Inspect the repository before changing anything — repository evidence wins "
        "over any description in this package.",
        "Implement, test, and commit; open a PR. Report evidence references "
        "(commits, PRs, CI runs, paths) — claims are not evidence.",
        "Do not self-verify; only repository evidence decides pass/fail.",
        "Stop at the stated stopping point. Do not continue past it.",
    ),
    "claude-chat": (
        "Analysis, architecture, and review only — do NOT claim any repository "
        "implementation or change.",
        "Identify assumptions and evidence gaps explicitly; flag anything you cannot "
        "verify from this package.",
        "Produce reasoning and recommendations, not code changes.",
    ),
    "claude-cowork": (
        "Operational design, documentation, and research organisation — do NOT claim "
        "repository changes.",
        "Produce implementation-ready artifacts (specs, plans, docs) a code worker can "
        "act on.",
        "Keep every output grounded in this assignment; mark anything speculative.",
    ),
}


@dataclass(frozen=True, slots=True)
class DispatchPackage:
    """One deterministic, copy-ready handoff package. Immutable."""

    agent: str
    workspace_name: str
    workspace_root: Path
    project_name: str
    project_id: str
    assignment: Assignment
    repository: RepositoryInfo
    kernel_location: str
    pack: str | None
    integrity: str


def build_dispatch(
    workspace_root: Path, *, agent: str, project: str, assignment: str | None = None
) -> DispatchPackage:
    """Assemble one handoff package for a project + assignment + agent. Read-only.

    Fails closed on an unsupported agent, an unresolved workspace/project, an
    uninitialised kernel, an integrity failure, a missing/ambiguous assignment, or
    malformed state — every case raised by the reused contracts.
    """
    if agent not in SUPPORTED_AGENTS:
        raise ValidationError(
            f"Unsupported agent {agent!r}",
            detail=f"Choose one of: {', '.join(SUPPORTED_AGENTS)}.",
        )

    # Reuse the P7 handoff read-model for resolution + repository/pack/kernel context.
    handoff = build_handoff(workspace_root, project=project)
    project_handoff = handoff.projects[0]  # focused: build_handoff returns just this one
    if not project_handoff.initialised:
        raise NotFoundError(
            f"Project {project!r} has no initialised kernel",
            detail="Run `projectos workspace init-project` first.",
        )

    kernel = open_project_kernel(workspace_root, project_handoff.name)
    integrity = kernel.lifecycle.verify_integrity().describe()  # fail closed on INV-6

    # Explicit id wins; otherwise the canonical in-flight assignment (require_current
    # raises if there is none — an ambiguous/missing current fails closed here).
    assignment_id = (
        AssignmentId.parse(assignment)
        if assignment
        else kernel.lifecycle.require_current().id
    )
    full = kernel.assignments.get(assignment_id)  # fail closed on missing/malformed

    return DispatchPackage(
        agent=agent,
        workspace_name=handoff.workspace_name,
        workspace_root=handoff.workspace_root,
        project_name=project_handoff.name,
        project_id=project_handoff.project_id,
        assignment=full,
        repository=project_handoff.repository,
        kernel_location=project_handoff.kernel_location,
        pack=project_handoff.pack,
        integrity=integrity,
    )


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_dispatch(package: DispatchPackage) -> str:
    """Render a package as deterministic, copy-ready text. Pure function — no clock,
    no environment lookup, no network."""
    assignment = package.assignment
    lines: list[str] = []

    lines.append(f"PROJECTOS AGENT HANDOFF  ({package.agent})")
    lines.append(_RULE)
    lines.append(f"  handoff version  {DISPATCH_VERSION}")
    lines.append(f"  agent            {package.agent}")
    lines.append(f"  workspace        {package.workspace_name}  ({package.workspace_root})")
    lines.append(f"  project          {package.project_name}  ({package.project_id})")
    lines.append(
        f"  assignment       {assignment.id}  {assignment.title}  [{assignment.status.value}]"
    )

    lines.append("")
    lines.append(f"AGENT GUIDANCE ({package.agent})")
    lines.append(_RULE)
    for item in _AGENT_GUIDANCE[package.agent]:
        lines.append(f"  - {item}")

    lines.append("")
    lines.append("REPOSITORY CONTEXT")
    lines.append(_RULE)
    lines.append(f"  repository       {_repository(package.repository)}")
    lines.append(f"  kernel           {package.kernel_location}")
    lines.append(f"  pack             {package.pack or UNAVAILABLE}")
    lines.append(f"  integrity        verified — {package.integrity}")

    lines.append("")
    lines.append("ASSIGNMENT")
    lines.append(_RULE)
    lines.append(f"  objective        {assignment.objective.strip() or UNAVAILABLE}")
    lines.append(f"  context          {_context(assignment)}")
    lines.append(f"  current state    {assignment.status.value}")
    lines.append(f"  inputs           {UNAVAILABLE}")  # no persisted 'inputs' field
    lines.append(f"  scope            {UNAVAILABLE}")  # no persisted 'scope' field
    lines.append(f"  out of scope     {UNAVAILABLE}")  # no persisted 'out of scope' field
    lines.append(f"  constraints      {UNAVAILABLE}")  # no free-text constraints field
    lines.append("  acceptance criteria:")
    lines.extend(_criteria(assignment))
    lines.append(f"  quality checks   {UNAVAILABLE}")  # no persisted 'quality checks' field
    lines.append(f"  stopping point   {assignment.stopping_point.strip() or UNAVAILABLE}")

    lines.append("")
    lines.append("  -- persisted metadata --")
    lines.append(f"  work type        {assignment.work_type.value}")
    lines.append(f"  executor         {assignment.executor.value}")
    lines.append(f"  workflow mode    {assignment.workflow_mode.value}")
    lines.append(f"  owner            {assignment.owner}")
    lines.append(f"  evidence required  {_evidence(assignment)}")
    lines.append(f"  dependencies     {_dependencies(assignment)}")
    lines.append(f"  risk flags       {', '.join(assignment.risk_flags) or 'none'}")

    return "\n".join(lines)


def _repository(repository: RepositoryInfo) -> str:
    if repository.is_empty:
        return UNAVAILABLE
    fields = [
        ("adapter", repository.adapter),
        ("remote", repository.remote),
        ("branch", repository.default_branch),
        ("path", repository.path),
    ]
    return "  ".join(f"{label}={value}" for label, value in fields if value)


def _context(assignment: Assignment) -> str:
    if not assignment.context_refs:
        return UNAVAILABLE
    return ", ".join(sorted(ref.path for ref in assignment.context_refs))


def _criteria(assignment: Assignment) -> list[str]:
    lines: list[str] = []
    for criterion in assignment.acceptance_criteria:
        params = ", ".join(f"{k}={v}" for k, v in sorted(criterion.verify.params.items()))
        lines.append(f"    {criterion.id}: {criterion.statement}")
        lines.append(f"          verify: {criterion.verify.type.value}({params})")
    return lines


def _evidence(assignment: Assignment) -> str:
    if not assignment.evidence_required:
        return UNAVAILABLE
    return ", ".join(sorted(e.value for e in assignment.evidence_required))


def _dependencies(assignment: Assignment) -> str:
    if not assignment.depends_on:
        return "none"
    return ", ".join(sorted(str(dep) for dep in assignment.depends_on))
