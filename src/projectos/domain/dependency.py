"""Assignment dependency graph (spec sections 4 and 6, `depends_on`).

Answers exactly two questions the lifecycle needs: is this assignment's dependency
set satisfied, and does the graph contain a cycle. Cycles are a validation error
rather than an escalation — a cyclic graph is a malformed repository, not a founder
decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.domain.assignment import Assignment
from projectos.domain.enums import Status
from projectos.domain.errors import ValidationError
from projectos.domain.ids import AssignmentId


@dataclass(frozen=True, slots=True)
class DependencyReport:
    assignment_id: AssignmentId
    unsatisfied: tuple[AssignmentId, ...]
    missing: tuple[AssignmentId, ...]

    @property
    def satisfied(self) -> bool:
        return not self.unsatisfied and not self.missing

    def describe(self) -> str:
        parts: list[str] = []
        if self.missing:
            parts.append(f"unknown: {', '.join(str(i) for i in self.missing)}")
        if self.unsatisfied:
            parts.append(f"not closed: {', '.join(str(i) for i in self.unsatisfied)}")
        return "; ".join(parts) if parts else "all dependencies closed"


class DependencyGraph:
    """An immutable view over the assignment registry.

    Constructed per operation from the current registry; it caches nothing across
    calls, so it can never serve a stale answer.
    """

    __slots__ = ("_by_id",)

    def __init__(self, assignments: tuple[Assignment, ...]) -> None:
        by_id: dict[AssignmentId, Assignment] = {}
        for assignment in assignments:
            if assignment.id in by_id:
                raise ValidationError(f"Duplicate assignment id {assignment.id}")
            by_id[assignment.id] = assignment
        self._by_id = by_id
        self._detect_cycle()

    def get(self, assignment_id: AssignmentId) -> Assignment | None:
        return self._by_id.get(assignment_id)

    def evaluate(self, assignment: Assignment) -> DependencyReport:
        unsatisfied: list[AssignmentId] = []
        missing: list[AssignmentId] = []
        for dependency_id in assignment.depends_on:
            dependency = self._by_id.get(dependency_id)
            if dependency is None:
                missing.append(dependency_id)
            elif dependency.status is not Status.CLOSED:
                unsatisfied.append(dependency_id)
        return DependencyReport(assignment.id, tuple(unsatisfied), tuple(missing))

    def dependents_of(self, assignment_id: AssignmentId) -> tuple[AssignmentId, ...]:
        return tuple(
            sorted(
                candidate.id
                for candidate in self._by_id.values()
                if assignment_id in candidate.depends_on
            )
        )

    def topological_order(self) -> tuple[AssignmentId, ...]:
        """Deterministic topological order; ties broken by identifier."""
        indegree = {aid: 0 for aid in self._by_id}
        for assignment in self._by_id.values():
            for dependency_id in assignment.depends_on:
                if dependency_id in indegree:
                    indegree[assignment.id] += 1

        ready = sorted(aid for aid, degree in indegree.items() if degree == 0)
        order: list[AssignmentId] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for dependent in self.dependents_of(current):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
            ready.sort()
        return tuple(order)

    def _detect_cycle(self) -> None:
        if len(self.topological_order()) != len(self._by_id):
            resolved = set(self.topological_order())
            cyclic = sorted(str(aid) for aid in self._by_id if aid not in resolved)
            raise ValidationError(
                "Assignment dependency graph contains a cycle",
                detail=f"Assignments involved: {', '.join(cyclic)}",
            )
