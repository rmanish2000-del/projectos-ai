"""Mapping between YAML documents and domain values.

Kept in one module so the on-disk shape has exactly one definition. Every `from_*`
function validates against the JSON Schema first, then constructs the domain value,
whose own constructor enforces the cross-field rules.

Serialisation is deterministic: keys are emitted in a fixed order and optional
fields are omitted when empty, so an unchanged assignment always round-trips to a
byte-identical file. That is what keeps `git diff` on `.projectos/` meaningful.
"""

from __future__ import annotations

from typing import Any

from projectos.domain.assignment import Assignment, ContextRef, NextSpec, TransitionRecord
from projectos.domain.enums import (
    EscalationState,
    EscalationTrigger,
    Event,
    EvidenceClass,
    ExecutorType,
    FounderDecision,
    RepositoryAdapterKind,
    RuleType,
    Status,
    WorkflowMode,
    WorkType,
)
from projectos.domain.errors import ValidationError
from projectos.domain.escalation import Escalation, EscalationOption, Resolution
from projectos.domain.evidence import AcceptanceCriterion, EvidenceRule
from projectos.domain.ids import AssignmentId, EscalationId
from projectos.domain.manifest import (
    KERNEL_GOVERNED_TRIGGERS,
    ApprovalsConfig,
    Identity,
    Manifest,
    PackRequirement,
    RepositoryConfig,
    WorkflowConfig,
)
from projectos.domain.pack import Pack, PackTemplate, PipelinePhase
from projectos.infrastructure.validation import validate

# --- manifest ---------------------------------------------------------------


def manifest_from_dict(raw: dict[str, Any], *, source: str = "manifest.yaml") -> Manifest:
    validate(raw, "manifest.schema.json", source=source)
    project = raw["project"]
    repository = raw["repository"]
    config = repository.get("config", {})
    github = config.get("github", {})
    workflow = raw.get("workflow", {})
    approvals = raw.get("approvals", {})

    triggers = workflow.get("governed_triggers")
    return Manifest(
        schema_version=raw["schema_version"],
        project_id=project["id"],
        project_name=project["name"],
        description=project.get("description", ""),
        founder=_identity(project["founder"]),
        owners=tuple(_identity(o) for o in raw["owners"]),
        packs=tuple(
            PackRequirement(p["name"], p.get("version", "*")) for p in raw.get("packs", [])
        ),
        repository=RepositoryConfig(
            adapter=RepositoryAdapterKind(repository["adapter"]),
            remote=config.get("remote", "origin"),
            default_branch=config.get("default_branch", "main"),
            github_owner=github.get("owner"),
            github_repo=github.get("repo"),
        ),
        agents=tuple(ExecutorType(a["type"]) for a in raw.get("agents", []))
        or (ExecutorType.COWORK, ExecutorType.CODE, ExecutorType.HUMAN),
        workflow=WorkflowConfig(
            default_mode=WorkflowMode(workflow.get("default_mode", "fast")),
            governed_triggers=(
                frozenset(triggers) if triggers is not None else KERNEL_GOVERNED_TRIGGERS
            ),
        ),
        approvals=ApprovalsConfig(
            merge=approvals.get("merge", "manual"),
            deploy=approvals.get("deploy", "manual"),
        ),
        hash_algorithm=raw.get("audit", {}).get("hash_algorithm", "sha256"),
    )


def manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    config: dict[str, Any] = {
        "remote": manifest.repository.remote,
        "default_branch": manifest.repository.default_branch,
    }
    if manifest.repository.adapter is RepositoryAdapterKind.GITHUB:
        config["github"] = {
            "owner": manifest.repository.github_owner,
            "repo": manifest.repository.github_repo,
        }
    return {
        "schema_version": manifest.schema_version,
        "project": {
            "id": manifest.project_id,
            "name": manifest.project_name,
            "description": manifest.description,
            "founder": {"id": manifest.founder.id, "name": manifest.founder.name},
        },
        "owners": [{"id": o.id, "name": o.name} for o in manifest.owners],
        "packs": [{"name": p.name, "version": p.version} for p in manifest.packs],
        "repository": {"adapter": manifest.repository.adapter.value, "config": config},
        "agents": [{"type": a.value} for a in manifest.agents],
        "workflow": {
            "default_mode": manifest.workflow.default_mode.value,
            "governed_triggers": sorted(manifest.workflow.governed_triggers),
        },
        "approvals": {
            "merge": manifest.approvals.merge,
            "deploy": manifest.approvals.deploy,
        },
        "audit": {"hash_algorithm": manifest.hash_algorithm},
    }


def _identity(raw: dict[str, Any]) -> Identity:
    return Identity(id=raw["id"], name=raw["name"])


# --- assignment -------------------------------------------------------------


def assignment_from_dict(raw: dict[str, Any], *, source: str) -> Assignment:
    validate(raw, "assignment.schema.json", source=source)
    state = raw.get("state", {})
    return Assignment(
        id=AssignmentId.parse(raw["id"]),
        schema_version=raw["schema_version"],
        title=raw["title"],
        work_type=WorkType(raw["work_type"]),
        objective=raw["objective"],
        owner=raw["owner"],
        executor=ExecutorType(raw["executor"]),
        workflow_mode=WorkflowMode(raw.get("workflow_mode", "fast")),
        risk_flags=tuple(raw.get("risk_flags", [])),
        depends_on=tuple(AssignmentId.parse(d) for d in raw.get("depends_on", [])),
        context_refs=tuple(ContextRef(c["path"]) for c in raw.get("context_refs", [])),
        stopping_point=raw["stopping_point"],
        acceptance_criteria=tuple(
            _criterion_from_dict(c) for c in raw["acceptance_criteria"]
        ),
        evidence_required=tuple(EvidenceClass(e) for e in raw.get("evidence_required", [])),
        next=NextSpec(raw["next"]["template"]) if raw.get("next") else None,
        origin_template=raw.get("origin_template"),
        classification_rule=raw.get("classification_rule"),
        rejection_reasons=tuple(raw.get("rejection_reasons", [])),
        status=Status(state.get("status", "draft")),
        history=tuple(_transition_from_dict(h) for h in state.get("history", [])),
    )


def assignment_to_dict(assignment: Assignment) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": assignment.schema_version,
        "id": str(assignment.id),
        "title": assignment.title,
        "work_type": assignment.work_type.value,
        "objective": assignment.objective,
        "owner": assignment.owner,
        "executor": assignment.executor.value,
        "workflow_mode": assignment.workflow_mode.value,
    }
    if assignment.risk_flags:
        data["risk_flags"] = list(assignment.risk_flags)
    if assignment.depends_on:
        data["depends_on"] = [str(d) for d in assignment.depends_on]
    if assignment.context_refs:
        data["context_refs"] = [{"path": c.path} for c in assignment.context_refs]
    data["stopping_point"] = assignment.stopping_point
    data["acceptance_criteria"] = [
        _criterion_to_dict(c) for c in assignment.acceptance_criteria
    ]
    if assignment.evidence_required:
        data["evidence_required"] = [e.value for e in assignment.evidence_required]
    if assignment.next is not None:
        data["next"] = {"template": assignment.next.template}
    if assignment.origin_template is not None:
        data["origin_template"] = assignment.origin_template
    if assignment.classification_rule is not None:
        data["classification_rule"] = assignment.classification_rule
    if assignment.rejection_reasons:
        data["rejection_reasons"] = list(assignment.rejection_reasons)
    data["state"] = {
        "status": assignment.status.value,
        "history": [_transition_to_dict(h) for h in assignment.history],
    }
    return data


def _criterion_from_dict(raw: dict[str, Any]) -> AcceptanceCriterion:
    verify = dict(raw["verify"])
    rule_type = RuleType(verify.pop("type"))
    return AcceptanceCriterion(
        id=raw["id"],
        statement=raw["statement"],
        verify=EvidenceRule(type=rule_type, params=verify),
    )


def _criterion_to_dict(criterion: AcceptanceCriterion) -> dict[str, Any]:
    return {
        "id": criterion.id,
        "statement": criterion.statement,
        "verify": {"type": criterion.verify.type.value, **criterion.verify.params},
    }


def _transition_from_dict(raw: dict[str, Any]) -> TransitionRecord:
    return TransitionRecord(
        event=Event(raw["event"]),
        from_status=Status(raw["from_status"]),
        to_status=Status(raw["to_status"]),
        actor=raw["actor"],
        timestamp=raw["timestamp"],
        audit_ref=raw["audit_ref"],
        reason=raw.get("reason"),
    )


def _transition_to_dict(record: TransitionRecord) -> dict[str, Any]:
    data: dict[str, Any] = {
        "event": record.event.value,
        "from_status": record.from_status.value,
        "to_status": record.to_status.value,
        "actor": record.actor,
        "timestamp": record.timestamp,
        "audit_ref": record.audit_ref,
    }
    if record.reason is not None:
        data["reason"] = record.reason
    return data


# --- escalation -------------------------------------------------------------


def escalation_from_dict(raw: dict[str, Any], *, source: str) -> Escalation:
    validate(raw, "escalation.schema.json", source=source)
    resolution_raw = raw.get("resolution")
    resolution = None
    if resolution_raw and resolution_raw.get("decision") is not None:
        resolution = Resolution(
            decision=resolution_raw["decision"],
            decided_by=resolution_raw["decided_by"],
            decided_at=resolution_raw["decided_at"],
            outcome=FounderDecision(resolution_raw["outcome"]),
        )
    assignment_id = raw.get("assignment_id")
    return Escalation(
        id=EscalationId.parse(raw["id"]),
        schema_version=raw["schema_version"],
        assignment_id=AssignmentId.parse(assignment_id) if assignment_id else None,
        trigger=EscalationTrigger(raw["trigger"]),
        summary=raw["summary"],
        options=tuple(
            EscalationOption(o["id"], o["description"], o["consequence"])
            for o in raw["options"]
        ),
        recommendation=raw.get("recommendation"),
        state=EscalationState(raw["state"]),
        resolution=resolution,
        created_at=raw.get("created_at", ""),
    )


def escalation_to_dict(escalation: Escalation) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": escalation.schema_version,
        "id": str(escalation.id),
        "assignment_id": str(escalation.assignment_id) if escalation.assignment_id else None,
        "trigger": escalation.trigger.value,
        "summary": escalation.summary,
        "options": [
            {"id": o.id, "description": o.description, "consequence": o.consequence}
            for o in escalation.options
        ],
        "recommendation": escalation.recommendation,
        "created_at": escalation.created_at,
        "state": escalation.state.value,
    }
    if escalation.resolution is not None:
        data["resolution"] = {
            "decision": escalation.resolution.decision,
            "decided_by": escalation.resolution.decided_by,
            "decided_at": escalation.resolution.decided_at,
            "outcome": escalation.resolution.outcome.value,
        }
    return data


# --- pack -------------------------------------------------------------------


def pack_from_dict(
    raw: dict[str, Any], templates: tuple[PackTemplate, ...], *, source: str
) -> Pack:
    validate(raw, "pack.schema.json", source=source)
    classification = raw.get("classification", {})
    return Pack(
        schema_version=raw["schema_version"],
        name=raw["name"],
        version=raw["version"],
        domain=raw.get("domain", "generic"),
        risk_flag_vocabulary=frozenset(raw.get("vocabulary", {}).get("risk_flags", [])),
        reviewed_work_types=frozenset(classification.get("reviewed_work_types", [])),
        protected_paths=frozenset(classification.get("protected_paths", [])),
        governed_triggers_add=frozenset(classification.get("governed_triggers_add", [])),
        escalation_triggers_add=frozenset(raw.get("escalation_triggers_add", [])),
        pipeline=tuple(
            PipelinePhase(p["phase"], tuple(p["templates"])) for p in raw.get("pipeline", [])
        ),
        templates=templates,
    )


def require_mapping(value: Any, *, source: str) -> dict[str, Any]:
    """Reject a YAML document that is not a mapping before indexing into it."""
    if not isinstance(value, dict):
        raise ValidationError(
            f"{source} must contain a YAML mapping",
            detail=f"Found {type(value).__name__}.",
        )
    return value
