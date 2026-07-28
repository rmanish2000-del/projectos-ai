# Platform Genome v1.0

**The permanent DNA inherited by every current and future product in the ecosystem.**

**Status:** PO-2 — proposed canonical Platform Genome. Design only; no implementation, no code, no contracts, no repository changes, no Capability Registry changes.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Depends on / amends alongside:** `PROJECTOS_METHODOLOGY_V2.md` (the operating model), the Capability Registry (CR-1, the catalog), `PROJECTOS_V0_1_FOUNDATION_SPEC.md` (the kernel), `PROJECTOS_WORKSPACE_RUNTIME_SPEC.md` (the runtime).
**Applies to:** AI Workspace, AI Workspace HQ, ProjectOS, TradeOS, EduOS, UrjaOps, Legal Engineering, and every future ecosystem product — without architectural redesign.

---

## 0. What the Platform Genome is — and, precisely, what it is not

The single most important thing about the Genome is where its boundary sits. It occupies exactly one job in the ecosystem — **inheritance and lineage** — and it must not absorb the jobs next to it. The acceptance criteria for this assignment are, first and foremost, that this boundary is unambiguous.

| The Genome **is** | The Genome **is not** |
|---|---|
| The **inheritance architecture** — what every product is born with, and how it inherits it. | **Not** the Capability Registry (CR-1). The Registry is the *catalog* — the list of capabilities and their maturity. The Genome adds *lineage, layer placement, and evolution* on top of those records; it never re-stores the catalog. |
| The **lineage & family-tree model** — the ancestry of every capability and how DNA is related across products. | **Not** ProjectOS Methodology. The Methodology is *how work flows* (assignments, lanes, verification). The Genome is *what is inherited*. Genome changes are **executed as** Methodology assignments; they are not the Methodology. |
| The **evolution model** — the governed operations (promote, demote, split, merge, retire) by which inherited DNA changes over time, with full ancestry preserved. | **Not** AI Workspace. AI Workspace (and AI Workspace HQ) is the *implementation platform* that hosts and realizes products. The Genome is implementation-independent; AI Workspace is one concrete realization of it. |
| The **versioning, compatibility, and migration model** for the inherited core. | **Not** the Capability Maturity Engine. Maturity grades *readiness* (M0–M4). The Genome consumes maturity as a *threshold* for evolution operations but owns the *act of inheritance-layer placement*. |

**One-line definitions, side by side, so no responsibility is duplicated:**

- **Methodology** — *how* we build (process).
- **Capability Registry** — *what* capabilities exist and how mature (catalog).
- **Capability Maturity Engine** — *how ready* a capability is (grading).
- **Platform Genome** — *what is inherited, from whom, and how that DNA evolves* (genetics).
- **AI Workspace / HQ** — *where* it runs (implementation & control plane).

Everything below stays inside the Genome's lane. Where a concept lives in a neighboring system, this document *references* it and defines the *relationship*, never a second copy of it (§23 makes every such boundary explicit).

---

## PART I — VISION & ARCHITECTURE

## 1. Platform Genome Vision

The Genome exists so that **no product ever builds its own foundations again.** Every product in the ecosystem is born inheriting a shared, versioned, evolving core — its DNA — and specializes only at the edges. The vision is a living inheritance system: a single genome from which AI Workspace, TradeOS, EduOS, UrjaOps, Legal Engineering, and every future product descend as siblings, sharing the same foundational genes, tracing every capability to its ancestry, and evolving that shared core through governed, auditable, eventually-autonomous operations rather than through forks and rewrites.

Three outcomes define success:

1. **Inheritance over reinvention.** A new product's foundational cost trends toward zero, because it inherits rather than rebuilds. The *n*-th product is dramatically cheaper to stand up than the first.
2. **Traceable lineage.** Every capability in every product can be walked back to its origin, its promotions, its splits and merges — the ecosystem has a complete family tree, and nothing exists without ancestry.
3. **Governed, autonomous-ready evolution.** The shared core changes safely: every change to inherited DNA is versioned, compatibility-checked, migration-pathed, and lineage-recorded — structured well enough that evolution can eventually be proposed and executed autonomously under governance.

The Genome is deliberately *anti-fork*: divergence is the enemy. Where the Methodology fights founder-decision fatigue, the Genome fights architectural entropy — the slow drift of six products into six incompatible foundations.

---

## 2. Genome Architecture

The Genome is a structural layer in the ecosystem, sitting between the operating model and the products, drawing capability records from the Registry and expressing them as inheritable DNA.

### 2.1 Architecture diagram (Deliverable 2)

```
                          ┌───────────────────────────────────────────────┐
   OPERATING MODEL        │            ProjectOS Methodology v2            │
   (how work flows)       │   assignments · lanes · verification levels    │
                          └───────────────────────┬───────────────────────┘
                                                  │ executes Genome changes
                                                  │ as Lane-B governed assignments
                          ┌───────────────────────▼───────────────────────┐
   INHERITANCE LAYER      │               PLATFORM GENOME  (this doc)      │
   (what is inherited)    │  ┌──────────────────────────────────────────┐  │
                          │  │  Platform DNA  (universal, inherited)     │  │
                          │  │  Capability DNA (inheritable genes)       │  │
                          │  │  Lineage / Family Tree   Evolution ops    │  │
                          │  │  Genome Versioning · Compatibility        │  │
                          │  │  Platform Knowledge (heritable knowledge) │  │
                          │  └──────────────────────────────────────────┘  │
                          └───┬───────────────┬───────────────┬───────────┘
       reads capability       │               │ inherited by  │
       records from ▲         │               │ (by reference,│
                    │         ▼               ▼  version-pinned)▼
   ┌────────────────┴───┐  ┌──────────┐  ┌──────────┐  ┌────────────────────┐
   │ Capability Registry│  │AI        │  │ TradeOS  │  │ UrjaOps · EduOS ·  │
   │ (CR-1, catalog +   │  │Workspace │  │          │  │ Legal · HQ · future│
   │  maturity records) │  │+HQ       │  │          │  │  + Domain DNA packs│
   └────────┬───────────┘  └──────────┘  └──────────┘  └────────────────────┘
            │ grades feed evolution thresholds
   ┌────────▼───────────┐   ┌───────────────────┐   ┌────────────────────────┐
   │ Capability Maturity│   │ Capability        │   │ Platform Intelligence  │
   │ Engine (readiness) │   │ Discovery Engine  │   │ (analytics over lineage)│
   └────────────────────┘   └───────────────────┘   └────────────────────────┘
        (threshold source)     (reads family tree)      (reads genome substrate)
```

### 2.2 Architectural stance

- **Implementation-independent.** The Genome describes inheritance abstractly. AI Workspace realizes it; a future host could realize it differently without the Genome changing.
- **Reference, not copy.** Products inherit DNA *by reference at a pinned genome version* — they do not embed private copies of the core. This is what prevents divergence.
- **Additive at the edges, immutable at the core.** Platform DNA is extended only at declared points; it is never overridden or forked. Specialization happens in Product and Domain DNA.
- **Every change is an event.** Inheritance-layer changes are discrete, versioned, lineage-recorded evolution events — never silent edits.

---

## 3. Genome Layers (Deliverable 4 — Genome Layer Model)

The inherited core is organized as concentric layers, from the universal invariant center outward to product-specific edges. Inner layers are inherited by more products and change most rarely; outer layers are increasingly product- and domain-specific and change freely.

```
      ┌─────────────────────────────────────────────────────────────┐
      │  L4  DOMAIN DNA        domain packs: rules, vocabulary        │  most specific
      │  ┌───────────────────────────────────────────────────────┐   │  changes freely
      │  │  L3  PRODUCT DNA    identity, expressed genes, config   │   │
      │  │  ┌─────────────────────────────────────────────────┐   │   │
      │  │  │  L2  CAPABILITY DNA   inheritable genes (M3–M4)   │   │   │
      │  │  │  ┌───────────────────────────────────────────┐   │   │   │
      │  │  │  │  L1  GENOME SERVICES   conventions, gates, │   │   │   │
      │  │  │  │       verification levels, lane model      │   │   │   │
      │  │  │  │  ┌─────────────────────────────────────┐   │   │   │   │
      │  │  │  │  │  L0  PLATFORM CORE   kernel, invariants│  │   │   │   │  most universal
      │  │  │  │  │      evidence model, fail-closed       │  │   │   │   │  changes = genome
      │  │  │  │  └─────────────────────────────────────┘   │   │   │   │  MAJOR events
      │  │  │  └───────────────────────────────────────────┘   │   │   │
      │  │  └─────────────────────────────────────────────────┘   │   │
      │  └───────────────────────────────────────────────────────┘   │
      └─────────────────────────────────────────────────────────────┘
```

| Layer | Name | Contents | Inherited by | Change class |
|---|---|---|---|---|
| **L0** | Platform Core | Kernel: assignment lifecycle, evidence verification, audit, the operating invariants, fail-closed defaults. | Every product, wholly, non-optionally. | Genome MAJOR. |
| **L1** | Genome Services | Shared conventions, quality gates, verification levels, the lane model, repository-organization principles. | Every product, wholly; extensible at declared points. | Genome MINOR (additive) / MAJOR (breaking). |
| **L2** | Capability DNA | Promoted platform capabilities (M3–M4) as inheritable genes, each with a lineage. | By reference, version-pinned; expression is chosen per product. | Evolution operations (§12–17). |
| **L3** | Product DNA | A product's identity, its expressed gene set, its product-local capabilities (M0–M2), its lane/adapter configuration. | Owned by one product; not inherited. | Product-local; free. |
| **L4** | Domain DNA | The domain pack: domain rules, vocabulary, quality overrides, templates. | Owned by one product; not inherited. | Product-local; free. |

The rule that ties the layers together: **inheritance strength decreases outward, mutability increases outward.** L0/L1 are inherited by all and change rarely and formally; L3/L4 are product-owned and change freely. L2 is the hinge — the shared capability genes whose movement between "product-local" and "inherited" is exactly what the evolution model governs.

---

## PART II — INHERITANCE

## 4. Inheritance Model (Deliverable 3 — Inheritance Diagram)

A product is not authored from scratch; it is **composed by inheritance**:

```
   effective_genome(product) =
        L0 Platform Core          (inherited whole, non-optional)
      ⊕ L1 Genome Services        (inherited whole, extensible at declared points)
      ⊕ L2 Capability DNA         (inherited BY REFERENCE, version-pinned,
      │                            only the genes the product EXPRESSES)
      ⊕ L3 Product DNA            (the product's own identity + local capabilities)
      ⊕ L4 Domain DNA             (the product's own domain pack)
```

```
                 PLATFORM GENOME (pinned at version vX)
                 ├── L0 Platform Core ───────────────┐
                 ├── L1 Genome Services ──────────────┤  inherited whole
                 └── L2 Capability DNA library ───┐   │
                       gene: evidence-verify (M4) │   │
                       gene: telemetry-ingest (M3)│   │ inherited by reference
                       gene: doc-generate (M3)    │   │ (product expresses a subset)
                        ...                        │   │
        ┌───────────────────────────┬──────────────┴───┴─────────────────┐
        ▼                           ▼                                     ▼
   ┌──────────┐              ┌──────────┐                        ┌──────────────┐
   │AI Workspace            │ TradeOS  │                        │  UrjaOps     │
   │ expresses:            │ expresses:│                        │ expresses:   │
   │  evidence-verify      │ evidence- │                        │ evidence-    │
   │  telemetry-ingest     │  verify   │                        │  verify      │
   │  doc-generate         │ risk-kernel(local M1)              │ telemetry-   │
   │ + Product DNA         │ + Domain  │                        │  ingest      │
   │ + Domain DNA          │   DNA     │                        │ + Domain DNA │
   └──────────┘              └──────────┘                        └──────────────┘
     siblings — no product inherits from another; all inherit vertically from the Genome
```

Key properties:

- **Inheritance is vertical only.** Products inherit from the Genome, never from each other. AI Workspace and TradeOS are *siblings*; a capability shared between them is a shared *gene from the Genome*, not a copy passed sideways.
- **Inheritance is by reference and version-pinned.** A product pins a genome version; it inherits the exact DNA at that version until it deliberately migrates (§20).
- **Availability vs. expression.** Every inheritable gene is *available* to every product; a product chooses which to *express*. (Biological analogy: same DNA, differentiated cells.) Expression is a Product-DNA choice; it never copies or mutates the gene.

## 5. Inheritance Rules

1. **Inherit the core whole.** L0 and L1 are inherited in full and non-optionally. A product cannot decline, fork, or partially inherit the Platform Core.
2. **No override of inherited DNA.** Platform DNA and inherited Capability DNA cannot be overridden. Products extend only at *declared extension points*; anywhere else, the inherited gene is authoritative.
3. **Specialize additively.** A product may add Product-local capabilities and Domain DNA freely, but may never remove or weaken an inherited gene or a Platform guarantee.
4. **Express a subset.** A product declares which inheritable Capability DNA it expresses. Non-expression is silent (the gene is simply unused); it is never deletion.
5. **Pin, then migrate deliberately.** A product inherits at a pinned genome version. Moving to a newer version is a deliberate, migration-pathed act (§20), never automatic for MAJOR changes.
6. **No sideways inheritance.** Capability reuse between products happens only by both expressing a shared inherited gene — never by copying one product's local capability into another. A sideways copy is a lineage violation and a review-blocking issue.
7. **Lineage is mandatory.** Anything inheritable carries a lineage record (§10). A gene with no ancestry cannot enter the inherited layer.

## 21. Cross-product Inheritance

Cross-product inheritance is the same vertical model applied across the whole ecosystem at once. The named products — AI Workspace, AI Workspace HQ, ProjectOS, TradeOS, EduOS, UrjaOps, Legal Engineering — are all siblings descending from one Genome.

- **One genome, many expressions.** Each product expresses a different subset of the same inheritable DNA plus its own Product and Domain DNA. AI Workspace HQ, as the control plane, typically expresses the widest gene set; a focused product like Legal Engineering expresses a narrow set plus heavy Domain DNA.
- **Shared genes are literally the same gene.** When TradeOS and UrjaOps both use evidence-verification, they express the *same* L2 gene at the same or compatible genome version — not two lookalike implementations. This is what makes an improvement to that gene benefit both at once.
- **Version skew is explicit.** Products may pin different genome versions; the Compatibility model (§19) defines which cross-product sharing is safe across a version gap and when migration is required.
- **New products are onboarded by inheritance.** A future ecosystem product is stood up by pinning the current genome, expressing the genes it needs, and adding its Domain DNA — with zero foundational rebuild. This is the concrete meaning of "supports future products without architectural redesign."

---

## PART III — THE DNA MODEL

The ecosystem's DNA exists at **three scopes** (Platform, Product, Domain), populated by one **molecular unit** (Capability DNA). Scopes answer *how widely inherited*; the unit answers *what a heritable gene actually is*.

## 6. Platform DNA

**Platform DNA is the universal, non-optional genome inherited by every product** — the contents of layers L0 and L1. It comprises the kernel and its invariants (assignment lifecycle, evidence-based verification, audit, fail-closed), the operating-model bindings (verification levels, quality gates, lane model), and the shared conventions (repository organization, determinism, portability).

Properties: inherited whole by every product; immutable except through genome versioning; extensible only at declared points; changing it is always a genome MAJOR/MINOR event affecting the entire ecosystem. Platform DNA is what makes any two products in the ecosystem *recognizably the same species*.

## 7. Product DNA

**Product DNA is what makes a specific product itself** — layer L3. It comprises the product's identity (its name, its purpose, its bound repository/host), its **expressed gene set** (which inheritable Capability DNA it turns on), its product-local capabilities (M0–M2 genes not yet promoted), and its configuration of the operating model (which lanes, which agent adapters).

Properties: owned by exactly one product; not inherited by anyone; freely mutable; may add but never subtract from inherited DNA. Product DNA is the differentiation layer — the same genome expressed as a distinct organism.

## 8. Domain DNA

**Domain DNA is the specializing genetic material at the ecosystem's edge** — layer L4, realized as the domain pack. It carries the domain's rules, vocabulary, risk triggers, quality overrides, and templates: solar-project rules for UrjaOps, trading methodology for TradeOS, legal-matter rules for Legal Engineering, education models for EduOS.

Properties: owned by one product; additive over Platform DNA (may raise a workflow mode, add a governed trigger, add vocabulary — never remove a core guarantee); the only place domain-specific logic is permitted to live. Domain DNA is what keeps the Platform Core domain-neutral: because domain rules have a designated home at the edge, they never contaminate the shared center.

## 9. Capability DNA (Deliverable 5 — Capability DNA Model)

**Capability DNA is the heritable unit — the gene.** A capability (evidence verification, telemetry ingestion, document generation, a risk kernel, scheduling) is expressed in the Genome as a Capability DNA descriptor: the structural, inheritable representation of that capability. It is the molecular unit that populates the DNA scopes — a gene can sit at Platform scope (inheritable, L2) or Product scope (local, L3).

**Boundary with the Capability Registry (critical, no duplication):** the Registry (CR-1) stores the capability's *record* — its identity, its maturity grade, its consumers, its status. Capability DNA references that record and adds only the **genetic** information the Registry does not hold: the gene's **layer placement** (inherited vs. local), its **lineage** (ancestry edges), its **expression availability**, and its **evolution history** (the promote/demote/split/merge/retire events it has undergone). The Registry answers *"what is this capability and how mature?"*; Capability DNA answers *"where does it sit in inheritance, where did it come from, and how has it changed?"*

Conceptual composition of a Capability DNA descriptor (design-level, not a contract — authoring contracts is out of scope):

| Facet | What it expresses | Source of truth |
|---|---|---|
| **Registry reference** | Which catalog record this gene corresponds to. | Capability Registry (referenced, not copied). |
| **Maturity grade** | M0–M4 readiness. | Capability Maturity Engine (referenced). |
| **Layer placement** | Platform-inheritable (L2) or product-local (L3). | **Genome (owned here).** |
| **Lineage** | Parent/derivation edges — the ancestry (§10). | **Genome (owned here).** |
| **Expression availability** | Which products may express it; expressed-by set. | **Genome (owned here).** |
| **Evolution history** | Ordered record of evolution events on this gene. | **Genome (owned here).** |
| **Compatibility band** | Genome versions across which this gene is inheritable. | **Genome (owned here).** |

The four "owned here" facets are precisely the genetics the Genome contributes and nothing else in the ecosystem holds — this is the concrete no-duplication guarantee at the capability level.

---

## PART IV — LINEAGE & FAMILY TREE

## 10. Capability Lineage

**Lineage is the ancestry of a gene.** Every Capability DNA descriptor records where it came from, as a set of directed edges to its ancestors and the event that created the relationship:

| Lineage edge | Meaning |
|---|---|
| `origin` | The gene was first authored (M0) in a named product — the root of its ancestry. |
| `promoted-from` | The gene was promoted from product-local to platform-inheritable (§13). |
| `derived-from` | The gene was created by specializing or forking an ancestor at a version (rare; governed). |
| `split-from` | The gene is one child of a capability that was split (§15). |
| `merged-from` | The gene absorbed one or more predecessors that were merged into it (§16). |
| `superseded-by` | The gene was retired or demoted in favor of a named successor (§14, §17). |

Lineage is **append-only and immutable**: an edge, once recorded, is never rewritten. Evolution operations add edges and events; they never erase ancestry. This is what makes the family tree a complete, auditable record — the genetic analogue of the kernel's append-only audit chain.

## 11. Capability Family Tree

The **family tree** is the whole ecosystem's lineage as a single directed acyclic graph: every capability (past and present) is a node; every lineage edge is an arc. It answers, for any capability: where did this come from, what did it come from, what descended from it, and what superseded it.

### 11.1 Family-tree diagram (illustrative)

```
   evidence-check@AI-Workspace (origin, M0)
        │ promoted-from
        ▼
   evidence-verify (L2 gene, M3) ───────────────► M4 (foundational; used by 5 products)
        │ split-from                     merged-from ▲
        ├──────────────► commit-verify (M3)         │
        └──────────────► approval-verify (M3)        │
                                                     │
   telemetry-ingest@UrjaOps (origin, M1) ───────────┘
        │ superseded-by
        ▼
   telemetry-ingest-v2 (M3)   [old node retained in tree, marked retired]
```

Properties of the family tree:

- **Complete.** Every gene has a path back to an `origin`; nothing exists without ancestry (Inheritance Rule 7).
- **Acyclic.** A gene cannot be its own ancestor; split/merge produce new nodes rather than cycles.
- **Non-destructive.** Retired and demoted nodes remain in the tree as history, marked, never deleted — the tree is the ecosystem's memory of how its capabilities came to be.
- **Read by others, owned here.** The Discovery Engine searches the tree, and Platform Intelligence analyzes it, but the tree's structure is authored only by Genome evolution operations.

---

## PART V — EVOLUTION

## 12. Capability Evolution (Deliverable 6 — Evolution Model)

The inherited core is not static; it evolves through a closed set of **five governed operations** on Capability DNA. Every operation shares the same discipline: it is **triggered by evidence** (usually a Maturity Engine threshold or a Platform Intelligence signal), it **preserves lineage** (adds edges/events, erases nothing), it **migrates consumers** before removing anything they depend on, and it runs at a **verification level** proportional to how many products the change touches.

| Operation | Direction | Typical trigger | Lineage effect | Verification level |
|---|---|---|---|---|
| **Promotion** (§13) | local → inherited (or M-grade up) | Maturity reaches M2→M3; reuse demand. | add `promoted-from`. | L2, or **L3** if it changes the inherited layer for all. |
| **Demotion** (§14) | inherited → local (or M-grade down) | Instability, contract erosion, low reuse. | add `superseded-by` (if replaced) + event. | **L3** (touches every consumer). |
| **Split** (§15) | one → many | A gene accreted two responsibilities. | children get `split-from`; parent retired. | **L3** if the parent is inherited. |
| **Merge** (§16) | many → one | Duplicate/convergent genes discovered. | survivor gets `merged-from`; predecessors retired. | **L3** if any input is inherited. |
| **Retirement** (§17) | active → sunset | Superseded, obsolete, or unsafe. | add `superseded-by` + retirement event. | L2–**L3** by consumer count. |

All five are executed **as ProjectOS Methodology assignments in Lane B** — the Genome defines the *rules and effects*; the Methodology provides the *execution and verification*. This is the clean seam between the two systems.

## 13. Capability Promotion Rules

Promotion moves a gene from product-local (L3) to platform-inheritable (L2), or raises its maturity within the inherited layer.

1. **Eligibility is evidence-gated.** A gene is eligible for promotion to inherited only when the Maturity Engine grades it **M2+** and there is demonstrated cross-product reuse demand (surfaced by the Discovery Engine or an improvement signal).
2. **Generalize before promoting.** The gene's contract must be domain-neutral and its dependencies clean; a gene carrying domain assumptions cannot be promoted until they are moved to Domain DNA.
3. **Promotion is governed.** Because it changes what every product may inherit, promotion to the inherited layer is **L3** and issues a genome MINOR version (additive new inheritable gene).
4. **Record the lineage.** A `promoted-from` edge is added; the origin product is preserved as ancestry.
5. **Expression stays opt-in.** Promotion makes the gene *available* to all; it does not force any product to express it.

## 14. Capability Demotion Rules

Demotion is the reverse: an inherited gene is withdrawn from the inherited layer, or its maturity grade is lowered.

1. **Trigger by evidence of decay.** Repeated instability, contract erosion, security concern, or reuse falling to a single consumer are the valid triggers — never opinion.
2. **Consumers first.** No inherited gene is demoted until every expressing product has a migration path (to a successor gene or to a product-local copy). Demotion that would strand a consumer fails closed.
3. **Always governed.** Demotion touches every consumer, so it is **L3** and issues at least a genome MINOR (or MAJOR if it removes an inheritable contract others depend on).
4. **Preserve ancestry.** The gene remains in the family tree, marked demoted, with a `superseded-by` edge if a successor exists.
5. **No silent regrade.** A maturity downgrade on an inherited gene is itself a recorded evolution event, because it changes the inherited layer's reliability guarantees.

## 15. Capability Split Rules

Split divides one capability into two or more when it has accreted separable responsibilities.

1. **Trigger: conflated responsibilities.** A gene that two different consumers use for two different reasons is a split candidate.
2. **Children are new nodes with lineage.** Each child gene is created with a `split-from` edge to the parent; the parent is retired (§17), not mutated.
3. **Migrate expressions.** Every product expressing the parent is migrated to the appropriate child(ren) before the parent is retired.
4. **Governed when inherited.** Splitting an inherited gene is a breaking change to its contract for all consumers → **L3**, genome MAJOR.
5. **Preserve the whole ancestry.** The parent node stays in the family tree as the common ancestor of its children.

## 16. Capability Merge Rules

Merge converges two or more capabilities into one when they turn out to be the same thing.

1. **Trigger: discovered duplication or convergence.** Two genes doing substantially the same job — often surfaced by the Discovery Engine or Platform Intelligence — are merge candidates.
2. **One survivor, recorded predecessors.** A single surviving gene absorbs the others; it receives `merged-from` edges to each predecessor; the predecessors are retired.
3. **Reconcile contracts.** The survivor's contract must cover every predecessor's consumers, or those consumers are migrated explicitly; unresolved coverage gaps fail closed.
4. **Governed when any input is inherited.** Merging inherited genes is contract-affecting for their consumers → **L3**.
5. **Non-destructive.** All predecessor nodes remain in the family tree as ancestors of the survivor.

## 17. Capability Retirement Rules

Retirement sunsets a capability that is superseded, obsolete, or unsafe.

1. **Trigger: superseded or unfit.** A gene replaced by a successor (via demotion, split, or merge), made obsolete, or found unsafe is retired.
2. **Migration path is mandatory.** Retirement requires a stated migration path for every consumer; a gene with live, un-migrated consumers cannot be retired (fail closed).
3. **Retire ≠ erase.** The gene is marked retired and made non-inheritable and non-expressible, but it **remains in the family tree** as ancestry, with a `superseded-by` edge to its successor where one exists.
4. **Proportional verification.** Retiring a product-local gene is L2; retiring a widely-inherited gene is **L3**.
5. **Deprecate, then retire.** A grace/deprecation window precedes retirement so consumers can migrate; the window is a recorded state, not an informal courtesy.

---

## PART VI — VERSIONING, COMPATIBILITY & MIGRATION

## 18. Genome Versioning

The Genome is versioned as a whole, so products can pin to a known DNA and migrate deliberately. Versioning is semantic, driven by the *impact on inheritors*:

| Bump | Meaning | Examples |
|---|---|---|
| **MAJOR** | A breaking change to Platform DNA or to an inherited (M3–M4) gene's contract. Requires product migration. | Split of an inherited gene; removal/contract-break of an L0/L1 guarantee; demotion removing an inherited contract. |
| **MINOR** | An additive, backward-compatible change. Inherited automatically on migration; safe. | New inheritable gene (promotion); new extension point; new convention; additive L1 service. |
| **PATCH** | A non-contractual correction with no inheritance effect. | Clarification, defect fix that preserves the contract. |

Rules: MAJOR changes are always L3 and always carry a migration path (§20); a product's pinned version records exactly which DNA it inherits; and a genome version is itself an auditable, lineage-bearing artifact (each version records the evolution events that produced it).

## 19. Genome Compatibility Rules (Deliverable 8 — Compatibility Matrix)

Compatibility governs which products and which genes can safely interoperate across a version gap.

**Rules:**

1. **Same MAJOR = compatible.** A product pinned to genome `vX.*` may express any inherited gene available within `vX` and interoperate with any sibling on the same MAJOR.
2. **MINOR-behind = compatible, upgrade-safe.** A product one or more MINORs behind within the same MAJOR is compatible; it simply hasn't expressed the newer additive genes yet. Upgrading is non-breaking.
3. **MAJOR-behind = migration-required.** Cross-MAJOR interoperation for a contract-affecting gene requires the trailing product to migrate; sharing across a MAJOR gap for a broken contract fails closed.
4. **Gene compatibility band.** Each inherited gene declares the genome MAJORs across which it is inheritable; expressing a gene outside its band is refused.
5. **No forward compatibility assumed.** A product never assumes a newer genome's genes; it inherits only what its pinned version offers.

**Compatibility matrix (template, Deliverable 8):**

| Product ↓ / Genome → | v1.x (current) | v2.x (next MAJOR) |
|---|---|---|
| AI Workspace | ✔ native | migration-required |
| AI Workspace HQ | ✔ native | migration-required |
| ProjectOS | ✔ native | migration-required |
| TradeOS | ✔ (pin v1) | migration-required |
| EduOS | ✔ (pin v1) | migration-required |
| UrjaOps | ✔ (pin v1) | migration-required |
| Legal Engineering | ✔ (pin v1) | migration-required |
| Future product | ✔ onboard at latest v1 | onboard at v2 natively |

*Gene-level band (illustrative):* `evidence-verify` M4 — bands v1–v2 (stable across the next MAJOR); `telemetry-ingest` M3 — band v1 only (superseded by `telemetry-ingest-v2` in v2). Cells are `native` / `migration-required` / `unsupported`; the live matrix is maintained as the genome versions and product pins evolve.

## 20. Genome Migration Strategy (Deliverable 9)

Migration is how a product moves from genome `vN` to `vN+1`, non-destructively and one product at a time.

1. **MINOR migrations are safe and lazy.** Additive-only; a product adopts a MINOR by re-pinning, gaining access to new genes without changing anything it already expresses. No migration assignment needed.
2. **MAJOR migrations are governed and pathed.** Each MAJOR ships a **migration path per changed gene**: what changed, the successor gene, and the consumer-side change required. Migrating a product to a new MAJOR is a Lane-B assignment at L3.
3. **One product at a time.** Products migrate independently on their own schedule; the compatibility window (§19) lets siblings sit on different MAJORs during the transition.
4. **Backward-compatibility window.** A superseded inherited gene is deprecated (not immediately retired) for a defined window so trailing products can migrate before it leaves the tree.
5. **Non-destructive and reversible-until-committed.** Until a product commits its migration, its prior pin remains valid; migration never strands a product mid-flight.
6. **Lineage carries the map.** The `superseded-by` / `split-from` / `merged-from` edges *are* the migration map — a product migrating a gene follows its lineage forward to the successor.

This mirrors the Methodology's migration discipline (additive, non-destructive, one unit at a time) applied to the inheritance layer rather than to a single product.

---

## PART VII — KNOWLEDGE & ECOSYSTEM

## 22. Platform Knowledge Model (Deliverable 7 — Knowledge Model)

The Genome carries not only structural DNA (capabilities) but **heritable knowledge** — the conventions, decisions, and patterns every product is born knowing. This is the genome's analogue of epigenetics: behavioral inheritance layered over the structural genes.

Two kinds of inheritance, kept distinct:

| | **Genetic** (structural) | **Epigenetic** (behavioral) |
|---|---|---|
| Unit | Capability DNA (genes) | Conventions, defaults, recorded decisions, patterns |
| Layer | L2 (inheritable capabilities) | L1 (genome services) + a knowledge layer |
| Inheritance | Expressed / not expressed | Applied by default; may be locally silenced at declared points |
| Changes via | Evolution operations (§12–17) | Knowledge promotion from the Methodology's Knowledge Lifecycle |

**Boundary with the Methodology (no duplication):** the Methodology owns the *Knowledge Lifecycle* — the day-to-day capture→structure→generalize→promote loop that runs at every assignment close. The Genome owns only the **destination and inheritance** of promoted knowledge: what becomes *heritable*, at which layer, and how a new product inherits it. Knowledge is *captured and generalized* by the Methodology; it is *inherited* through the Genome. The Genome does not run capture; the Methodology does not define inheritance.

Properties:

- **Promoted knowledge becomes DNA.** A convention that proves general is promoted into the genome's knowledge layer and thereafter inherited by every product — a new product is born already knowing it.
- **Decisions are heritable.** A recurring founder decision, once resolved into a default, enters the knowledge layer so no future product re-surfaces it — directly serving the Methodology's Founder Decision Budget.
- **Silencing, not overriding.** A product may locally silence an inherited default at a declared point (like non-expression of a gene), but cannot rewrite the inherited knowledge itself.
- **Non-destructive.** Superseded knowledge is retired from active inheritance but retained as history, exactly like retired genes.

## 23. Relationship with the ecosystem (the no-duplication contract)

This section is the explicit differentiation the acceptance criteria require. For each neighboring system: what it owns, what the Genome owns, and the one-directional relationship between them.

| System | It owns | Genome owns | Relationship (no overlap) |
|---|---|---|---|
| **AI Workspace** | The implementation/host platform — the running realization of products. | The abstract inheritance model. | Genome is implementation-independent; **AI Workspace realizes it**. Many hosts could; the Genome doesn't change. |
| **AI Workspace HQ** | The control plane / operations surface over running products. | Inheritance structure & lineage. | HQ *operates* products; it *reads* the Genome for lineage/version state; it does not author DNA. |
| **ProjectOS (Methodology)** | The operating model — how work flows (assignments, lanes, verification). | What is inherited and how DNA evolves. | Genome evolution operations **run as** Methodology Lane-B assignments. Process vs. genetics — no shared responsibility. |
| **Capability Registry (CR-1)** | The catalog — capability records: identity, maturity, consumers, status. | Lineage, layer placement, expression, evolution history (the genetics on top of records). | Genome **references** Registry records; it never re-stores the catalog. Inventory vs. ancestry. |
| **Capability Maturity Engine** | Readiness grading (M0–M4). | The act of inheritance-layer placement. | Maturity is the **threshold** that gates evolution operations; the Genome performs the operation. Readiness vs. placement. |
| **Capability Discovery Engine** | Search — matching needs to capabilities, surfacing reuse candidates. | The family tree & lineage structure. | Discovery **reads** the Genome's tree to search; it does not author lineage. Search vs. structure. |
| **Platform Intelligence** | Analytics & insight over the ecosystem (health, reuse rate, drift, anomalies). | The lineage/version/compatibility substrate. | Intelligence **reads** the Genome as its substrate and may *propose* evolution operations; the Genome (via governance) *decides and records* them. Insight vs. substrate. |

The pattern is consistent: neighboring engines either **realize**, **reference**, or **read** the Genome; only Genome evolution operations (executed as governed Methodology assignments) **author** its DNA and lineage. That single-authorship rule is what guarantees no duplicated responsibility.

---

## PART VIII — FUTURE

## 24. Future Evolution Strategy

The Genome is designed for **long-term autonomous evolution** — a shared core that can eventually improve itself under governance.

1. **Autonomous-ready by construction.** Because every evolution operation is evidence-triggered, lineage-recorded, compatibility-checked, and migration-pathed, the operations are structured enough to be *proposed and executed autonomously*. Platform Intelligence proposes; the Maturity Engine gates on readiness; the Methodology executes as a governed assignment; lineage records the act — with the founder engaged only for breaking-MAJOR decisions.
2. **Self-optimizing inheritance.** Over time the target is a genome that continuously promotes proven genes, merges discovered duplicates, splits conflated ones, and retires the obsolete — keeping average maturity and reuse rising and divergence falling, with minimal human involvement.
3. **New products at near-zero foundational cost.** As the inherited layer matures, standing up a new product trends toward *pure expression* — pin the genome, express the needed genes, add Domain DNA. The ecosystem scales to many products without a foundational rebuild for any of them.
4. **The Genome evolves through itself.** Changes to the Genome model are governed, versioned amendments (like this document) — the inheritance system is subject to the same lineage-and-version discipline it imposes on capabilities.
5. **Anticipated extensions (neither required nor blocked):** cross-product portfolio lineage views, autonomous promotion pipelines gated by Platform Intelligence, signed lineage records for multi-party trust, and additional host realizations beyond AI Workspace. Each arrives as an additive genome MINOR.

---

## PART IX — DELIVERABLES INDEX

| # | Deliverable | Where |
|---|---|---|
| 1 | **Platform Genome v1.0** | This document, in full. |
| 2 | **Architecture Diagram** | §2.1. |
| 3 | **Inheritance Diagram** | §4 (both the composition formula and the sibling diagram). |
| 4 | **Genome Layer Model** | §3. |
| 5 | **Capability DNA Model** | §9. |
| 6 | **Evolution Model** | §12 (summary table) + §13–§17 (per-operation rules). |
| 7 | **Knowledge Model** | §22. |
| 8 | **Compatibility Matrix** | §19. |
| 9 | **Migration Strategy** | §20. |
| 10 | **Recommendations for future implementation** | Part X. |

---

## PART X — RECOMMENDATIONS FOR FUTURE IMPLEMENTATION

Design-level recommendations only; implementation is assigned separately (per the stopping point). Sequenced so each step is independently valuable and non-breaking.

1. **Seed the genome from what already works.** Populate Platform DNA (L0/L1) by *promoting* the existing kernel, runtime, and shared conventions — do not design a new core. Genome v1.0 should be an extraction, not an invention.
2. **Establish lineage before evolution.** Stand up the family-tree structure (lineage edges over existing Registry records) first; evolution operations are meaningless without ancestry to record against.
3. **Wire the Registry reference, don't duplicate it.** Capability DNA should reference CR-1 records and hold only the four genetics facets (§9); resist re-storing catalog data in the Genome.
4. **Implement the five evolution operations as Lane-B assignment types.** Each operation is a Methodology assignment with a fixed verification level (§12); build them as governed workflows, not bespoke scripts.
5. **Pin the first sibling.** Onboard one additional product (e.g., TradeOS or UrjaOps) by inheritance from genome v1.0 as the real test that "inherit, don't fork" holds end to end.
6. **Instrument for autonomy last.** Only after lineage, versioning, and the evolution operations are solid should Platform Intelligence begin *proposing* operations; autonomy rides on the audit-quality of everything beneath it.

**Top risks & mitigations:**

- *Genome absorbs the Registry's job.* Mitigate by the §9 facet split — genetics only, reference the catalog.
- *Genome absorbs the Methodology's job.* Mitigate by executing all evolution operations *as* Methodology assignments, not as a parallel process.
- *Divergence via sideways copying.* Mitigate by Inheritance Rule 6 (vertical-only) and making sideways copies a review-blocking issue.
- *Lineage erasure.* Mitigate by append-only, non-destructive lineage — retirement marks, never deletes.

---

## APPENDIX A — L2 VERIFICATION RECORD

Independent, delta-only, verdict-oriented review against the assignment's acceptance criteria (verification level L2 as assigned).

| Acceptance criterion | Verdict | Basis |
|---|---|---|
| Differentiated from **Capability Registry** | **PASS** | §0 and §9 draw the boundary at the facet level: Registry holds records (identity, maturity, consumers, status); Genome holds only genetics (layer placement, lineage, expression, evolution history) and *references* the Registry. §23 states the reference-not-duplicate relationship. |
| Differentiated from **ProjectOS Methodology** | **PASS** | §0, §12, §23: Methodology = process; Genome = inheritance. Evolution operations *execute as* Methodology Lane-B assignments — the seam is explicit and non-overlapping. |
| Differentiated from **AI Workspace implementation** | **PASS** | §0, §2.2, §23: Genome is implementation-independent; AI Workspace/HQ *realize and operate*, they do not author DNA. |
| Supports all current and future products | **PASS** | §21 + §3–§4: one genome, sibling products expressing subsets; new products onboarded by pinning + expression + Domain DNA with zero foundational rebuild. All named products (incl. AI Workspace HQ) covered. |
| No duplicated responsibilities | **PASS** | §23 no-duplication contract: neighbors *realize / reference / read* the Genome; only governed evolution operations *author* it. Single-authorship rule stated. |
| Implementation-ready | **PASS** | Concrete layer model, DNA facets, five evolution operations with triggers/lineage/levels, versioning scheme, compatibility matrix, migration strategy, sequenced recommendations — while remaining implementation-independent (no code, no contracts, no repo/Registry changes, per scope). |
| Scope coverage: all 24 items | **PASS** | Traceability below. |
| Scope coverage: all 10 deliverables | **PASS** | Part IX index. |

**Scope traceability (24 items):** 1 Vision §1 · 2 Genome Architecture §2 · 3 Genome Layers §3 · 4 Inheritance Model §4 · 5 Inheritance Rules §5 · 6 Platform DNA §6 · 7 Product DNA §7 · 8 Domain DNA §8 · 9 Capability DNA §9 · 10 Capability Lineage §10 · 11 Capability Family Tree §11 · 12 Capability Evolution §12 · 13 Promotion §13 · 14 Demotion §14 · 15 Split §15 · 16 Merge §16 · 17 Retirement §17 · 18 Genome Versioning §18 · 19 Compatibility Rules §19 · 20 Migration Strategy §20 · 21 Cross-product Inheritance §21 · 22 Platform Knowledge Model §22 · 23 Relationships §23 · 24 Future Evolution Strategy §24.

**Reviewer verdict: PASS.** No blocking issues. The Genome is cleanly differentiated from the Registry, the Methodology, and AI Workspace; carries no duplicated responsibilities; supports every current and future product by inheritance; and is implementation-ready without containing implementation.

---

*End of Platform Genome v1.0. This assignment designs the inheritance architecture only. No implementation, code, contracts, or Registry changes were performed; future implementation is assigned separately.*
