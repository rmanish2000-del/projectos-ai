"""Binding pack templates into concrete DRAFT assignments (spec sections 3.3, 10.1).

A template is the assignment schema minus the kernel-issued fields. Binding fills
those in — identifier, owner, status, dependency on the predecessor — and refuses
any template that tries to supply them itself. That refusal is what keeps packs
declarative: a pack cannot mint an identifier, set a status, or pre-approve itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from projectos.domain.assignment import Assignment
from projectos.domain.errors import ValidationError
from projectos.domain.ids import AssignmentId
from projectos.domain.manifest import Manifest
from projectos.domain.pack import PackTemplate
from projectos.infrastructure.serialization import assignment_from_dict

#: Fields only the kernel may set. A template containing any of these is rejected.
KERNEL_ISSUED_FIELDS: frozenset[str] = frozenset({"id", "state", "origin_template"})


@dataclass(frozen=True, slots=True)
class YamlTemplateBinder:
    """Infrastructure implementation of the `TemplateBinder` port.

    Binding needs the serialisation layer, which is why it is a port: the
    application layer asks for a bound assignment and never learns that YAML is
    involved.
    """

    def bind(
        self,
        template: PackTemplate,
        *,
        assignment_id: AssignmentId,
        manifest: Manifest,
        predecessor: Assignment | None = None,
    ) -> Assignment:
        return bind_template(
            template,
            assignment_id=assignment_id,
            manifest=manifest,
            predecessor=predecessor,
        )


def bind_template(
    template: PackTemplate,
    *,
    assignment_id: AssignmentId,
    manifest: Manifest,
    predecessor: Assignment | None = None,
) -> Assignment:
    """Produce a DRAFT assignment from a template."""
    body: dict[str, Any] = dict(template.body)

    intruding = KERNEL_ISSUED_FIELDS & set(body)
    if intruding:
        raise ValidationError(
            f"Template {template.name!r} sets kernel-issued fields: "
            f"{', '.join(sorted(intruding))}",
            detail="Packs are declarative data; the kernel issues identity and state.",
        )

    body["schema_version"] = 1
    body["id"] = str(assignment_id)
    body["origin_template"] = template.name
    body.setdefault("owner", manifest.founder.id)
    body["state"] = {"status": "draft", "history": []}

    # Chain onto the predecessor unless the template declares its own dependencies,
    # so a generated pipeline is sequential by default (INV-7, no parallel work).
    if predecessor is not None and "depends_on" not in body:
        body["depends_on"] = [str(predecessor.id)]

    return assignment_from_dict(body, source=f"pack template {template.name!r}")
