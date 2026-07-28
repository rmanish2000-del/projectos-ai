# PO-3 — AI Workspace Integration Specification

**The canonical integration model between ProjectOS, AI Workspace, AI Workspace HQ, and the products — with exactly one owner for every platform capability.**

**Status:** PO-3 — proposed canonical integration specification. Integration spec only; no implementation, no code, no contracts, no registry design, no genome redesign, no repository changes.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Inputs / amends alongside:** `PROJECTOS_METHODOLOGY_V2.md`, `PLATFORM_GENOME_V1.md`, `PO-2.5_ARCHITECTURE_CONSISTENCY_REVIEW.md`, `PROJECTOS_V0_1_FOUNDATION_SPEC.md`, `PROJECTOS_WORKSPACE_RUNTIME_SPEC.md`.
**Resolves from PO-2.5:** M-3 (AI Workspace boundary undefined), O-1 (operating-model ownership), D-1 (duplicated operating model), and the single-owner requirement across the capability set.

---

## 0. Ownership model

### 0.1 The four realms — one owner each, no overlap

The ecosystem has exactly four owning entities, each confined to one **realm**. A capability's realm decides its owner, and the realms do not overlap — which is what makes "exactly one owner" structurally true rather than merely asserted.

| Entity | Realm | Owns (accountable for) | Never owns |
|---|---|---|---|
| **ProjectOS** | **Definition** — methodology & architecture | Models, specifications, methodology, invariants, the inheritance architecture. *The rules of the system.* | Any running system; any commercial function. |
| **AI Workspace** | **Implementation** — the platform | Runtime, infrastructure, engines, execution of the models. *The running system.* | The definitions it executes; the business. |
| **AI Workspace HQ** | **Business** — go-to-market | Commercial, marketplace, brand, revenue, customer relationships. *The business around the platform.* | The platform internals; the methodology. |
| **Products** (EduOS, TradeOS, UrjaOps, Legal, …) | **Domain** — the product | Product DNA, Domain DNA, domain logic, product content, product brand/site. *What is built on the platform.* | Any platform, definitional, or business capability. |

"ProjectOS remains **methodology-only**" is interpreted precisely as **definition-only**: ProjectOS owns definitional artifacts (the Methodology *and* the Genome *and* the Registry model *and* the capability-engine models — which remain **separate documents**, per Genome v1 and PO-2.5, not merged) and never owns an implementation or a commercial function. "AI Workspace remains the **implementation platform**" and "HQ remains the **business platform**" are the mirror constraints.

### 0.2 The six lenses (how each capability is specified)

For every capability the ownership is stated through six lenses, so "owner" is never ambiguous with "who runs it" or "who uses it":

| Lens | Question | Cardinality |
|---|---|---|
| **Owner** | Who is *accountable* for the capability's definition and evolution? | **Exactly one** (the single owner; RACI "A"). |
| **Consumer** | Who *uses* it? | Many. |
| **Reference** | Which canonical artifact *defines* it (source of truth)? | One artifact. |
| **Inheritance** | How is it inherited (Genome layer)? | One placement. |
| **Implementation** | Who *builds / runs* it? | One implementer (RACI "R"). |
| **Governance** | At what verification level, and who approves changes? | One governance path. |

**Owner ≠ Implementation** is the crux. A model can be owned by ProjectOS (definition) and implemented by AI Workspace (runtime) with no conflict, because the two lenses answer different questions. This is what resolves PO-2.5's duplicated-ownership findings without pretending ProjectOS runs anything.

### 0.3 The decision rule (which realm owns a given capability)

Applied uniformly, so ownership is principled, not case-by-case:

- The capability is fundamentally a **rule / model / standard** → **ProjectOS** (e.g., the maturity *grading rules*, the evidence *model*).
- The capability is fundamentally a **running system / infra / engine** → **AI Workspace** (e.g., the discovery *engine*, the analytics *runtime*).
- The capability is fundamentally **commercial / market-facing** → **HQ** (e.g., marketplace, sales).
- The capability is fundamentally **domain / product-specific** → **Product**.

Where a capability has both a "rules" facet and an "engine" facet (Maturity, Evidence, Governance, Registry), the **rules facet is the essence** and sets the owner (ProjectOS); the engine is the *implementation* lens (AI Workspace). Where the essence is search mechanics or analytics with thin rules (Discovery, Platform Intelligence), the **engine is the essence** and sets the owner (AI Workspace).

### 0.4 The three hard constraints (verified in Appendix A)

1. **One owner per capability** — every row has exactly one Owner.
2. **No duplicated ownership** — no capability appears with two owners; "shared" means *consumed by many*, never *owned by many* (§5).
3. **No circular ownership** — the ownership/dependency graph is acyclic (§10). Ownership (who is accountable) is distinct from inheritance-content (what a spec describes); a spec that *describes* ProjectOS is not *owned by* the thing it describes.

---

## PART I — RESPONSIBILITIES BY ENTITY

## 1. ProjectOS responsibilities (Definition realm)

ProjectOS is the single **definitional authority**. It owns the *rules of the system* and nothing that runs or sells. Its owned capabilities:

- **Assignment Engine** (the lifecycle, states, invariants — the kernel *model*).
- **Evidence** (the verification/evidence model — what counts as proof).
- **Governance** (workflow modes, verification levels L0–L3, escalation model).
- **Architecture** (the architecture authority; owns architecture specs and this integration model).
- **Platform Genome** (the inheritance architecture — the *specification*, per Genome v1).
- **Capability Registry (model)** (the record *model* the catalog obeys — ownership only; no schema is designed here, per scope).
- **Capability Maturity (model)** (the M0–M4 grading *rules*, extracted from Methodology §10.2 as PO-2.5 O-3 recommends).
- **Knowledge Management (model)** (the Knowledge Lifecycle — capture→promote rules).
- **Documentation (standard)** (the documentation *policy*; content authorship is federated to each capability owner).

ProjectOS **never** implements or operates any of these; AI Workspace does. ProjectOS **never** owns a commercial function. This is the concrete meaning of "methodology-only = definition-only." These artifacts remain **separate documents** — owning the Genome does not fold it into the Methodology.

## 2. AI Workspace responsibilities (Implementation realm)

AI Workspace is the single **implementation platform**. It *realizes* every ProjectOS definition and owns every capability whose essence is a running system:

- **Capability Discovery** (the search engine over the Registry + Genome family tree).
- **Platform Intelligence** (the analytics/insight runtime over the genome/lineage substrate; consumes ProjectOS metric definitions).
- **Deployment** (release mechanics; the *act* is founder/human-approved per governance).
- **Operations** (runtime, monitoring, incident response, SRE).
- **Security** (platform security architecture and controls).
- **Identity** (authentication, accounts, identity infrastructure).
- **Enterprise Integrations** (connector/integration platform; enterprise *deals* are HQ's).

AI Workspace is additionally the **Implementer (Responsible)** for the ProjectOS-owned capabilities (it builds and runs the Assignment Engine, Registry store, Genome/lineage store, Maturity engine, Knowledge store, Evidence adapters, Governance enforcement). It never owns their *definitions* and never owns a commercial function.

## 3. AI Workspace HQ responsibilities (Business realm)

HQ is the single **business platform** — the commercial layer around the platform:

- **Marketplace** (the plugin/capability marketplace as a business: curation, monetization, partner program; AI Workspace runs the marketplace tech).
- **Website (ecosystem)** (the corporate/ecosystem web presence; product marketing sites are Product-owned).
- **Brand (ecosystem)** (the ecosystem brand; product brands — e.g., EduOS "Gyan Tara" — are Product-owned).
- **Sales**, **Marketing**, **Customer Success** (the commercial functions).

HQ **consumes** the platform (AI Workspace) and the methodology (ProjectOS) but owns none of their internals. HQ owns the enterprise *relationship*; AI Workspace owns the enterprise *integration capability*.

## 4. Product responsibilities (Domain realm)

Each product (EduOS, TradeOS, UrjaOps, Legal Engineering, future products) owns only its **domain**:

- **Product DNA** (identity, expressed gene set, configuration — Genome §7).
- **Domain DNA** (domain rules, vocabulary, quality overrides, templates — Genome §8; e.g., the trading GOVERNED triggers PO-2.5 O-2 says belong here, not at workspace root).
- **Domain logic and product content** (e.g., EduOS content bundles; TradeOS strategy logic).
- **Product brand and product website** (e.g., `eduos.ai`).
- **Product roadmap and product-local capabilities** (M0–M2 genes not yet promoted).

Products are pure **consumers** of every Definition, Implementation, and Business capability. A product never owns a platform capability; when a product-local capability proves reusable it is **promoted** into the Genome (Genome §13), transferring ownership upward — the only sanctioned path, and never a sideways copy.

## 5. Shared responsibilities (consumption model — *not* shared ownership)

"Shared" is the most dangerous word for an ownership model, so it is defined precisely: **shared means consumed by many, owned by one.** There is **no co-ownership** anywhere in this specification.

A capability is *shared* when its Inheritance lens is **Platform DNA** (inherited by every product) — the Assignment Engine, Evidence, Governance, Genome, Registry, Maturity, Knowledge, Security, Identity. These are consumed ecosystem-wide but each has exactly one owner (§7). The Genome (Platform DNA) is the mechanism of sharing; ownership of the shared thing still resides with a single entity. This is how the ecosystem gets universal reuse without violating single-ownership.

---

## PART II — MATRICES

## 6. Ownership Matrix (Deliverable 1)

Summary of which entity owns which class of capability. Each capability appears under exactly one owner.

| Owner (realm) | Owned capabilities |
|---|---|
| **ProjectOS** (Definition) | Assignment Engine · Evidence · Governance · Architecture · Platform Genome · Capability Registry (model) · Capability Maturity (model) · Knowledge Management (model) · Documentation (standard) |
| **AI Workspace** (Implementation) | Capability Discovery · Platform Intelligence · Deployment · Operations · Security · Identity · Enterprise Integrations |
| **AI Workspace HQ** (Business) | Marketplace · Website (ecosystem) · Brand (ecosystem) · Sales · Marketing · Customer Success |
| **Products** (Domain) | Product DNA · Domain DNA · Domain logic & content · Product brand & site · Product-local capabilities |

Counts: ProjectOS 9, AI Workspace 7, HQ 6, Products (domain-scope). No capability is listed twice → **no duplicated ownership**.

## 7. Capability Ownership Table (Deliverable 4 — the six lenses)

The canonical table. One row per capability; **Owner** is the single accountable entity. `AIW` = AI Workspace; `PDNA` = Platform DNA; `DDNA` = Domain DNA; `PL` = Product-local; `n/a` = not inherited (platform/business service).

| Capability | Owner | Consumer(s) | Reference | Inheritance | Implementation | Governance |
|---|---|---|---|---|---|---|
| **Assignment Engine** | ProjectOS | All products, AIW | Foundation Spec | PDNA | AIW | GOVERNED / L3 (frozen kernel) |
| **Evidence** | ProjectOS | All products | Foundation Spec §8 | PDNA | AIW (git/CI adapters) | GOVERNED / L3 |
| **Governance** | ProjectOS | All; Founder | Methodology §6–7, §16 | PDNA | AIW (enforcement) | GOVERNED / L3; Founder approves |
| **Architecture** | ProjectOS | All | This spec; Genome; Runtime spec | PDNA | — (definitional); AIW realizes | GOVERNED / L3, Lane B |
| **Platform Genome** | ProjectOS | All products | `PLATFORM_GENOME_V1.md` | *is the substrate* | AIW (lineage/genome store) | GOVERNED / L3, Lane B evolution ops |
| **Capability Registry** | ProjectOS (model) | Products, Genome, Discovery, Maturity | Genome §9; CR-1 (to be authored) | PDNA | AIW (catalog store) | GOVERNED / L3 (schema); REVIEWED (records) |
| **Capability Discovery** | AIW | Products, Founder, Platform Intelligence | *to be authored* | PDNA (platform service) | AIW | REVIEWED / L2 |
| **Capability Maturity** | ProjectOS (model) | Genome (thresholds), products, Founder | Methodology §10.2 → own spec | PDNA | AIW (grading engine) | GOVERNED (rules) / REVIEWED (grade changes) |
| **Platform Intelligence** | AIW | ProjectOS (metrics), HQ, Founder | *to be authored* | PDNA (platform service) | AIW | REVIEWED / L2 |
| **Knowledge Management** | ProjectOS (model) | All | Methodology §12; Genome §22 | PDNA + epigenetic | AIW (knowledge store) | REVIEWED / L2 |
| **Documentation** | ProjectOS (standard) | All | Methodology (doc policy) | PDNA (standard); content federated | Each owner (R) | FAST–REVIEWED |
| **Deployment** | AIW | Products | Runtime spec; kernel (manual deploy) | n/a (platform service) | AIW | REVIEWED–GOVERNED; Founder approves |
| **Operations** | AIW | Products, HQ | *to be authored* | n/a | AIW | REVIEWED / L2 |
| **Security** | AIW | All | *to be authored* | PDNA (secure defaults) | AIW | GOVERNED / L3; Founder for boundary changes |
| **Identity** | AIW | All, HQ | *to be authored* | PDNA | AIW | GOVERNED / L3 |
| **Enterprise Integrations** | AIW | HQ, enterprise customers, products | *to be authored* | n/a (platform service) | AIW | REVIEWED / L2 |
| **Marketplace** | HQ | Products, customers, 3rd-party authors | *to be authored* | n/a (business) | AIW (tech) / HQ (program) | REVIEWED / L2 |
| **Website (ecosystem)** | HQ | Prospects, public | *to be authored* | n/a | AIW / HQ | FAST–REVIEWED |
| **Brand (ecosystem)** | HQ | All, public | *to be authored* | n/a | HQ | REVIEWED (business) |
| **Sales** | HQ | — (HQ function) | *to be authored* | n/a | HQ | Business governance |
| **Marketing** | HQ | — (HQ function) | *to be authored* | n/a | HQ | Business governance |
| **Customer Success** | HQ | Customers, products | *to be authored* | n/a | HQ | Business governance |
| **Product DNA / Domain DNA / content** | Product | The product itself | Product constitution + Genome §7–8 | Product-local (promote → PDNA) | Product (impl by AIW-hosted agents) | Per product; promotion is GOVERNED |

*"to be authored" marks capabilities whose canonical Reference document does not yet exist (consistent with PO-2.5 Missing Concepts); this spec assigns their ownership so the authoring assignment has a defined owner.*

## 8. Responsibility Matrix — RACI (Deliverable 2)

**A** = Accountable (the single Owner) · **R** = Responsible (does the work) · **C** = Consulted · **I** = Informed. Exactly one **A** per row (= single-owner guarantee). Founder is the ultimate accountable authority only for governed/L3 approvals and genuine decisions (Methodology §9, §16) — shown as **C/approve** to avoid diluting capability-level accountability.

| Capability | ProjectOS | AI Workspace | HQ | Product | Founder |
|---|---|---|---|---|---|
| Assignment Engine | **A** | R | I | C (consumer) | C/approve (L3) |
| Evidence | **A** | R | I | C | I |
| Governance | **A** | R | I | C | C/approve (L3) |
| Architecture | **A** | R | I | C | C/approve (L3) |
| Platform Genome | **A** | R | I | C | C/approve (evolution) |
| Capability Registry | **A** | R | I | C | I |
| Capability Discovery | C | **A**/R | I | C | I |
| Capability Maturity | **A** | R | I | C | I |
| Platform Intelligence | C (metrics) | **A**/R | C | I | I |
| Knowledge Management | **A** | R | I | C | I |
| Documentation | **A** (standard) | R | C | R (own docs) | I |
| Deployment | C | **A**/R | I | C | C/approve |
| Operations | I | **A**/R | C | C | I |
| Security | C (governance) | **A**/R | I | I | C/approve (boundary) |
| Identity | C | **A**/R | C | I | C/approve |
| Enterprise Integrations | I | **A**/R | C | C | I |
| Marketplace | I | R (tech) | **A** | C | C/approve |
| Website (ecosystem) | I | R | **A** | I | I |
| Brand (ecosystem) | I | I | **A** | I | C/approve |
| Sales | I | I | **A** | I | I |
| Marketing | I | I | **A** | I | I |
| Customer Success | I | I | **A** | C | I |
| Product DNA / Domain / content | C (rules) | R (hosts) | I | **A** | C/approve |

Every row has exactly one **A** → single-owner confirmed at the RACI level.

---

## PART III — INTEGRATION ARCHITECTURE

## 9. Integration Architecture (Deliverable 3)

How the four entities interconnect. The flow is one-directional by realm: **Definition → Implementation → Business**, with **Products** consuming across all three and **inheriting** through the Genome.

```
┌──────────────────────────────────────────────────────────────────────┐
│  PROJECTOS — Definition realm (owns the rules)                        │
│  Assignment Engine · Evidence · Governance · Architecture · Genome ·  │
│  Registry model · Maturity model · Knowledge model · Doc standard     │
└───────────────────────────────┬──────────────────────────────────────┘
              defines / specifies │  (ProjectOS never runs anything)
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│  AI WORKSPACE — Implementation realm (runs the rules)                 │
│  realizes every ProjectOS model + owns: Discovery · Platform          │
│  Intelligence · Deployment · Operations · Security · Identity ·       │
│  Enterprise Integrations                                              │
└───────────┬───────────────────────────────────────────┬──────────────┘
   hosts &   │ serves the running platform to            │ exposes commercial
   inherited │                                           │ surfaces to
   by (Genome)▼                                          ▼
┌───────────────────────────────┐        ┌──────────────────────────────┐
│  PRODUCTS — Domain realm      │        │  AI WORKSPACE HQ — Business   │
│  EduOS · TradeOS · UrjaOps ·  │◄──────►│  Marketplace · Website ·      │
│  Legal · future               │  sells │  Brand · Sales · Marketing ·  │
│  own: Product/Domain DNA,     │  & sup-│  Customer Success             │
│  content, product brand/site  │  ports │  (consumes platform;          │
│  consume everything above     │        │   owns no platform internals) │
└───────────────────────────────┘        └──────────────────────────────┘
      ▲  promote proven local capability (Genome §13) ─┐
      └──────────────── inherit Platform DNA ◄─────────┘ (vertical only; no
                                                          product↔product)
```

Integration rules:

1. **Definition never runs; Implementation never defines.** ProjectOS hands specifications to AI Workspace; AI Workspace realizes them and returns evidence-of-conformance — it does not alter the definitions.
2. **Business consumes, never owns platform internals.** HQ builds commerce *on* the platform; it cannot reach into Definition or Implementation ownership.
3. **Products inherit vertically through the Genome.** Products get platform capabilities as inherited Platform DNA (Genome), never by copying from another product.
4. **Promotion is the only upward ownership transfer.** A product-local capability becomes platform-owned only via Genome promotion — an explicit, governed act.
5. **Every cross-realm interaction is Owner-defined, Implementer-run, Consumer-used** — the six lenses hold at every seam.

## 10. Dependency Diagram (Deliverable 5 — acyclic)

Capability-level dependencies. An arrow `X → Y` means *X depends on / is defined-atop Y*. The graph is a DAG — **no circular ownership or dependency**.

```
                         Assignment Engine ───► Evidence ───► Governance
                                │                   │             │
                                ▼                   ▼             ▼
                          Knowledge Mgmt        Architecture ◄────┘
                                │                   │
   Capability Registry ◄────────┘                   ▼
        │      ▲                              Platform Genome
        │      │ records                        │    │    │
        ▼      │                       inherits │    │    │ grades feed
   Capability Maturity ──────────────────────────┘    │    ▼
        │  thresholds                                  │  Capability Discovery
        ▼                                              │    ▲ reads tree
   Platform Intelligence ◄─────────────────────────────┘    │
        │ reads substrate                                   │
        ▼                                                    │
   (Products consume all above via inheritance) ────────────┘

   Platform services (no cycles): Security ─► Identity ;  Deployment ─► Operations
   Business (consumes platform, depended-on by none):
        Marketplace ─► (Registry, Genome) ;  Sales/Marketing/CS ─► Website ─► Brand
```

Ownership-graph acyclicity (the stricter check): ProjectOS-owned → implemented-by AIW → consumed-by Products/HQ. No entity owns a capability that (transitively) owns one of its own. The Genome *describes* inheritance of ProjectOS's methodology, but ProjectOS *owns* the Genome — content-reference is not ownership, so no cycle exists (§0.4 constraint 3, verified Appendix A).

---

## PART IV — GOVERNANCE

## 11. Governance Model (Deliverable 6)

How changes to owned capabilities are governed. Governance authority is itself a ProjectOS-owned capability (§7), so this model is uniform across the ecosystem.

1. **The Owner proposes; the Governance level gates.** Only a capability's Owner may propose a change to it. The change's verification level (Methodology §6) is set by the capability's Governance lens (§7): frozen/definitional capabilities (Assignment Engine, Evidence, Genome, Security) are **GOVERNED / L3**; platform services are **REVIEWED / L2**; business/content varies.
2. **Cross-realm changes require the consuming realms as Consulted, not co-owners.** A Genome change (ProjectOS-owned) that affects products consults product owners and is executed as a Lane-B governed assignment (Genome §12) — but ownership never transfers to the consumers.
3. **Implementation conformance is evidence-gated.** AI Workspace's implementation of a ProjectOS definition is verified against that definition's acceptance criteria (kernel evidence model). A drift between definition and implementation is a defect owned by AI Workspace, not a license to change the definition.
4. **Founder authority is reserved and narrow.** The Founder is the approval authority only for L3/governed changes and genuine decisions (Methodology §9, §16): frozen-architecture, security boundary, breaking public contract, Genome MAJOR, and business bets. Everything else is resolved within the owning realm.
5. **Ownership disputes escalate as architecture conflicts.** If two parties claim authority over one capability, that is an `architecture_conflict` escalation (kernel escalation trigger) resolved by the Founder against this specification — this spec is the tie-breaker.
6. **Business governance is separate from engineering governance.** HQ-owned capabilities follow business governance (commercial approval), not the L0–L3 engineering ladder — preserving the plane separation (Methodology §2.1).

---

## PART V — RECOMMENDED OPERATING BOUNDARIES

## 12. Recommended operating boundaries (Deliverable 7)

The rules of engagement that keep ownership from drifting back into the duplication PO-2.5 found. These are boundaries, not new design.

1. **ProjectOS may never ship a running system.** If a ProjectOS artifact starts to run, it has crossed into Implementation — hand it to AI Workspace. (Prevents the methodology from re-absorbing engines.)
2. **AI Workspace may never redefine a rule.** If implementation needs a different rule, it raises a change *to the Owner*, not a local override. (Prevents implementation drift — PO-2.5 C-3/C-4 class.)
3. **A product may never re-author a platform capability.** If a product needs different platform behavior, it either configures the provided extension point or proposes a Genome change — it does not fork the operating model. (Directly closes PO-2.5 O-1/D-1: EduOS's re-authored operating model becomes *product-local expression* of the inherited ProjectOS model, not a competing owner.)
4. **HQ may never reach into platform internals.** Commercial needs are met by consuming platform surfaces, not by owning platform capabilities.
5. **"Shared" is always "consumed by many, owned by one."** No document may introduce co-ownership; sharing is expressed through Genome inheritance (§5).
6. **Every new capability gets an Owner before it gets an implementation.** A capability with no single Owner cannot be built — it must first be placed in a realm via this specification (fail-closed on ownership, mirroring the kernel's fail-closed posture).
7. **This specification is the authority for ownership disputes** (§11 rule 5). Ownership changes are amendments to *this* document, governed at L3, Lane B.

---

## APPENDIX A — L2 VERIFICATION RECORD

Independent, delta-only, verdict-oriented review against the assignment's acceptance criteria and hard constraints.

| Check | Verdict | Basis |
|---|---|---|
| **Every capability has exactly one owner** | **PASS** | §7 table and §8 RACI each assign exactly one Owner / one **A** per capability; §6 lists each capability under one owner only. All 22 named capabilities + the product-scope row covered. |
| **No duplicated responsibilities** | **PASS** | No capability appears under two owners (§6). Owner vs Implementation lenses are distinct (§0.2), so ProjectOS-owns + AIW-implements is not duplication. "Shared" defined as consumption, not ownership (§5). |
| **No circular ownership** | **PASS** | §10 ownership graph is a DAG; the Genome content-reference-to-ProjectOS is not an ownership edge (§0.4 constraint 3). |
| **No conflicting authority** | **PASS** | Single **A** per row; disputes route to `architecture_conflict` escalation resolved against this spec (§11 rule 5). |
| **ProjectOS remains methodology-only** | **PASS** | ProjectOS owns only Definition-realm artifacts; explicitly never implements or commercializes (§0.1, §1). "Methodology-only = definition-only" stated. Genome remains a separate document, not merged. |
| **AI Workspace remains implementation platform** | **PASS** | AIW owns only runtime/infra/engines and implements ProjectOS definitions; never defines or sells (§2). |
| **HQ remains business platform** | **PASS** | HQ owns only commercial functions; consumes platform, owns no internals (§3). |
| **Future products inherit correctly** | **PASS** | Products consume via Genome Platform DNA; promotion is the only upward transfer; no product↔product ownership (§4, §9 rules 3–4). |
| **Implementation-ready** | **PASS** | Concrete matrices (Ownership, RACI, six-lens table), architecture, acyclic dependency graph, governance model, operating boundaries — while remaining implementation-independent (no code, no contracts, no registry/genome design, per scope). |
| **PO-2.5 findings addressed** | **PASS** | M-3 (AI Workspace boundary) defined (§2); O-1/D-1 (operating-model ownership) resolved to ProjectOS with product-local expression (§12 rule 3); O-2 (domain triggers) placed in Domain DNA (§4). C-1/C-2 content decision remains a Founder call (noted below) — ownership is assigned regardless of which content wins. |

**Note on the open Founder decision:** PO-2.5's C-2 (which operating-model *content* is canonical) is a genuine Founder decision and is **not** resolved by this spec. PO-3 resolves *who owns* the operating model (ProjectOS) and mandates that products express, not re-author, it (§12 rule 3). Once the Founder picks the canonical content, it lands in the ProjectOS-owned Methodology and is inherited — no ownership ambiguity remains.

**Reviewer verdict: PASS.** No blocking issues. Every capability has exactly one owner; ownership is non-duplicated, non-circular, non-conflicting; the three realms hold their boundaries; products inherit correctly; and the specification is implementation-ready without containing implementation.

---

## APPENDIX B — DELIVERABLES INDEX

| # | Deliverable | Where |
|---|---|---|
| 1 | Ownership Matrix | §6 |
| 2 | Responsibility Matrix (RACI) | §8 |
| 3 | Integration Architecture | §9 |
| 4 | Capability Ownership Table | §7 |
| 5 | Dependency Diagram | §10 |
| 6 | Governance Model | §11 |
| 7 | Recommended operating boundaries | §12 |

**Scope traceability:** 1 ProjectOS responsibilities §1 · 2 AI Workspace responsibilities §2 · 3 AI Workspace HQ responsibilities §3 · 4 Product responsibilities §4 · 5 Shared responsibilities §5 · 6 Ownership Matrix §6 · 7 Capability Ownership Matrix §7. All 22 minimum capabilities appear in §7/§8.

---

*End of PO-3 AI Workspace Integration Specification. Integration model only — no implementation, no code, no contracts, no registry design, no genome redesign, no repository changes. Every platform capability has exactly one owner; future implementation is assigned separately.*
