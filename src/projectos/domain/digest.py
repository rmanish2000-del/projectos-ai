"""Immutable-field integrity digest (spec section 6.1).

A SHA-256 digest over an assignment's *scope-defining* fields. The kernel binds
this digest into the hash-chained audit log at the `classify_ok` transition, then
recomputes it on every load; a mismatch means a scope or classification field was
hand-edited after the assignment left DRAFT, and halts the kernel.

The digest is computed here, in the domain, from the Assignment value alone — no
I/O, no serializer. The application layer binds and checks it, but the canonical
form is defined once, here, so the value bound at `classify_ok` and the value
recomputed at verification cannot diverge in representation.

Excluded from the digest (mutable by design, per §6.1): the `state` block, and the
kernel-written annotations `classification_rule` and `rejection_reasons`. Those
carry no authority and no verification effect.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from projectos.domain.assignment import Assignment


def immutable_payload(assignment: Assignment) -> dict[str, Any]:
    """The canonical, digest-covered view of an assignment's immutable fields.

    Every scope-defining field named in §6.1 appears here. Acceptance criteria
    include their verification-rule type *and parameters*, so tampering with a rule
    parameter (for example lowering `approvals_required`) changes the digest.
    """
    return {
        "id": str(assignment.id),
        "schema_version": assignment.schema_version,
        "title": assignment.title,
        "work_type": assignment.work_type.value,
        "objective": assignment.objective,
        "owner": assignment.owner,
        "executor": assignment.executor.value,
        "workflow_mode": assignment.workflow_mode.value,
        "risk_flags": sorted(assignment.risk_flags),
        "depends_on": [str(dependency) for dependency in assignment.depends_on],
        "context_refs": [ref.path for ref in assignment.context_refs],
        "stopping_point": assignment.stopping_point,
        "acceptance_criteria": [
            {
                "id": criterion.id,
                "statement": criterion.statement,
                "type": criterion.verify.type.value,
                "params": _canonical_params(criterion.verify.params),
            }
            for criterion in assignment.acceptance_criteria
        ],
        "evidence_required": [cls.value for cls in assignment.evidence_required],
        "next": assignment.next.template if assignment.next is not None else None,
        "origin_template": assignment.origin_template,
    }


def immutable_digest(assignment: Assignment) -> str:
    """SHA-256 hex digest of :func:`immutable_payload`, canonically serialized."""
    canonical = json.dumps(
        immutable_payload(assignment),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_params(params: Any) -> dict[str, Any]:
    """Rule parameters as a plain, ordered dict.

    `EvidenceRule.params` is a read-only mapping; JSON with `sort_keys=True` orders
    it deterministically, so this only needs to materialise it as a dict.
    """
    return {key: params[key] for key in sorted(params)}
