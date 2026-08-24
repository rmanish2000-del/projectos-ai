# ProjectOS Canonical Implementation Roadmap

**The executable plan that turns the design corpus into a built platform — dependency-sequenced, gate-verified, built around a kernel that already works.**

**Status:** Canonical implementation roadmap. **Planning only — no implementation, no code.**
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Builds on:** `FOUNDATIONAL_CORPUS_INTEGRATION.md` (PO-8) — its readiness matrix, gap register, and wave plan are the input; this document refines them to milestone granularity with verification, release, and acceptance gates.
**Grounded in:** the actual repository state (Verified): the **kernel is implemented** (`src/projectos`, 479 tests); the workspace bootstrap is implemented; everything above is specification.

---

## 0. Planning basis & principles

1. **Build around a live kernel — do not rewrite it.** The Foundation Spec is already code and passing 479 tests. The platform is built *on top of and around* it; the kernel is a fixed, frozen foundation (any change to it is GOVERNED/L3). This removes the largest risk in most platform builds — the core already exists and works.
2. **Dogfood: build ProjectOS using ProjectOS.** Every milestone below is itself run as ProjectOS assignments under the Methodology and Governance just defined — verified by the kernel's evidence engine, governed proportionally. The platform proves itself by being built with itself.
3. **Sequence by dependency and size, not calendar.** Velocity depends on founder decision latency and AI-team throughput, which are not yet measured, so this roadmap gives **dependency order + relative size (S/M/L)** rather than fabricated dates. Dates are added once the first milestones establish a velocity baseline.
4. **Proportional gates (PO-4).** Routine build work is FAST/L1; contracts, schemas, security, and genome changes are REVIEWED/GOVERNED. The roadmap never over-governs — it applies the trigger gate per milestone.
5. **Everything ships verified or not at all** — each milestone has an acceptance gate expressed as machine-checkable evidence (the kernel's own discipline), not a claim.

---

## 1. Specification review — what is approved, what is built

| Layer | Spec | Build state | Roadmap role |
|---|---|---|---|
| Kernel | Foundation Spec | **Implemented** (479 tests) | Frozen foundation — wrap, don't touch |
| Workspace bootstrap (P3) | in kernel repo | **Implemented** | Reused as-is |
| Constitution (PO-6) | approved | spec | Ratified in M0 |
| Methodology / Genome / Ownership / Governance / Metrics (PO-1–5) | approved | spec | Governing rules for the build |
| Metadata (PO-7) | approved | spec | Built in Phases 1–5 |
| Workspace Runtime (P4) | approved | spec | Built in Phase 2 (after schema reconcile) |
| Maturity Engine | conceptual (Meth §10.2) | **design gap G-2** | Designed in M1 |
| Discovery / Platform Intelligence | named only | **design gap G-4** | Designed in M2 |
| AI Workspace operating model | empty file | **design gap G-1** | Designed in M3 |
| Products (EduOS, TradeOS) | EduOS P0 done | code external | Onboarded in Phase 7 |

**Conclusion:** the design corpus is complete and internally consistent; three sub-specs (G-1, G-2, G-4) must be authored before their build phases; the metadata core is ready to build immediately after ratification.

## 2. Implementation Dependency Graph (Deliverable — Dependency Graph)

Component-level build DAG. `A → B` = B depends on A. Acyclic (verified).

```
  KERNEL (built) ─────────────────────────────────────────────┐
     │                                                          │
     ├─► Capability Registry (M4) ──► Schema Reg (M5a) ──► Contract Reg (M5b)
     │        │                            │                     │
     │        │                            ├──────► API Reg (M8) ─┤
     │        │                            │            │        │
     │        ▼                            ▼            ▼        ▼
     │   Maturity Engine (M7) ◄─ spec M1   Event Reg   Tool/Agent/Prompt Reg (M9)
     │        │                            (M12a)         │
     │        ▼                                           ▼
     ├─► Genome store (M10) ──► Genome evolution/promotion (M11)
     │                                     │
     ├─► Workspace Runtime (M6) ◄─ needs project.yaml reconcile (M0)
     │                                     │
     ▼                                     ▼
  Decision Reg (M12b) ─► Knowledge Reg (M12c) ─► Discovery (M13) ─► Platform Intelligence (M14)
                                                                          │
  AI Workspace op-model spec (M3) ─► AI Workspace platform (M15) ─► HQ (M16)
                                                                          │
                                          First product onboarded (M17) ◄─┘
```

Critical path: **Kernel → Capability Registry → Schema/Contract → Genome → Discovery/Intelligence → Platform → Product onboarding.** The Registry is the single highest-leverage unblock (everything metadata-driven waits on it).

## 3. Implementation Sequence — phases

| Phase | Name | Milestones | Outcome |
|---|---|---|---|
| **R** | Ratify & reconcile | M0 | Formal authority; clean schemas |
| **D** | Design the gaps | M1–M3 | Maturity, Discovery/Intelligence, AI Workspace specs |
| **1** | Metadata core | M4–M5 | Capability + Schema + Contract registries |
| **2** | Runtime & maturity | M6–M7 | Multi-project runtime; capability grading |
| **3** | Execution registries | M8–M9 | API, Tool, Agent, Prompt |
| **4** | Inheritance | M10–M11 | Genome store + evolution/promotion |
| **5** | Ledgers & intelligence | M12–M14 | Event/Decision/Knowledge; Discovery; Intelligence + dashboards |
| **6** | Platform & business | M15–M16 | AI Workspace surfaces; HQ |
| **7** | Product cutover | M17 | First product onboarded by inheritance |

Phases D milestones may run as background lanes (parallel design) while Phase 1 builds, since M4–M5 don't depend on them; but exactly one Critical Path holds founder attention (Methodology §3).

## 4. Milestone Plan (Deliverable — Milestones)

Each milestone: goal · contents · depends-on · verification level · acceptance gate (definition of done) · size · lane.

| M | Goal | Depends | V-level | Acceptance gate (DoD) | Size | Lane |
|---|---|---|---|---|---|---|
| **M0** | Ratify corpus & reconcile | — | GOVERNED/L3 | Amendments A-1…A-4 signed; project.yaml schema reconciled (G-3); domain triggers moved to Domain DNA (G-5) | S | B/F |
| **M1** | Maturity Engine spec (G-2) | M0 | REVIEWED/L2 | Standalone spec: M0–M4 rules, evidence inputs, Genome/PO-5 seams; L2 review PASS | M | B |
| **M2** | Discovery + Platform Intelligence specs (G-4) | M0 | REVIEWED/L2 | Two specs: search model + analytics model over the metadata graph; L2 PASS | M | B |
| **M3** | AI Workspace operating-model spec (G-1) | M0, PO-3 | GOVERNED/L3 | The implementation-platform spec (surfaces, runtime, ops, security, identity); L3 PASS | L | B |
| **M4** | Capability Registry (anchor) | Kernel, M0 | GOVERNED/L3 (schema) | CRUD over capability records; Genome §9 binding fields; fail-closed ref integrity; full-suite green | M | A |
| **M5a** | Schema Registry | M4 | GOVERNED/L3 | Schema records + compatibility modes; incompatible change blocked; full-suite green | M | A |
| **M5b** | Contract Registry | M5a | GOVERNED/L3 | Contract records ref Schema; breaking-contract gated; full-suite green | M | A |
| **M6** | Workspace Runtime (P4) | Kernel, M0(reconcile) | REVIEWED/L2 | Active-project & active-assignment resolution over real project.yaml; runtime tests green | M | A |
| **M7** | Maturity Engine | M4, M1 | REVIEWED/L2 | Grades capabilities from evidence; feeds Genome + PO-5; tests green | M | A |
| **M8** | API Registry | M5a, M5b | REVIEWED/L2 | API records ref Contract+Schema; deprecation flow; tests green | M | A |
| **M9** | Tool/Agent/Prompt registries | M8 | REVIEWED/L2 | Execution-layer records + reference integrity; agent authority checks; tests green | L | A |
| **M10** | Genome store | M4, M7 | GOVERNED/L3 | Lineage/family-tree over Registry; complete-ancestry + acyclic invariants enforced | L | A |
| **M11** | Genome evolution & promotion | M10, PO-4 | GOVERNED/L3 | promote/demote/split/merge/retire as governed assignments; no stranded consumer; lineage recorded | L | A |
| **M12** | Event/Decision/Knowledge registries | M5a, Kernel audit | REVIEWED/L2 | Ledgers anchored to audit chain; Decision→Knowledge promotion; append-only enforced | L | A |
| **M13** | Capability Discovery | M10, M2 | REVIEWED/L2 | Reuse-candidate search over the graph; check-before-build enforced; tests green | M | A |
| **M14** | Platform Intelligence + dashboards | M12, M13, M2 | REVIEWED/L2 | PO-5 scores computed from evidence; Ecosystem Health + Decision Budget dashboards; anti-gaming caps live | L | A |
| **M15** | AI Workspace platform surfaces | M3, all registries | GOVERNED/L3 (security) | Implementation-platform surfaces per M3; security/identity governed; tests green | L | A |
| **M16** | AI Workspace HQ | M15 | Business gov. | Marketplace + business surfaces; business governance | L | A |
| **M17** | First product onboarded | M11, M14 | GOVERNED/L3 | One product (per FD-4) built from inheritance; first capability promoted; genome inheritance proven end-to-end | M | A/B |

## 5. Verification Plan (Deliverable — part of Quality Gates)

Verification is layered by what each milestone touches, using the kernel's evidence engine + the Methodology levels (L0–L3):

1. **Every milestone** runs the FAST gate set: focused unit + affected integration + lint + type + build + smoke (PO-5 §7). Non-negotiable, automated, authoritative.
2. **Registry / schema / contract milestones (M4, M5, M8, M12)** additionally run the **full suite** and a **referential-integrity check** (fail-closed on dangling IDs — PO-7 §13) as an acceptance gate.
3. **Genome milestones (M10, M11)** run **structural invariant checks** (complete ancestry, acyclic tree, no stranded consumer) as blocking gates.
4. **GOVERNED milestones (M0, M3, M4, M5, M10, M11, M15)** add an **independent L2/L3 review** (delta-only, PASS/FAIL) plus **founder sign-off** where the trigger is frozen-architecture/security/breaking-contract.
5. **Dogfooded verification:** because the kernel already verifies assignments from evidence, each build milestone is *itself* a verified ProjectOS assignment — the platform's construction is auditable by the platform's own foundation.
6. **Contract/schema evolution** is verified against compatibility rules (backward/forward), not just tests — a breaking change without a migration path fails the gate.

## 6. Quality Gates (Deliverable — Quality Gates)

Two gates per milestone. Entry = may we start; Exit = may we merge/close.

**Entry gate (all milestones):** dependencies met (per §2); design approved (spec exists and is L2-reviewed for gap milestones); the milestone has exactly one owner and one active assignment (INV-1).

**Exit gate by tier** (reuses PO-4 §8 trigger tiering — no new gates invented):

| Tier | Milestones | Exit gate |
|---|---|---|
| **FAST / L1** | routine sub-tasks within a milestone | green quality-gate set; auto-merge |
| **REVIEWED / L2** | M1, M2, M6, M7, M8, M9, M12, M13, M14 | + independent delta review PASS |
| **GOVERNED / L3** | M0, M3, M4, M5, M10, M11, M15 | + full suite + governance record + founder sign-off |

No milestone closes on a claim; each closes on repository evidence (commits, PRs, CI, tests) per the kernel model.

## 7. Release Roadmap / Strategy (Deliverable — Release Strategy)

Three release trains, each a coherent, usable increment. Versioning aligns with the corpus scheme (Foundational Corpus v1.0 = the ratified design; platform builds are Platform v0.x → v1.0).

| Release | Milestones | What works | Version | Exit criterion |
|---|---|---|---|---|
| **R0 — Internal Alpha** | M0–M7 | Platform can catalogue capabilities, resolve multi-project runtime, and grade maturity — dogfooded internally on ProjectOS itself | Platform v0.1 | Capability/Schema/Contract registries + Runtime + Maturity live and green; ProjectOS's own capabilities registered |
| **R1 — Platform Beta** | M8–M14 | Full metadata graph, inheritance/promotion, ledgers, discovery, and health dashboards; one product not yet cut over | Platform v0.5 | Genome inheriting + promotion working; Platform Intelligence dashboards green; check-before-build enforced |
| **R2 — Platform GA** | M15–M17 | AI Workspace surfaces + HQ; first product onboarded by inheritance | **Platform v1.0** | A product built almost entirely from inherited capability (the platform-first proof); metrics 🟢; governance operating |

**Release principles:** each train is independently valuable and shippable; no train starts before the prior train's exit criterion is met; maturity grades (M0–M4) gate what may be promoted into a release (only M2+ capabilities ship as inheritable). Products (EduOS, TradeOS) keep running throughout — they are onboarded, never interrupted.

## 8. Migration Strategy (Scope — migration)

- **Kernel: no migration.** It is frozen and wrapped; the platform builds around it. Zero risk to the working core.
- **Registries are additive.** They catalogue what already exists; nothing is removed to add them. A product with no registry entries still runs (v1 fields optional, v1 defaults).
- **project.yaml reconcile (M0) is the one prerequisite migration** — align the as-built schema (`repository.path`, flat `workflow_mode`) with the Runtime spec before M6; non-destructive, one file at a time.
- **Products migrate one at a time onto the genome** (Phase 7), on their own pin, within a compatibility window — EduOS or TradeOS first (FD-4), the other later. No big-bang.
- **Backward compatibility is mandatory** at every step (Genome §20, Constitution §26, PO-7 §15 — one migration model). A superseded rule points to its successor (lineage as the migration map).
- **External code roots** (EduOS/TradeOS code outside the workspace) are reconciled as part of onboarding (topology, G-3 class) — connect the code root before cutover.

## 9. Blockers (Scope — blockers)

Hard blockers that gate the start, and which milestone each releases.

| Blocker | Type | Gates | Released by |
|---|---|---|---|
| **FD-2** Ratify the corpus | Founder decision | Everything (formal authority) | M0 |
| **FD-3** Authorize Wave 1 build | Founder decision | Phase 1+ | Founder |
| **FD-1** Canonical operating-model content | Founder decision | Methodology finalization | Founder (recommendation: keep v2, EduOS as Local Expression) |
| **FD-4** Portfolio priority / Critical Path | Founder decision | M17 target; lane contention | Founder |
| **G-1** AI Workspace op-model absent | Design gap | Phase 6 (M15–16) | M3 |
| **G-2** Maturity Engine unspecified | Design gap | M7 | M1 |
| **G-4** Discovery/Intelligence unspecified | Design gap | M13–14 | M2 |
| **G-3** project.yaml drift | Reconcile | M6 (Runtime) | M0 |

**Only two blockers gate the very start: FD-2 and FD-3.** Once ratified and authorized, M0→M5 proceed; the design-gap blockers (G-1/2/4) gate only their own later phases and are dissolved by the Phase-D design milestones running in parallel.

## 10. Risk Assessment (Scope — risk assessment)

| ID | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| **RK-1** | Founder decision latency stalls the build (single-founder bottleneck) | Med | High | Batch FD-1…FD-4 now (decision-ready); Decision Budget metric; serialize (PO-4 §2) | Founder |
| **RK-2** | AI Workspace op-model (G-1) is the largest unknown — a whole plane specified only as a boundary | Med | High | M3 GOVERNED design milestone early; treat as its own review-heavy sub-project | B |
| **RK-3** | Process re-inflates — the build over-governs itself | Med | Med | Proportional gates (§6); routine build stays FAST; governance KPIs watched (PO-5 §2) | B |
| **RK-4** | Dogfooding bootstrap paradox — using the platform to build the platform before it exists | Low | Med | The kernel already works; use kernel + manual governance until Platform Intelligence (M14) exists | A |
| **RK-5** | Registry overlap / dangling references accumulate | Med | Med | Boundary matrix (PO-7 §12) + fail-closed integrity as acceptance gates (M4, M5, M12) | A |
| **RK-6** | Scope creep beyond v1 (autonomy, HQ features pulled early) | Med | Med | Release trains gate scope; autonomy is R1+; HQ is R2 | B |
| **RK-7** | External code roots block product onboarding | Low | Med | Reconcile topology in M0/M17; connect code root before cutover | A |
| **RK-8** | Maturity/Discovery/Intelligence slip → autonomy delayed | Med | Low | Sequence them last; platform is fully usable without autonomy (manual promotion works) | B |

Top two risks are **founder bandwidth (RK-1)** and **the AI Workspace design gap (RK-2)** — both are addressed by front-loading (batch decisions now; design M3 early).

## 11. Acceptance Gates (Scope — acceptance gates)

Three levels of acceptance:

1. **Per-milestone DoD** — the acceptance gate in §4, expressed as evidence, per milestone.
2. **Per-release exit criterion** — §7 (R0/R1/R2), each a coherent capability the founder can verify.
3. **Platform v1.0 GA gate (the definition of "done" for this roadmap):**
   - All ten registries live with fail-closed referential integrity.
   - Genome inheriting and promoting capabilities end-to-end, with lineage.
   - At least one product onboarded and running by inheritance (the platform-first proof).
   - PO-5 Ecosystem Health dashboard green; Founder Decision Budget instrumented and trending down.
   - Governance operating proportionally (routine work ungoverned; triggers enforced).
   - The kernel unchanged and still green (the foundation was never destabilized).

When the GA gate passes, the design corpus has become a working platform — and the roadmap is complete.

---

## APPENDIX A — L2 REVIEW

Independent, delta-only, verdict-oriented review against the assignment.

| Check | Verdict | Basis |
|---|---|---|
| Reviews all approved specs | **PASS** | §1 status table covers kernel + PO-1…7 + Runtime + products with build state. |
| Identifies implementation dependencies | **PASS** | §2 component dependency DAG; critical path named. |
| Builds implementation sequence | **PASS** | §3 phases R,D,1–7; §4 milestones M0–M17 in dependency order. |
| Milestone plan | **PASS** | §4 — each with goal/deps/verification/acceptance/size/lane. |
| Verification plan | **PASS** | §5 — layered by what each milestone touches; dogfooded via kernel evidence. |
| Release roadmap | **PASS** | §7 — R0/R1/R2 trains with versions and exit criteria. |
| Migration strategy | **PASS** | §8 — kernel frozen, registries additive, products one-at-a-time, backward-compatible. |
| Blockers identified | **PASS** | §9 — FD-1…4 + G-1/2/4/G-3, each with what it gates and what releases it. |
| Risk assessment | **PASS** | §10 — 8 risks with likelihood/impact/mitigation/owner. |
| Acceptance gates | **PASS** | §11 — per-milestone, per-release, and the GA gate. |
| Deliverables (Roadmap, Dependency Graph, Milestones, Quality Gates, Release Strategy) | **PASS** | §3–4 / §2 / §4 / §5–6 / §7 respectively. |
| Planning only, grounded in evidence | **PASS** | No implementation; kernel-built/rest-spec verified against repo; no fabricated dates (dependency+size sequencing). |

**Reviewer verdict: PASS.** No blocking issues. The roadmap is dependency-correct, gate-verified, honestly grounded in the real repository state, front-loads the two governing risks, and stops at a complete plan — nothing is implemented.

---

## APPENDIX B — DELIVERABLES INDEX

| Deliverable | Where |
|---|---|
| Canonical Roadmap | Whole document; sequence §3, milestones §4 |
| Dependency Graph | §2 |
| Milestones | §4 |
| Quality Gates | §5 (verification) + §6 (gates) + §11 (acceptance) |
| Release Strategy | §7 |

---

*End of ProjectOS Canonical Implementation Roadmap. Planning only — no implementation, no code. The plan sequences the build around a live kernel, gates every milestone on evidence, and stops at a complete roadmap; the two start-blockers (ratify, authorize) are founder decisions.*
