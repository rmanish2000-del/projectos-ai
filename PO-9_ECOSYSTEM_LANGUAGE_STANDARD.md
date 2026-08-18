# PO-9 — Canonical Ecosystem Language & Naming Standard v1.1

> **v1.1, 2026-08-18.** Two changes, both §20-MINOR (additive), both ruled: §5.1 Evidence Grades added as the single normative definition (PO9-GRADE-PROMOTION, 2026-08-14), and the grade set corrected from four to five by Chat ruling SEAT-VOCABULARY-CORRECTION-2 (2026-08-17): **PROPOSED is a grade**. v1.0 stands unedited in git history (commit e4e4d9f and earlier); this line is the record of what changed and why.

**One authoritative vocabulary for the entire ecosystem — every concept has exactly one official name, and every name means exactly one thing.**

**Status:** PO-9 — proposed canonical language standard. Design only; no implementation, no code, no backlog. **No renaming inside existing documents; no constitutional amendment** — this produces the standard and recommendations only.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Owned by:** ProjectOS (the naming standard is an architecture/definition artifact). Becomes canonical only by a future constitutional amendment (not performed here).
**Reviewed against:** the full corpus (Constitution, Methodology, Genome, PO-3/4/5/7/8, Kernel, Runtime) and the as-built products (EduOS-AI, TradeOS-AI).
**Honesty note:** four flagged terms — *Enterprise Experience System, Experience System, Encounter Intelligence, Design System* — have **no definition anywhere in the ProjectOS corpus** (they originate in AI Workspace / product material not on disk). Their entries below are **provisional recommendations pending source confirmation**, marked ⚠, not authoritative rulings.

---

## 0. Purpose & how to use this standard

As the ecosystem grows, ambiguity gets expensive: the same word means three things, three words mean the same thing, and acronyms collide. This standard fixes one canonical language so that a name, once read, is unambiguous — and so that future products inherit the vocabulary instead of inventing their own.

**The two rules that generate everything else:**
1. **One concept → one name.** Every important concept has exactly one official name (the single-source-of-truth principle, applied to language).
2. **One name → one concept.** No official name ever denotes two things; if a word is overloaded, at most one meaning keeps it and the others are renamed.

**How to use it:** when naming anything — a capability, registry, engine, product, ID — consult the Reserved Words (§3), pick from the Prefix table (§8), follow the category rule (§9–18), and check the term is not Deprecated (§19). New terms are added only through the process in Appendix B.

---

## PART I — THE NAMING SYSTEM

## 1. Naming Principles

1. **One concept, one name; one name, one concept.** (§0.)
2. **Name the role, not the implementation.** A name describes what a thing *is*, never the vendor or tech that realizes it — "Assignment Engine", not "PythonKernel". (Implementation-independence, per the whole corpus.)
3. **Scope is explicit.** When a reserved suffix could apply at more than one level, the name carries its scope: *Platform* Intelligence vs *Product* Intelligence.
4. **Reserved words have fixed, ecosystem-wide meaning.** Genome, Registry, DNA, Capability, Engine, Intelligence, Pack — each means exactly one thing everywhere (§3).
5. **Neutral core, specific edges.** Platform names are domain-neutral; product and domain names carry the product/domain. The core never borrows a product's word.
6. **Inheritable.** Products inherit this standard whole and add only their own product prefix and product-local terms — they never redefine a reserved word.
7. **Boring beats clever.** Prefer literal, predictable names; allow a metaphor (Genome/DNA) *only* as a reserved word with one fixed meaning.
8. **Stable and versioned.** Names change only by governed migration (alias → deprecate → retire), never by silent redefinition (§19–20).
9. **Human-first in public, ID-first internally.** A concept may have a readable public name and a canonical internal name + ID; the internal name is authoritative for engineering (§17–18).
10. **Fail-closed on ambiguity.** An un-registered or colliding name is invalid until resolved — the standard never guesses which meaning is intended.

## 2. Naming Rules

1. A **reserved word** (§3) may be used only in its canonical sense; any other use is a deprecation candidate.
2. A **"… Registry"** is one of the ten canonical metadata catalogs (PO-7). Nothing else may be called a Registry.
3. An **"… Engine"** is a runtime component that computes or executes a model (Maturity Engine, Discovery Engine); Engines are implementation-realm (AI Workspace).
4. An **"… Intelligence"** is an analytics/insight system and **must** carry a scope qualifier; *Platform Intelligence* is the only platform-scope Intelligence.
5. **"… System"** is discouraged (overloaded) — resolve to a specific type (Registry / Engine / Platform / Service / Layer). Bare "System" is deprecated (§19).
6. **"Genome"** = the inheritance architecture (exactly one, PO-2). **"DNA"** = an inheritable unit or scope (Platform/Product/Domain/Capability DNA). No other use of either word.
7. **"Pack"** = a Domain-DNA container (domain rules/vocabulary/templates). It is **not** content data (→ *content bundle*) and **not** a catalog (→ *Registry*).
8. **"Metadata"** = the registry layer collectively (PO-7); never a single registry.
9. **Casing:** Concept names in prose use Title Case (*Capability Registry*); IDs and slugs use kebab-case (*cap-evidence-verify*); prefixes and codes are UPPERCASE (*CAP-*).
10. **Prefixes** come only from the Prefix table (§8); no ad-hoc prefixes. **Acronyms** come only from the Allowed Abbreviations table (§7); no new acronym without registration.
11. **IDs** follow the ID grammar (§8.3). Every registrable thing has a canonical ID.
12. **No two official names may be homographs** (same spelling) or share an acronym — the standard resolves collisions before a term is admitted.

## 3. Reserved Words

Each may be used **only** in the sense given. (Owner = the authoritative document defining the concept.)

| Reserved word | Canonical meaning | Owner |
|---|---|---|
| **ProjectOS** | The definition realm: methodology + architecture authority (the entity, not an assignment). | Constitution |
| **AI Workspace** | The implementation platform. | PO-3 |
| **AI Workspace HQ** | The business platform. | PO-3 |
| **Kernel** | The assignment-lifecycle/evidence/audit core. | Foundation Spec |
| **Methodology** | The operating model. | PO-1 |
| **Genome** | The inheritance architecture. | PO-2 |
| **DNA** | An inheritable unit/scope (Platform/Product/Domain/Capability). | PO-2 |
| **Capability** | A reusable unit of platform ability. | PO-2 / PO-7 |
| **Registry** | A metadata catalog (one of the ten). | PO-7 |
| **Metadata** | The registry layer collectively. | PO-7 |
| **Engine** | A runtime component executing a model. | PO-3 |
| **Intelligence** | A scoped analytics/insight system. | PO-5 / PO-7 |
| **Knowledge** | Generalized, promoted learnings (the Knowledge Registry/layer). | PO-1 / PO-7 |
| **Decision** | A recorded decision event (the Decision Registry). | PO-4 / PO-7 |
| **Event** | An event *type* (the Event Registry). | PO-7 |
| **Discovery** | Reuse-candidate search over the metadata graph. | PO-7 |
| **Governance** | The proportional change/decision control system. | PO-4 |
| **Pack** | A Domain-DNA container. | Kernel / PO-2 |
| **Assignment** | The atomic unit of verified work. | Kernel |
| **Constitution** | The supreme document-ordering authority. | PO-6 |

Words that are **NOT reserved and must be qualified or avoided:** *System, Platform (bare), Experience, Service, Module, Component, Layer* — each is generic and must be preceded by a specific type or scope.

## 7. Allowed Abbreviations

The only acronyms permitted. Anything else is spelled out.

| Abbrev. | Expansion | | Abbrev. | Expansion |
|---|---|---|---|---|
| **POS** | ProjectOS (entity) | | **CAP** | Capability |
| **AIW** | AI Workspace | | **CON** | Contract |
| **HQ** | AI Workspace HQ | | **SCH** | Schema |
| **PRD** | Product (generic) | | **API** | API (interface) |
| **PO-** | Platform assignment / work item (series) | | **TOL** | Tool |
| **REG** | Registry (generic) | | **AGT** | Agent |
| **GEN** | Genome | | **PRM** | Prompt |
| **DNA** | DNA / gene | | **EVT** | Event |
| **ENG** | Engine | | **DEC** | Decision |
| **INT** | Intelligence | | **KNW** | Knowledge |
| **DSC** | Discovery | | **MAT** | Maturity |
| **GOV** | Governance | | **L0–L3** | Verification Level (reserved to verification) |
| **T0–T4** | Document Tier (reserved to Constitution tiers) | | **M0–M4** | Maturity Grade (reserved to maturity) |

Deliberately **retired/avoided acronyms** (collision-prone): **PI** (Platform Intelligence — spell out or use INT), **CR** (ambiguous: Capability Registry / Contract Registry / Change Request — never use bare "CR"), **PO** as the *entity* (use POS; PO- is work-items only).

## 8. Prefix Strategy

### 8.1 Entity / scope prefixes (who owns / where it lives)

| Prefix | Scope |
|---|---|
| `POS` | ProjectOS (definition) |
| `AIW` | AI Workspace (implementation) |
| `HQ` | AI Workspace HQ (business) |
| `PRD` | Product (generic); each product has a 3-letter code (below) |
| `PO-` | Platform assignment/work-item series (PO-1, PO-9…) |

**Product codes:** `EDU` EduOS · `TRD` TradeOS · `URJ` UrjaOps · `LGL` Legal Engineering · `KUS` PM-KUSUM · `SNX` SensexPilot. New products register a unique 3-letter code.

### 8.2 Record-type prefixes (metadata registries, PO-7)

| Prefix | Registry / type |
|---|---|
| `CAP-` | Capability | `CON-` Contract | `SCH-` Schema | `API-` API |
| `TOL-` | Tool | `AGT-` Agent | `PRM-` Prompt |
| `EVT-` | Event | `DEC-` Decision | `KNW-` Knowledge |
| `GEN-` | Genome record | `DNA-` DNA/gene | `REG-` Registry (generic) |

### 8.3 Canonical ID grammar

```
   <TYPE>-<kebab-slug-or-number>[@<version>]
   scoped (product-local):  <PRD-CODE>:<TYPE>-<slug>
```

Examples: `CAP-evidence-verify@1.2` · `DEC-0001` · `EVT-assignment-verified` · `GEN-v1` · `EDU:CAP-content-bundle` · `PO-9`. IDs are stable and immutable; a rename creates an alias, never mutates the ID (§19).

### 8.4 Reserved series (disambiguated — see Special Review §21)

| Series | Meaning | Reserved from |
|---|---|---|
| `L0–L3` | Verification Levels | Methodology |
| `T0–T4` | Document Tiers | Constitution (replaces the ambiguous "L0–L4" tier labels) |
| `M0–M4` | Maturity Grades | Genome/Maturity |
| `MS-<n>` | Implementation Milestones | Roadmap (replaces the ambiguous "M0–M17" milestone labels) |
| `POS-P<n>` | Platform phase | Kernel/platform |
| `<PRD>-P<n>` | Product phase | Product |
| `FAST/REVIEWED/GOVERNED` | Workflow modes | Methodology/PO-4 |
| `Verified/Reported/Assumed/Proposed/Blocked` | Evidence grades (closed set) | PO-9 §5.1 |
| Lanes `A/B/C/D/F` | Execution lanes | Methodology |

## 20. Versioning Rules

- **The standard is versioned** (this is v1.0). Aligned with the corpus semver scheme (MAJOR/MINOR/PATCH).
- **A term's meaning never changes silently.** A changed meaning = a new term or a version bump on the term, with the old meaning deprecated (§19). Redefinition-in-place is prohibited.
- **Adding a reserved word or prefix is a MINOR** standard change (additive); **changing/removing one is a MAJOR** (governed, migration-pathed).
- **Reserved-word and prefix changes are GOVERNED** (they affect every document and product).

## 19. Migration Rules

- **Rename = alias → deprecate → retire**, never silent replacement. The old name becomes a recorded alias pointing to the new one (lineage), kept through a compatibility window (Genome §20 discipline).
- **IDs are immutable;** a rename changes the display name, not the ID, so references never break (PO-7 reference-by-ID).
- **One document/product at a time**, backward-compatible throughout; nothing is renamed everywhere at once.
- **Per this assignment's stopping point, no renames are applied now.** §19–21 define *how* corrections land later, as governed migrations; the corrections themselves are recommendations (§21).

---

## PART II — THE CANONICAL VOCABULARY

## 4 & 5. Glossary / Canonical Vocabulary (master term table)

The authoritative name for each core concept. (Status: ✅ canonical · ⚠ provisional/needs source.)

| Canonical name | Prefix | Category | One-line meaning | Owner | Status |
|---|---|---|---|---|---|
| ProjectOS | POS | Platform | Definition realm: methodology + architecture authority | Constitution | ✅ |
| AI Workspace | AIW | Platform | Implementation platform | PO-3 | ✅ |
| AI Workspace HQ | HQ | Business | Business platform | PO-3 | ✅ |
| Kernel | — | Platform | Assignment/evidence/audit core | Kernel | ✅ |
| Methodology | — | Platform | Operating model | PO-1 | ✅ |
| Platform Genome | GEN | Platform | Inheritance architecture | PO-2 | ✅ |
| Platform/Product/Domain/Capability DNA | DNA | Inheritance | Inheritable units/scopes | PO-2 | ✅ |
| Capability | CAP | Capability | Reusable unit of ability | PO-2/7 | ✅ |
| Capability Registry | CAP/REG | Registry | Catalog of capabilities (the anchor) | PO-7 | ✅ |
| Contract Registry | CON | Registry | Semantic promises at boundaries | PO-7 | ✅ |
| Schema Registry | SCH | Registry | Canonical data shapes | PO-7 | ✅ |
| API Registry | API | Registry | Addressable operations | PO-7 | ✅ |
| Tool Registry | TOL | Registry | Invokable tools | PO-7 | ✅ |
| Agent Registry | AGT | Registry | Executors/adapters | PO-7 | ✅ |
| Prompt Registry | PRM | Registry | Instruction assets | PO-7 | ✅ |
| Event Registry | EVT | Registry | Event taxonomy | PO-7 | ✅ |
| Decision Registry | DEC | Registry | Decision ledger | PO-7 | ✅ |
| Knowledge Registry | KNW | Registry | Generalized learnings | PO-7 | ✅ |
| Maturity Engine | MAT/ENG | Engine | Grades capabilities M0–M4 | PO-5/Genome | ✅ |
| Discovery Engine | DSC/ENG | Engine | Reuse-candidate search | PO-7 | ✅ |
| Platform Intelligence | INT | Intelligence | Ecosystem analytics/insight | PO-5 | ✅ |
| Governance | GOV | Platform | Proportional control system | PO-4 | ✅ |
| Assignment | — | Workflow | Atomic unit of verified work | Kernel | ✅ |
| Workspace Runtime | — | Platform | Multi-project runtime above the kernel | P4 | ✅ |
| Pack (Domain Pack) | — | Inheritance | Domain-DNA container | Kernel/PO-2 | ✅ |
| Content Bundle | — | Product | Product content data (was EduOS "content pack") | Product | ✅ (rename) |
| Product Brief | — | Product | Founder product intent (was EduOS "product DNA") | Product | ✅ (rename) |
| Design System | — | Platform? | Reusable UI component/token library | AIW? | ⚠ needs source |
| Experience System | — | ? | End-to-end product experience layer | ? | ⚠ needs source |
| Enterprise Experience System | — | HQ? | Enterprise-facing experience offering | HQ? | ⚠ needs source |
| Encounter Intelligence | INT | Product | A product-scope Intelligence (rename to `<Product> Intelligence`) | Product | ⚠ needs source |

## 5.1 Evidence Grades (normative)

**This is the single normative definition of the evidence grades for the whole ecosystem.** The set is closed — five grades, no others:

> **VERIFIED · REPORTED · ASSUMED · PROPOSED · BLOCKED**

*Verified* means read from the artefact itself (repo/git). A claim is **Verified** unless explicitly tagged otherwise inline. "Unconfirmed" is not a grade; it maps to **Assumed**.

**ASSUMED vs PROPOSED — the gap is the useful part** (ruling wording, verbatim): "ASSUMED is something we are acting on without evidence, PROPOSED is something nobody has acted on at all. Collapsing them would let a proposal be read as an operating assumption, which is how a suggestion becomes a fact without anyone deciding."

**Provenance.** Four grades (Verified, Reported, Assumed, Blocked) were defined in `POS-COW-CHAT-BRIDGE-001-SPEC.md` §"Evidence classification" and moved here unchanged by assignment PO9-GRADE-PROMOTION (2026-08-14). The set was corrected to five by Chat ruling SEAT-VOCABULARY-CORRECTION-2 (2026-08-17), resolving the divergence PO9-GRADE-PROMOTION reported: PO-2.5's five-label citation was right and this section was short by one. PROPOSED was in live use (user preferences, EduOS `PROJECT_STATE.md`, `FOUNDER_LEARNING.md` L-002 — per PO-2.5 D-4/T-3) before it was in the standard; this entry closes that gap. A standing fleet rule (INTEL-INTEGRATION, 2026-08-14) depends on this vocabulary, which is why it lives in the standard rather than in a handoff document.

**Gloss status, honestly.** *Verified* is glossed by its source wording; *Assumed* and *Proposed* by the ruling quoted above; *Reported* and *Blocked* are named but not glossed anywhere authoritative. That remaining gap is preserved rather than filled — glossing them is a separate proposal (Appendix B).

**Do not confuse with `EvidenceClass`** (kernel, Foundation Spec §8.1 — `commit`, `pr`, `ci_run`, `test_report`, `artifact`, `approval`). That is *what kind of evidence exists*; an evidence grade is *how well a claim is supported*. Two concepts, two vocabularies, similar words — §2.12 (no homographs) applies: prefer "evidence **grade**" for this set and "evidence **class**" for the kernel's.

## 14. Platform Naming

The three platform entities are fixed reserved names: **ProjectOS** (definition), **AI Workspace** (implementation), **AI Workspace HQ** (business). No new "platform" is coined without a governed reserved-word addition. Bare "Platform" is always qualified ("the platform" = AI Workspace's implementation platform in context; write the specific name when precision matters).

## 10. Registry Naming

Pattern: **`<Type> Registry`**, where `<Type>` is one of the ten canonical types (§8.2). Exactly one registry per type (PO-7 single-source). ID prefix per type. Nothing outside the ten is a "Registry" — a product's internal catalog uses a product-scoped name (e.g., `EDU:Content Registry`), never bare "Registry".

## 12. Engine Naming

Pattern: **`<Function> Engine`** — a runtime that executes a model (Maturity Engine, Discovery Engine). Engines are AI-Workspace-owned (implementation). The model an Engine executes is ProjectOS-owned and named separately (e.g., the *Maturity model* vs the *Maturity Engine*).

## 13. Intelligence Naming

Pattern: **`<Scope> Intelligence`** — always scope-qualified. **Platform Intelligence** is the single platform-scope system (PO-5). A product's analytics is **`<Product> Intelligence`** (e.g., `EDU Intelligence`). "Encounter Intelligence" resolves to `<Product> Intelligence` once its product is confirmed (§21).

## 11 → renumbered. Capability Naming (scope item 10)

Pattern: **`CAP-<verb-noun>`** (kebab-case), domain-neutral for platform capabilities: `CAP-evidence-verify`, `CAP-telemetry-ingest`, `CAP-doc-generate`. Product-local capabilities are scoped: `EDU:CAP-content-compile`. A capability name states the ability, never the implementation. Promotion to platform drops any product scope (Genome §13).

## 9. Product Naming

- **Family suffix convention:** platform-grade products use **`…OS`** (EduOS, TradeOS). Operations tools use **`…Ops`** (UrjaOps). *Recommendation (§21): make this rule explicit so UrjaOps vs TradeOS isn't read as inconsistency.*
- **Product code:** a unique 3-letter UPPER code per product (§8.1) for IDs.
- **Public/brand name** (e.g., EduOS's "Gyan Tara") is HQ/brand-owned and separate from the technical product name (§17); it must not collide with a reserved word.
- **Canonical domains** (e.g., `eduos.ai`) are product-owned.

## 15. Business Naming

HQ owns public/commercial names (marketplace, brand, campaigns). Business names follow brand rules, **but may not reuse a reserved word** (§3) in a conflicting sense. A commercial name that needs a technical concept references its canonical internal name (§17–18).

## 16. Technical Naming

IDs, prefixes, and slugs per §8; kebab-case identifiers; UPPER prefixes; the ID grammar §8.3. Code symbols follow the language's conventions but derive from the canonical name (a capability `CAP-evidence-verify` → module/identifier `evidence_verify`), so code and vocabulary stay traceable.

## 17. Public-facing Terminology

- Readable, brand-appropriate, jargon-free; owned by HQ (business) or the product.
- A public term **maps to exactly one canonical internal name** (a documented alias). "Gyan Tara" → `PRD:EDU`. The map is authoritative; the public name is a presentation of the canonical one.
- Public terms never redefine reserved words; where a public surface needs a platform concept, it uses plain language, not an overloaded reserved word.

## 18. Internal Terminology

- Canonical internal names + IDs (§8) are **authoritative for engineering, governance, and metadata**.
- Every internal concept has one canonical name (the glossary, §4–5); prose uses the canonical name, IDs use the prefixed form.
- Internal names are domain-neutral at the platform level; product-local internal names carry the product code.

---

## PART III — CORRECTIONS

## 6. Deprecated Terms

Deprecated term → canonical replacement, with the reason. (Recommendations; renames land later as governed migrations, §19.)

| Deprecated | → Canonical | Reason |
|---|---|---|
| "product DNA" (EduOS sense) | **Product Brief** | Collides with Genome "Product DNA"; different concept (founder intent vs identity+genes). |
| "content pack" (EduOS) | **Content Bundle** | "Pack" is reserved for Domain DNA; content data is not a pack. |
| "Pack Registry" (EduOS backend) | **`EDU:Content Registry`** | "Registry" reserved for the ten; product-scope it and rename to reflect content, not packs. |
| bare "pack" (ambiguous) | **Domain Pack** (or scope it) | "Pack" = Domain-DNA container only. |
| bare "System" (Experience/Enterprise Experience) | a specific **Registry/Engine/Platform/Layer** | "System" is overloaded; resolve to a type (§21). |
| "Encounter Intelligence" | **`<Product> Intelligence`** | "Intelligence" must be scope-qualified; avoid a bespoke name. |
| "PO" as the *entity* | **POS** (entity); **PO-** = work items | Acronym collision (entity vs assignment series). |
| "PI" (for Platform Intelligence) | spell out / **INT** | Collides with common "PI" uses. |
| bare "CR" | spell out the registry | Ambiguous: Capability/Contract/Content Registry / Change Request. |
| "L0–L4" document tiers | **T0–T4** | Collides with L0–L3 verification levels. |
| "M0–M17" milestones | **MS-0…MS-17** | Collides with M0–M4 maturity grades. |

## 21. Special Review — findings & recommended permanent corrections

Reviewed the corpus for the four failure classes. Findings, with recommended corrections (to be applied later as governed migrations — **not applied here**).

### 21.1 Duplicate names (one word, many meanings)

| Word | Conflicting meanings | Recommendation |
|---|---|---|
| **Registry** | Capability Registry (PO-7) · EduOS "Pack Registry" (content) | Reserve for the ten; rename EduOS's to `EDU:Content Registry`. |
| **DNA / Product DNA** | Genome "Product DNA" (identity+genes) · EduOS "product DNA" (strategy) | Reserve for Genome; EduOS → "Product Brief". |
| **Pack** | kernel Domain Pack · Shared/Packs catalog · Genome Domain DNA · EduOS "content pack" | Reserve "Pack" = Domain DNA container; EduOS → "Content Bundle". |
| **Intelligence** | Platform Intelligence (ecosystem) · "Encounter Intelligence" (product) | Require scope qualifier; the two are different scopes, both valid once qualified. |
| **System** | Experience System · Enterprise Experience System · Design System · "operating system" senses | Deprecate bare "System"; resolve each to a specific type (§21.4). |

### 21.2 Conflicting acronyms

| Acronym | Collides | Recommendation |
|---|---|---|
| **PO** | ProjectOS (entity) vs PO-n (assignment series) | Entity = **POS**; keep PO- for work items only. |
| **CR** | Capability Registry ("CR-1") / Contract Registry / Content Registry / Change Request | Never use bare "CR"; spell out; drop the "CR-1" label in favor of "Capability Registry (PO-7)". |
| **M0/M-series** | Maturity Grade M0–M4 vs Roadmap Milestones M0–M17 | Milestones → **MS-0…MS-17**; reserve M0–M4 for maturity. |
| **L2 / L-series** | Verification Level L0–L3 vs Constitution Document Tier L0–L4 | Tiers → **T0–T4**; reserve L0–L3 for verification. |
| **PI** | Platform Intelligence vs common "PI" | Use **INT** or spell out. |
| **P-phases** | Kernel P1–P4 · EduOS P0–P6 · roadmap phases | Namespace: **POS-Pn** (platform) · **`<PRD>-Pn`** (product). |

### 21.3 Misleading terminology

| Term | Why misleading | Recommendation |
|---|---|---|
| "Pack Registry" | Holds content, not packs | Rename to Content Registry (product-scope). |
| "AI Workspace" (bare) | Could read as a product, not the platform | Always qualify: "AI Workspace (implementation platform)" vs a named product. |
| "Genome / DNA" | Metaphor — but *acceptable* as a reserved word with fixed meaning | Keep; it is consistent and load-bearing. |
| "Encounter Intelligence" | Bespoke name hides that it's a product-scope Intelligence | Rename to `<Product> Intelligence`. |

### 21.4 Future scaling problems

| Problem | Risk as ecosystem grows | Recommendation |
|---|---|---|
| **3-letter code exhaustion** (products, prefixes) | Collisions when many products/types exist | Register codes centrally; allow 4-letter fallback when 3-letter space is contended. |
| **Suffix proliferation** (…System, …Engine, …Intelligence, …Service) | New coinages re-blur the vocabulary | Only Engine/Intelligence/Registry are reserved suffixes; "System/Service/Module/Layer" require justification and registration. |
| **"…OS" vs "…Ops" product suffix** | Read as inconsistency (TradeOS vs UrjaOps) | Make the rule explicit: **…OS** = platform-grade product; **…Ops** = operations tool. |
| **The Experience/Design/Enterprise cluster** ⚠ | Four undefined, overlapping terms will harden into permanent ambiguity if left | **Resolve at the concept level first** (source not in corpus): likely *Design System* = UI component/token library (AIW capability); *Experience System* = a product's end-to-end UX layer; *Enterprise Experience System* = HQ's enterprise offering. **Founder/AI Workspace to confirm the concepts, then this standard assigns one canonical name each.** |
| **Public vs internal drift** | Brand names outrunning canonical names | Enforce the public→canonical alias map (§17) so every public term resolves. |

**Priority corrections (highest ambiguity cost first):** (1) T0–T4 vs L0–L3 tier/level collision; (2) MS-n vs M0–M4 milestone/maturity collision; (3) POS vs PO- entity/assignment; (4) the Registry/Pack/DNA overloads; (5) resolve the Experience/Design/Enterprise cluster (blocked on concept confirmation).

---

## APPENDIX A — L2 REVIEW

| Check | Verdict | Basis |
|---|---|---|
| One canonical language standard produced | **PASS** | This document: principles → rules → reserved words → vocabulary → corrections. |
| Every important concept has exactly one official name | **PASS** | §4–5 master table: one canonical name per concept; §3 reserved words fix meaning. |
| No ambiguity remains (for corpus terms) | **PASS** | §21 identifies every overload/collision in the corpus and assigns a single resolution; unsourced terms are explicitly flagged ⚠ not silently resolved. |
| Future products inherit the standard | **PASS** | §1.6 inheritance principle; §9 product naming; Appendix B add-process. |
| All 20 scope items present | **PASS** | Principles §1 · Rules §2 · Reserved §3 · Glossary §4 · Canonical Vocab §5 · Deprecated §6 · Abbreviations §7 · Prefix §8 · Product §9 · Capability (§"Capability Naming") · Registry §10 · Engine §12 · Intelligence §13 · Platform §14 · Business §15 · Technical §16 · Public §17 · Internal §18 · Migration §19 · Versioning §20. |
| Special review complete | **PASS** | §21 covers duplicate names, conflicting acronyms, misleading terms, scaling problems, with recommended corrections. |
| No renaming applied; no amendment performed | **PASS** | §19 states corrections are recommendations; status line and §21 confirm nothing renamed in existing docs. |
| Honest about unsourced terms | **PASS** | Four external terms marked ⚠ provisional pending source confirmation, not authoritatively ruled. |

**Reviewer verdict: PASS.** No blocking issues. The standard establishes one canonical name per concept, a collision-free prefix/acronym system (fixing real collisions including tier-vs-level and milestone-vs-maturity), a deprecation map, and a complete special review — while honestly deferring four terms whose concepts are not yet defined, and applying no renames.

---

## APPENDIX B — Adding a new term (the process)

1. Check it is not an existing concept under a different name (one concept, one name).
2. Check it collides with no reserved word or acronym (§3, §7).
3. Assign a category (§9–18), a prefix (§8), and a canonical ID.
4. Add it to the glossary (§4–5) via a MINOR standard version bump (governed reserved-word/prefix additions are GOVERNED).
5. If it replaces a term, register the old as a deprecated alias (§19) — never silently reuse or redefine.

---

*End of PO-9 Canonical Ecosystem Language & Naming Standard v1.1 (v1.0 + §5.1 Evidence Grades, five-grade set per SEAT-VOCABULARY-CORRECTION-2). Design only — no implementation, no renaming inside existing documents, no constitutional amendment. One concept, one name; corrections are recommendations to be applied later as governed migrations.*
