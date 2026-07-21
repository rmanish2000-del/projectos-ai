"""Assignment lifecycle service — the kernel's single write path.

Every state change in ProjectOS goes through `_transition`, which enforces the
transition table, writes the audit entry, and persists the assignment as one unit.
Nothing else in the codebase may change an assignment's status, which is what makes
the audit log complete rather than merely well-intentioned.

Invariants enforced here:
  INV-1  at most one assignment occupies the active slot
  INV-2  exactly one owner and one executor, both validated against the manifest
  INV-3  no VERIFIED without every criterion passing
  INV-4  every error path blocks; none defaults to success
  INV-6  a broken audit chain halts the kernel before any write
  INV-7  next-assignment generation produces exactly one READY assignment
"""

from __future__ import annotations

from dataclasses import dataclass

from projectos.application.integrity import IntegrityReport, verify_state
from projectos.application.ports import (
    AssignmentRepository,
    AuditLog,
    Clock,
    EscalationRepository,
    IdentityProvider,
    ManifestRepository,
    PackRepository,
    RepositoryAdapter,
    TemplateBinder,
)
from projectos.application.verification import (
    VerificationEngine,
    reject_code_evidence_on_document_work,
)
from projectos.domain import next_engine, routing
from projectos.domain.approvals import ApprovalStatus, decision_matches_event, is_authorized
from projectos.domain.approvals import evaluate as evaluate_approvals
from projectos.domain.assignment import Assignment, TransitionRecord
from projectos.domain.audit import AuditEntry, seal_next
from projectos.domain.classification import Classification, classify
from projectos.domain.dependency import DependencyGraph
from projectos.domain.digest import immutable_digest
from projectos.domain.enums import (
    Actor,
    Decision,
    EscalationState,
    EscalationTrigger,
    Event,
    FounderDecision,
    Role,
    Status,
)
from projectos.domain.errors import (
    EscalationRequired,
    InvariantViolation,
    NotFoundError,
    RuleFailure,
    ValidationError,
)
from projectos.domain.escalation import Escalation, EscalationOption, Resolution
from projectos.domain.evidence import ApprovalRecord, CompletionClaim, VerificationReport
from projectos.domain.ids import AssignmentId, EscalationId
from projectos.domain.manifest import Manifest
from projectos.domain.pack import PackSet

#: Statuses that count as "in flight", most-advanced first. VERIFIED and REJECTED
#: are included: they are still the current work even though they have left the
#: INV-1 execution slot.
IN_FLIGHT_ORDER: tuple[Status, ...] = (
    Status.ACTIVE,
    Status.EVIDENCE_SUBMITTED,
    Status.VERIFYING,
    Status.VERIFIED,
    Status.REJECTED,
)


@dataclass(frozen=True, slots=True)
class NextResult:
    """Outcome of next-assignment generation."""

    assignment: Assignment | None
    decision: next_engine.NextDecision
    escalation: Escalation | None = None


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    report: VerificationReport
    assignment: Assignment


class LifecycleService:
    """Coordinates the state machine, audit log, and repositories.

    Constructed with explicit collaborators (no global state, no module-level
    singletons) so a test can substitute any of them.
    """

    def __init__(
        self,
        *,
        manifests: ManifestRepository,
        packs: PackRepository,
        assignments: AssignmentRepository,
        escalations: EscalationRepository,
        audit: AuditLog,
        adapter: RepositoryAdapter,
        templates: TemplateBinder,
        clock: Clock,
        identity: IdentityProvider,
    ) -> None:
        self._manifests = manifests
        self._pack_repository = packs
        self._assignments = assignments
        self._escalations = escalations
        self._audit = audit
        self._adapter = adapter
        self._templates = templates
        self._clock = clock
        self._identity = identity

    # -- context ---------------------------------------------------------------

    @property
    def manifest(self) -> Manifest:
        return self._manifests.load()

    @property
    def packs(self) -> PackSet:
        return self._pack_repository.load_all(self.manifest)

    def graph(self) -> DependencyGraph:
        return DependencyGraph(self._assignments.list_all())

    def _guard(self) -> None:
        """INV-6: refuse to operate on tampered state.

        Checks the chain *and* its agreement with the assignment files, so a
        truncated or deleted log is caught rather than passing as intact.
        """
        self.verify_integrity()

    def verify_integrity(self) -> IntegrityReport:
        return verify_state(self._audit.read_all(), self._assignments.list_all())

    def _assert_active_slot_free(self, assignment_id: AssignmentId) -> None:
        """INV-1, enforced on every path that can occupy the execution slot.

        Previously only `start` checked this, so `resume` and a founder's
        proceed-resolution could each produce a second active assignment.
        """
        occupant = self._active_occupant()
        if occupant is None or occupant.id == assignment_id:
            return
        raise InvariantViolation(
            f"Cannot activate {assignment_id}: {occupant.id} is already "
            f"{occupant.status.value}",
            detail=(
                "INV-1 permits at most one active assignment. Complete, block, or "
                f"cancel {occupant.id} first."
            ),
        )

    def _actor_role(self, declared: Actor) -> Actor:
        """Founder identity outranks a declared role: the founder may act as owner."""
        if declared is Actor.OWNER and self.manifest.is_founder(self._identity.current()):
            return Actor.FOUNDER
        return declared

    # -- the single write path -------------------------------------------------

    def _transition(
        self,
        assignment: Assignment,
        event: Event,
        actor: Actor,
        *,
        reason: str | None = None,
        evidence_refs: tuple[str, ...] = (),
        data: dict[str, object] | None = None,
    ) -> Assignment:
        from projectos.domain import state_machine

        prior = self._prior_status(assignment)
        target = state_machine.resolve(
            assignment.status, event, actor, prior_status=prior
        )

        entry = seal_next(
            AuditEntry(
                sequence=0,
                timestamp=self._clock.now_iso(),
                event=event.value,
                actor=self._identity.current(),
                assignment_id=str(assignment.id),
                from_status=assignment.status.value,
                to_status=target.value,
                reason=reason,
                evidence_refs=evidence_refs,
                data=dict(data or {}),
            ),
            self._audit.last(),
        )
        written = self._audit.append(entry)

        record = TransitionRecord(
            event=event,
            from_status=assignment.status,
            to_status=target,
            actor=self._identity.current(),
            timestamp=written.timestamp,
            audit_ref=written.hash,
            reason=reason,
        )
        updated = assignment.with_status(target, record)
        self._assignments.save(updated)

        # The active pointer is derived from status, never set independently, so it
        # cannot disagree with the assignment files.
        if updated.occupies_active_slot:
            self._assignments.set_active(updated.id)
        elif assignment.occupies_active_slot:
            self._assignments.set_active(None)

        return updated

    @staticmethod
    def _prior_status(assignment: Assignment) -> Status | None:
        """The status held immediately before entering ESCALATED."""
        for record in reversed(assignment.history):
            if record.to_status is Status.ESCALATED:
                return record.from_status
        return None

    # -- operations ------------------------------------------------------------

    def create(self, assignment: Assignment) -> Assignment:
        """Register a DRAFT assignment after validating routing and ownership."""
        self._guard()
        manifest = self.manifest

        if not manifest.is_owner(assignment.owner):
            raise ValidationError(
                f"{assignment.id}: owner {assignment.owner!r} is not listed in the manifest",
                detail="INV-2 requires exactly one owner, drawn from manifest.owners.",
            )
        routing.validate_routing(assignment, manifest.agents)

        unknown_flags = set(assignment.risk_flags) - (
            manifest.workflow.governed_triggers | self.packs.risk_flag_vocabulary
        )
        if unknown_flags:
            raise ValidationError(
                f"{assignment.id}: unknown risk flags {', '.join(sorted(unknown_flags))}",
                detail="Risk flags must come from kernel triggers or a pack's vocabulary.",
            )

        self._assignments.save(assignment)
        self._append_event(
            "assignment_created",
            assignment_id=str(assignment.id),
            data={"title": assignment.title, "work_type": assignment.work_type.value},
        )
        return assignment

    def classify_assignment(self, assignment_id: AssignmentId) -> tuple[Assignment, Classification]:
        """DRAFT -> READY, recording the classification rule that fired."""
        self._guard()
        assignment = self._assignments.get(assignment_id)

        if assignment.status is not Status.DRAFT:
            raise InvariantViolation(
                f"{assignment_id} is {assignment.status.value}, not draft",
                detail="Only DRAFT assignments are classified (decision D-5).",
            )

        classification = classify(assignment, self.manifest, self.packs)
        classified = assignment.with_classification(classification.mode, classification.rule)
        self._assignments.save(classified)

        # `classify_ok` is the only event out of DRAFT toward READY, and the spec
        # gates it on "deps CLOSED, no block". When either gate is shut the
        # assignment stays in DRAFT rather than moving sideways: DRAFT has no
        # `block` or `escalate` edge, and inventing one would widen the machine.
        report = self.graph().evaluate(classified)
        if not report.satisfied:
            self._append_event(
                "classify_deferred",
                assignment_id=str(assignment_id),
                data={"reason": f"dependencies unsatisfied — {report.describe()}"},
            )
            return classified, classification

        blocker = self._blocking_escalation(assignment_id)
        if blocker is not None:
            self._append_event(
                "classify_deferred",
                assignment_id=str(assignment_id),
                escalation_id=str(blocker.id),
                data={"reason": f"open escalation {blocker.id} blocks this assignment"},
            )
            return classified, classification

        # Bind the immutable-field digest into the (hash-chained) classify_ok entry.
        # From here the assignment is immutable except for `state` (§6.1); any later
        # hand-edit to scope or classification will not match this digest and halts
        # the kernel on the next load.
        ready = self._transition(
            classified,
            Event.CLASSIFY_OK,
            Actor.KERNEL,
            reason=classification.describe(),
            data={
                "mode": classification.mode.value,
                "rule": classification.rule,
                "immutable_digest": immutable_digest(classified),
            },
        )
        return ready, classification

    def start(self, assignment_id: AssignmentId) -> tuple[Assignment, routing.AssignmentBriefing]:
        """READY -> ACTIVE. Enforces INV-1."""
        self._guard()
        assignment = self._assignments.get(assignment_id)
        self._assert_active_slot_free(assignment_id)

        started = self._transition(assignment, Event.START, Actor.KERNEL)
        return started, routing.brief(started)

    def submit(self, assignment_id: AssignmentId, claim: CompletionClaim) -> Assignment:
        """ACTIVE -> EVIDENCE_SUBMITTED. A claim is never evidence (spec 4.3)."""
        self._guard()
        assignment = self._assignments.get(assignment_id)
        reject_code_evidence_on_document_work(assignment, claim)

        return self._transition(
            assignment,
            Event.SUBMIT,
            Actor.EXECUTOR,
            reason=claim.summary,
            evidence_refs=tuple(ref.reference for ref in claim.evidence),
        )

    def verify(
        self, assignment_id: AssignmentId, claim: CompletionClaim | None = None
    ) -> VerificationOutcome:
        """ACTIVE -> EVIDENCE_SUBMITTED -> VERIFYING -> VERIFIED | REJECTED.

        Verifying an ACTIVE assignment ingests the claim first, so the caller never
        has to sequence `submit` and `verify` itself. An absent claim stages an
        empty one, which verifies exactly as harshly — the repository decides.
        """
        self._guard()
        assignment = self._assignments.get(assignment_id)

        if assignment.status is Status.ACTIVE:
            assignment = self.submit(
                assignment_id,
                claim
                or CompletionClaim(
                    assignment_id=str(assignment_id), summary="completion claimed"
                ),
            )

        verifying = self._transition(assignment, Event.VERIFY_START, Actor.KERNEL)
        engine = VerificationEngine(
            adapter=self._adapter, audit=self._audit, manifest=self.manifest
        )

        try:
            report = engine.verify(verifying)
        except Exception as exc:
            # VERIFYING has exactly one other exit, and letting an unexpected
            # exception escape here would strand the assignment there forever with
            # no legal transition out. `verifier_error` is the state machine's
            # designated fail-closed edge; emit it rather than propagating.
            rejected = self._transition(
                verifying,
                Event.VERIFIER_ERROR,
                Actor.KERNEL,
                reason=f"verifier error ({type(exc).__name__}): {exc}",
            )
            reason = (
                f"The verifier failed before reaching a verdict: {exc}. "
                "Fix the acceptance criterion or the adapter configuration, then retry."
            )
            rejected = rejected.with_rejection_reasons((reason,))
            self._assignments.save(rejected)
            raise RuleFailure(
                f"{assignment_id} REJECTED: the verifier errored before producing a verdict",
                detail=reason,
            ) from exc

        if report.passed:
            verified = self._transition(
                verifying,
                Event.ALL_CRITERIA_PASS,
                Actor.KERNEL,
                reason=f"{len(report.results)} of {len(report.results)} criteria passed",
            )
            # Reasons from an earlier rejection no longer apply; persist the clearing
            # so they cannot resurface in `status` or a later briefing.
            verified = verified.cleared_of_rejections()
            self._assignments.save(verified)
            return VerificationOutcome(report, verified)

        reasons = tuple(f"{r.criterion_id}: {r.reason}" for r in report.failures)
        rejected = self._transition(
            verifying,
            Event.ANY_CRITERION_FAIL,
            Actor.KERNEL,
            reason=f"{len(report.failures)} of {len(report.results)} criteria failed",
        )
        rejected = rejected.with_rejection_reasons(reasons)
        self._assignments.save(rejected)
        return VerificationOutcome(report, rejected)

    def approval_status(self, assignment: Assignment) -> ApprovalStatus:
        return evaluate_approvals(
            assignment.workflow_mode,
            assignment.work_type,
            self._authorized_approvals(assignment),
        )

    def _authorized_approvals(self, assignment: Assignment) -> tuple[ApprovalRecord, ...]:
        """Recorded approvals that survive §8.6.2 authority validation.

        The CLOSE gate must apply the same read-time authority check as verification:
        a hand-appended approval attributed to an unauthorized identity, or with an
        inconsistent event/decision pairing, must not count toward closing an
        assignment. The raw projection returns every record; the kernel decides
        which ones count.
        """
        manifest = self.manifest
        return tuple(
            record
            for record in self._audit.approvals_for(assignment.id)
            if decision_matches_event(record.decision, record.event)
            and is_authorized(
                manifest,
                role=record.role,
                actor=record.actor,
                assignment_owner=assignment.owner,
            )
        )

    def approve(self, assignment_id: AssignmentId, role: Role) -> tuple[Assignment, ApprovalStatus]:
        """Record an approval; CLOSE automatically once the mode's roles are satisfied."""
        self._guard()
        assignment = self._assignments.get(assignment_id)
        actor_id = self._identity.current()

        if assignment.status is not Status.VERIFIED:
            raise InvariantViolation(
                f"{assignment_id} is {assignment.status.value}; only VERIFIED assignments "
                "accept approvals",
                detail="Run `projectos verify` first — approval never substitutes for evidence.",
            )
        self._validate_authority(assignment, role)

        self._append_event(
            "approval_recorded",
            assignment_id=str(assignment_id),
            data={"role": role.value, "decision": Decision.APPROVED.value, "actor": actor_id},
        )

        status = self.approval_status(assignment)
        if not status.complete:
            return assignment, status

        closed = self._transition(
            assignment,
            Event.APPROVALS_COMPLETE,
            self._actor_role(Actor.OWNER) if role is Role.OWNER else Actor(role.value),
            reason=f"approvals complete for {assignment.workflow_mode.value} mode",
        )
        return closed, status

    def _validate_authority(self, assignment: Assignment, role: Role) -> None:
        """Check that the acting identity may speak in `role` for this assignment.

        Shared by `approve` and `attest`, and using the *same* `is_authorized`
        predicate the verification read path uses (spec 8.6.2), so an entry the
        kernel would record and an entry appended by hand are held to identical
        rules. Attestation previously validated nothing (R-8); a reviewer was only
        checked for independence, which left the reviewer role unbounded and
        therefore forgeable (R-9). Both are closed by requiring an authorized
        identity here and re-checking on read.
        """
        actor_id = self._identity.current()
        manifest = self.manifest
        if is_authorized(
            manifest, role=role, actor=actor_id, assignment_owner=assignment.owner
        ):
            return

        # Rejected. Produce a role-specific message; the decision above is the single
        # source of truth, this only explains it.
        if role is Role.FOUNDER:
            raise InvariantViolation(
                f"{actor_id!r} is not the founder ({manifest.founder.id})",
                detail="Founder decisions are validated against manifest.project.founder.id.",
            )
        if role is Role.OWNER:
            if not manifest.is_owner(actor_id):
                raise InvariantViolation(
                    f"{actor_id!r} is not listed in manifest.owners",
                    detail="An owner decision must come from an identity the project knows.",
                )
            raise InvariantViolation(
                f"{actor_id!r} does not own {assignment.id} ({assignment.owner})",
                detail="An owner decision must come from the assignment's owner or the founder.",
            )
        # Reviewer.
        if not manifest.is_owner(actor_id):
            raise InvariantViolation(
                f"{actor_id!r} is not a manifest owner and cannot review {assignment.id}",
                detail=(
                    "Spec 8.6.2 binds reviewer authority to manifest.owners so an appended "
                    "reviewer approval cannot be forged from an unknown identity."
                ),
            )
        raise InvariantViolation(
            f"{actor_id!r} owns {assignment.id} and cannot review it",
            detail="A reviewer must be independent of the executor (spec 4.1).",
        )

    def attest(self, assignment_id: AssignmentId, role: Role) -> None:
        """Record a human attestation for facts outside the repository (spec 8.2)."""
        self._guard()
        assignment = self._assignments.get(assignment_id)
        self._validate_authority(assignment, role)
        self._append_event(
            "attestation_recorded",
            assignment_id=str(assignment_id),
            data={
                "role": role.value,
                "decision": Decision.ATTESTED.value,
                "actor": self._identity.current(),
            },
        )

    def reject(self, assignment_id: AssignmentId, reason: str) -> Assignment:
        """VERIFIED -> REJECTED on human review."""
        self._guard()
        assignment = self._assignments.get(assignment_id)
        is_founder = self.manifest.is_founder(self._identity.current())
        actor = Actor.FOUNDER if is_founder else Actor.REVIEWER
        rejected = self._transition(assignment, Event.REVIEW_REJECT, actor, reason=reason)
        rejected = rejected.with_rejection_reasons((reason,))
        self._assignments.save(rejected)
        return rejected

    def resume(self, assignment_id: AssignmentId) -> tuple[Assignment, routing.AssignmentBriefing]:
        """REJECTED -> ACTIVE, carrying the rejection reasons into the new briefing."""
        self._guard()
        assignment = self._assignments.get(assignment_id)
        self._assert_active_slot_free(assignment_id)
        resumed = self._transition(
            assignment,
            Event.RESUME,
            Actor.KERNEL,
            reason="; ".join(assignment.rejection_reasons) or None,
        )
        return resumed, routing.brief(resumed)

    def block(self, assignment_id: AssignmentId, reason: str) -> Assignment:
        self._guard()
        assignment = self._assignments.get(assignment_id)
        actor = Actor.KERNEL if assignment.status is Status.READY else Actor.OWNER
        return self._transition(assignment, Event.BLOCK, actor, reason=reason)

    def unblock(self, assignment_id: AssignmentId) -> Assignment:
        """BLOCKED -> READY, but only once the dependencies genuinely are closed."""
        self._guard()
        assignment = self._assignments.get(assignment_id)
        report = self.graph().evaluate(assignment)
        if not report.satisfied:
            raise InvariantViolation(
                f"Cannot unblock {assignment_id}: {report.describe()}",
                detail="Dependencies must be CLOSED before an assignment returns to READY.",
            )
        return self._transition(
            assignment, Event.UNBLOCK, Actor.KERNEL, reason="dependencies restored"
        )

    def cancel(self, assignment_id: AssignmentId, reason: str) -> Assignment:
        self._guard()
        assignment = self._assignments.get(assignment_id)
        actor = Actor.FOUNDER if self.manifest.is_founder(self._identity.current()) else Actor.OWNER
        return self._transition(assignment, Event.CANCEL, actor, reason=reason)

    # -- escalation ------------------------------------------------------------

    def escalate(
        self,
        *,
        trigger: EscalationTrigger,
        summary: str,
        options: tuple[EscalationOption, ...],
        assignment_id: AssignmentId | None = None,
        recommendation: str | None = None,
    ) -> Escalation:
        """Create a decision-ready escalation and freeze the assignment if scoped to one."""
        self._guard()

        # Validate the freeze before writing anything. Persisting the escalation
        # first meant an illegal transition left an orphan open escalation that
        # blocked the project while the assignment stayed unfrozen — a failed
        # operation must not leave a trace.
        freeze_actor = self._plan_freeze(assignment_id)

        escalation = Escalation(
            id=self._escalations.next_id(),
            trigger=trigger,
            summary=summary,
            options=options,
            assignment_id=assignment_id,
            recommendation=recommendation,
            created_at=self._clock.now_iso(),
        )
        self._escalations.save(escalation)
        self._append_event(
            "escalation_opened",
            assignment_id=str(assignment_id) if assignment_id else None,
            escalation_id=str(escalation.id),
            data={"trigger": trigger.value, "summary": summary},
        )

        if assignment_id is not None and freeze_actor is not None:
            self._transition(
                self._assignments.get(assignment_id),
                Event.ESCALATE,
                freeze_actor,
                reason=f"{escalation.id}: {summary}",
            )
        return escalation

    def _plan_freeze(self, assignment_id: AssignmentId | None) -> Actor | None:
        """Resolve which actor may freeze this assignment, or raise.

        Returns None when there is nothing to freeze: a project-level escalation,
        or an assignment already in ESCALATED.
        """
        if assignment_id is None:
            return None

        from projectos.domain import state_machine

        assignment = self._assignments.get(assignment_id)
        if assignment.status is Status.ESCALATED:
            return None

        actor = Actor.KERNEL if assignment.status is Status.READY else Actor.OWNER
        # Raises IllegalTransition here, before any write, if the assignment is in a
        # status with no `escalate` edge.
        state_machine.resolve(assignment.status, Event.ESCALATE, actor)
        return actor

    def resolve(
        self, escalation_id: EscalationId, decision: str, outcome: FounderDecision
    ) -> tuple[Escalation, Assignment | None]:
        """Founder-only. Resolution re-drives the state machine deterministically."""
        self._guard()
        actor_id = self._identity.current()
        if not self.manifest.is_founder(actor_id):
            raise InvariantViolation(
                f"{actor_id!r} is not the founder ({self.manifest.founder.id})",
                detail="Only the founder resolves escalations (spec 9.2).",
            )

        escalation = self._escalations.get(escalation_id)
        if not escalation.is_open:
            raise ValidationError(f"{escalation_id} is already resolved")
        if escalation.option(decision) is None and outcome is FounderDecision.PROCEED:
            known = ", ".join(option.id for option in escalation.options)
            raise ValidationError(
                f"{decision!r} is not one of {escalation_id}'s options",
                detail=f"Options: {known}",
            )

        resolved = escalation.resolved(
            Resolution(
                decision=decision,
                decided_by=actor_id,
                decided_at=self._clock.now_iso(),
                outcome=outcome,
            )
        )
        self._escalations.save(resolved)
        self._append_event(
            "escalation_resolved",
            assignment_id=str(escalation.assignment_id) if escalation.assignment_id else None,
            escalation_id=str(escalation_id),
            data={"decision": decision, "outcome": outcome.value},
        )

        if escalation.assignment_id is None:
            return resolved, None

        assignment = self._assignments.get(escalation.assignment_id)
        if assignment.status is not Status.ESCALATED:
            return resolved, assignment

        event = {
            FounderDecision.PROCEED: Event.FOUNDER_RESOLVE_PROCEED,
            FounderDecision.CANCEL: Event.FOUNDER_RESOLVE_CANCEL,
            FounderDecision.RESCOPE: Event.FOUNDER_RESOLVE_RESCOPE,
        }[outcome]
        if outcome is FounderDecision.PROCEED:
            # Proceeding restores the pre-escalation status, which may be an
            # active-slot state. Another assignment may have been started in the
            # meantime, so INV-1 has to be re-checked here too.
            prior = self._prior_status(assignment)
            if prior is not None and prior.is_active_slot:
                self._assert_active_slot_free(assignment.id)
        updated = self._transition(
            assignment, event, Actor.FOUNDER, reason=f"{escalation_id}: {decision}"
        )
        return resolved, updated

    def open_escalations(self) -> tuple[Escalation, ...]:
        return tuple(e for e in self._escalations.list_all() if e.state is EscalationState.OPEN)

    def _blocking_escalation(self, assignment_id: AssignmentId | None) -> Escalation | None:
        for escalation in self.open_escalations():
            if escalation.is_project_level or escalation.assignment_id == assignment_id:
                return escalation
        return None

    # -- next-assignment generation -------------------------------------------

    def generate_next(self) -> NextResult:
        """Produce exactly one successor assignment, or a NEXT_UNDETERMINED escalation.

        INV-7: this method returns at most one assignment. There is no code path here
        that creates two.
        """
        self._guard()

        blocker = self._blocking_escalation(None)
        if blocker is not None and blocker.is_project_level:
            raise EscalationRequired(
                f"Project-level escalation {blocker.id} blocks next-assignment generation",
                detail=f"{blocker.summary}\n  Resolve with: projectos founder resolve {blocker.id}",
            )

        assignments = self._assignments.list_all()

        pending = self._first_pending(assignments)
        if pending is not None:
            return NextResult(
                pending,
                next_engine.NextDecision(
                    pending.origin_template, "existing", "an unfinished assignment already exists"
                ),
            )

        # An empty project bootstraps from the head of the pack pipeline; there is
        # no predecessor to read a `next` block from.
        closed = [a for a in assignments if a.status is Status.CLOSED]
        latest = max(closed, key=lambda a: a.id) if closed else None
        if latest is None and assignments:
            raise ValidationError(
                "No closed assignment to generate a successor from",
                detail=(
                    "Every existing assignment is cancelled. Author the next one "
                    "explicitly, or extend the pack pipeline."
                ),
            )

        decision = next_engine.decide(latest, assignments, self.packs)
        if not decision.determined:
            after = f"after {latest.id} closed" if latest is not None else "for this project"
            escalation = self.escalate(
                trigger=EscalationTrigger.NEXT_UNDETERMINED,
                summary=f"No successor could be determined {after}. {decision.reason}",
                options=(
                    EscalationOption(
                        "O1",
                        "Extend the pack pipeline with the next phase",
                        "Generation resumes automatically; no assignment is lost.",
                    ),
                    EscalationOption(
                        "O2",
                        "Author the next assignment explicitly",
                        "Immediate progress; the pipeline stays incomplete for next time.",
                    ),
                    EscalationOption(
                        "O3",
                        "Declare the project phase complete",
                        "No further assignments are generated until a new phase is declared.",
                    ),
                ),
                recommendation="O1",
            )
            return NextResult(None, decision, escalation)

        assert decision.template is not None
        generated = self._materialise(decision.template, latest)
        return NextResult(generated, decision)

    def _first_pending(self, assignments: tuple[Assignment, ...]) -> Assignment | None:
        """The assignment that already claims the pipeline, if any (INV-7)."""
        ordering = (
            Status.ACTIVE,
            Status.EVIDENCE_SUBMITTED,
            Status.VERIFYING,
            Status.VERIFIED,
            Status.REJECTED,
            Status.READY,
            Status.DRAFT,
        )
        for status in ordering:
            matches = sorted((a for a in assignments if a.status is status), key=lambda a: a.id)
            if matches:
                return matches[0]
        return None

    def _materialise(self, template_name: str, predecessor: Assignment | None) -> Assignment:
        """Turn a pack template into a DRAFT assignment, then classify it to READY."""
        found = self.packs.find_template(template_name)
        if found is None:
            raise ValidationError(
                f"Template {template_name!r} is not provided by any installed pack",
                detail="Check the pack pipeline and the templates directory.",
            )
        _, template = found

        draft = self._templates.bind(
            template,
            assignment_id=self._assignments.next_id(),
            manifest=self.manifest,
            predecessor=predecessor,
        )
        self.create(draft)
        classified, _ = self.classify_assignment(draft.id)
        return classified

    # -- reads -----------------------------------------------------------------

    def _active_occupant(self) -> Assignment | None:
        for assignment in self._assignments.list_all():
            if assignment.occupies_active_slot:
                return assignment
        return None

    def active(self) -> Assignment | None:
        """The assignment occupying the INV-1 execution slot, if any."""
        return self._active_occupant()

    def current(self) -> Assignment | None:
        """The assignment the founder is working on right now.

        Broader than :meth:`active`: an assignment awaiting approval (VERIFIED) or
        awaiting a fix (REJECTED) is still the current one even though it no longer
        occupies the INV-1 execution slot. Keeping the two concepts apart is what
        lets `complete` and `verify` default to the obvious target without
        weakening INV-1.
        """
        for status in IN_FLIGHT_ORDER:
            matches = sorted(
                (a for a in self._assignments.list_all() if a.status is status),
                key=lambda a: a.id,
            )
            if matches:
                return matches[0]
        return None

    def require_current(self) -> Assignment:
        assignment = self.current()
        if assignment is None:
            raise NotFoundError(
                "No assignment in flight",
                detail="Run `projectos next` to activate the next ready assignment.",
            )
        return assignment

    def blocked(self) -> tuple[Assignment, ...]:
        return tuple(
            a
            for a in self._assignments.list_all()
            if a.status in (Status.BLOCKED, Status.ESCALATED)
        )

    def _append_event(
        self,
        event: str,
        *,
        assignment_id: str | None = None,
        escalation_id: str | None = None,
        data: dict[str, object] | None = None,
    ) -> AuditEntry:
        entry = seal_next(
            AuditEntry(
                sequence=0,
                timestamp=self._clock.now_iso(),
                event=event,
                actor=self._identity.current(),
                assignment_id=assignment_id,
                escalation_id=escalation_id,
                data=dict(data or {}),
            ),
            self._audit.last(),
        )
        return self._audit.append(entry)


__all__ = ["LifecycleService", "NextResult", "VerificationOutcome"]
