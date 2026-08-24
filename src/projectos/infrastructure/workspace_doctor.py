"""Workspace doctor — deterministic, read-only diagnostics with remediation (P9).

The P8 status *interprets* the workspace into a condition and a flat problem list;
the doctor re-presents that same interpretation as a set of **named checks**, each
with a stable id, a PASS/WARN/FAIL/SKIP result, the affected scope, a concise
explanation, and — where one genuinely exists — a *safe, advisory* remediation that
references only verified ProjectOS commands.

It adds no new collection path: it calls :func:`build_status` (which itself reuses
the P7 :func:`build_handoff` read-model) and derives diagnostics from its structured
fields. Nothing here writes, initialises, registers, or reaches the network.

Some committed contracts fold several requested diagnostics into one signal, and the
checks below are honest about that:

* ``workspace-manifest`` covers workspace- and project-manifest validity, duplicate
  project identifiers, and duplicate registrations — the resolver fails closed on any
  of them, so they surface as one workspace-level failure naming the offending file.
* ``audit-integrity`` covers both audit-chain integrity and assignment-state
  readability — a fault reading either raises the same typed error.
* ``project-identifier`` passes whenever the workspace resolved, because the manifest
  schema already rejects malformed ids at load time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from projectos.domain.errors import NotFoundError
from projectos.infrastructure.workspace import WorkspaceLayout
from projectos.infrastructure.workspace_status import (
    Condition,
    IntegrityState,
    ProjectStatusLine,
    WorkspaceStatus,
    build_status,
)

# -- stable check identifiers -------------------------------------------------

CHECK_WORKSPACE_MANIFEST = "workspace-manifest"
CHECK_PROJECT_FOCUS = "project-focus"
CHECK_CONFIGURED_PACKS = "configured-packs"
CHECK_PROJECT_IDENTIFIER = "project-identifier"
CHECK_KERNEL_INITIALISED = "kernel-initialised"
CHECK_PROJECT_PACK = "project-pack"
CHECK_AUDIT_INTEGRITY = "audit-integrity"
CHECK_REPOSITORY_METADATA = "repository-metadata"

WORKSPACE = "workspace"
_AUDIT_PROBLEM_PREFIX = "audit integrity failure: "


class DiagnosticResult(StrEnum):
    """The result of a single check. ``SKIP`` is neutral — it does not affect the
    overall outcome (the check could not run, e.g. no kernel to inspect)."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class Outcome(StrEnum):
    """The doctor's overall verdict."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


#: Display/sort order: failures first, then warnings, passes, and neutral skips.
_RESULT_RANK: dict[DiagnosticResult, int] = {
    DiagnosticResult.FAIL: 0,
    DiagnosticResult.WARN: 1,
    DiagnosticResult.PASS: 2,
    DiagnosticResult.SKIP: 3,
}


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One check's outcome, attributed to a scope, with optional remediation."""

    check: str
    result: DiagnosticResult
    scope: str
    """`"workspace"` or a project's stable identifier."""
    explanation: str
    action: str | None = None
    """A safe, advisory remediation referencing only verified commands; else ``None``."""


@dataclass(frozen=True, slots=True)
class DoctorReport:
    """The deterministic diagnostic report."""

    outcome: Outcome
    workspace_name: str
    workspace_root: Path
    focus: str | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def passed(self) -> int:
        return sum(1 for d in self.diagnostics if d.result is DiagnosticResult.PASS)

    @property
    def warned(self) -> int:
        return sum(1 for d in self.diagnostics if d.result is DiagnosticResult.WARN)

    @property
    def failed(self) -> int:
        return sum(1 for d in self.diagnostics if d.result is DiagnosticResult.FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for d in self.diagnostics if d.result is DiagnosticResult.SKIP)


def build_report(workspace_root: Path, *, project: str | None = None) -> DoctorReport:
    """Diagnose a workspace (or one focused project). Read-only.

    Delegates all collection to :func:`build_status`. A missing workspace is a
    precondition failure (fail-closed); every other problem — a malformed manifest,
    a broken chain, an unresolved focus — is reported as a diagnostic, never raised.
    """
    workspace_root = workspace_root.resolve()
    layout = WorkspaceLayout.at(workspace_root)
    if not layout.manifest.is_file():
        raise NotFoundError(
            f"No workspace at {workspace_root}",
            detail="Run `projectos workspace init` first.",
        )

    status = build_status(workspace_root, project=project)
    diagnostics: list[Diagnostic] = []

    if _resolution_failed(status):
        diagnostics.extend(_resolution_failure_diagnostics(status, project))
    else:
        diagnostics.append(_workspace_manifest_ok())
        diagnostics.append(_project_focus_diagnostic(status, project))
        diagnostics.extend(_pack_diagnostics(status))
        diagnostics.extend(_project_diagnostics(status))

    ordered = tuple(sorted(diagnostics, key=_sort_key))
    return DoctorReport(
        outcome=_outcome(ordered),
        workspace_name=status.workspace_name,
        workspace_root=workspace_root,
        focus=status.focus,
        diagnostics=ordered,
    )


# -- workspace-level checks ---------------------------------------------------


def _resolution_failed(status: WorkspaceStatus) -> bool:
    """Distinguish a workspace that failed to resolve (malformed/duplicate manifest)
    from a valid-but-empty one. The P8 failure sentinel empties both projects and
    packs; a valid workspace always carries its configured packs."""
    return (
        status.condition is Condition.FAILURE
        and not status.projects
        and not status.packs
    )


def _resolution_failure_diagnostics(
    status: WorkspaceStatus, project: str | None
) -> list[Diagnostic]:
    message = status.problems[0].message if status.problems else "workspace did not resolve"
    diagnostics = [
        Diagnostic(
            check=CHECK_WORKSPACE_MANIFEST,
            result=DiagnosticResult.FAIL,
            scope=WORKSPACE,
            explanation=f"workspace could not be resolved: {message}",
            action="Correct the manifest problem described above (it names the file), "
            "then re-run `projectos workspace status` to confirm.",
        )
    ]
    if project is not None:
        diagnostics.append(
            Diagnostic(
                check=CHECK_PROJECT_FOCUS,
                result=DiagnosticResult.SKIP,
                scope=WORKSPACE,
                explanation="project focus not checked — the workspace did not resolve",
            )
        )
    return diagnostics


def _workspace_manifest_ok() -> Diagnostic:
    return Diagnostic(
        check=CHECK_WORKSPACE_MANIFEST,
        result=DiagnosticResult.PASS,
        scope=WORKSPACE,
        explanation="workspace and project manifests resolve, validate, and have "
        "unique identifiers and repositories",
    )


def _project_focus_diagnostic(status: WorkspaceStatus, project: str | None) -> Diagnostic:
    if project is None:
        return Diagnostic(
            check=CHECK_PROJECT_FOCUS,
            result=DiagnosticResult.PASS,
            scope=WORKSPACE,
            explanation="no project focus requested",
        )
    if status.focus is not None:
        return Diagnostic(
            check=CHECK_PROJECT_FOCUS,
            result=DiagnosticResult.PASS,
            scope=WORKSPACE,
            explanation=f"project focus resolves to {status.focus!r}",
        )
    return Diagnostic(
        check=CHECK_PROJECT_FOCUS,
        result=DiagnosticResult.FAIL,
        scope=WORKSPACE,
        explanation=f"project focus {project!r} does not resolve to a registered project",
        action="Use a registered project id or name; "
        "`projectos workspace status` lists them.",
    )


def _pack_diagnostics(status: WorkspaceStatus) -> list[Diagnostic]:
    missing = [pack for pack in status.packs if not pack.available]
    if not missing:
        return [
            Diagnostic(
                check=CHECK_CONFIGURED_PACKS,
                result=DiagnosticResult.PASS,
                scope=WORKSPACE,
                explanation=f"all {len(status.packs)} configured pack path(s) present",
            )
        ]
    return [
        Diagnostic(
            check=CHECK_CONFIGURED_PACKS,
            result=DiagnosticResult.WARN,
            scope=WORKSPACE,
            explanation=f"configured pack {pack.name!r} directory is missing: {pack.path}",
            action="Restore the pack directory, or remove its entry from "
            "`Workspace.yaml`.",
        )
        for pack in missing
    ]


# -- per-project checks -------------------------------------------------------


def _project_diagnostics(status: WorkspaceStatus) -> list[Diagnostic]:
    # A focused run diagnoses only the focused project; otherwise every project.
    targets: tuple[ProjectStatusLine, ...]
    if status.focus is not None:
        targets = tuple(p for p in status.projects if p.project_id == status.focus)
    else:
        targets = status.projects

    audit_details = _audit_failure_details(status)
    diagnostics: list[Diagnostic] = []
    for project in targets:
        diagnostics.append(_identifier_diagnostic(project))
        diagnostics.append(_kernel_diagnostic(project))
        diagnostics.append(_pack_resolution_diagnostic(project))
        diagnostics.append(_audit_diagnostic(project, audit_details.get(project.project_id)))
        diagnostics.append(_repository_diagnostic(project))
    return diagnostics


def _identifier_diagnostic(project: ProjectStatusLine) -> Diagnostic:
    return Diagnostic(
        check=CHECK_PROJECT_IDENTIFIER,
        result=DiagnosticResult.PASS,
        scope=project.project_id,
        explanation=f"stable identifier {project.project_id!r}",
    )


def _kernel_diagnostic(project: ProjectStatusLine) -> Diagnostic:
    if project.initialised:
        return Diagnostic(
            check=CHECK_KERNEL_INITIALISED,
            result=DiagnosticResult.PASS,
            scope=project.project_id,
            explanation="project kernel is initialised",
        )
    return Diagnostic(
        check=CHECK_KERNEL_INITIALISED,
        result=DiagnosticResult.WARN,
        scope=project.project_id,
        explanation="project kernel is not initialised",
        action=f"Initialise it: `projectos workspace init-project {project.name} "
        "--founder-id <id> --founder-name <name>`.",
    )


def _pack_resolution_diagnostic(project: ProjectStatusLine) -> Diagnostic:
    if project.pack is None:
        return Diagnostic(
            check=CHECK_PROJECT_PACK,
            result=DiagnosticResult.WARN,
            scope=project.project_id,
            explanation="project declares no pack",
            action=f"Set a `pack:` in `Projects/{project.name}/project.yaml`.",
        )
    if project.pack_available:
        return Diagnostic(
            check=CHECK_PROJECT_PACK,
            result=DiagnosticResult.PASS,
            scope=project.project_id,
            explanation=f"pack {project.pack!r} resolves and is available",
        )
    return Diagnostic(
        check=CHECK_PROJECT_PACK,
        result=DiagnosticResult.WARN,
        scope=project.project_id,
        explanation=f"pack {project.pack!r} is not available in the workspace",
        action="Add the pack under `Shared/Packs` and configure it in "
        f"`Workspace.yaml`; `projectos pack validate Shared/Packs/{project.pack}` "
        "checks a pack.",
    )


def _audit_diagnostic(project: ProjectStatusLine, detail: str | None) -> Diagnostic:
    if project.integrity is IntegrityState.VERIFIED:
        return Diagnostic(
            check=CHECK_AUDIT_INTEGRITY,
            result=DiagnosticResult.PASS,
            scope=project.project_id,
            explanation="audit chain intact and consistent with state files",
        )
    if project.integrity is IntegrityState.FAILED:
        reason = f": {detail}" if detail else ""
        return Diagnostic(
            check=CHECK_AUDIT_INTEGRITY,
            result=DiagnosticResult.FAIL,
            scope=project.project_id,
            explanation=f"audit chain or assignment state could not be verified{reason}",
            action="Do not operate on this project. Inspect the chain (read-only) with "
            "`projectos history --verify` from the project's repository.",
        )
    return Diagnostic(
        check=CHECK_AUDIT_INTEGRITY,
        result=DiagnosticResult.SKIP,
        scope=project.project_id,
        explanation="no audit chain to verify — kernel not initialised",
    )


def _repository_diagnostic(project: ProjectStatusLine) -> Diagnostic:
    if project.has_repository:
        return Diagnostic(
            check=CHECK_REPOSITORY_METADATA,
            result=DiagnosticResult.PASS,
            scope=project.project_id,
            explanation="repository metadata is declared",
        )
    return Diagnostic(
        check=CHECK_REPOSITORY_METADATA,
        result=DiagnosticResult.WARN,
        scope=project.project_id,
        explanation="no repository metadata declared (optional but recommended)",
        action=f"Declare a `repository:` block (adapter + remote/branch or path) in "
        f"`Projects/{project.name}/project.yaml`.",
    )


# -- helpers ------------------------------------------------------------------


def _audit_failure_details(status: WorkspaceStatus) -> dict[str, str]:
    """Recover the underlying audit-failure reason per project from the P8 problems,
    so the doctor can explain *why* without re-reading kernel state."""
    details: dict[str, str] = {}
    for problem in status.problems:
        if problem.message.startswith(_AUDIT_PROBLEM_PREFIX):
            details[problem.scope] = problem.message[len(_AUDIT_PROBLEM_PREFIX) :]
    return details


def _sort_key(diagnostic: Diagnostic) -> tuple[int, int, str, str, str]:
    """Deterministic total order: failures → warnings → passes → skips, then
    workspace-scoped before project-scoped (projects by stable id), then by check id,
    then by explanation as a final tiebreak."""
    scope_rank = 0 if diagnostic.scope == WORKSPACE else 1
    return (
        _RESULT_RANK[diagnostic.result],
        scope_rank,
        diagnostic.scope,
        diagnostic.check,
        diagnostic.explanation,
    )


def _outcome(diagnostics: tuple[Diagnostic, ...]) -> Outcome:
    if any(d.result is DiagnosticResult.FAIL for d in diagnostics):
        return Outcome.FAIL
    if any(d.result is DiagnosticResult.WARN for d in diagnostics):
        return Outcome.WARN
    return Outcome.PASS


# -- rendering (deterministic text) -------------------------------------------

_RULE = "─" * 68


def render_report(report: DoctorReport) -> str:
    """Render a diagnostic report as deterministic, human-readable text."""
    lines: list[str] = []
    lines.append(f"WORKSPACE DOCTOR  {report.workspace_name}  [{report.outcome.value.upper()}]")
    lines.append(_RULE)
    lines.append(f"  root   {report.workspace_root}")
    lines.append(f"  focus  {report.focus or 'none'}")
    lines.append("")
    lines.append(
        f"  checks {len(report.diagnostics)}    pass {report.passed}    "
        f"warn {report.warned}    fail {report.failed}    skip {report.skipped}"
    )
    lines.append("")
    lines.append(f"DIAGNOSTICS  ({len(report.diagnostics)})")
    for diagnostic in report.diagnostics:
        lines.append(
            f"  [{diagnostic.result.value.upper()}] {diagnostic.check}  "
            f"({diagnostic.scope}): {diagnostic.explanation}"
        )
        if diagnostic.action is not None:
            lines.append(f"         → action: {diagnostic.action}")
    return "\n".join(lines)
