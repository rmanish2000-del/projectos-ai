# PO-4 — Ecosystem Governance Framework

**The canonical governance model for the whole ecosystem — proportional by design, so routine work is never governed and only genuine stakes are.**

**Status:** PO-4 — proposed canonical governance framework. Design only; no implementation, no code, no repository changes.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Owned by:** ProjectOS (the *Governance* capability, per `PO-3` §7). This document *is* the definition of that capability.
**Inputs / amends alongside:** `PROJECTOS_METHODOLOGY_V2.md`, `PLATFORM_GENOME_V1.md`, `PO-2.5_ARCHITECTURE_CONSISTENCY_REVIEW.md`, `PO-3_AI_WORKSPACE_INTEGRATION_SPEC.md`, `PROJECTOS_V0_1_FOUNDATION_SPEC.md`.
**Establishes:** the six governance domains ProjectOS now defines — Ecosystem, Cross-project, Capability Promotion, Change, Evolution, and Decision Governance.

---

## 0. The governing principle — govern the few, not the many

Governance in this ecosystem exists to control genuine risk with the least possible friction. Its success metric is **not** how much it governs but how little it needs to: a framework that turns ordinary development into governance work has failed, regardless of how thorough it looks.

Three rules make this real and are binding on every domain below:

1. **Proportional by default.** Routine work (FAST / L0–L1) is **ungoverned** — green quality gates are a complete and sufficient basis to proceed, with no review, no record, no approval. Governance engages **only** on an explicit trigger (§8). Absence of a trigger means absence of governance.
2. **Trigger-based, not habitual.** Governance is invoked by enumerable triggers — frozen-architecture, security boundary, breaking public contract, research/risk/legal methodology, genome MAJOR, capability promotion, cross-project impact, irreversible business/legal decision. Nothing else invokes it. "It felt important" is not a trigger.
3. **Batched at milestones.** Governance records and reviews accrue at meaningful milestones (a release freeze, a genome MAJOR, a promotion), never per feature. The framework never asks for an ADR, sign-off pack, or decision log for ordinary implementation.

If any procedure in this document appears to add overhead to routine work, that procedure is misapplied — the trigger gate (§8) is the first check every time.

### 0.1 One authority per governance scope

Mirroring PO-3's single-owner rule: **each governance scope has exactly one governing authority.** No scope is co-governed; overlapping authority is itself an `architecture_conflict` (§10). The six domains partition the governance space without overlap:

```
                     ECOSYSTEM GOVERNANCE  (§1 — the constitution / meta)
                     defines authorities, planes, governance-of-governance
                                    │  contains ▼
        ┌───────────────────────────┼──────────────────────────────┐
        │                           │                              │
  DECISION GOVERNANCE (§2)   CHANGE GOVERNANCE (§3)      CROSS-PROJECT GOV. (§6)
  horizontal: HOW any        single-capability change    the space BETWEEN
  governance decision is     control (propose→verify→    products: portfolio,
  made (rights, escalation,  approve), proportional      shared-capability
  serialization, records)         │  specializes ▼       coordination, one
        │ used by all             │                      critical path
        │                  EVOLUTION GOVERNANCE (§4)
        │                  change control for the SHARED
        │                  CORE (Genome/Platform DNA):
        │                  the 5 ops, versioning, migration
        │                         │  special case ▼
        │                  CAPABILITY PROMOTION GOV. (§5)
        └── informs ───────► local → platform inheritance
```

Relationships (no duplicated authority):
- **Ecosystem Governance** is the container — it defines the authorities the other five use, and governs changes to governance itself.
- **Decision Governance** is horizontal — it defines *how* any governed decision is made and is *used by* the other domains; it does not itself govern any capability.
- **Change Governance** governs a change to *one owned capability*.
- **Evolution Governance** is Change Governance *specialized for the shared inherited core* — stricter because every inheritor is affected.
- **Capability Promotion Governance** is the *specific* evolution flow that moves a capability from product-local to platform-inherited.
- **Cross-project Governance** governs the *space between products* — the portfolio, not any single capability.

Every governance action traces to exactly one of these domains.

---

## 1. Ecosystem Governance (the meta-framework)

**Scope:** the whole ecosystem — the authorities, the planes, and the governance of governance itself.
**Authority:** ProjectOS defines the framework; the Founder is the ultimate approval authority for the reserved decisions (below). AI Workspace enforces; HQ governs the business plane separately.

Ecosystem Governance establishes:

1. **The three planes stay separate under governance** (Methodology §2.1). Engineering governance (the L0–L3 ladder) governs the platform and products. **Business governance** (HQ) governs commerce on its own track and never uses the engineering ladder. **Governance-of-definition** (ProjectOS) governs the rules themselves. A change in one plane never silently governs another.
2. **Governance authorities are those of PO-3** — governance never invents a new owner. The authority to govern a capability's change is the capability's Owner (PO-3 §7), gated by this framework's tiers.
3. **The Founder's reserved authority is narrow and fixed** (Methodology §9, §16): frozen-architecture change, security-boundary change, breaking public contract, genome MAJOR, capability promotion to M4/foundational, legal/regulatory posture, irreversible business bets. Everything else is resolved within the owning realm. This list is the entire founder governance surface — nothing else reaches the Founder.
4. **The Founder Decision Budget is a governed metric.** A rising count of founder governance interruptions is a defect in the framework (Methodology §9); Ecosystem Governance owns the mandate to push resolved decision-classes down into defaults so the budget trends down.
5. **Governance governs itself.** A change to *this framework* (or to any governance rule) is itself GOVERNED / L3, Lane B — the framework is subject to the same discipline it imposes. This is the only self-referential authority, and it is deliberate.

---

## 2. Decision Governance (how any governed decision is made)

**Scope:** the decision-making process used by every other domain — horizontal, not tied to any one capability.
**Authority:** ProjectOS defines the model; the decider is set per decision class.

Decision Governance is the ecosystem's single decision protocol (Methodology §16, kernel escalation model):

1. **Decision classification determines the decider.** Every decision is one class, and the class fixes who decides:

   | Class | Decider | Mechanism |
   |---|---|---|
   | Routine (naming, local design, adapter shape) | Owning agent | Resolved silently from conventions. **Never escalated.** |
   | Reversible product-shaping | Owner, with default | Take the reasonable default; record the assumption; proceed. |
   | Genuine founder (irreversible bet, priority, material trade-off) | Founder | Decision-ready escalation. |
   | Legal / regulatory | Founder | Escalation; business-plane governance record. |
   | Security / risk | Founder | Escalation; GOVERNED record. |
   | Frozen-architecture / breaking-contract | Founder | Escalation; L3. |

2. **Escalate only genuine decisions.** If conventions or a reversible default can resolve it safely, it is not a founder decision (Methodology Principle 10). This is the primary defense of the Founder Decision Budget.
3. **Every escalation is decision-ready.** ≥2 concrete options, each with its consequence, plus a recommendation — the Founder decides in one read (kernel §9.3).
4. **Decisions are serialized.** One founder decision at a time, like the Critical Path — the Founder is never handed a batch to triage.
5. **Decisions are recorded once, and become defaults.** A resolved genuine decision is recorded (audit) and, where it recurs, promoted into a default/convention (Knowledge Lifecycle → Genome knowledge layer) so it never returns as a founder decision. Routine decisions are **not** recorded — recording them would be governance overhead.
6. **The open canonical-operating-model decision (PO-2.5 C-2) is an instance of this protocol:** it is a genuine founder decision, decision-ready, serialized — routed here, not resolved here.

---

## 3. Change Governance (single-capability change control)

**Scope:** a change to one owned capability (not the shared core — that is §4).
**Authority:** the capability's Owner (PO-3 §7) proposes; the change's tier gates.

1. **Only the Owner proposes a change** to a capability. A consumer that needs different behavior raises a change *to the Owner* or uses a provided extension point — never a local override or fork (PO-3 §12 boundaries 2–3).
2. **The tier is set by the capability's Governance lens** (PO-3 §7), not by the changer's discretion:

   | Tier | When | Requirement |
   |---|---|---|
   | **Ungoverned (FAST / L0–L1)** | No trigger present | Green quality gates only. No review, record, or approval. |
   | **Reviewed (REVIEWED / L2)** | Shared-contract, schema, auth/secrets, security-sensitive, higher-impact | One independent delta-only review (PASS / FAIL-blocking-only). |
   | **Governed (GOVERNED / L3)** | Frozen module, breaking public contract, research/risk/legal methodology, security boundary | Full-suite verification + governance record + Founder sign-off. |

3. **Protected surfaces auto-raise the tier and cannot be touched silently:** frozen modules, public contracts, security boundaries, and the Platform Genome. Touching one forces at least REVIEWED, usually GOVERNED.
4. **Conformance, not redefinition** (PO-3 §12 boundary 2): an implementer whose runtime diverges from the definition fixes the implementation; it does not change the definition to match. Definition changes are the Owner's, under this tiering.
5. **Records only at REVIEWED+.** Ungoverned changes leave only their normal commit/evidence trail; no governance artifact is produced for routine work.

---

## 4. Evolution Governance (changes to the shared inherited core)

**Scope:** changes to the Platform Genome / Platform DNA — the shared core every product inherits (Genome v1). This is Change Governance specialized and made stricter because *all inheritors* are affected.
**Authority:** ProjectOS (Genome owner, PO-3) proposes as Lane-B assignments; Founder approves MAJOR and foundational changes.

1. **The five evolution operations are the only ways the core changes** (Genome §12–17): promote, demote, split, merge, retire. Each is executed as a governed Methodology assignment, evidence-triggered, lineage-preserving, consumer-migrating.
2. **Genome versioning sets the governance weight** (Genome §18): **MAJOR** (breaking Platform DNA / an M3–M4 contract) is always **GOVERNED / L3 + Founder sign-off + migration path**; **MINOR** (additive, backward-compatible) is **REVIEWED / L2**; **PATCH** (non-contractual) is FAST.
3. **No inheritor is stranded.** A change that removes or breaks an inherited capability requires a migration path for every consumer *before* it lands (Genome §14, §20) — fail-closed: a change that would strand a consumer is blocked.
4. **Lineage is the governance record.** Every evolution operation appends immutable lineage edges/events (Genome §10–11); this *is* the audit trail — no separate governance document is manufactured.
5. **Autonomous evolution is guarded** (Genome §24): when Platform Intelligence proposes an evolution operation, it is still gated by the Maturity threshold, executed as a governed assignment, and — for MAJOR / foundational — approved by the Founder. Autonomy never bypasses the tier; it only proposes.
6. **Backward-compatibility windows are governed** (Genome §20): deprecation precedes retirement; products migrate one at a time on their own schedule within the window.

---

## 5. Capability Promotion Governance (local → platform)

**Scope:** the specific evolution flow that moves a capability from product-local (Product-owned) to platform-inherited (ProjectOS/Genome-owned). The single sanctioned path to cross-product reuse, and an ownership transfer, so it is governed tightly.
**Authority:** ProjectOS (Genome/Registry owner) governs the promotion; Founder approves promotion to **M4/foundational**.

1. **Eligibility is evidence-gated, never asserted** (Genome §13, Maturity Engine): a capability is promotable only at **M2+** with demonstrated cross-product reuse demand (surfaced by Discovery / an improvement signal). Maturity supplies the threshold; the Genome performs the placement (PO-3 separation of readiness vs. placement).
2. **Generalize before promoting.** The capability's contract must be domain-neutral and its dependencies clean; any domain assumption is first moved to Domain DNA (Genome §13; resolves PO-2.5 O-2's class). A capability carrying domain logic cannot be promoted.
3. **Promotion is a governed ownership transfer.** Moving a capability from Product to platform changes what every product may inherit → **GOVERNED / L3, Lane B**, with a `promoted-from` lineage edge recorded; promotion to **M4/foundational** additionally requires **Founder sign-off** (breaking it later is a breaking public contract).
4. **Expression stays opt-in.** Promotion makes a capability *available* to all; it never forces any product to express it (Genome §4).
5. **Demotion is the governed reverse** (Genome §14): withdrawal from the inherited layer requires consumer migration paths first and is GOVERNED; nothing is stranded, and lineage is preserved (retire ≠ erase).
6. **No sideways promotion.** A capability is promoted *up* into the Genome, never copied product-to-product (Genome §18); a sideways copy is a governance violation and a review-blocking issue.

---

## 6. Cross-project Governance (the space between products)

**Scope:** governance of the portfolio — interactions, priorities, and shared-capability coordination *across* sibling products. Not any single capability (that is §3) and not the shared core's internals (that is §4).
**Authority:** ProjectOS defines the model; the Founder sets portfolio priority and the Critical Path; product owners coordinate shared-capability impact.

1. **One Critical Path across the portfolio** (Methodology §3.1). Multiple products/lanes run in parallel, but exactly one lane holds the Founder's attention at a time; background lanes run only self-verifying work and never compete for it. Promotion of a lane to Critical Path is a lightweight founder decision or a scheduled rotation — never automatic contention.
2. **Shared-capability changes consult all consumers.** A change to an inherited capability (governed under §4) treats every expressing product as **Consulted** (PO-3 RACI) — never as a co-owner, and never blocked-by-committee. Consultation informs the Owner's decision; it does not transfer authority.
3. **No sideways coupling between products.** Products are siblings; they inherit vertically from the Genome and never depend directly on each other (Genome §21). A proposed product-to-product dependency is refused and redirected to promotion (§5). This is the primary structural control against portfolio entanglement.
4. **Cross-project dependency is expressed as shared inheritance, not integration.** When two products need the same capability, they both express the same inherited gene at a compatible genome version (Genome §19) — governed by compatibility rules, not by a bespoke integration.
5. **Portfolio priority is a reserved founder decision.** Which product is on the Critical Path, and the relative priority of products, is a business-plane decision the Founder owns (Decision Governance §2); the AI team never reprioritizes the portfolio on its own authority.
6. **Domain rules stay in Domain DNA, per product.** Cross-project governance enforces that domain vocabulary and triggers live in each product's Domain DNA, never at the shared/workspace level (Genome §8; directly closes PO-2.5 O-2).

---

## 7. Governance Authority Matrix

Who governs each domain, who approves, and the default tier. One authority per scope (§0.1).

| Governance domain | Defining authority | Approval authority (when triggered) | Default tier | Records |
|---|---|---|---|---|
| Ecosystem (§1) | ProjectOS | Founder (framework changes) | GOVERNED / L3 | At framework amendment |
| Decision (§2) | ProjectOS | Per decision class | n/a (protocol) | Genuine decisions only |
| Change (§3) | Capability Owner (PO-3) | Owner; Founder for L3 triggers | Ungoverned unless triggered | REVIEWED+ only |
| Evolution (§4) | ProjectOS (Genome owner) | Founder (MAJOR / foundational) | Per version bump | Lineage (automatic) |
| Promotion (§5) | ProjectOS (Genome/Registry) | Founder (M4/foundational) | GOVERNED / L3 | Lineage (`promoted-from`) |
| Cross-project (§6) | ProjectOS; Founder (priority) | Founder (portfolio priority) | Lightweight | Critical-path pointer |

## 8. When governance applies — the trigger gate (proportionality)

The single gate every change passes through. **No trigger → ungoverned.** This table is the operational heart of "govern the few."

| Trigger present? | Tier | What happens |
|---|---|---|
| None (routine feature, fix, refactor, adapter, docs) | **Ungoverned (FAST / L0–L1)** | Green gates → proceed. No review, record, or approval. |
| Shared contract · schema · auth/authz/secrets · security-sensitive · higher-impact | **REVIEWED / L2** | One independent delta-only review. |
| Frozen module · breaking public contract · research/risk/statistical/legal methodology · security boundary · Genome MAJOR · capability promotion · irreversible business/legal decision | **GOVERNED / L3** | Full verification + governance record + Founder sign-off. |

The trigger list is closed and identical to the kernel governed-trigger set plus its pack/domain additions and the genome/promotion triggers — governance introduces **no new trigger vocabulary**, so it cannot silently expand its own reach.

## 9. Governance records & audit

1. **Records are proportional.** Ungoverned changes produce only their normal commit/evidence trail. REVIEWED changes produce a PASS/FAIL verdict. GOVERNED changes produce a governance record + Founder approval. Evolution produces lineage automatically. **No governance artifact is ever produced for routine work.**
2. **Evidence is the record.** Governance reuses the kernel's evidence and hash-chained audit (Foundation Spec §8) and the Genome's lineage — it does not create a parallel bureaucracy.
3. **Batched at milestones.** Governance summaries (freeze reports, promotion records) are produced at milestones — a release, a genome MAJOR — never per feature (Methodology governance policy).
4. **Decisions are auditable and re-derivable.** Every governed decision records its options, choice, actor, and consequence, and links to the audit chain — so the ecosystem can always answer "what was decided, by whom, on what basis."

## 10. Escalation model (unified)

All governance escalations use the kernel's closed trigger set (Foundation Spec §9.1) plus the ownership tie-breaker:

- `founder_decision`, `security_risk`, `legal_risk`, `architecture_conflict`, `blocker`, `next_undetermined`.
- **`architecture_conflict` is the ownership/authority tie-breaker:** if two parties claim authority over one capability or governance scope, it escalates and is resolved by the Founder **against PO-3 and this framework** — the specifications are the tie-breaker, not negotiation.
- Escalations are decision-ready and serialized (§2). Resolution is recorded and, where recurring, promoted to a default.

---

## APPENDIX A — L2 VERIFICATION RECORD

Independent, delta-only, verdict-oriented review against the assignment and the framework's own principles.

| Check | Verdict | Basis |
|---|---|---|
| All six governance domains defined | **PASS** | §1 Ecosystem · §2 Decision · §3 Change · §4 Evolution · §5 Promotion · §6 Cross-project. |
| Domains are non-overlapping (one authority per scope) | **PASS** | §0.1 containment map: Ecosystem contains; Decision is horizontal (governs no capability); Change=one capability; Evolution=shared core; Promotion=local→platform; Cross-project=between products. Every action traces to exactly one domain. |
| Proportional — routine work stays ungoverned | **PASS** | §0 governing principle; §8 trigger gate ("no trigger → ungoverned"); §3 tier table; §9 "no artifact for routine work." Aligns with the founder's anti-over-governance policy. |
| Minimizes founder decision fatigue | **PASS** | Reserved narrow founder surface (§1.3); escalate-only-genuine + serialization + decision-as-default (§2); Founder Decision Budget as a governed metric (§1.4). |
| Single authority per governance scope; no conflicting authority | **PASS** | §0.1, §7 authority matrix (one defining authority per domain); `architecture_conflict` tie-breaker resolved against the specs (§10). |
| Consistent with prior specs (no new owners/triggers) | **PASS** | Authorities are PO-3's owners; triggers are the kernel set + genome/promotion; verification ladder is Methodology §6; evolution/lineage is Genome v1. Governance adds no new owner and no new trigger vocabulary (§8). |
| ProjectOS-owned; implementation-independent | **PASS** | Framework is the ProjectOS *Governance* capability (PO-3 §7); no code, no repo changes, design only. |
| Implementation-ready | **PASS** | Concrete domains, authority matrix, trigger gate, tier tables, records model, unified escalation — assignable without further design while remaining implementation-independent. |

**Reviewer verdict: PASS.** No blocking issues. The six domains are complete, non-overlapping, single-authority, and — critically — proportional: the framework governs only triggered high-stakes work and leaves routine development ungoverned, consistent with the founder's operating model.

---

## APPENDIX B — RELATIONSHIP TO PRIOR SPECS

- **Methodology v2** — supplies the verification levels (L0–L3), workflow modes, decision framework, plane separation, and Founder Decision Budget that this framework operationalizes as governance. Governance is the *enforcement* view of the methodology.
- **Genome v1** — supplies the evolution operations, versioning, compatibility, migration, and lineage that Evolution and Promotion Governance govern. Governance adds *authority and tiering* over Genome mechanics; it does not redesign them.
- **PO-2.5** — this framework closes O-2 (domain triggers → Domain DNA, §6.6) and routes C-2 (canonical operating-model decision) through Decision Governance (§2.6) without pre-empting the Founder.
- **PO-3** — supplies the owners who hold governance authority; this framework never invents an owner. `architecture_conflict` is resolved against PO-3 (§10).
- **Kernel (Foundation Spec)** — supplies the evidence model, audit chain, and closed escalation-trigger set governance reuses (§9–10); governance manufactures no parallel bureaucracy.

---

*End of PO-4 Ecosystem Governance Framework. Design only — no implementation, no code, no repository changes. Governance is proportional: it engages only on explicit triggers and leaves routine work ungoverned. Future implementation is assigned separately.*
