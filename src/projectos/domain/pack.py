"""Project-pack model (spec section 10).

Packs are declarative data, never code. They extend the kernel only at the declared
extension points, and every extension is additive: a pack can raise a
classification, add a governed trigger, or add an escalation trigger, but it has no
representation for removing one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from projectos.domain.errors import ValidationError


@dataclass(frozen=True, slots=True)
class PackTemplate:
    """An assignment template: schema section 6 minus kernel-issued fields."""

    name: str
    body: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PipelinePhase:
    phase: str
    templates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Pack:
    schema_version: int
    name: str
    version: str
    domain: str = "generic"
    risk_flag_vocabulary: frozenset[str] = frozenset()
    reviewed_work_types: frozenset[str] = frozenset()
    protected_paths: frozenset[str] = frozenset()
    governed_triggers_add: frozenset[str] = frozenset()
    escalation_triggers_add: frozenset[str] = frozenset()
    pipeline: tuple[PipelinePhase, ...] = ()
    templates: tuple[PackTemplate, ...] = ()

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValidationError(f"Unsupported pack schema_version {self.schema_version}")
        if not self.name.strip():
            raise ValidationError("Pack name must be non-empty")
        declared = {phase.phase for phase in self.pipeline}
        if len(declared) != len(self.pipeline):
            raise ValidationError(f"Pack {self.name} declares a phase more than once")
        known = {template.name for template in self.templates}
        for phase in self.pipeline:
            for template_name in phase.templates:
                if template_name not in known:
                    raise ValidationError(
                        f"Pack {self.name} pipeline references unknown template "
                        f"{template_name!r} in phase {phase.phase!r}",
                        detail=f"Known templates: {', '.join(sorted(known)) or 'none'}",
                    )

    def template(self, name: str) -> PackTemplate | None:
        for template in self.templates:
            if template.name == name:
                return template
        return None

    def phase(self, name: str) -> PipelinePhase | None:
        for phase in self.pipeline:
            if phase.phase == name:
                return phase
        return None


@dataclass(frozen=True, slots=True)
class PackSet:
    """The installed packs, in manifest order (last wins on overrides).

    Exposes the union of every pack's additive extension points, so callers never
    need to know how many packs are installed.
    """

    packs: tuple[Pack, ...] = ()

    def _union(self, attribute: str) -> frozenset[str]:
        result: set[str] = set()
        for pack in self.packs:
            result |= getattr(pack, attribute)
        return frozenset(result)

    @property
    def governed_triggers_add(self) -> frozenset[str]:
        return self._union("governed_triggers_add")

    @property
    def reviewed_work_types(self) -> frozenset[str]:
        return self._union("reviewed_work_types")

    @property
    def protected_paths(self) -> frozenset[str]:
        return self._union("protected_paths")

    @property
    def escalation_triggers_add(self) -> frozenset[str]:
        return self._union("escalation_triggers_add")

    @property
    def risk_flag_vocabulary(self) -> frozenset[str]:
        return self._union("risk_flag_vocabulary")

    def find_template(self, name: str) -> tuple[Pack, PackTemplate] | None:
        """Later packs take precedence (manifest order, last wins)."""
        for pack in reversed(self.packs):
            template = pack.template(name)
            if template is not None:
                return pack, template
        return None

    def phase_templates(self, phase: str) -> tuple[str, ...]:
        """Templates for a phase, from the last pack that declares that phase."""
        for pack in reversed(self.packs):
            declared = pack.phase(phase)
            if declared is not None:
                return declared.templates
        return ()

    def phases(self) -> tuple[str, ...]:
        seen: list[str] = []
        for pack in self.packs:
            for phase in pack.pipeline:
                if phase.phase not in seen:
                    seen.append(phase.phase)
        return tuple(seen)
