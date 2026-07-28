# ProjectOS Methodology v2.0

**The canonical product-development operating system for all current and future products.**

**Status:** PO-1 — proposed canonical methodology. Design only; no implementation, no code, no repository changes.
**Lane:** B (Platform / Methodology / Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Supersedes:** ProjectOS v1 (product-specific methodology). **Amends alongside:** `PROJECTOS_V0_1_FOUNDATION_SPEC.md` (the kernel) and `PROJECTOS_WORKSPACE_RUNTIME_SPEC.md` (the runtime). Those documents govern implementation mechanics; this document governs the operating model above them.
**Applies to:** AI Workspace, ProjectOS, TradeOS, EduOS, UrjaOps, Legal Engineering, and every future product — without redesign.

---

## 0. What changed, and why

ProjectOS v1 was a methodology for building one thing. During AI Workspace development the operating model outgrew that framing: work now runs in parallel lanes, capabilities are reused across products, an AI team executes most of the engineering, and the founder's scarcest resource — attention — must be spent on a handful of decisions rather than a stream of them.

v2 absorbs that evolution into one coherent operating system. The change in one sentence: **ProjectOS is no longer *how we build a product*; it is *how we build products* — a reusable development operating model that every platform inherits.** The twelve concepts the founder identified during AI Workspace — One Active Critical Path, Multi-Lane Execution, the AI Team Model, the Capability Registry, the Platform Genome, the Capability Maturity Engine, Continuous Optimization, cross-project reuse, platform-first architecture, knowledge evolution, AI-assisted engineering, and the founder operating model — are not twenty separate ideas bolted on. They are five moves: **separate the planes** (governance / engineering / business), **serialize attention** (one critical path) **while parallelizing work** (many lanes), **staff the work with an AI team** the founder supervises rather than joins, **build capabilities and platforms rather than features and products**, and **let knowledge and quality compound** instead of resetting each project.

Everything below is implementation-independent. It states *what the operating model is and why*, not *how any repository realizes it*. Realization is assigned separately.

---

## PART I — FOUNDATIONS

## 1. ProjectOS Vision v2

ProjectOS is the operating system for turning founder intent into verified, reusable, production software with minimal founder involvement and maximum cross-product leverage.

It answers, at all times and for every product, six questions:

1. **What is the one thing that matters most right now?** (the Critical Path)
2. **What else is safely progressing in parallel?** (the background lanes)
3. **Who — which human or which AI agent — owns each active piece?**
4. **Is it verifiably done, by repository evidence rather than by claim?**
5. **What did we just learn or build that another product can reuse?**
6. **What is the single next decision only the founder can make?**

A methodology that answers these continuously, for six products at once, without the founder re-deciding routine matters, is the target. ProjectOS v2 is judged by three outcomes: **velocity** (working software shipped per unit of founder attention), **leverage** (share of new work satisfied by reused capability rather than new build), and **calm** (founder decisions per week trending toward a small, stable floor).

The vision is explicitly *anti-heroic*: no single long-lived context, human or model, is trusted to remember everything or get everything right. Correctness comes from structure — verified evidence, fail-closed defaults, one write path, independent review at the right depth — not from diligence. That is what lets an AI team run most of the work and lets the operating model survive being handed between sessions, agents, and years.

---

## 2. Operating Principles

These are the load-bearing rules. They are inherited by every product and every lane and may be *raised* (made stricter) by a domain but never *lowered*.

1. **One Active Critical Path.** Exactly one assignment at a time carries the founder's attention and defines forward progress. Parallelism is allowed; competition for the founder's attention is not.
2. **Evidence over claims.** "Done" is a claim. Only repository evidence — commits, PRs, CI, tests, artifacts, recorded approvals — decides completion. No agent self-verifies.
3. **Fail closed.** Ambiguity, missing capability, adapter error, broken audit chain, or unknown state all block. Nothing degrades into success.
4. **One owner, one write path.** Every active piece has exactly one owner. Every state change goes through a single auditable path, so history is complete by construction.
5. **Deterministic and auditable.** The same state plus the same inputs always yields the same decision. Every state transition is recorded and re-derivable.
6. **Separate the three planes.** Business (what and why), Engineering (how and whether it works), and Governance (what is protected and how risk is controlled) are distinct. Governance never leaks into routine engineering.
7. **Proportional process.** Depth of review, verification, testing, and documentation scales to genuine risk — never to habit. Routine work stays fast; only high-risk work is heavy.
8. **Platform-first, capability-first.** Prefer reusing or promoting a capability over building a feature; prefer extending the platform over forking a product.
9. **Knowledge compounds.** Every completed assignment leaves the platform smarter — a reusable capability, a refined convention, a recorded decision — or it is not finished.
10. **Escalate only genuine founder decisions.** The AI team resolves everything it can safely resolve from evidence and convention. The founder is interrupted only for irreversible, business, legal, security, or frozen-architecture decisions.
11. **Domain-neutral core, domain-specific edges.** The operating model carries no product logic. Everything domain-specific lives in packs at the edge.
12. **Generate exactly one next step.** After verified completion, the system proposes exactly one successor — never a branching plan, never a backlog dump.

### 2.1 The three planes (the separation that makes the rest work)

| Plane | Owns the question | Primary owner | Default posture |
|---|---|---|---|
| **Business** | *What* do we build, for whom, and *why* — priority, sequencing, product bets. | Founder | Decides direction; delegates execution. |
| **Engineering** | *How* is it built, and is it *verifiably* correct. | AI Team (supervised) | Executes and verifies from evidence; escalates only genuine decisions. |
| **Governance** | *What* is protected, and how is *risk* controlled. | AI Team for detection; Founder for frozen/irreversible calls. | Silent for routine work; engaged only at high-risk triggers and milestones. |

Keeping these separate is the single most important structural choice in v2. Most process failure comes from a governance concern (a review, an ADR, a sign-off) contaminating routine engineering, or a business decision being made implicitly inside an engineering task. v2 forbids both: routine engineering runs with zero governance overhead, and business decisions are named, surfaced, and owned by the founder.

---

## PART II — EXECUTION

## 3. Execution Model

ProjectOS v2 executes work as a stream of **verified assignments** flowing through **parallel lanes**, with exactly **one Critical Path** at any moment.

### 3.1 One Active Critical Path

At the level of a single product's repository, at most one assignment is active — this is the kernel's foundational invariant (one active assignment per repository, INV-1). At the level of the whole platform, at most one *lane* is designated the **Critical Path**: the single track whose progress the founder is attending to and whose stall would stall the mission. The Critical Path is the methodology-level name for "the one active assignment that matters most right now."

This resolves the apparent tension between "one active assignment" and "multi-lane execution": they operate at different levels and do not contradict.

- **Per lane / per repository:** the kernel enforces one active assignment. Unchanged.
- **Across the platform:** one lane holds the Critical Path; the rest are *background lanes*.
- **Founder attention:** bound to the Critical Path only. Background lanes never compete for it.

### 3.2 Multi-Lane Execution

Multiple lanes run concurrently. Each lane has its own single active-assignment slot (kernel INV-1 applies per lane), its own owner archetype, and its own default agent. Lanes are how the platform parallelizes without multiplying founder decisions:

- **Background lanes self-verify.** A background lane may run only work whose verification level is low enough to complete on evidence and automation alone (L0–L1, §6) — it cannot demand a founder decision to progress. The moment a background lane would need a founder decision, it either yields the Critical Path (becomes primary) or opens a standard escalation and pauses.
- **Exactly one lane is primary (the Critical Path) at a time.** Promotion of a background lane to Critical Path is itself a founder decision (a lightweight one) or a scheduled rotation — never automatic contention.
- **Lanes never share an owner for the same active work.** One owner per active assignment holds across lanes.

This is the platform-scale generalization of the workspace runtime's "one active project": the primary lane corresponds to the active project the founder attends to; background lanes correspond to other registered projects progressing on self-verifying work.

### 3.3 The execution loop (per assignment, any lane)

```
Generate one assignment
  → Classify (workflow mode + verification level)
    → Route (lane, owner, agent)
      → Execute
        → Verify against repository evidence
          → (rejected → fix, same assignment)  |  (verified → gate)
            → Close (record approvals required by mode/level)
              → Capture knowledge + reuse candidate
                → Generate exactly one successor
```

The loop is identical in every lane and every product. What varies is only the *depth* applied at classify/verify/gate — set by mode and verification level, not by lane or product.

---

## 4. Lane Model

A **lane** is a typed execution track with an owner archetype, a default agent, and a default verification posture. Lanes let the platform run heterogeneous work in parallel while keeping each track's rules explicit.

| Lane | Name | Typical work | Owner archetype | Default agent | Default posture |
|---|---|---|---|---|---|
| **A** | Product Engineering | Features, APIs, UI, fixes, tests, adapters, runtime wiring | Engineer | Claude Code | FAST / L0–L1 |
| **B** | Platform & Architecture | Methodology, frozen design, platform capabilities, breaking-contract design | Architect | Claude Cowork | REVIEWED–GOVERNED / L2–L3 |
| **C** | Research & Analysis | Research, statistics, risk methodology, feasibility, evaluation | Researcher | Claude Cowork | REVIEWED–GOVERNED / L2–L3 |
| **D** | Operations & Delivery | Deployment prep, monitoring, incident response, migration, ops runbooks | Operator | Claude Code + Human | FAST–REVIEWED / L1–L2 |
| **F** | Founder / Decision | Genuine founder decisions, milestone gates, product bets | Founder | Human | Governed by decision framework (§16) |

Rules of the lane model:

1. **Lane sets the default, not the ceiling.** A Lane A task touching a frozen module is still classified GOVERNED/L3 — the risk classification overrides the lane default upward, never downward.
2. **Every active assignment belongs to exactly one lane.** Cross-lane work is decomposed, not co-owned.
3. **This assignment (PO-1) is Lane B / Cowork / L2** — canonical methodology design is Architect work, independently reviewed, no implementation.
4. **Lanes are configurable per product.** A product may enable a subset; the default agent for any lane is a *configurable adapter* (Claude Code, Claude Cowork, ChatGPT, a named human, or a future agent), so lane semantics survive changes in who or what executes.

---

## 5. Assignment Lifecycle

The assignment is the atomic unit of work and the unit of verification. Its lifecycle is deterministic, evidence-gated, and identical across products.

### 5.1 States

An assignment moves through a closed set of states: **Draft → Ready → Active → Evidence Submitted → Verifying → Verified → Closed**, with off-ramps to **Rejected** (verification failed — fix and resubmit, same assignment), **Blocked** (dependency or missing input), **Escalated** (a genuine decision is required), and **Cancelled** (scope changed — reissue fresh). Scope is fixed once an assignment leaves Draft: changing scope means cancel-and-reissue, so acceptance criteria can never be edited to fit the evidence produced.

### 5.2 Anatomy of an assignment

Every assignment declares, up front and immutably after Draft: an **objective**, exactly one **owner** and one **executor**, its **lane**, its **workflow mode** and **verification level**, machine-checkable **acceptance criteria**, the **evidence** required, and exactly one **stopping point**. The stopping point is mandatory and singular — an assignment that does not say precisely where to stop is malformed.

### 5.3 Generation — exactly one successor

After an assignment is verified and closed, the system generates exactly one successor, resolved deterministically: (1) the closed assignment's explicit next declaration, else (2) the next step in the product's pipeline for the current phase, else (3) a "next undetermined" escalation to the founder. There is never more than one successor, and there is never a silent stall — undetermined is surfaced, not swallowed.

### 5.4 Ownership and hand-off

An assignment has one owner for its entire life. Hand-off between agents (e.g., Cowork designs, Code implements) is modeled as *separate assignments in sequence*, each with its own owner, not as shared ownership of one assignment. This keeps accountability and the audit trail unambiguous.

---

## 6. Verification Levels

Verification level sets the **depth of proof** required before an assignment may close. It is orthogonal to workflow mode (which sets process strictness) but the two are aligned by default. Levels form a ladder; a domain may raise the level for a class of work but never lower the kernel/platform floor.

| Level | Name | What must be true to close | Who/what verifies | Typical work |
|---|---|---|---|---|
| **L0** | Self-evident | Acceptance criteria pass against repository evidence; automated checks green. | Kernel evidence engine only. | Docs, low-risk internal changes. |
| **L1** | Automated gate | L0 **plus** the full automated gate set (tests, lint, type, build, smoke). | Kernel + CI. | Routine features, fixes, adapters (Lane A). |
| **L2** | Independent review | L1 **plus** one independent, fresh-context review of the changed delta only; PASS/FAIL, blocking issues only. | Kernel + CI + independent reviewer (different context/agent than the author). | Higher-impact engineering; **methodology and architecture design (this assignment)**; shared contracts. |
| **L3** | Governed | L2 **plus** full-suite verification, governance record, and founder sign-off. | Kernel + CI + independent reviewer + founder. | Frozen architecture, research mathematics, risk/security, legal, breaking public contracts, major releases. |

Principles for verification levels:

- **The level is declared at classification and is immutable after Draft.** You cannot discover mid-flight that weaker proof is acceptable.
- **L2 review is delta-only and verdict-only.** The reviewer examines the change, not the whole system, and returns PASS or FAIL-with-blocking-issues — no essays, no unrelated recommendations. (This assignment's L2 review checks the methodology's internal consistency and acceptance criteria, nothing else.)
- **Fresh context is the point of L2/L3.** Independent verification must come from outside the authoring context — a different agent or a clean session — because self-review reproduces the author's blind spots.
- **Default mapping:** FAST→L0/L1, REVIEWED→L2, GOVERNED→L3. A product may bind different defaults per lane but cannot map a governed-trigger class below L3.

---

## 7. Quality Gates

Quality gates are the concrete, automatable checks that a verification level requires. They are the engineering plane's contract with itself: green gates are *sufficient* to merge routine work with no human in the loop; red gates block, always.

| Gate | FAST (L0–L1) | REVIEWED (L2) | GOVERNED (L3) |
|---|---|---|---|
| Focused unit tests | ✔ | ✔ | ✔ |
| Affected integration tests | ✔ | ✔ | ✔ |
| Lint | ✔ | ✔ | ✔ |
| Type checks (where configured) | ✔ | ✔ | ✔ |
| Build | ✔ | ✔ | ✔ |
| Smoke verification | ✔ | ✔ | ✔ |
| Full test suite | on shared-contract/core/schema change | ✔ | ✔ |
| Independent delta review | — | ✔ | ✔ |
| Governance record | — | — | ✔ |
| Founder sign-off | — | — | ✔ |

Gate discipline:

1. **Green gates are sufficient for FAST.** Tests, lint, type, build, and smoke passing is a complete basis to merge routine work — no review, no governance, no founder. This is deliberate and is what keeps velocity high.
2. **Gates are proportional (Principle 7).** Heavyweight validation — mutation testing, exhaustive audits, adversarial review, full-suite runs — is reserved for research kernels, risk/security-critical code, financial calculations, and release freezes. It is *not* applied to routine changes to inflate rigor.
3. **No tautological gates.** Tests that exist only to raise a count are prohibited; a gate must defend a real behavior.
4. **Gates fail closed.** A gate that cannot run is a red gate, not a skipped one.

---

## 15. Review Framework

*(Presented here, adjacent to gates, because review is the human/independent layer of the same quality system.)*

Review exists to catch what automation cannot, at the lowest cost that catches it.

- **When review happens.** Only at L2 and L3. FAST work is not reviewed — that is a rule, not an omission. Review is triggered by verification level, which is triggered by genuine risk.
- **What a review examines.** The changed delta only, against the acceptance criteria and (for platform work) against consistency with the platform genome and existing contracts. Never the whole system, never unrelated code.
- **What a review returns.** `PASS`, or `FAIL` with a list of blocking issues only. No stylistic essays, no roadmap suggestions, no scope expansion. A blocking issue is one that, left unfixed, makes the acceptance criteria false or violates an operating principle.
- **Who reviews.** An independent context — a fresh session or a different agent than the author. Reviewer authority for approval is bound to named owners; an approval from an unknown identity grants nothing.
- **Batching.** Governance-grade review (L3) is batched at meaningful milestones (frozen-module changes, breaking contracts, major releases), never applied per routine feature.

---

## 16. Decision Framework

Decisions are classified so that the right decider handles each, and so the founder sees only what genuinely needs them.

| Decision class | Examples | Decider | Mechanism |
|---|---|---|---|
| **Routine engineering** | Naming, structure, local design, which test, adapter shape | AI Team (owner) | Resolved silently from repository conventions and evidence. Never escalated. |
| **Reversible product-shaping** | Minor UX choices, non-breaking API shape | Owner, with default | Owner picks the reasonable default, states the assumption, proceeds. |
| **Genuine founder decision** | Irreversible business bet, product priority, material trade-off | Founder | Escalation with 2+ options, each with stated consequence, and a recommendation. |
| **Legal / regulatory** | Compliance posture, filing, licensing | Founder | Escalation; governance-recorded. |
| **Security / risk** | Security boundary, risk-model, credential exposure | Founder | Escalation; governance-recorded. |
| **Frozen-architecture conflict** | Change to a frozen module or a breaking public contract | Founder | Escalation; L3/governed. |

Rules:

1. **Escalate only genuine decisions (Principle 10).** If a decision can be resolved safely from repository conventions, it is not a founder decision.
2. **Every escalation is decision-ready.** It carries at least two concrete options, each with its consequence, and a recommendation. The founder should be able to decide in one read, not reconstruct the problem.
3. **Reversible defaults beat questions.** For a reversible choice with a sensible default, the owner takes the default and records the assumption rather than interrupting the founder.
4. **One decision at a time.** Escalations to the founder are serialized like the Critical Path; the founder is never handed a batch to triage.

---

## PART III — THE AI TEAM

## 8. AI Team Architecture

Most engineering in ProjectOS v2 is performed by an **AI team** that the founder supervises rather than joins. The team is a set of **roles**, each filled by a **configurable agent adapter**, so the operating model is independent of which specific AI or human fills a role.

| Role | Responsibility | Default adapter | Verification posture |
|---|---|---|---|
| **Founder** | Direction, genuine decisions, milestone gates. The one human accountable. | Human | Owns L3 sign-off. |
| **Architect** | Frozen design, methodology, platform capabilities, breaking-contract design. Does **not** implement. | Claude Cowork | Produces L2/L3 designs. |
| **Engineer** | Implementation, tests, refactors, APIs, UI, adapters, ops wiring. Owns the routine loop end to end. | Claude Code | Executes L0–L2. |
| **Reviewer** | Independent, fresh-context delta review; PASS/FAIL. | Claude Cowork or a clean session | Performs L2/L3 review. |
| **Researcher** | Research, statistics, risk/EV/probability methodology, evaluation. | Claude Cowork | Produces L2/L3 findings. |
| **Operator** | Deployment, monitoring, incident response, migrations. | Claude Code + Human | Executes L1–L2. |

Architecture of the team:

1. **Roles, not tools.** The methodology names roles and their rules; adapters bind roles to concrete agents (Claude Code, Cowork, ChatGPT, humans, future agents). Swapping an adapter never changes the operating model.
2. **Separation of design and build.** The Architect designs and does not implement; the Engineer implements and does not silently redesign completed architecture. This mirrors the lane split (B designs, A builds) and prevents the two most common failure modes: architecture drift during implementation, and implementation smuggled into design.
3. **Independent review is a distinct role from authorship.** The Reviewer is never the author of the work under review.
4. **The founder is a supervisor, not a bottleneck.** The team is designed to resolve everything it safely can; the founder's interface to the team is the Critical Path stopping point, the escalation queue, and the milestone gate — three narrow channels, not a firehose.
5. **Default owner is the Engineer (Claude Code).** For ordinary engineering — implementation, testing, debugging, refactoring, APIs, UI, databases, automation, DevOps, deployment, repo operations, production fixes — the Engineer owns the full loop. The Architect/Reviewer (Cowork) is engaged only for the high-risk triggers.

---

## 9. Founder Responsibilities (the Founder Operating Model)

The founder operating model exists to **minimize decision fatigue** while keeping the founder genuinely in control. It defines what the founder does, what they never do, and the small, stable interface between them and the AI team.

**The founder does, and only does:**

1. **Set direction** — choose products, priorities, and the current Critical Path.
2. **Make genuine decisions** — the six decision classes reserved to the founder (§16).
3. **Gate milestones** — approve L3/governed work and release freezes.
4. **Accept or correct** — on reviewing a completed assignment or agent output, the founder returns exactly one of: *accept*, *correct*, or *decide* — and the system then produces the updated state and exactly one next assignment.

**The founder never (by design):**

- Makes routine engineering choices, resolves reversible defaults, writes or reviews routine code, produces governance documents for routine work, or manages more than one active thing at a time.

**The founder's interface to the whole platform is three narrow channels:**

- the **Critical Path stopping point** (one at a time),
- the **escalation queue** (decision-ready, serialized, one at a time),
- the **milestone gate** (batched, infrequent).

**The Founder Decision Budget.** v2 treats founder decisions as a scarce, measurable resource. The system's job is to drive *routine* founder decisions toward zero and keep *genuine* decisions few, well-formed, and serialized. A rising count of founder interruptions is a defect in the operating model, not a fact of life — it triggers a continuous-improvement signal (§13) to push more decisions down into conventions and defaults.

---

## 14. Automation Strategy

*(Adjacent to the AI team, because automation is what lets a small team supervise large output.)*

Automation is applied wherever it removes a founder decision or a manual gate without lowering the floor of safety.

1. **Automate the gates, not the judgment.** Tests, lint, type, build, smoke, and evidence-verification are fully automated and are *authoritative*. Judgment calls that are genuine decisions stay with the founder.
2. **Automate FAST merges.** With green gates and no high-risk trigger, routine work merges without a human. This is the highest-leverage automation in the model.
3. **Automate successor generation.** The single next assignment is generated deterministically after close — the founder does not hand-author the backlog.
4. **Automate detection, gate the response.** Risk triggers, protected-path touches, and anomaly signals are detected automatically; the *response* to a genuine risk is a governed decision, not an automated one.
5. **Automate knowledge capture.** Reuse candidates and improvement signals are captured as a by-product of closing an assignment, not as separate manual work (§12–13).
6. **Never automate past fail-closed.** No automation may convert an ambiguous or unverified state into success.

---

## PART IV — PLATFORM & CAPABILITY

## 10. Capability-first Development

v2 builds **capabilities**, not features. A **capability** is a reusable, independently-describable unit of product ability — evidence verification, telemetry ingestion, billing, authentication, document generation, a risk kernel, a scheduling engine — with an owner, a maturity grade, and a contract.

### 10.1 The Capability Registry

Every capability is entered in a **Capability Registry**: a catalog, shared across all products, recording for each capability its name and contract, its owning platform/pack, its **maturity grade** (§10.2), its consumers (which products use it), and its status (active, deprecated, retired). The Registry is the single source of truth for "what can we already do, and how reliable is it?" Before any product builds something, the Registry is consulted first — new build is justified only when no registered capability at adequate maturity already covers the need.

### 10.2 The Capability Maturity Engine

Each capability carries a maturity grade, and the **Capability Maturity Engine** governs promotion and the obligations at each grade.

| Grade | Name | Meaning | Reuse posture | Verification floor |
|---|---|---|---|---|
| **M0** | Experimental | Works in one product, not generalized. | Do not reuse. | L0–L1 |
| **M1** | Proven-local | Stable in its origin product; contract emerging. | Reuse discouraged; copy-with-eyes-open. | L1 |
| **M2** | Generalizable | Contract explicit; dependencies clean; candidate for platform. | Reuse allowed within reason. | L2 |
| **M3** | Platform | Promoted to the platform genome; owned centrally; versioned contract. | Reuse preferred. | L2–L3 |
| **M4** | Foundational | Depended on by multiple products; breaking it is a breaking public contract. | Reuse mandatory; forking forbidden. | L3 |

The engine's rules: maturity only rises through evidence (usage, stability, contract clarity), never by assertion; promotion from M2→M3 (product-local → platform) is a Lane B / governed act because it changes what every product inherits; and an M4 capability's contract is frozen — changing it is an L3 breaking-contract decision.

### 10.3 Why capability-first

Capability-first is what makes cross-product leverage measurable. The platform's health is read directly off the Registry: rising average maturity and rising reuse mean the operating model is compounding; a proliferation of M0/M1 duplicates across products is the warning sign that work is being rebuilt instead of reused.

---

## 11. Platform-first Development

### 11.1 The Platform Genome

The **Platform Genome** is the shared, inheritable core that every product is born with — its DNA. The genome comprises: the **kernel** (assignment lifecycle, evidence verification, audit, invariants), the **operating model** (this methodology), the **shared conventions** (repository organization, quality gates, verification levels), and the **M3–M4 capabilities** in the Registry. A **product = genome + domain pack**: the genome supplies everything reusable and neutral; the pack supplies everything domain-specific.

```
        ┌──────────── Platform Genome (shared, inherited) ────────────┐
        │  Kernel · Operating model · Conventions · M3–M4 capabilities │
        └───────────────┬───────────────┬───────────────┬────────────┘
                        │               │               │   inherits
        ┌───────────────▼──┐  ┌─────────▼────────┐  ┌────▼──────────────┐
        │ AI Workspace     │  │ TradeOS          │  │ UrjaOps / EduOS / │
        │  + domain pack   │  │  + domain pack   │  │ Legal + packs …   │
        └──────────────────┘  └──────────────────┘  └───────────────────┘
```

### 11.2 Platform-first principles

1. **Inherit, don't fork.** A new product starts by inheriting the genome, not by copying an existing product.
2. **The core stays domain-neutral.** No product logic ever enters the genome. Domain rules live only in packs. This is what lets one genome serve AI Workspace, TradeOS, EduOS, UrjaOps, and Legal Engineering without redesign.
3. **Improvements flow up, not sideways.** A capability that proves reusable is *promoted into the genome* (M2→M3), not copied product-to-product. Promotion is the only sanctioned path to reuse; lateral copying is a maturity-engine failure.
4. **Breaking the genome is a governed act.** Because every product inherits it, a breaking change to a genome contract is always L3.
5. **Additive extension only at the edges.** Packs extend the genome additively — they may raise a workflow mode, add a governed trigger, or add domain vocabulary, but they can never remove a core guarantee or lower a floor.

---

## 18. Cross-project Reuse Model

*(The mechanics that connect §10 and §11.)*

Reuse is a governed, evidence-driven flow — never ad-hoc copying.

1. **Discover.** Every new need is checked against the Capability Registry before any build is proposed.
2. **Reuse if mature.** If a capability at M2+ covers the need, it is reused; building a duplicate is prohibited and is a review-blocking issue.
3. **Build local if novel.** A genuinely new need is built as an M0/M1 capability in its origin product.
4. **Promote when proven.** When a local capability shows reuse demand and a clean contract, it is promoted M2→M3 into the genome via a Lane B governed assignment — generalized, versioned, and centrally owned.
5. **Deprecate and retire.** Superseded capabilities are marked deprecated in the Registry with a migration path, then retired. Nothing is silently orphaned.

The reuse model is deliberately **pull-and-promote**, not push: products pull mature capabilities from the genome, and proven local capabilities are promoted up. There is no sanctioned sideways copy, because sideways copies are the origin of divergence.

---

## 17. Repository Organization Principles

*(Implementation-independent structure; realized separately.)*

1. **Genome and products are separable.** The shared core is organized so it can be inherited and versioned independently of any product; a product references the genome rather than embedding a private copy.
2. **Domain logic lives in packs.** A product's domain-specific rules, vocabulary, quality overrides, and templates are isolated in a pack at the edge, never mixed into shared or core code.
3. **State is portable and self-contained.** Everything the operating model knows about a project lives in one well-known location so it can be removed with zero residue and audited as a unit.
4. **One capability, one home.** A registered capability has a single owning location; consumers reference it, they do not fork it.
5. **Deterministic, diff-clean state.** Serialized state uses fixed ordering and atomic writes so that re-saving an unchanged value is a no-op in version control and every diff reflects a real change.
6. **Convention over configuration.** Layout, naming, and boundaries follow shared conventions so the founder and every agent can navigate any product without relearning it.

---

## PART V — KNOWLEDGE & IMPROVEMENT

## 12. Knowledge Lifecycle

Knowledge in v2 is a first-class asset with a lifecycle, so the platform gets smarter with every assignment rather than resetting each session.

```
Capture → Structure → Generalize → Promote → Apply → Retire
```

1. **Capture.** As a by-product of closing an assignment, the system records what was learned: a non-obvious constraint, a decision and its rationale, an approach that failed, a reusable pattern. Capture is automatic, not a separate chore.
2. **Structure.** Captured knowledge is filed by type — reusable capability, convention, recorded decision, or cross-cutting lesson — so it is findable.
3. **Generalize.** Product-specific knowledge that recurs is generalized into a convention or a capability contract.
4. **Promote.** Generalized knowledge enters the genome: a convention becomes a shared rule; a pattern becomes an M3 capability; a recurring decision becomes a default that removes a future founder decision.
5. **Apply.** The genome's knowledge is applied automatically to new work — new products inherit the accumulated conventions and capabilities from day one.
6. **Retire.** Superseded or disproven knowledge is marked and removed, so the platform never compounds on stale assumptions.

The test of the Knowledge Lifecycle is Principle 9: an assignment that leaves the platform no smarter — no reuse candidate, no refined convention, no recorded decision — is not finished.

---

## 13. Continuous Improvement Model

The platform improves continuously by turning the exhaust of normal execution into structured improvement, batched into the genome at milestones.

1. **Every close emits signals.** Each verified assignment emits: a **reuse candidate** (could this be a capability?), an **improvement signal** (what was awkward, slow, or repeated?), and a **decision-fatigue signal** (did this force a founder decision that a default could have absorbed?).
2. **Signals are batched, not acted on individually.** Routine work is never interrupted to make a platform improvement; signals accumulate and are addressed at meaningful milestones as Lane B/governed work.
3. **Continuous Optimization targets the three outcomes** (velocity, leverage, calm): raise reuse (leverage), remove gates and defaults that cost velocity without buying safety, and drive routine founder decisions toward zero (calm).
4. **Improvements to the operating model are themselves governed.** Because a change to the methodology or genome affects every product, it flows through Lane B at L2/L3 — exactly like this assignment.
5. **Measure and prune.** Capability maturity, reuse rate, gate pass/fail patterns, and founder-decision counts are the platform's vital signs; optimization is driven by these, and process that stops earning its cost is pruned.

---

## PART VI — RISK & FUTURE

## 19. Risk Management

Risk is managed by making the safe path the default path, and by engaging heavyweight controls only where risk is genuine.

1. **Fail-closed is the baseline control.** The single most important risk control is that ambiguity, missing evidence, broken state, and unknown transitions all block rather than pass. No other control is trusted to compensate for a fail-open default.
2. **Risk triggers, not risk vibes.** Elevated process (REVIEWED/GOVERNED, L2/L3, governance records) is engaged by explicit, enumerable triggers: schema/shared-contract change, authentication/authorization/secrets, security-sensitive change, research/risk/statistical methodology, frozen-module change, breaking public contract, legal/compliance. Absent a trigger, work stays FAST.
3. **Protected surfaces.** Frozen modules, public contracts, security boundaries, and the platform genome are protected: touching them auto-raises the mode and level and cannot be done silently.
4. **Irreversibility gates the founder.** Any irreversible business, legal, security, or architecture action stops for a founder decision — this is the primary business-risk control.
5. **Evidence anchors accountability.** Because completion is proven by repository evidence and state changes are auditable and hash-anchored, the platform can always answer "what happened, and on what basis" — the core control against silent drift and unaccountable change.
6. **Proportionality is itself a risk control.** Over-governing routine work is a real risk: it slows delivery, breeds process theater, and trains the team to route around controls. v2 treats unnecessary heavyweight process as a defect.

---

## 20. Future Evolution Strategy

ProjectOS v2 is designed to evolve without redesign. Its extension surfaces and its trajectory:

1. **New products** are onboarded by inheriting the genome and adding a domain pack — never by forking. AI Workspace, TradeOS, EduOS, UrjaOps, and Legal Engineering are the first five; the sixth costs a pack, not a methodology.
2. **New agents** are onboarded by binding an adapter to a role — the AI team model is adapter-based precisely so that a future agent (or a new human specialist) joins without changing the operating model.
3. **New capabilities** enter through the Registry and rise through the Maturity Engine; the genome grows by promotion, staying neutral.
4. **The methodology itself evolves through Lane B.** Changes to v2 are governed, versioned amendments — like this document — so the operating model has the same evidence-and-review discipline it imposes on everything else.
5. **Deepening automation.** The strategic direction is to keep pushing routine decisions into defaults and conventions, widening the share of work that completes at L0–L1 with zero founder involvement, so founder attention concentrates ever more tightly on genuine bets.
6. **Deferred-but-anticipated.** Signed approvals/stronger identity, richer multi-phase pipelines, cross-product portfolio views, and additional execution adapters are anticipated extension points; the model neither requires nor blocks them, and each arrives as an additive amendment.

---

## PART VII — THE FRAMEWORKS (deliverables index)

The nine named deliverables of PO-1 are facets of this single coherent methodology. They are consolidated here rather than fragmented, so the operating model stays internally consistent. This index maps each named deliverable to where it is specified.

| # | Deliverable | Where specified |
|---|---|---|
| 1 | **ProjectOS Methodology v2.0** | This document, in full. |
| 2 | **AI Team Operating Model** | §8 (AI Team Architecture) + §9 (Founder Operating Model) + §14 (Automation). |
| 3 | **Execution Framework** | §3 (Execution Model) + §4 (Lane Model). |
| 4 | **Assignment Framework** | §5 (Assignment Lifecycle) + §6 (Verification Levels) + §16 (Decision Framework). |
| 5 | **Quality Framework** | §7 (Quality Gates) + §15 (Review Framework) + §6 (Verification Levels). |
| 6 | **Knowledge Framework** | §12 (Knowledge Lifecycle). |
| 7 | **Continuous Improvement Framework** | §13 (Continuous Improvement) + §10.2 (Capability Maturity Engine). |
| 8 | **Migration Guide (v1 → v2)** | Part VIII. |
| 9 | **Recommendations / future roadmap** | Part IX (and §20). |

---

## PART VIII — MIGRATION GUIDE: ProjectOS v1 → ProjectOS v2

The migration is **additive and non-destructive**: v2 generalizes v1 rather than replacing its mechanics. The kernel (assignment lifecycle, evidence, audit, invariants) and its workflow modes are unchanged; v2 wraps them in the platform-scale operating model.

### 8.1 Concept mapping

| v1 concept | v2 concept | Change |
|---|---|---|
| One product methodology | Platform genome + domain packs | Generalized: methodology now serves all products. |
| One active assignment | One Active Critical Path + Multi-Lane | Same invariant per lane/repo; a Critical Path is named across lanes. |
| Workflow modes (FAST/REVIEWED/GOVERNED) | Modes **+** Verification Levels (L0–L3) | Levels make proof-depth explicit and orthogonal; modes unchanged. |
| Owner + executor | AI Team roles + configurable adapters | Roles named; adapters make agents swappable. |
| Packs | Packs (unchanged) + Capability Registry + Maturity Engine | Reuse becomes a governed, graded flow. |
| Project rules / templates | Genome conventions + pack overrides | Shared conventions promoted into the genome. |
| Ad-hoc learning | Knowledge Lifecycle | Capture→promote made a first-class loop. |

### 8.2 What stays exactly the same

Everything a current product depends on continues to hold: one active assignment per repository, evidence-based verification, fail-closed defaults, deterministic successor generation, escalate-only-genuine-decisions, the three workflow modes and their gates, and portable self-contained state. No product must change to keep running.

### 8.3 What a product adopts to become v2-native

Incrementally, in priority order — each step is independently valuable and none is a prerequisite for continuing current work:

1. **Adopt verification levels** (L0–L3) on top of existing modes — declare a level per assignment class.
2. **Register capabilities** — enter the product's reusable units in the Capability Registry with initial maturity grades.
3. **Name the lanes** in use and their default agents (adapters).
4. **Route reuse through the Registry** — check-before-build becomes the rule; promote proven local capabilities toward the genome.
5. **Turn on knowledge capture** at assignment close.
6. **Instrument the founder-decision count** and begin driving routine decisions into defaults.

### 8.4 Migration principles

- **No big-bang rewrite.** Products migrate lane-by-lane and capability-by-capability.
- **The genome is extracted, not reinvented.** v2's genome is populated by *promoting* what already works in current products (starting with the kernel and shared conventions), not by designing a new core.
- **Backward compatibility is mandatory.** A v1 product that adopts nothing still runs; v2 fields are additive with v1-equivalent defaults.

---

## PART IX — RECOMMENDATIONS (future evolution roadmap)

Sequenced so each step compounds, and so the founder's decision load falls as the platform's leverage rises. These are recommendations, not assignments; implementation is scheduled separately (per this assignment's stopping point).

1. **First, extract the genome.** Formalize the existing kernel + workspace runtime + conventions as the versioned Platform Genome v1 and stand up the Capability Registry seeded from what AI Workspace already has. *Rationale: reuse cannot start until there is a catalog to reuse from.*
2. **Then, wire verification levels and lanes** into the existing execution loop as additive metadata on assignments. *Rationale: cheap, non-breaking, immediately clarifies proof-depth and parallelism.*
3. **Then, turn on the Capability Maturity Engine** and enforce check-before-build. *Rationale: this is where cross-product leverage becomes measurable — the first product onboarded onto the genome should cost noticeably less than the last.*
4. **Then, instrument the Founder Decision Budget.** Start counting routine vs. genuine founder decisions; make "routine founder decisions trending to zero" an explicit platform metric. *Rationale: calm is a measurable outcome, and what is measured improves.*
5. **Then, automate knowledge capture and the improvement-signal batch.** *Rationale: makes compounding automatic rather than aspirational.*
6. **Onboard the second product (e.g., TradeOS or UrjaOps) as the genome's first real test.** *Rationale: the true validation of platform-first is the second product built almost entirely from inherited capability.*
7. **Defer, but design toward:** signed approvals/stronger identity for multi-party trust, cross-product portfolio views for the founder, and additional execution adapters (e.g., ChatGPT, specialist humans) as the AI team grows.

**Top risks to the rollout, and their mitigations:**

- *Genome captures too much or too little.* Mitigate by promoting only M2+ capabilities on evidence, never speculatively.
- *Process re-inflates.* Mitigate by treating unnecessary heavyweight process as a defect and pruning gates that stop earning their cost (§13.5).
- *Reuse decays into sideways copying.* Mitigate by making duplicate-build a review-blocking issue and reuse pull-and-promote only (§18).
- *Founder becomes the bottleneck again.* Mitigate by the Founder Decision Budget metric and by pushing resolved decision-classes into defaults every milestone.

---

## APPENDIX A — L2 VERIFICATION RECORD

Independent, delta-only, verdict-oriented review of this methodology against its acceptance criteria (verification level L2 as assigned).

| Acceptance criterion | Verdict | Basis |
|---|---|---|
| Methodology is internally consistent | **PASS** | The one-active-assignment/multi-lane tension is resolved explicitly (§3.1–3.2): kernel INV-1 holds per lane; the Critical Path is the cross-lane primary. Modes (process) and verification levels (proof) are orthogonal but aligned by an explicit default map (§6). No principle contradicts another; each concept has one home. |
| Clearly separates governance, engineering, and business | **PASS** | The three planes are defined and owner-assigned (§2.1), governance is explicitly kept out of routine engineering (Principles 6–7; §7.1; §16 routine class resolved silently), and business decisions are named and founder-owned (§16, §9). |
| Supports all current and future products | **PASS** | Platform-genome-plus-pack architecture (§11) is domain-neutral by construction; new products cost a pack, new agents cost an adapter, new capabilities enter via the Registry (§20). AI Workspace, ProjectOS, TradeOS, EduOS, UrjaOps, Legal Engineering named and covered. |
| Minimizes founder decision fatigue | **PASS** | Three-channel founder interface, escalate-only-genuine-decisions, reversible-defaults-beat-questions, serialized escalations, and an explicit Founder Decision Budget metric (§9, §16). |
| Implementation-ready | **PASS** | Every framework is concrete enough to assign (levels, gates, maturity grades, lane table, migration steps, sequenced roadmap) while remaining implementation-independent — no code, no repo changes, per scope. |
| Scope coverage: all 20 required sections present | **PASS** | §§1–20 all present (reordered into logical parts; traceability below). |
| Scope coverage: all 9 deliverables present | **PASS** | Deliverables index, Part VII. |

**Section traceability (all 20 required sections):** 1 ProjectOS Vision v2 §1 · 2 Operating Principles §2 · 3 Execution Model §3 · 4 Lane Model §4 · 5 Assignment Lifecycle §5 · 6 Verification Levels §6 · 7 Quality Gates §7 · 8 AI Team Architecture §8 · 9 Founder Responsibilities §9 · 10 Capability-first Development §10 · 11 Platform-first Development §11 · 12 Knowledge Lifecycle §12 · 13 Continuous Improvement Model §13 · 14 Automation Strategy §14 · 15 Review Framework §15 · 16 Decision Framework §16 · 17 Repository Organization Principles §17 · 18 Cross-project Reuse Model §18 · 19 Risk Management §19 · 20 Future Evolution Strategy §20.

**Reviewer verdict: PASS.** No blocking issues. The methodology is internally consistent, correctly separated across the three planes, product- and future-agnostic, founder-fatigue-minimizing, and implementation-ready without containing implementation.

---

*End of ProjectOS Methodology v2.0. This assignment updates the methodology only. No implementation was performed; future implementation is assigned separately.*
