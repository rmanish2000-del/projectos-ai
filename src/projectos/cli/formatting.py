"""Output formatting. Presentation only — no logic, no decisions.

Every function here takes already-decided values and renders them. The CLI is a
thin wrapper over kernel operations (spec section 2.2, UI layer), so nothing in
this module may branch on domain rules.
"""

from __future__ import annotations

from projectos.domain.assignment import Assignment
from projectos.domain.audit import AuditEntry
from projectos.domain.escalation import Escalation
from projectos.domain.evidence import VerificationReport
from projectos.domain.manifest import Manifest

RULE = "─" * 68


def heading(text: str) -> str:
    return f"{text}\n{RULE}"


def project_summary(manifest: Manifest) -> str:
    return "\n".join(
        [
            heading(f"PROJECT  {manifest.project_name}  ({manifest.project_id})"),
            f"  Founder     {manifest.founder.name} <{manifest.founder.id}>",
            f"  Repository  {manifest.repository.adapter.value} "
            f"(branch {manifest.repository.default_branch})",
            f"  Packs       {', '.join(p.name for p in manifest.packs) or 'none'}",
            f"  Default     {manifest.workflow.default_mode.value}",
        ]
    )


def assignment_summary(assignment: Assignment, *, indent: str = "  ") -> str:
    lines = [
        f"{indent}{assignment.id}  {assignment.title}",
        f"{indent}  Status    {assignment.status.value.upper()}",
        f"{indent}  Owner     {assignment.owner}",
        f"{indent}  Work      {assignment.work_type.value} → {assignment.executor.value}",
        f"{indent}  Workflow  {assignment.workflow_mode.value}",
    ]
    if assignment.classification_rule:
        lines.append(f"{indent}  Rule      {assignment.classification_rule}")
    if assignment.depends_on:
        deps = ", ".join(str(d) for d in assignment.depends_on)
        lines.append(f"{indent}  Depends   {deps}")
    if assignment.rejection_reasons:
        lines.append(f"{indent}  Rejected because:")
        lines += [f"{indent}    - {reason}" for reason in assignment.rejection_reasons]
    return "\n".join(lines)


def next_summary(
    assignment: Assignment,
    *,
    source: str,
    dependencies: str,
    indent: str = "  ",
) -> str:
    """The `projectos next` block: every field the P2 CLI contract requires —
    id, title, owner, executor, workflow mode, generation source, dependency
    status, and current status — in one deterministic layout."""
    lines = [
        f"{indent}{assignment.id}  {assignment.title}",
        f"{indent}  Status      {assignment.status.value.upper()}",
        f"{indent}  Owner       {assignment.owner}",
        f"{indent}  Executor    {assignment.executor.value}  ({assignment.work_type.value})",
        f"{indent}  Workflow    {assignment.workflow_mode.value}",
        f"{indent}  Source      {source}",
        f"{indent}  Dependency  {dependencies}",
    ]
    if assignment.rejection_reasons:
        lines.append(f"{indent}  Rejected because:")
        lines += [f"{indent}    - {reason}" for reason in assignment.rejection_reasons]
    return "\n".join(lines)


def verification_report(report: VerificationReport) -> str:
    lines = [heading(f"VERIFICATION  {report.assignment_id}")]
    for result in report.results:
        marker = "PASS" if result.passed else "FAIL"
        lines.append(f"  [{marker}]  {result.criterion_id}  {result.rule}")
        lines.append(f"          {result.reason}")
    lines.append(RULE)
    lines.append(f"  VERDICT: {'VERIFIED' if report.passed else 'REJECTED'}")
    return "\n".join(lines)


def escalation_summary(escalation: Escalation, *, indent: str = "  ") -> str:
    scope = str(escalation.assignment_id) if escalation.assignment_id else "project-level"
    lines = [
        f"{indent}{escalation.id}  [{escalation.trigger.value}]  {scope}",
        f"{indent}  {escalation.summary}",
    ]
    for option in escalation.options:
        marker = " (recommended)" if option.id == escalation.recommendation else ""
        lines.append(f"{indent}    {option.id}{marker}  {option.description}")
        lines.append(f"{indent}         → {option.consequence}")
    if escalation.resolution is not None:
        lines.append(
            f"{indent}  RESOLVED  {escalation.resolution.decision} "
            f"by {escalation.resolution.decided_by} at {escalation.resolution.decided_at}"
        )
    return "\n".join(lines)


def audit_line(entry: AuditEntry) -> str:
    scope = entry.assignment_id or entry.escalation_id or "project"
    transition = (
        f"{entry.from_status} → {entry.to_status}"
        if entry.from_status and entry.to_status
        else "—"
    )
    line = (
        f"  {entry.sequence:>4}  {entry.timestamp}  {scope:<8}  "
        f"{entry.event:<24}  {transition}"
    )
    if entry.reason:
        line += f"\n        reason: {entry.reason}"
    return line


def briefing_block(rendered: str) -> str:
    return "\n".join([heading("BRIEFING"), rendered])
