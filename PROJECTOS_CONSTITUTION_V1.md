# ProjectOS Constitution v1.0

**The supreme, foundational governance document of ProjectOS — it establishes the hierarchy of all ProjectOS documents, names one authoritative source for every governance domain, and governs how the whole system changes.**

**Status:** PO-6 — proposed canonical Constitution. Design only; no implementation, no code, no repository changes, no redesign of any existing approved document.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Authority:** supreme. This document sits above every other ProjectOS artifact and is the tie-breaker of last resort.
**Inputs (governed, not restated):** `PROJECTOS_METHODOLOGY_V2.md`, `PLATFORM_GENOME_V1.md`, `PO-2.5_ARCHITECTURE_CONSISTENCY_REVIEW.md`, `PO-3_AI_WORKSPACE_INTEGRATION_SPEC.md`, `PO-4_ECOSYSTEM_GOVERNANCE_FRAMEWORK.md`, `PO-5_GOVERNANCE_METRICS_PLATFORM_HEALTH.md`, `PROJECTOS_V0_1_FOUNDATION_SPEC.md`.

---

## Preamble

ProjectOS has grown from a kernel into a family of foundational documents — a methodology, an inheritance architecture, an ownership model, a governance framework, a metrics model. Each is authoritative in its own domain. What has been missing is the **document that orders the documents**: which is supreme, how authority flows between them, what happens when two appear to conflict, and how the whole corpus changes without collapsing into contradiction.

This Constitution is that document. It is deliberately **thin on domain content and thick on hierarchy**: it does not restate what the canonical documents already own — doing so would create the duplicated authority it exists to prevent. Instead it declares, for every governance domain, the *single* document that governs it, and it fixes the rules by which that map may change.

The Constitution is designed to be **rarely amended**. Stability is its primary value: a constitution that changes often governs nothing.

---

## PART I — FOUNDATIONS

## 1. Purpose of the Constitution

The Constitution exists to guarantee five properties across all ProjectOS documents, forever:

1. **One hierarchy.** Every ProjectOS document has a defined place in a single authority hierarchy; none floats outside it.
2. **One authoritative source per governance domain.** Every governance domain (ownership, inheritance, methodology, governance process, metrics, kernel behavior) is legislated by exactly one document. No domain has two legislators.
3. **Predictable conflict resolution.** When documents appear to disagree, the outcome is determined by fixed rules, not negotiation.
4. **Governed, versioned evolution.** The corpus changes only through a defined amendment process, so authority never drifts silently.
5. **Permanent extensibility.** New documents and new products slot into the existing hierarchy without redesigning it — the Constitution supports ecosystem growth without constitutional redesign.

The Constitution does **not** decide domain content (that belongs to each canonical document); it decides *who decides*.

## 2. Constitutional Principles

The entrenched principles. The first four are **immutable** — they may not be amended away, only clarified; amending them would make the Constitution self-contradictory.

1. **Supremacy (immutable).** This Constitution is the highest authority. No document, decision, or agent overrides it. It is the tie-breaker of last resort.
2. **Single authoritative source (immutable).** Every governance domain has exactly one authoritative document (§8.2 Register). No domain is co-legislated; duplicated authority is a defect, not a style.
3. **Downward inheritance (immutable).** Authority flows down the hierarchy: higher documents bind lower ones. A lower document may *specialize* but never *contradict* a higher one. Local never overrides canonical.
4. **Evidence & fail-closed (immutable — inherited from the kernel).** The kernel's guarantees — evidence over claims, fail-closed defaults, one write path, determinism, audit — are constitutional DNA carried into every document. No document may weaken them.
5. **Proportional minimalism.** The Constitution governs only the few meta-rules; it never micromanages. Like the governance framework it sits above (PO-4), it is minimal by design — routine work never touches it.
6. **Amendable but stable.** The Constitution changes only through a governed amendment (§10), rarely, and versioned (§11). Stability is a feature.
7. **Implementation-independent.** The Constitution constitutes *documents and authority*, never code. It is realized by AI Workspace, never authored by it.
8. **Protected local expression.** Products are guaranteed autonomy within their own domain: a product may express and configure freely at the edge, subordinate to canonical documents only where domains intersect (§7). The core is bound; the edge is free.

---

## PART II — THE DOCUMENT SYSTEM

## 3. Document Hierarchy (Deliverable 2 — Constitution Architecture; Deliverable 3)

All ProjectOS documents occupy one of five tiers. Higher tiers bind lower tiers.

```
        ┌───────────────────────────────────────────────────────────┐
  L0    │  THE CONSTITUTION  (this document) — supreme meta-authority │
        └───────────────────────────────┬───────────────────────────┘
                                        │ orders & binds
        ┌───────────────────────────────▼───────────────────────────┐
  L1    │  CANONICAL DOCUMENTS — each supreme WITHIN its one domain   │
        │  Kernel · Methodology · Genome · Integration/Ownership ·    │
        │  Governance · Metrics                                       │
        └───────────────────────────────┬───────────────────────────┘
                                        │ elaborated by
        ┌───────────────────────────────▼───────────────────────────┐
  L2    │  SUPPORTING DOCUMENTS — subordinate elaborations & specs    │
        │  Workspace Runtime · architecture.md · cli.md · CR-1 (spec) │
        └───────────────────────────────┬───────────────────────────┘
                                        │ informed by
        ┌───────────────────────────────▼───────────────────────────┐
  L3    │  REFERENCE DOCUMENTS — informational, non-binding           │
        │  Consistency reviews · research · external standards        │
        └───────────────────────────────┬───────────────────────────┘
                                        │ expressed locally by
        ┌───────────────────────────────▼───────────────────────────┐
  L4    │  LOCAL EXPRESSIONS — binding only WITHIN one product        │
        │  product constitutions · project.yaml · product specs       │
        └───────────────────────────────────────────────────────────┘
```

## 4. Canonical Documents

**Definition:** the constitutional corpus — documents each **supreme within exactly one governance domain**. Canonical status is conferred only by constitutional amendment (§10). A canonical document may not legislate outside its declared domain.

The founding canonical set (each with its one domain — the Register, §8.2):

| Canonical document | Sole domain it governs |
|---|---|
| Foundation Spec (kernel) | Assignment lifecycle, evidence, audit, kernel invariants. |
| Methodology v2 | The operating model (lanes, verification levels, decision framework, knowledge lifecycle). |
| Platform Genome v1 | Inheritance, DNA, lineage, capability evolution. |
| PO-3 Integration Spec | Capability ownership & entity responsibilities. |
| PO-4 Governance Framework | Governance process, tiers, triggers, escalation. |
| PO-5 Metrics & Health Model | Ecosystem measurement & health scores. |

The Constitution itself is **L0**, above the canonical tier.

## 5. Supporting Documents

**Definition:** documents that **elaborate or implement** a canonical document without adding authority. A supporting document is subordinate to its parent canonical document and may never contradict it. Examples: the Workspace Runtime spec (elaborates the kernel/runtime), `architecture.md` and `cli.md` (elaborate the kernel), the forthcoming Capability Registry (CR-1) spec (elaborates the Genome/ownership). Supporting documents change under normal Change Governance (PO-4 §3), not constitutional amendment.

## 6. Reference Documents

**Definition:** **informational, non-binding** documents — findings, research, analyses, external standards. They inform but never govern. The **PO-2.5 Architecture Consistency Review is a Reference document**: authoritative as a *finding of fact* about consistency, but it legislates nothing; its recommendations become binding only when adopted into a canonical or supporting document. Reference documents carry no authority level in conflicts (§9).

## 7. Local Expressions

**Definition:** product-level documents that are **binding within one product only** and subordinate to every canonical document where their domains intersect. Examples: a product constitution (e.g., EduOS's `PROJECT_BOOTSTRAP`/`SOURCE`/`HANDOFF`/`STATE`/`FOUNDER_LEARNING` suite), `project.yaml`, product specs.

The protected-local-expression principle (§2.8) applies: within its own domain — product identity, product strategy, domain content, product roadmap — a Local Expression is authoritative and free. Where it touches a canonical domain (the operating model, ownership, governance, inheritance), it is an *expression of* the canonical rule, never an override of it. A Local Expression that contradicts a canonical document is void in the overlap and yields (§9).

**This resolves the standing PO-2.5 C-2 question at the structural level:** a product's operating-model document is a **Local Expression** of the canonical Methodology, not a competitor to it. Which *content* becomes the canonical Methodology remains a Founder amendment-level decision (§10, §23); the *hierarchy* is now fixed — canonical Methodology is supreme, product constitutions express within it.

## 8. Authority Levels (Deliverable 4 — Authority Matrix)

### 8.1 Precedence ladder (highest → lowest)

| Level | Tier | Binds | Conflict weight |
|---|---|---|---|
| **L0** | Constitution | everything | supreme; never yields |
| **L1** | Canonical | L2–L4, within its domain | supreme within its one domain |
| **L2** | Supporting | L3–L4 | yields to its parent canonical |
| **L3** | Reference | — | non-binding; never wins a conflict |
| **L4** | Local Expression | within one product | yields to all above on domain overlap |

**Precedence rule:** a higher level wins. Within the canonical level there is *by construction* no conflict, because each canonical document owns a **distinct** domain (§2.2); an apparent canonical-vs-canonical conflict is a duplicated-authority defect resolved by amendment (§9.5).

### 8.2 The Authoritative Source Register (the heart of the Constitution)

Exactly one authoritative document per governance domain. This table *is* the "one authoritative source per governance domain" guarantee. No other document may legislate a domain listed here.

| Governance domain | Single authoritative source | Tier |
|---|---|---|
| Constitutional hierarchy, authority, amendment | **This Constitution** | L0 |
| Assignment lifecycle, evidence, audit, kernel invariants | Foundation Spec | L1 |
| Operating model (lanes, verification levels, decisions, knowledge) | Methodology v2 | L1 |
| Inheritance, DNA, lineage, capability evolution operations | Platform Genome v1 | L1 |
| Capability ownership & entity responsibilities | PO-3 Integration Spec | L1 |
| Governance process, tiers, triggers, escalation | PO-4 Governance Framework | L1 |
| Ecosystem metrics & health | PO-5 Metrics & Health Model | L1 |
| Runtime/workspace resolution | Workspace Runtime spec | L2 (under kernel) |
| Capability catalog schema | CR-1 (to be authored) | L2 (under Genome/ownership) |
| Product identity, strategy, domain content | the product's Local Expression | L4 |

Reading: the Constitution owns *meta*; each L1 document owns *one* domain; nothing owns two; every domain is owned by one. Duplicated authority is structurally impossible if every new document is registered here before it gains authority (§10).

## 9. Conflict Resolution Rules (Deliverable 6 — Conflict Resolution Model)

A deterministic algorithm; no negotiation.

1. **Identify the domain** in dispute.
2. **Look it up in the Register (§8.2).** The listed document governs; all others yield in the overlap.
3. **If the documents are in different tiers**, the higher tier wins (§8.1) — even before consulting the Register (a Local Expression never beats a Canonical document).
4. **If the domain is unclaimed** (no Register entry) → it is a **gap**: escalate to assign ownership (a constitutional amendment adds the domain to the Register, or delegates it to an existing canonical document). Until assigned, the matter is **blocked** (fail-closed — no document may self-appoint).
5. **If two documents claim the same domain** → a **duplicated-authority defect** → `architecture_conflict` escalation (kernel trigger) → the Founder resolves it by amendment assigning the domain to exactly one document.
6. **The Constitution is the final tie-breaker.** Anything unresolved by 1–5 escalates to the Founder and is resolved *against this Constitution*; the resolution is recorded and, if general, promoted into the Register by amendment.

This subsumes and unifies the local tie-breakers named in earlier documents: PO-3 remains the authority *for ownership disputes* and PO-4 *for governance disputes* — because the Register points there — and the Constitution is the authority for disputes *about the documents themselves*.

---

## PART III — CHANGE & EVOLUTION

## 10. Amendment Process

The Constitution and the canonical corpus change only through a defined process:

1. **Amendments are Lane-B, GOVERNED / L3 assignments** (PO-4 §4) — the highest tier, because a constitutional change affects the whole ecosystem.
2. **Founder sign-off is mandatory.** A constitutional amendment is a reserved Founder decision (Methodology §9, PO-4 §1.3). No amendment lands without it.
3. **Conferring or revoking canonical status** (adding a document to the Register, promoting a Supporting document to Canonical, retiring a Canonical document) is an amendment — this is the *only* way authority is granted or removed.
4. **Entrenched principles (§2.1–2.4) require the highest bar:** they may be clarified but not weakened; an amendment that contradicts an immutable principle is void.
5. **Amendments are additive and non-destructive where possible** (§24); a breaking amendment carries a migration path (§26).
6. **Every amendment is recorded** in the audit chain and versioned (§11); the Register is updated in the same amendment.

No document may amend itself into higher authority; authority is conferred only from above (the Constitution), never claimed from within.

## 11. Versioning Rules (Deliverable 9 — Versioning Model)

The Constitution and each canonical document are semantically versioned, aligned with the Genome's scheme (§18 of Genome v1) for one consistent mental model:

| Bump | Meaning | Examples |
|---|---|---|
| **MAJOR** | A breaking change to constitutional principles, the hierarchy, or the Register's ownership assignments. Requires migration. | Re-assigning a domain to a different document; changing a precedence rule. |
| **MINOR** | An additive, backward-compatible change. | Adding a new canonical document + its domain; adding a Supporting document. |
| **PATCH** | A clarification with no authority effect. | Wording, examples, cross-references. |

Documents declare the Constitution version they conform to; a MAJOR constitutional change triggers a conformance review of the corpus (§27).

## 12. Inheritance Rules (Deliverable 7 — Inheritance Model)

Authority inheritance mirrors the Genome's DNA inheritance (Genome v1 §4–5), applied to documents:

1. **Every document inherits the entire stack above it as binding context.** A Local Expression inherits all Canonical documents and the Constitution; a Supporting document inherits its parent Canonical document and the Constitution.
2. **Inheritance is by reference and version-pinned.** A document conforms to a stated version of each higher document; it does not embed private copies of their rules.
3. **Specialization is additive.** A lower document may add detail, configuration, or product-specific rules; it may never remove or contradict an inherited rule (§2.3).
4. **No sideways inheritance.** One Local Expression never inherits from another (products are siblings — Genome §21); shared rules come only from the canonical tier above.
5. **The constitutional core is inherited by all, non-optionally** — every document, of every tier, is bound by §2.1–2.4.

## 24. Evolution Rules (Deliverable 8 — Evolution Model)

How the corpus evolves over time, without contradiction:

1. **Documents evolve through their own domain's governance**, not through the Constitution — except changes to *authority* (canonical status, the Register, principles), which are constitutional amendments (§10).
2. **A canonical document may grow within its domain freely** (MINOR/PATCH under its own governance); it may cross into a new domain only by amendment that extends its Register entry.
3. **New governance needs get a new authoritative source, never a second claimant.** When a genuinely new domain appears (as CR-1 did), it is added to the Register with one owner — the ecosystem grows by adding single-owned domains, never by splitting a domain between two documents.
4. **Evolution preserves consistency.** Every evolution that could affect another document triggers the consumers as Consulted (PO-3/PO-4), and a MAJOR triggers a corpus conformance review (§27).

## 25. Deprecation Rules

1. **Deprecation ≠ deletion.** A superseded document is marked **deprecated**, retained for history (like Genome retirement, §17 of Genome v1), and removed from the Register only when its successor is registered.
2. **A domain is never left unowned.** A canonical document is deprecated only when its domain is simultaneously re-assigned to a successor — there is never a moment with a gap (fail-closed).
3. **Deprecation is an amendment** (§10) with Founder sign-off, because it changes the Register.
4. **Deprecated documents lose authority but keep provenance** — they remain readable as the lineage of the current rule.

## 26. Migration Rules

1. **MAJOR constitutional or canonical changes ship a migration path** — what changed, the successor rule, and the required conformance change for dependent documents.
2. **Documents and products migrate independently**, one at a time, within a compatibility window (mirroring Genome §20), pinned to a stated version until they migrate.
3. **Migration is non-destructive and reversible until committed** — a document's prior conformance remains valid until it adopts the new version.
4. **The Register is the migration map:** a deprecated domain's entry points to its successor, so anything conforming to the old rule can follow the pointer forward.

---

## PART IV — GOVERNANCE & METHODOLOGY HIERARCHY

## 13. Governance Hierarchy (Deliverable 5)

The Constitution does not define governance process — **PO-4 is the single authoritative source** (Register). The Constitution fixes only where governance sits in the hierarchy:

```
  Constitution (L0)  ── authorizes ──►  PO-4 Governance Framework (L1, governance domain)
        │                                     │ defines the process for
        │ reserves                            ▼
        ▼                            all change/evolution/decision governance
  Founder authority (constitutional amendments, entrenched-principle protection)
```

Constitutional governance (amending authority itself) is **above** PO-4's operational governance: PO-4 governs changes to capabilities and the core; the Constitution governs changes to *who governs*. The Founder is the approval authority for both, but constitutional amendments are the narrower, rarer, higher bar.

## 14. Methodology Hierarchy (Deliverable — methodology ordering)

Likewise, the Constitution does not define the operating model — **Methodology v2 is the single authoritative source** (Register). The Constitution fixes the ordering:

```
  Constitution (L0)
     └─► Methodology v2 (L1, operating-model domain)   ← canonical, supreme for "how we operate"
            └─► product Local Expressions (L4)          ← express/configure the methodology per product
```

A product operating-model document (a Local Expression) is **subordinate to** and an **expression of** the canonical Methodology. This is the constitutional resolution of PO-2.5 C-2 (§7): the *hierarchy* is fixed here; the *content* choice is a Founder amendment (§23).

## 23. Decision Authority Matrix (Deliverable 4 — Authority Matrix, decision view)

The Constitution does not re-define decision rights — **Methodology §16 and PO-4 §2 are the authoritative sources**. It fixes only the constitutional-level decisions and confirms the single decider for each, so no authority is duplicated:

| Decision | Single authority | Governed by |
|---|---|---|
| Amend the Constitution / entrenched principles | **Founder** | This Constitution §10 |
| Confer/revoke canonical status; change the Register | **Founder** (constitutional amendment) | §10, §25 |
| Choose canonical Methodology *content* (the open C-2) | **Founder** | §7, §14 |
| Capability ownership disputes | per **PO-3** (Founder for `architecture_conflict`) | PO-3, §9.5 |
| Governance/change/evolution disputes | per **PO-4** | PO-4 |
| Genome MAJOR / promotion to foundational | **Founder** | Genome, PO-4 §4–5 |
| Routine engineering decisions | **owning agent** (never escalated) | Methodology §16 |

Every row has one authority → no conflicting authority, consistent with PO-3's single-owner rule applied to decisions.

---

## PART V — ENTITY RELATIONSHIPS

*The Constitution does not re-legislate entity ownership — **PO-3 is the single authoritative source** (Register). It states the constitutional-level relationship and the differentiation the acceptance criteria require, and points to PO-3 for the detail. This is the no-duplication discipline: declare the authority, do not copy it.*

## 15. Platform Relationship

The four entities relate in one direction — **Definition → Implementation → Business**, with **Products** consuming and inheriting (PO-3 §9). The Constitution binds all four; each is authoritative only in its own realm. The platform is the composition of ProjectOS (definition), AI Workspace (implementation), and HQ (business); Products are built upon it.

## 16. Relationship with AI Workspace

AI Workspace is the **implementation platform**: it *realizes* every ProjectOS definition and *never authors* one (§2.7, PO-3 §2). The Constitution is implementation-independent; AI Workspace implements the Constitution, the same way it implements every canonical document — it cannot amend or reinterpret them. Authoritative detail: PO-3.

## 17. Relationship with AI Workspace HQ

HQ is the **business platform**: it consumes the platform and owns commerce (marketplace, brand, sales, marketing, customer success — PO-3 §3). HQ governs the business plane on its own track (PO-4 §1.1) and holds **no authority over any canonical document** or platform internal. Business governance never uses the engineering hierarchy and never touches the Constitution.

## 18. Relationship with Products

Products are the **domain** realm: they own Product/Domain DNA and content, express the canonical documents locally (§7), and consume the platform (PO-3 §4). Products inherit the entire canonical corpus non-optionally and specialize additively; they never override it and never depend sideways on one another. Authoritative detail: PO-3, Genome §21.

## 19. ProjectOS Responsibilities

ProjectOS is the **definitional authority** — it owns the canonical corpus (methodology, genome, ownership model, governance, metrics) and this Constitution, and it never implements or commercializes (PO-3 §1). "ProjectOS is methodology-only" is constitutionally read as **definition-only**. Authoritative detail: PO-3 §1.

## 20. AI Workspace Responsibilities

AI Workspace **implements and operates** — runtime, engines, deployment, operations, security, identity, and the realization of every ProjectOS definition (PO-3 §2). It owns no definition and no commerce. Authoritative detail: PO-3 §2.

## 21. Products Responsibilities

Products own their **domain** — Product DNA, Domain DNA, domain logic, product content, product brand and site (PO-3 §4). They consume everything above and promote proven local capabilities upward via the Genome (never sideways). Authoritative detail: PO-3 §4, Genome §13.

## 22. HQ Responsibilities

HQ owns the **business** — marketplace, ecosystem website and brand, sales, marketing, customer success (PO-3 §3). It consumes the platform and owns no platform internals. Authoritative detail: PO-3 §3.

---

## PART VI — STABILITY & REVIEW

## 27. Constitution Review Cycle

1. **Reviewed at milestones, not continuously.** A Constitution Review is triggered by: a MAJOR constitutional or canonical amendment, the onboarding of a new canonical document, a new product family, or a fixed cadence (at minimum annually) — never per feature.
2. **A review is a Lane-B governed assignment** producing a consistency check of the corpus against reality (the PO-2.5 pattern, now recurring): does every domain still have exactly one owner? Any gaps, duplications, drift, or dead documents?
3. **Reviews produce findings (Reference, L3)**, which become binding only when adopted by amendment. A review never silently changes authority.
4. **Stability is the metric.** A review that recommends few changes is a healthy sign; frequent constitutional churn is itself a flagged defect (ties to PO-5 governance KPIs).

## 28. Long-term Stability Principles (Deliverable 10 — Recommendations for long-term governance)

1. **Entrench the core; keep the edge free.** The immutable principles (§2.1–2.4) never change; product-local expression stays maximally free (§2.8). Stability at the center enables velocity at the edge.
2. **Grow by adding single-owned domains, never by splitting one.** New needs get a new authoritative source in the Register — never a second claimant on an existing domain. This is how the ecosystem scales to many products and documents without constitutional redesign.
3. **Amend rarely, additively, and with migration.** Prefer MINOR additive amendments; reserve MAJOR for genuine breaks and always ship a migration path.
4. **Keep the Constitution thin.** Resist the pull to restate domain content here; every restatement is a future duplication defect. The Constitution's power comes from being short, stable, and purely about hierarchy.
5. **The Register is the living heart — protect it.** Every new document is registered before it gains authority; an unregistered document has none. Guard the one-owner-per-domain invariant above all.
6. **Measure constitutional health** (PO-5): amendment frequency, gap/duplication counts from reviews, and time-to-resolve `architecture_conflict` escalations. Rising churn or recurring gaps signal the hierarchy needs attention — before it drifts.

---

## APPENDIX A — L2 VERIFICATION RECORD

Independent, delta-only, verdict-oriented review against the assignment's acceptance criteria and design requirements.

| Check | Verdict | Basis |
|---|---|---|
| One constitutional hierarchy | **PASS** | Single five-tier hierarchy (§3), every document placed; one precedence ladder (§8.1). |
| One authoritative source per governance domain | **PASS** | The Register (§8.2) assigns exactly one document per domain; §24.3 forbids splitting a domain. |
| No duplicated authority | **PASS** | Register is one-to-one; §9.5 makes duplication an `architecture_conflict` resolved to a single owner; the Constitution references (never restates) PO-3/PO-4/etc. |
| No conflicting ownership | **PASS** | Deterministic conflict algorithm (§9); higher tier wins; canonical docs own disjoint domains; Decision Authority Matrix (§23) has one authority per row. |
| Differentiates ProjectOS / AI Workspace / HQ / Products | **PASS** | §§15–22 state each entity's realm and point to PO-3 as authoritative — differentiation without duplication. |
| Implementation-independent | **PASS** | §2.7; constitutes documents/authority only; no code, no repo changes, no redesign of approved docs. |
| Prevents duplicate ownership (design req) | **PASS** | Register + §24.3 + §10 (authority conferred only by amendment, only to one owner). |
| Permanent hierarchy for all future documents | **PASS** | Five tiers + Register accommodate any new document by placement; §28.2 growth rule. |
| Supports ecosystem growth without constitutional redesign | **PASS** | New products = Local Expressions; new domains = new single-owned Register entries; no redesign needed (§24.3, §28.2). |
| Does not redesign existing approved documents | **PASS** | The Constitution references and orders them; it changes none (explicit in status line and throughout Part V). |
| All 28 scope items covered | **PASS** | Traceability below. |
| All 10 deliverables covered | **PASS** | Appendix B. |

**Scope traceability (28 items):** 1 §1 · 2 §2 · 3 §3 · 4 §4 · 5 §5 · 6 §6 · 7 §7 · 8 §8 · 9 §9 · 10 §10 · 11 §11 · 12 §12 · 13 §13 · 14 §14 · 15 §15 · 16 §16 · 17 §17 · 18 §18 · 19 §19 · 20 §20 · 21 §21 · 22 §22 · 23 §23 · 24 §24 · 25 §25 · 26 §26 · 27 §27 · 28 §28.

**Reviewer verdict: PASS.** No blocking issues. One hierarchy, one authoritative source per domain (the Register), deterministic conflict resolution, governed amendment/versioning/inheritance, clean four-entity differentiation by reference to PO-3, and permanent extensibility — all without restating or redesigning any existing document.

---

## APPENDIX B — DELIVERABLES INDEX

| # | Deliverable | Where |
|---|---|---|
| 1 | ProjectOS Constitution v1.0 | This document |
| 2 | Constitution Architecture | §3 (hierarchy diagram) |
| 3 | Document Hierarchy | §3–§8 |
| 4 | Authority Matrix | §8 (ladder + Register) + §23 (decision view) |
| 5 | Governance Hierarchy | §13 |
| 6 | Conflict Resolution Model | §9 |
| 7 | Inheritance Model | §12 |
| 8 | Evolution Model | §24–§26 |
| 9 | Versioning Model | §11 |
| 10 | Recommendations for long-term governance | §28 |

---

## APPENDIX C — THE CONSTITUTIONAL CORPUS REGISTER (snapshot)

The current corpus and its placement. Adding, promoting, deprecating, or re-registering any entry is a constitutional amendment (§10).

| Document | Tier | Domain owned | Realm owner (PO-3) |
|---|---|---|---|
| ProjectOS Constitution v1.0 | L0 | Constitutional hierarchy & authority | ProjectOS |
| Foundation Spec (kernel) | L1 | Kernel: lifecycle, evidence, audit | ProjectOS |
| Methodology v2 | L1 | Operating model | ProjectOS |
| Platform Genome v1 | L1 | Inheritance & lineage | ProjectOS |
| PO-3 Integration Spec | L1 | Capability ownership | ProjectOS |
| PO-4 Governance Framework | L1 | Governance process | ProjectOS |
| PO-5 Metrics & Health | L1 | Ecosystem measurement | ProjectOS |
| Workspace Runtime spec | L2 | Runtime resolution (under kernel) | ProjectOS def / AIW impl |
| architecture.md, cli.md | L2 | Kernel elaboration | ProjectOS |
| CR-1 Capability Registry spec | L2 (to be authored) | Catalog schema (under Genome/ownership) | ProjectOS def / AIW impl |
| PO-2.5 Consistency Review | L3 | Finding of fact (non-binding) | ProjectOS |
| Product constitutions, project.yaml, product specs | L4 | Product identity/strategy/content | Product |

---

*End of ProjectOS Constitution v1.0. Design only — no implementation, no code, no repository changes, no redesign of any existing approved document. The Constitution orders the documents; it does not restate them. Future implementation and any amendment are governed and assigned separately.*
