"""Workflow-risk classification (spec section 7.3).

Classification is computed, never chosen. The rules are evaluated in a fixed order
and the first rule that fires is recorded in the audit log alongside the result, so
there are no silent judgment calls.

Packs may raise a classification and never lower it: the classifier takes the
maximum of every rule that fires rather than the last one.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch

from projectos.domain.assignment import Assignment
from projectos.domain.enums import WorkflowMode
from projectos.domain.manifest import Manifest
from projectos.domain.pack import PackSet


@dataclass(frozen=True, slots=True)
class Classification:
    mode: WorkflowMode
    rule: str

    def describe(self) -> str:
        return f"{self.mode.value.upper()} (rule: {self.rule})"


def classify(
    assignment: Assignment,
    manifest: Manifest,
    packs: PackSet,
    *,
    touched_paths: tuple[str, ...] = (),
) -> Classification:
    """Classify an assignment deterministically and monotonically.

    Every rule is evaluated and the **maximum** severity wins. Returning on the
    first rule that fired was a defect: a pack marking a work type as REVIEWED
    could pull an assignment below a GOVERNED project default, or below a level the
    owner had raised it to. Spec 7.3 permits packs to raise a classification and
    never to lower it, so resolution must be a maximum rather than a first match.

    `touched_paths` are the repository paths the assignment is expected to modify;
    they are matched against pack-declared protected globs.
    """
    default = manifest.workflow.default_mode

    # The project default is the floor. Nothing below it can be reached, which is
    # what makes the result monotonic.
    candidates: list[Classification] = [
        Classification(default, f"project default ({default.value})")
    ]

    governed_triggers = manifest.workflow.governed_triggers | packs.governed_triggers_add
    fired = set(assignment.risk_flags) & governed_triggers
    if fired:
        candidates.append(
            Classification(
                WorkflowMode.GOVERNED,
                f"risk_flags ∩ governed_triggers = {{{', '.join(sorted(fired))}}}",
            )
        )

    if assignment.work_type.value in packs.reviewed_work_types:
        candidates.append(
            Classification(
                WorkflowMode.REVIEWED,
                f"pack marks work_type '{assignment.work_type.value}' as high-risk",
            )
        )

    for path in touched_paths:
        for glob in sorted(packs.protected_paths):
            if _matches(path, glob):
                candidates.append(
                    Classification(
                        WorkflowMode.REVIEWED,
                        f"path '{path}' matches pack protected glob '{glob}'",
                    )
                )

    # An owner may raise an assignment above the default when authoring it.
    if assignment.workflow_mode.rank > default.rank:
        candidates.append(
            Classification(
                assignment.workflow_mode,
                f"owner raised classification to {assignment.workflow_mode.value}",
            )
        )

    # Highest severity wins. Ties break on the order rules were appended above, so
    # the result is deterministic for a given state and pack set.
    return max(candidates, key=lambda candidate: candidate.mode.rank)


def _matches(path: str, glob: str) -> bool:
    """Glob match with `**` semantics.

    fnmatch treats `*` as crossing separators already, so `src/kernel/**` is
    normalised to `src/kernel/*` to mean "anything beneath this prefix".
    """
    normalised = glob.replace("/**", "/*")
    return fnmatch(path, normalised) or fnmatch(path, glob)
