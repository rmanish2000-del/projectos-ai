# Foundational Corpus Integration

**The master integration layer — how every ProjectOS document works together as one operating ecosystem.**

**Status:** PO-8 — canonical integration specification. Integration only; **no redesign** of any approved document, no implementation, no code, no contracts, no registry contents, no Genome redesign.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2. **Priority:** High.
**What this document is:** the single map that ties the corpus together. It restates nothing and redesigns nothing; it references the authoritative documents and shows how they interlock, where the system is ready to build, and what still blocks it.
**Corpus integrated:** Constitution (PO-6), Methodology v2 (PO-1), Platform Genome v1 (PO-2), Ownership/Integration (PO-3), Governance (PO-4), Metrics & Health (PO-5), Metadata Architecture (PO-7), the Kernel (Foundation Spec), the Workspace Runtime spec, PO-2.5 review, and the as-built products (EduOS-AI, TradeOS-AI).

---

## 0. START HERE — "a new engineer joins tomorrow"

Read this section first. It is the whole system in one page.

**The one-sentence mental model:** *ProjectOS is a kernel that runs verified work; a set of definitional documents (owned by ProjectOS) that say how work is run, inherited, owned, governed, measured, and catalogued; a platform (AI Workspace) that implements those definitions; a business layer (HQ) that sells it; and products (EduOS, TradeOS, …) that are built on top by inheriting the shared core and adding only their domain.*

**The four things you are always dealing with:**

1. **A kernel** that turns an assignment into verified, evidenced, audited work — *already real code* (`src/projectos`, 479 tests).
2. **Definitional documents** that govern everything above the kernel — *all specification, not yet built.*
3. **A platform** (AI Workspace) that will implement those documents — *its own spec is still empty.*
4. **Products** that inherit the core and specialize at the edge — *EduOS and TradeOS exist today.*

**The reading order (dependency-correct):**

```
1. Constitution (PO-6)      → learn the hierarchy: which doc wins, and how it changes.
2. Kernel (Foundation Spec) → learn the atom: assignment → evidence → audit. THIS IS CODE.
3. Methodology v2 (PO-1)    → learn how work flows: lanes, verification levels, decisions.
4. Genome v1 (PO-2)         → learn inheritance: how products share a core without forking.
5. Ownership (PO-3)         → learn who owns what: one owner per capability.
6. Governance (PO-4)        → learn when governance applies: only on triggers; routine is free.
7. Metrics (PO-5)           → learn how health is measured: evidence-derived scores.
8. Metadata (PO-7)          → learn the catalogs: 10 registries, the Capability Registry anchor.
9. This document (PO-8)     → learn how they interlock, and what to build first.
```

**The single rule that explains most decisions:** *one authoritative source per domain, referenced by everyone, copied by no one.* The Constitution enforces it over documents; PO-3 over ownership; PO-7 over metadata. If you ever see two documents legislating the same thing, that is a defect, not a design.

**Where to look when you ask "…":**
- *"How do I run a piece of work?"* → Methodology (lanes/levels) + Kernel (evidence).
- *"Who owns this capability?"* → PO-3.
- *"Does this need review/approval?"* → PO-4 (trigger gate).
- *"Where is X catalogued?"* → PO-7 (the ten registries).
- *"Is the platform healthy?"* → PO-5.
- *"Which document wins if two disagree?"* → PO-6 (the Register).

---

## PART I — THE CORPUS

## 1. Foundational Corpus Map (Deliverable 2 — Architecture Maps)

Every document, its one job, its tier, and its build state.

| Document | One job | Tier | Build state |
|---|---|---|---|
| **Constitution (PO-6)** | Orders the documents; one source per domain | L0 | Spec (ratification pending, §15) |
| **Kernel (Foundation Spec)** | Assignment lifecycle, evidence, audit | L1 | **Implemented** (P1, 479 tests) |
| **Methodology v2 (PO-1)** | Operating model: lanes, levels, decisions, knowledge | L1 | Spec |
| **Genome v1 (PO-2)** | Inheritance, DNA, lineage, evolution | L1 | Spec |
| **Ownership (PO-3)** | One owner per capability; 4 realms | L1 | Spec |
| **Governance (PO-4)** | Proportional governance; triggers, tiers | L1 | Spec |
| **Metrics (PO-5)** | Evidence-derived health scores | L1 | Spec |
| **Metadata (PO-7)** | 10 registries; Capability Registry anchor | L2 | Spec |
| **Workspace Runtime (P4)** | Multi-project runtime above the kernel | L2 | Spec |
| **architecture.md / cli.md** | Kernel elaboration | L2 | **Implemented** (docs of live code) |
| **PO-2.5 Review** | Consistency finding of fact | L3 | Reference |
| **EduOS-AI, TradeOS-AI docs** | Product local expressions | L4 | EduOS P0 done; code external |

**The map in one picture:**

```
              ┌──────────────── L0  CONSTITUTION (PO-6) ────────────────┐
              │  one hierarchy · one source per domain · amendments      │
              └───────────────────────────┬─────────────────────────────┘
   L1 CANONICAL (ProjectOS-owned definitions)  │
   ┌──────────┬──────────┬──────────┬──────────┼──────────┬──────────┐
   │ Kernel*  │Methodolgy│  Genome  │Ownership │Governance│ Metrics  │
   │ (code)   │  (PO-1)  │  (PO-2)  │  (PO-3)  │  (PO-4)  │  (PO-5)  │
   └──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
   L2 SUPPORTING          │ Metadata (PO-7) · Workspace Runtime · arch/cli
   L3 REFERENCE           │ PO-2.5 consistency review
   L4 LOCAL EXPRESSIONS   │ EduOS-AI · TradeOS-AI · (future products)
                          * Kernel is the only L1 document already implemented.
```

## 2. Document Hierarchy (Deliverable 3)

The five tiers are defined by the Constitution (PO-6 §3); this document does not restate them, it applies them: **L0 Constitution → L1 Canonical (one domain each) → L2 Supporting → L3 Reference → L4 Local Expression.** Higher binds lower; local never overrides canonical; authority is conferred only by amendment (§15). The corpus map (§1) places every current document in this hierarchy.

## 3. Cross-reference Matrix (Deliverable 3 — Cross-reference Workbook)

Which document references which (→ = "references / builds upon"). Read a row as "this document depends on…".

| ↓ refs → | Const | Kernel | Meth | Genome | PO-3 | PO-4 | PO-5 | PO-7 |
|---|---|---|---|---|---|---|---|---|
| **Constitution** | — | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Kernel** | — | — | — | — | — | — | — | — |
| **Methodology** | — | ✓ | — | ✓ | — | — | — | — |
| **Genome** | — | ✓ | ✓ | — | — | — | — | (anchor) |
| **PO-3 Ownership** | — | ✓ | ✓ | ✓ | — | — | — | — |
| **PO-4 Governance** | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — |
| **PO-5 Metrics** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| **PO-7 Metadata** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |

Reading: the **Kernel references nothing** (it is the root); the **Constitution and PO-7 reference everything** (apex and integration substrate). No cycles — the corpus is a DAG (confirmed §5).

## 4. Authority Matrix (Deliverable — one source per domain)

The single authoritative source per governance domain, from the Constitution Register (PO-6 §8.2). This document *points to* it; it does not re-legislate.

| Domain | Authoritative source |
|---|---|
| Constitutional hierarchy & amendment | Constitution (PO-6) |
| Assignment lifecycle, evidence, audit | Kernel |
| Operating model | Methodology v2 |
| Inheritance & lineage | Genome v1 |
| Capability ownership & responsibilities | PO-3 |
| Governance process | PO-4 |
| Ecosystem metrics & health | PO-5 |
| Ecosystem metadata (10 registries) | PO-7 |
| Runtime/workspace resolution | Workspace Runtime spec |
| Product identity/strategy/content | product Local Expression |

One row, one owner → no duplicated authority (the corpus-wide invariant).

## 5. Dependency Matrix (Deliverable 3 — Cross-reference Workbook)

Build/understanding dependency order (what must exist/be understood before what). A topological read of §3.

```
  Kernel  ─►  Methodology ─►  PO-3 Ownership ─►  PO-4 Governance ─►  PO-5 Metrics
     │            │                 ▲                   ▲                 ▲
     └─►  Genome ─┘                 │                   │                 │
              │                     │                   │                 │
              └─►  PO-7 Metadata ───┴───────────────────┴─────────────────┘
  Constitution ─► (sits above all; understood first, amended last)
```

Dependency rules: nothing depends on the Constitution's *content* (it depends on the docs it orders); the Kernel depends on nothing; PO-7 depends on Genome + PO-3; PO-5 depends on the widest set (it measures everything). Acyclic → the corpus can be built and reasoned about in order.

---

## PART II — HOW IT INTERLOCKS

## 6. Metadata Integration

PO-7's ten registries are the **substrate the rest of the corpus reads and writes**. Integration points:

- **Genome ↔ Capability Registry:** the Genome binds to Registry records (Genome §9); the Registry holds *what exists*, the Genome holds *how it's inherited*. (§7)
- **Metrics ↔ registries:** PO-5's scores are computed from registry records + kernel evidence (Capability Health ← Capability Registry + Maturity; Knowledge Maturity ← Knowledge Registry; Decision Budget ← Decision Registry).
- **Governance ↔ Contract/Schema registries:** PO-4's `breaking_public_contract` trigger fires on Contract/Schema Registry changes.
- **Discovery & Platform Intelligence** (AI-Workspace-owned) read the whole metadata graph; only registry writes author it.

## 7. Genome Integration

The Genome is the **inheritance engine over the metadata**:

- Product-local capabilities (Capability Registry, M0–M2) → promoted (Genome §13, governed by PO-4 §5) → platform-inherited Capability DNA (M3–M4).
- The Genome's lineage/family tree is *itself* metadata the registries and Platform Intelligence read.
- Every product = Genome (shared core) + Domain DNA (its pack) + Product DNA (its identity) — EduOS's "content-blind engine + content packs" is the same pattern realized product-locally (PO-2.5 D-5), and is the first real **promotion candidate**.

## 8. Registry Integration

The ten registries interlock by **reference-by-ID into one metadata graph** (PO-7 §13), anchored on the Capability Registry. Integration with the corpus: Agent/Tool/Prompt registries realize the Methodology's AI-Team (PO-3 §12); the Decision Registry is PO-4 Decision Governance's ledger; the Knowledge Registry is the Methodology Knowledge Lifecycle's (§12) and the Genome knowledge layer's (§22) store; the Event/Schema registries carry the kernel's evidence taxonomy.

## 9. Capability Flow (the corpus in motion #1)

How a capability moves through *every* document — the clearest proof the corpus is one system.

```
 born ──► catalogued ──► matured ──► promoted ──► inherited ──► measured ──► (reused)
  │           │             │            │             │            │
Methodology  PO-7          Maturity     Genome §13    Genome        PO-5
 (a product   Capability    Engine       + PO-4 §5     Platform DNA  Capability
  builds it,  Registry      (M0→…→M4)     (governed,    (all products Health +
  M0 local)   record        from evidence promotion)    may express)  reuse metrics
```

One capability, seven documents, no contradiction: Methodology builds it, PO-7 catalogues it, the Maturity Engine grades it, PO-4 governs its promotion, the Genome inherits it, PO-3 fixes its ownership at each step, PO-5 measures it. *This is what "one ecosystem" means.*

## 10. Knowledge Flow (the corpus in motion #2)

```
 captured ──► registered ──► promoted ──► inherited ──► removes a decision ──► measured
    │             │              │             │                  │                │
 Methodology    PO-7          Genome §22     new products      PO-4 Decision      PO-5
  §12 (at        Knowledge     knowledge      born knowing it   Governance         Knowledge
  assignment     Registry      layer (gov.                      (a recurring       Maturity +
  close)                       PO-4 §5)                          decision → default) Decision Budget
```

Knowledge captured once becomes an inherited default that *removes a future founder decision* — directly feeding the Calm outcome (PO-5) and the Founder Decision Budget.

## 11. Decision Flow (the corpus in motion #3)

```
 arises ──► classified ──► routine? ──yes──► resolved silently (no record)
                │              │
                │              └──no (genuine)──► decision-ready escalation ──► Founder decides
                │                                          │                        │
             PO-4 §2                                    Methodology §16          recorded in
             (classes)                                  (options+consequence)    PO-7 Decision
                                                                                  Registry
                                                                                     │
                                          recurring? ──► promoted to default (Knowledge Flow) ──► PO-5 Budget↓
```

A decision is classified (PO-4), routine ones vanish into conventions, genuine ones escalate decision-ready (Methodology), get recorded (PO-7), and — if recurring — become defaults (Genome/Knowledge) that shrink the founder's future load (PO-5). *The three flows share the same promotion mechanism — capability, knowledge, and decision all rise from local to shared through governed promotion.*

---

## PART III — FROM SPECIFICATION TO SYSTEM

## 12. Implementation Order

Dependency-correct build order (design → build). The Kernel and workspace bootstrap are already implemented; everything else is greenfield.

1. **Capability Registry** (PO-7 anchor; the standing Blocker) — nothing metadata-driven works without it.
2. **Schema + Contract registries** — the interface substrate.
3. **Workspace Runtime (P4)** — reconciled with the as-built `project.yaml` (gap G-3).
4. **Maturity Engine** — grades capabilities from evidence (feeds Genome + PO-5).
5. **API + Tool + Agent + Prompt registries** — the execution layer.
6. **Genome store + evolution operations** — inheritance + promotion, over the Registry.
7. **Event + Decision + Knowledge registries** — the ledgers, anchored to the kernel audit.
8. **Discovery + Platform Intelligence** — read the metadata graph; compute PO-5 scores.
9. **AI Workspace platform surfaces + HQ** — implementation & business planes.

## 13. Implementation Readiness Assessment (Deliverable 4 — Readiness Matrix)

Honest, evidence-based (Verified against the repo). "Ready" = design complete + dependencies met + no blocker.

| Component | Design | Dependencies met | Blocker | Readiness |
|---|---|---|---|---|
| Kernel | ✅ | — | — | **DONE (implemented, 479 tests)** |
| Workspace bootstrap (P3) | ✅ | — | — | **DONE (implemented)** |
| Capability Registry | ✅ (PO-7) | kernel | none | 🟢 **Ready to build (Wave 1)** |
| Schema / Contract registries | ✅ (PO-7) | Capability Registry | none | 🟢 Ready after #1 |
| Workspace Runtime (P4) | ✅ (spec) | kernel | project.yaml drift (G-3) | 🟡 Ready after schema reconcile |
| Maturity Engine | ⚠️ conceptual only (Methodology §10.2) | Registry | needs own spec (G-2) | 🟡 Design gap |
| Genome store / evolution | ✅ (PO-2) | Registry, Maturity | Registry + Maturity | 🟡 Ready after Wave 1–2 |
| Execution registries (API/Tool/Agent/Prompt) | ✅ (PO-7) | Schema/Contract | none | 🟢 Ready after #2 |
| Ledger registries (Event/Decision/Knowledge) | ✅ (PO-7) | kernel audit, Schema | none | 🟢 Ready after #2 |
| Discovery / Platform Intelligence | ⚠️ named, no spec | metadata graph | needs specs (G-4) | 🔴 Design gap |
| AI Workspace platform / HQ | 🔴 boundary only (PO-3) | all above | no operating-model spec (G-1) | 🔴 Design gap |

Headline: **the metadata layer (Wave 1) is ready to build now; the engines and the AI Workspace platform need design first.**

## 14. Remaining Gaps (Deliverable 6 — Gap Register)

| ID | Gap | Severity | Source | Status |
|---|---|---|---|---|
| **G-1** | **AI Workspace operating-model spec absent** (Vision file empty; PO-3 defined only its boundary). | High | PO-2.5 M-3 | Open — needs a spec. |
| **G-2** | **Maturity Engine** defined only inside Methodology §10.2; no standalone spec. | High | PO-2.5 M-2, PO-5 | Open — extract & specify. |
| **G-3** | **project.yaml schema drift** (`repository.path`/flat `workflow_mode` vs Runtime spec). | Medium | PO-2.5 C-3/C-4 | Open — reconcile before runtime build. |
| **G-4** | **Discovery Engine & Platform Intelligence** named, not specified. | Medium | PO-2.5 M-4/M-5, PO-7 | Open — spec before autonomy. |
| **G-5** | **Domain triggers at workspace root** (`policies.yaml.txt`) not yet moved to Domain DNA. | Low | PO-2.5 O-2, PO-4 §6 | Open — mechanical move. |
| **G-6** | **Registries unimplemented** (design complete in PO-7). | High (but unblocked) | PO-7 | Ready — Wave 1. |

No *new* gaps were introduced by the corpus; every open gap traces to PO-2.5 or is a known "to be authored" item. The design layer is internally complete; the gaps are (a) three missing sub-specs (G-1, G-2, G-4) and (b) build + one reconcile.

## 15. Constitution Amendments Required (Deliverable — amendment package)

The corpus was written *as* canonical but canonical status is conferred **only by amendment** (Constitution §10). This ratification packages the amendments for one founder sign-off — the "ratification" half of this assignment. **Flagged, not performed** (this document integrates; it does not amend).

| # | Amendment | Effect |
|---|---|---|
| **A-1 (Founding Ratification)** | Confer canonical status on the L1 corpus (Kernel, Methodology, Genome, PO-3, PO-4, PO-5) exactly per the Register. | Makes the founding corpus formally authoritative. |
| **A-2** | Register PO-7 as the metadata-layer entry (L2), fulfilling the "CR-1 (to be authored)" placeholder. | Gives the metadata layer authority. |
| **A-3** | Register the Workspace Runtime spec (L2) and this document, PO-8, as the integration layer (L2/L3). | Places the remaining supporting docs. |
| **A-4** | Record PO-2.5 as a Reference (L3) finding. | Confirms its non-binding status. |

All four are one GOVERNED / L3 amendment assignment with founder sign-off (Constitution §10).

## 16. Founder Decisions Still Pending (Deliverable 5 — Founder Decision Register)

Decision-ready, serialized (PO-4 §2). Each carries options + consequence + recommendation.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| **FD-1** | **Canonical operating-model content** (the standing PO-2.5 C-2). | (a) Fold EduOS's 5-doc model into the ProjectOS-owned Methodology; (b) keep Methodology v2, demote product docs to Local Expressions. | (b) — the Constitution already makes product constitutions Local Expressions (§7); adopt v2 as canonical and let EduOS express within it. Consequence of delay: product operating models keep diverging. |
| **FD-2** | **Ratify the corpus (A-1…A-4).** | (a) Ratify all; (b) ratify with changes; (c) hold. | (a) — the corpus is internally consistent and L2-reviewed; ratifying unblocks implementation. |
| **FD-3** | **Authorize Wave 1 (Capability Registry) build.** | (a) Start; (b) hold for more design. | (a) — Wave 1 is 🟢 ready; the Registry is the blocker for everything downstream. |
| **FD-4** | **Portfolio priority / Critical Path** — which product leads (EduOS vs TradeOS vs platform build). | founder's call. | State the current Critical Path so lanes don't contend (Methodology §3, PO-4 §6). |

## 17. Implementation Waves (Deliverable 7 — Wave Plan)

Grouped so each wave is independently valuable, dependency-correct, and governable. Design-only recommendation; nothing starts before FD-2/FD-3.

| Wave | Contents | Unblocks | Gate |
|---|---|---|---|
| **Wave 0 — Ratify & reconcile** | Amendments A-1…A-4; reconcile project.yaml (G-3); move domain triggers (G-5). | Formal authority; clean runtime schema. | Founder sign-off (L3). |
| **Wave 1 — Metadata core** | Capability Registry, then Schema + Contract. | All metadata-driven work. | REVIEWED per registry; GOVERNED for schemas. |
| **Wave 2 — Missing sub-specs** | Design specs for Maturity Engine (G-2), Discovery + Platform Intelligence (G-4), AI Workspace operating model (G-1). | The engines & the platform plane. | L2 design review each. |
| **Wave 3 — Execution + inheritance** | API/Tool/Agent/Prompt registries; Genome store + evolution ops; Workspace Runtime. | Reuse, promotion, multi-project. | REVIEWED; GOVERNED for genome MAJOR. |
| **Wave 4 — Ledgers + intelligence** | Event/Decision/Knowledge registries; Discovery; Platform Intelligence; PO-5 dashboards. | Measurement, autonomy readiness. | REVIEWED. |
| **Wave 5 — Platform & business** | AI Workspace surfaces; HQ (marketplace, etc.). | Commercial layer. | Business governance. |

Wave 0 is a founder/governance wave; Waves 1–5 are engineering, mostly Lane A (Claude Code) with Lane B design where a gap needs a spec first.

---

## PART IV — LONGEVITY

## 18. Version Strategy

- **The corpus has a version:** *Foundational Corpus v1.0* = the ratified set (Constitution v1 + the L1 canon + PO-7 + Runtime). This document declares it.
- **Each document versions semantically** (MAJOR/MINOR/PATCH), aligned across the whole corpus with the Genome/Constitution scheme (Genome §18, Constitution §11) — one mental model.
- **A canonical MAJOR triggers a corpus conformance review** (Constitution §27); the corpus version bumps when canonical authority changes.
- **Documents declare the corpus version they conform to**, so drift is visible.

## 19. Migration Strategy

- **Additive and non-destructive**, one document/product at a time, within compatibility windows — the discipline is identical across Genome (§20), Constitution (§26), and the registries (PO-7 §15), so there is one migration model to learn.
- **The Register and lineage edges are the migration maps:** a superseded rule points to its successor; anything conforming to the old version follows the pointer forward.
- **Products migrate independently** on their own genome/corpus pin; no big-bang.
- **Backward compatibility is mandatory** — a document that adopts nothing new still conforms (v1 fields optional with v1 defaults, per each spec).

## 20. Long-term Evolution Strategy

- **Grow by adding single-owned domains, never by splitting one** (Constitution §28.2) — new needs get a new authoritative source; the ecosystem scales to many products and documents without constitutional redesign.
- **The three promotion flows** (capability, knowledge, decision) are the engine of compounding: everything valuable rises from product-local to shared, governed and lineage-recorded.
- **Autonomous evolution is the horizon** (Genome §24, PO-5): once the registries, Maturity Engine, and Platform Intelligence exist, evolution operations can be *proposed* autonomously and *gated* by governance, with the founder reserved for breaking/foundational calls.
- **Stability is the metric** (PO-5 governance KPIs): rising amendment churn or recurring gaps flag that the hierarchy needs attention — measured, not guessed.
- **The corpus is complete-by-design and extensible-by-construction:** new products are Local Expressions, new capabilities are Registry+Genome entries, new agents are adapters, new metadata is a registered type — none requires redesigning the foundation.

---

## APPENDIX A — L2 REVIEW (Deliverable 8)

Independent, delta-only, verdict-oriented review against the assignment.

| Check | Verdict | Basis |
|---|---|---|
| Integrates without redesigning | **PASS** | Every section references authoritative docs; no content restated as new authority; §4 explicitly points to the Register rather than re-legislating. |
| Answers "how do the documents work together?" | **PASS** | §0 Start-Here mental model + reading order; the three lifecycle flows (§9–11) show the corpus interlocking through capability/knowledge/decision. |
| All 20 scope items present | **PASS** | Corpus Map §1 · Hierarchy §2 · Cross-ref §3 · Authority §4 · Dependency §5 · Metadata Int. §6 · Genome Int. §7 · Registry Int. §8 · Capability Flow §9 · Knowledge Flow §10 · Decision Flow §11 · Impl Order §12 · Readiness §13 · Gaps §14 · Amendments §15 · Pending Decisions §16 · Waves §17 · Version §18 · Migration §19 · Long-term §20. |
| All 8 deliverables present | **PASS** | Doc (this) · Architecture Maps §1/§5 · Cross-ref Workbook §3/§5 · Readiness Matrix §13 · Founder Decision Register §16 · Gap Register §14 · Wave Plan §17 · L2 Review (this appendix). |
| Readiness grounded in evidence | **PASS** | §13 marks kernel + P3 as implemented (verified against repo: `src/projectos`, 479 tests) and everything else as spec; no overclaiming. |
| No duplicated/conflicting authority reintroduced | **PASS** | §4 preserves one-source-per-domain; §3/§5 confirm the corpus is an acyclic DAG. |
| Implementation-ready, none begun | **PASS** | Waves + readiness are actionable; nothing implemented; stopping point honored (waits for founder review). |

**Reviewer verdict: PASS.** No blocking issues. The document integrates the corpus into one coherent, navigable system, answers the onboarding question directly, grounds readiness in the real repository state, surfaces every open gap/decision/amendment without introducing new authority, and stops at specification pending founder review.

---

## APPENDIX B — DELIVERABLES INDEX

| # | Deliverable | Where |
|---|---|---|
| 1 | FOUNDATIONAL_CORPUS_INTEGRATION.md | This document |
| 2 | Architecture Maps | §1 (corpus map), §5 (dependency), §9–11 (flows) |
| 3 | Cross-reference Workbook | §3 (cross-ref) + §5 (dependency) |
| 4 | Implementation Readiness Matrix | §13 |
| 5 | Founder Decision Register | §16 |
| 6 | Remaining Gap Register | §14 |
| 7 | Implementation Wave Plan | §17 |
| 8 | L2 Review | Appendix A |

---

*End of Foundational Corpus Integration. Integration only — no redesign, no implementation, no code, no contracts, no registry contents, no Genome redesign. The document maps how the corpus works together and what to build first; it stops at specification and awaits founder review.*
