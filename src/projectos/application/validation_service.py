"""Reusable validation capability (spec sections 5, 10, 13, 14.1).

One service, four callers: the `validate` command, the `pack validate` command,
pack loading, and pack activation. Writing a validator per command would let the
commands drift from what loading actually enforces — a pack that `pack validate`
blesses but loading rejects, or worse, the reverse.

Validation is **side-effect free**. Nothing here writes, transitions, installs, or
activates. It reads, judges, and returns a structured report; turning that report
into console output and an exit code happens at the CLI boundary and nowhere else.

Findings are structured rather than raised so a single run reports everything wrong
with a repository, in the same spirit as the verification engine collecting all
failing criteria instead of stopping at the first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from projectos.application.ports import TemplateBinder
from projectos.domain import compatibility
from projectos.domain.assignment import Assignment
from projectos.domain.compatibility import KERNEL_VERSION
from projectos.domain.enums import Status
from projectos.domain.errors import ProjectOSError
from projectos.domain.evidence import RULE_CAPABILITIES
from projectos.domain.ids import AssignmentId
from projectos.domain.manifest import Manifest
from projectos.domain.pack import Pack
from projectos.domain.routing import validate_routing


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class Finding:
    """One validation result. `code` is stable and machine-greppable."""

    severity: Severity
    code: str
    message: str
    location: str
    hint: str = ""

    def describe(self) -> str:
        marker = "ERROR" if self.severity is Severity.ERROR else "warn "
        line = f"  [{marker}] {self.location}: {self.message}"
        if self.hint:
            line += f"\n           {self.hint}"
        return line


@dataclass(frozen=True, slots=True)
class ValidationReport:
    findings: tuple[Finding, ...] = ()
    checked: tuple[str, ...] = field(default=())

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.WARNING)

    @property
    def ok(self) -> bool:
        """Warnings do not fail validation; errors do."""
        return not self.errors

    def merged_with(self, other: ValidationReport) -> ValidationReport:
        return ValidationReport(
            findings=self.findings + other.findings,
            checked=self.checked + other.checked,
        )


def _error(code: str, message: str, location: str, hint: str = "") -> Finding:
    return Finding(Severity.ERROR, code, message, location, hint)


def _warning(code: str, message: str, location: str, hint: str = "") -> Finding:
    return Finding(Severity.WARNING, code, message, location, hint)


# -- pack version compatibility ----------------------------------------------


def check_pack_compatibility(
    pack: Pack, *, declared_constraint: str | None, kernel_version: str = KERNEL_VERSION
) -> tuple[Finding, ...]:
    """Check both compatibility questions for one pack.

    Shared by the validation commands and by pack loading, so a pack cannot be
    loaded on a path that skips a check the commands would have applied.
    """
    findings: list[Finding] = []
    location = f"pack {pack.name!r}"

    if declared_constraint is not None:
        try:
            result = compatibility.check(
                subject=f"pack {pack.name}",
                version=pack.version,
                constraint=declared_constraint,
                source=f"{location} manifest constraint",
            )
        except ProjectOSError as exc:
            findings.append(
                _error("pack.version.constraint_invalid", exc.message, location, exc.detail or "")
            )
        else:
            if not result.compatible:
                findings.append(
                    _error(
                        "pack.version.mismatch",
                        f"pack version {pack.version} does not satisfy the manifest "
                        f"constraint {declared_constraint!r}",
                        location,
                        result.reason,
                    )
                )

    if pack.requires_projectos is None:
        findings.append(
            _warning(
                "pack.requires_projectos.missing",
                "pack declares no ProjectOS compatibility constraint",
                location,
                "Add `requires_projectos: \">=0.1.0,<0.2.0\"` so incompatible kernels "
                "are rejected rather than assumed to work.",
            )
        )
    else:
        try:
            result = compatibility.check(
                subject="kernel",
                version=kernel_version,
                constraint=pack.requires_projectos,
                source=f"{location} requires_projectos",
            )
        except ProjectOSError as exc:
            findings.append(
                _error("pack.requires_projectos.invalid", exc.message, location, exc.detail or "")
            )
        else:
            if not result.compatible:
                findings.append(
                    _error(
                        "pack.requires_projectos.incompatible",
                        f"pack requires ProjectOS {pack.requires_projectos!r} but the "
                        f"running kernel is {kernel_version}",
                        location,
                        result.reason,
                    )
                )

    return tuple(findings)


# -- pack structural and semantic validation ---------------------------------


def validate_pack(
    pack: Pack,
    *,
    declared_constraint: str | None = None,
    kernel_version: str = KERNEL_VERSION,
    binder: TemplateBinder | None = None,
) -> ValidationReport:
    """Validate one pack in isolation. Never installs or activates it."""
    findings: list[Finding] = list(
        check_pack_compatibility(
            pack, declared_constraint=declared_constraint, kernel_version=kernel_version
        )
    )
    location = f"pack {pack.name!r}"

    # Referential integrity: the domain constructor already rejects a pipeline
    # naming an unknown template, so anything reaching here is about the reverse —
    # templates that no phase will ever reach.
    referenced = {name for phase in pack.pipeline for name in phase.templates}
    for template in pack.templates:
        if template.name not in referenced:
            findings.append(
                _warning(
                    "pack.template.unreferenced",
                    f"template {template.name!r} is not referenced by any pipeline phase",
                    location,
                    "It will never be generated automatically.",
                )
            )

    if not pack.pipeline:
        findings.append(
            _warning(
                "pack.pipeline.empty",
                "pack declares no pipeline",
                location,
                "`projectos next` cannot generate successors from this pack.",
            )
        )

    findings.extend(_validate_pack_templates(pack, location, binder))
    findings.extend(_validate_pack_declarations(pack, location))

    return ValidationReport(
        findings=tuple(findings),
        checked=(f"pack {pack.name} v{pack.version}",),
    )


def _validate_pack_templates(
    pack: Pack, location: str, binder: TemplateBinder | None
) -> tuple[Finding, ...]:
    """Bind every template so authoring errors surface here, not at generation time.

    Binding is what `projectos next` does, so validating by binding means the two
    cannot disagree about whether a template is well formed. The binder arrives as
    a port; the application layer never reaches into infrastructure for it.
    """
    if binder is None:
        return ()

    findings: list[Finding] = []
    for template in pack.templates:
        try:
            binder.bind(
                template,
                assignment_id=AssignmentId(1),
                manifest=_probe_manifest(),
                predecessor=None,
            )
        except ProjectOSError as exc:
            findings.append(
                _error(
                    "pack.template.invalid",
                    f"template {template.name!r} does not produce a valid assignment: "
                    f"{exc.message}",
                    location,
                    exc.detail or "",
                )
            )
    return tuple(findings)


def _validate_pack_declarations(pack: Pack, location: str) -> tuple[Finding, ...]:
    """Check declarations that reference kernel vocabulary."""
    from projectos.domain.enums import WorkType

    findings: list[Finding] = []
    known_work_types = {member.value for member in WorkType}

    for work_type in sorted(pack.reviewed_work_types):
        if work_type not in known_work_types:
            findings.append(
                _error(
                    "pack.classification.unknown_work_type",
                    f"reviewed_work_types names unknown work type {work_type!r}",
                    location,
                    f"Known work types: {', '.join(sorted(known_work_types))}.",
                )
            )

    for path in sorted(pack.protected_paths):
        if not path.strip():
            findings.append(
                _error(
                    "pack.classification.empty_protected_path",
                    "protected_paths contains an empty glob",
                    location,
                )
            )

    return tuple(findings)


def _probe_manifest() -> Manifest:
    """A minimal in-memory manifest used only to bind templates during validation.

    Never written anywhere. Template binding needs a founder identity to default
    the owner, and validating a pack must not require a project to exist.
    """
    from projectos.domain.enums import RepositoryAdapterKind
    from projectos.domain.manifest import Identity, RepositoryConfig

    probe = Identity(id="validation-probe@localhost", name="Validation Probe")
    return Manifest(
        schema_version=1,
        project_id="validation-probe",
        project_name="Validation Probe",
        description="",
        founder=probe,
        owners=(probe,),
        repository=RepositoryConfig(adapter=RepositoryAdapterKind.LOCAL_GIT),
    )


# -- whole-project validation -------------------------------------------------


def validate_project(
    *,
    manifest: Manifest,
    packs: tuple[tuple[Pack, str | None], ...],
    assignments: tuple[Assignment, ...],
    kernel_version: str = KERNEL_VERSION,
    binder: TemplateBinder | None = None,
) -> ValidationReport:
    """Validate manifest, packs, and assignment state together.

    Takes already-loaded values rather than paths: loading is infrastructure's job,
    and keeping it out of here is what makes the service side-effect free and
    trivially testable.
    """
    report = ValidationReport(checked=(f"manifest for project {manifest.project_id!r}",))
    findings: list[Finding] = []

    for pack, constraint in packs:
        report = report.merged_with(
            validate_pack(
                pack,
                declared_constraint=constraint,
                kernel_version=kernel_version,
                binder=binder,
            )
        )

    findings.extend(_validate_assignments(manifest, assignments))
    findings.extend(_validate_manifest_semantics(manifest))

    return report.merged_with(
        ValidationReport(
            findings=tuple(findings),
            checked=(f"{len(assignments)} assignment(s)",),
        )
    )


def _validate_manifest_semantics(manifest: Manifest) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    if manifest.repository.adapter.value == "github":
        findings.append(
            _warning(
                "manifest.adapter.unimplemented",
                "the github adapter is not implemented in this phase",
                "manifest.repository.adapter",
                "PR, CI, and artifact rules will fail closed. Use 'local_git' until "
                "phase P4.",
            )
        )
    return tuple(findings)


def _validate_assignments(
    manifest: Manifest, assignments: tuple[Assignment, ...]
) -> tuple[Finding, ...]:
    """Semantic checks across the assignment registry."""
    findings: list[Finding] = []

    active = [a for a in assignments if a.occupies_active_slot]
    if len(active) > 1:
        findings.append(
            _error(
                "state.inv1_violated",
                "more than one assignment occupies the active slot: "
                f"{', '.join(str(a.id) for a in active)}",
                "assignments",
                "INV-1 permits at most one. State has been edited outside the kernel.",
            )
        )

    known_ids = {a.id for a in assignments}
    for assignment in assignments:
        location = f"assignment {assignment.id}"

        if not manifest.is_owner(assignment.owner):
            findings.append(
                _error(
                    "assignment.owner.unknown",
                    f"owner {assignment.owner!r} is not listed in manifest.owners",
                    location,
                )
            )

        try:
            validate_routing(assignment, manifest.agents)
        except ProjectOSError as exc:
            findings.append(
                _error("assignment.routing.invalid", exc.message, location, exc.detail or "")
            )

        for dependency in assignment.depends_on:
            if dependency not in known_ids:
                findings.append(
                    _error(
                        "assignment.depends_on.missing",
                        f"depends on {dependency}, which does not exist",
                        location,
                    )
                )

        findings.extend(_validate_criteria(assignment, location))

        if assignment.status is Status.DRAFT and assignment.classification_rule is None:
            findings.append(
                _warning(
                    "assignment.unclassified",
                    "assignment is still DRAFT and has never been classified",
                    location,
                    "Run `projectos next` to classify it.",
                )
            )

    return tuple(findings)


def _validate_criteria(assignment: Assignment, location: str) -> tuple[Finding, ...]:
    """Check that every acceptance criterion is evaluable as authored."""
    findings: list[Finding] = []
    for criterion in assignment.acceptance_criteria:
        rule = criterion.verify
        if rule.type not in RULE_CAPABILITIES:
            findings.append(
                _error(
                    "criterion.rule.unknown",
                    f"{criterion.id} uses unknown rule type {rule.type!r}",
                    location,
                )
            )
            continue
        capability = rule.required_capability
        if capability is not None:
            findings.append(
                _warning(
                    "criterion.rule.needs_capability",
                    f"{criterion.id} needs the '{capability}' adapter capability",
                    location,
                    "It will fail closed unless an adapter providing it is configured.",
                )
            )
    return tuple(findings)
