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
    """Classify an assignment deterministically.

    `touched_paths` are the repository paths the assignment is expected to modify;
    they are matched against pack-declared protected globs.
    """
    governed_triggers = manifest.workflow.governed_triggers | packs.governed_triggers_add
    flags = set(assignment.risk_flags)

    fired = flags & governed_triggers
    if fired:
        return Classification(
            WorkflowMode.GOVERNED,
            f"risk_flags ∩ governed_triggers = {{{', '.join(sorted(fired))}}}",
        )

    # REVIEWED rules, in the order given by the spec table.
    if assignment.work_type.value in packs.reviewed_work_types:
        return Classification(
            WorkflowMode.REVIEWED,
            f"pack marks work_type '{assignment.work_type.value}' as high-risk",
        )

    for path in touched_paths:
        for glob in sorted(packs.protected_paths):
            if _matches(path, glob):
                return Classification(
                    WorkflowMode.REVIEWED,
                    f"path '{path}' matches pack protected glob '{glob}'",
                )

    # Owner may manually raise: an assignment authored above the default keeps that
    # level rather than being lowered back to the project default.
    default = manifest.workflow.default_mode
    if assignment.workflow_mode.rank > default.rank:
        return Classification(
            assignment.workflow_mode,
            f"owner raised classification to {assignment.workflow_mode.value}",
        )

    return Classification(default, f"default ({default.value}) — no raising rule fired")


def _matches(path: str, glob: str) -> bool:
    """Glob match with `**` semantics.

    fnmatch treats `*` as crossing separators already, so `src/kernel/**` is
    normalised to `src/kernel/*` to mean "anything beneath this prefix".
    """
    normalised = glob.replace("/**", "/*")
    return fnmatch(path, normalised) or fnmatch(path, glob)
