# PO-7 — Platform Metadata Architecture

**The ecosystem's metadata layer — ten registries, each the single source of truth for one kind of metadata, linked into one graph by reference and never by copy.**

**Status:** PO-7 (Revised) — proposed canonical metadata architecture. Design only; no implementation, no code, no contracts authored, no repository changes. Defines the *models* of the registries, not their contents.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Owned by:** ProjectOS owns the registry *models* (what each record means); AI Workspace's platform (the metadata substrate / Platform Intelligence) *implements and runs* the stores — per `PO-3` §7.
**Constitutional placement:** a **Supporting document (L2)** under the Genome (inheritance) and PO-3 (ownership) canonical documents; it fulfils and supersedes the "CR-1 (to be authored)" placeholder in the Constitution Register (§16). Registering it is a constitutional amendment (Constitution §10).
**Inputs (governed, not restated):** `PLATFORM_GENOME_V1.md`, `PROJECTOS_METHODOLOGY_V2.md`, `PO-3`, `PO-4`, `PO-5`, `PROJECTOS_CONSTITUTION_V1.md`, `PROJECTOS_V0_1_FOUNDATION_SPEC.md`.

---

## 0. Design principles for the metadata layer

Metadata is what lets the ecosystem know itself — what capabilities exist, what they promise, what data they exchange, who runs them, what happened, and what was learned. Ten registries hold it. The danger with ten of anything is overlap; these principles make the ten disjoint and coherent.

1. **One registry per metadata type — single source of truth.** Each kind of metadata has exactly one registry that owns it (Constitution §2.2 applied to metadata). No fact lives authoritatively in two registries.
2. **Reference, never copy.** Registries link to each other by **stable ID**, never by duplicating each other's content. The API Registry references a Contract by ID; it does not restate the contract. This is the anti-duplication rule and the reason the ten compose cleanly.
3. **The registries form one metadata graph.** Stable IDs + references make the ten a single queryable graph (§13). The Capability Discovery Engine searches it; Platform Intelligence analyses it (both AI-Workspace-owned, PO-3).
4. **Evidence-derived and fail-closed.** Records are created from evidence (kernel/CI/lineage), not from claims. A dangling reference (broken ID) is a fail-closed error, never silently ignored.
5. **Uniform versioning & lineage.** Every registry versions its records semantically and keeps append-only history, aligned with the Genome's scheme (Genome §18–19) — one mental model across all ten.
6. **Owned once, implemented once.** ProjectOS owns every registry *model*; AI Workspace implements every registry *store* (PO-3). No registry is co-owned; "shared" means consumed by many (Constitution / PO-3 §5).
7. **Boundary discipline is mandatory.** Every registry is specified with what it **holds** and what it **does NOT hold** (delegated to a named neighbor). The boundary matrix (§12) is the contract that keeps them disjoint.

---

## 1. Architecture — three planes and the metadata graph

The ten registries group into three planes by what their metadata describes: **what exists and its shape** (structural), **who/what acts** (execution), and **what happened, was decided, and was learned** (activity/ledger). The Capability Registry is the anchor every other registry references.

```
┌──────────────────────── STRUCTURAL PLANE (what exists & its shape) ───────────────────────┐
│   CAPABILITY ─┬─ defines boundary ─► CONTRACT ─┬─ shapes data ─► SCHEMA                    │
│   (the anchor)│                                 └─ exposed via ─► API ──► (refs Contract+Schema)│
└──────────────┼────────────────────────────────────────────────────────────────────────────┘
               │ implemented / invoked by ▼
┌──────────────┼──────────── EXECUTION PLANE (who/what acts) ────────────────────────────────┐
│   TOOL ──wraps──► API ;   AGENT ──uses──► TOOL + PROMPT ;   PROMPT ──instructs──► AGENT     │
└──────────────┼────────────────────────────────────────────────────────────────────────────┘
               │ produces ▼
┌──────────────┼──────── ACTIVITY / LEDGER PLANE (what happened / decided / learned) ─────────┐
│   EVENT (taxonomy, refs SCHEMA) ;  DECISION (log, refs PO-4 classes) ;                       │
│   KNOWLEDGE (promoted learnings) ◄── promoted-from ── DECISION (recurring → default)         │
└─────────────────────────────────────────────────────────────────────────────────────────────┘

   All ten link by STABLE ID (never copy). Discovery searches the graph; Platform Intelligence reads it.
```

---

## PART I — STRUCTURAL REGISTRIES

## 2. Capability Registry (the anchor)

**Purpose:** the catalog of *what the platform can do*. The anchor every other registry references.
**Holds:** capability identity (stable ID, name), maturity grade (M0–M4, from the Maturity Engine — referenced, not computed here), status (active/deprecated/retired), consumer list (which products express it), **references** to its owning Genome layer, its lineage node, and the Contracts/APIs/Tools/Agents/Prompts that belong to it.
**Does NOT hold:** the capability's interface (→ Contract), its data shapes (→ Schema), its endpoints (→ API), its runtime maturity computation (→ Maturity Engine), its inheritance genetics (→ Genome). It holds the capability *as a unit* and points to the rest.
**Owner / Impl:** ProjectOS (model) / AI Workspace (store). **Consumers:** Genome, Discovery, Maturity, Platform Intelligence, products.
**Links:** → Contract, API, Tool, Agent, Prompt (by ID); ↔ Genome lineage (Genome §9 binding seam).
**Versioning/Governance:** record changes REVIEWED; schema of the registry GOVERNED (Constitution/PO-4).

## 3. Contract Registry

**Purpose:** the *semantic promises at boundaries* — what a provider guarantees a consumer. The home of "public contracts" (the kernel's `breaking_public_contract` governed trigger lives here).
**Holds:** contract identity, provider and consumer (capability IDs), the promised behavior/semantics (design-level description), version, compatibility band, breaking-change status.
**Does NOT hold:** the data structure exchanged (→ Schema, by ref), the callable endpoint (→ API, by ref), the capability itself (→ Capability). It holds the *agreement*, not its shape or address.
**Owner / Impl:** ProjectOS / AI Workspace. **Consumers:** capabilities on both sides, Governance (contract changes), Discovery.
**Links:** → Schema (data), ← Capability (provider/consumer), → API (fulfilled by).
**Versioning/Governance:** a breaking contract change is **GOVERNED / L3** (kernel trigger, PO-4 §8); compatible changes REVIEWED. Compatibility bands mirror Genome §19.

## 4. Schema Registry

**Purpose:** the *canonical data shapes* — the structures exchanged and stored (record shapes, event payloads, config).
**Holds:** schema identity, structural definition (design-level reference), version, compatibility mode (backward/forward/full), producers and consumers.
**Does NOT hold:** behavioral promises (→ Contract), transport/endpoints (→ API), event semantics (→ Event, which references a schema). Pure structure + evolution rules.
**Owner / Impl:** ProjectOS / AI Workspace. **Consumers:** Contracts, APIs, Events, capabilities.
**Links:** ← Contract, ← API, ← Event (all reference a schema by ID).
**Versioning/Governance:** schema evolution follows compatibility rules; a backward-incompatible schema change is a breaking contract → GOVERNED. This is the classic schema-registry compatibility discipline, aligned with Genome versioning.

## 5. API Registry

**Purpose:** the *addressable surfaces* — the operations exposed for invocation.
**Holds:** API identity, operations, the Contract it fulfils (ref), the Schemas it uses (ref), version, deprecation status, owning capability (ref).
**Does NOT hold:** the semantic promise (→ Contract) or the data shape (→ Schema) — it *references* both; the wrapping tool (→ Tool). It holds *where and how to call*, nothing the neighbors own.
**Owner / Impl:** ProjectOS (model) / AI Workspace (runs the surface). **Consumers:** Tools, agents, products, integrations.
**Links:** → Contract (fulfils), → Schema (uses), ← Tool (wraps), ← Capability (belongs to).
**Versioning/Governance:** API version tied to its Contract; deprecation follows the migration model (§15). Endpoint changes REVIEWED; contract-affecting changes GOVERNED.

---

## PART II — EXECUTION REGISTRIES

## 6. Tool Registry

**Purpose:** the *invokable tools* agents can call — MCP tools, functions, connectors (e.g., the `mcp__*` tools in this very session).
**Holds:** tool identity, the API/Contract it wraps (ref), the capability it belongs to (ref), permission scope, availability/status, version.
**Does NOT hold:** the agent that calls it (→ Agent), the prompt that instructs its use (→ Prompt), the API definition (→ API, by ref). It holds *the invokable*, referencing what it wraps.
**Owner / Impl:** ProjectOS (model) / AI Workspace (registers/serves tools). **Consumers:** agents, Discovery, security/governance (scope review).
**Links:** → API (wraps), ← Agent (uses), ← Capability.
**Versioning/Governance:** tool availability and scope are security-sensitive → REVIEWED, GOVERNED if it touches a security boundary (PO-4).

## 7. Agent Registry

**Purpose:** the *executors* — the AI-team agents and adapters (Claude Code, Cowork, ChatGPT, humans, future agents) bound to roles (PO-3 §12, Methodology §8).
**Holds:** agent identity, adapter type, role binding (Architect/Engineer/Reviewer/…), the Tools it may use (ref), the Prompts it runs (ref), verification authority (which levels it may execute/approve).
**Does NOT hold:** the prompts themselves (→ Prompt), the tools themselves (→ Tool), the assignment routing rules (→ Methodology/kernel routing). It holds *who/what executes and with what authority*.
**Owner / Impl:** ProjectOS (role model) / AI Workspace (adapter registration). **Consumers:** the routing/assignment engine, governance (authority checks), Platform Intelligence (AI Adoption metric, PO-5 §10).
**Links:** → Tool (uses), → Prompt (runs), ↔ PO-3 agent-adapter map.
**Versioning/Governance:** an agent's verification authority is governance-sensitive → REVIEWED; binding an agent to `human` approval authority requires manifest-owner identity (kernel §8.6).

## 8. Prompt Registry

**Purpose:** the *reusable instruction assets* — system prompts, task templates, skill instructions, grounding constraints.
**Holds:** prompt identity, version, the agent/role and capability/task it serves (ref), grounding/guardrail constraints, evaluation status.
**Does NOT hold:** the agent (→ Agent), the knowledge content it may cite (→ Knowledge, by ref), the tools it names (→ Tool, by ref). It holds *the instruction*, referencing who runs it and what it grounds on.
**Owner / Impl:** ProjectOS (model) / AI Workspace (store); prompt *content* for a product is a product Local Expression. **Consumers:** agents, evaluation, governance.
**Links:** ← Agent (runs), → Knowledge (grounds on), → Tool (invokes).
**Versioning/Governance:** prompts affecting safety/pedagogy (e.g., EduOS child-facing grounding) are REVIEWED+; a change to a governed-safety prompt is GOVERNED.

---

## PART III — ACTIVITY / LEDGER REGISTRIES

## 9. Event Registry

**Purpose:** the *event taxonomy* — the catalog of event *types* the ecosystem can emit (not the instances).
**Holds:** event-type identity, payload Schema (ref), producers and consumers, version, semantics.
**Does NOT hold:** event *instances* (those are runtime data — the kernel audit stream, EduOS's `EventLog`, analytics — read by Platform Intelligence), nor the payload structure itself (→ Schema, by ref). It holds *what kinds of things can happen* and their payload binding.
**Owner / Impl:** ProjectOS (taxonomy model) / AI Workspace (store; the instance stream is runtime, not a registry). **Consumers:** producers/consumers of events, Platform Intelligence, Schema Registry.
**Links:** → Schema (payload), ↔ producing/consuming Capabilities.
**Versioning/Governance:** event-type changes follow schema compatibility; adding an event type is additive (MINOR), changing a payload incompatibly is a breaking contract (GOVERNED).

## 10. Decision Registry

**Purpose:** the *decision ledger* — the append-only record of decisions made (the runtime home of PO-4 Decision Governance and the kernel's decision audit).
**Holds:** decision identity, class (routine / genuine-founder / legal / security / … per PO-4 §2), options considered, choice, consequence, decider, timestamp, escalation reference, and whether it was promoted to a default.
**Does NOT hold:** the *generalized* learning a recurring decision becomes (→ Knowledge, by promotion), nor the decision-making *rules* (→ PO-4, the authoritative source). It holds *what was decided*, as events; the rules for deciding live in PO-4.
**Owner / Impl:** ProjectOS (model) / AI Workspace (store); anchored to the kernel audit chain (evidence). **Consumers:** governance, Founder Decision Budget dashboard (PO-5 §3), Knowledge Registry (promotion).
**Links:** → Knowledge (recurring decision `promoted-to` a default), ↔ kernel audit, ↔ PO-4 escalations.
**Versioning/Governance:** append-only (never rewritten); routine decisions are *not* recorded here (that would be governance overhead — PO-4 §2.5); only genuine/governed decisions are logged.

## 11. Knowledge Registry

**Purpose:** the *promoted, generalized learnings* — the structural home of the Methodology Knowledge Lifecycle (§12) and the Genome knowledge layer (§22).
**Holds:** knowledge item identity, type (convention / lesson / pattern / default), promotion status (captured → generalized → promoted), scope (product-local / platform), freshness/retirement.
**Does NOT hold:** individual decision events (→ Decision — knowledge is what a *recurring* decision *generalizes into*), nor the prompt that applies it (→ Prompt, by ref). The seam with Decision is **promotion**: a specific decision that recurs is promoted into a general default here.
**Owner / Impl:** ProjectOS (model) / AI Workspace (store). **Consumers:** all agents (inherit defaults), prompts (grounding), Platform Intelligence (Knowledge Maturity, PO-5 §8).
**Links:** ← Decision (`promoted-from`), ← Prompt (grounds on), ↔ Genome epigenetic knowledge layer (Genome §22).
**Versioning/Governance:** promotion of product-local knowledge to platform is governed like a capability promotion (PO-4 §5); stale knowledge is retired non-destructively (Genome §17 pattern).

---

## PART IV — CROSS-CUTTING MODELS

## 12. Boundary Matrix (the anti-duplication contract)

The crisp seam between each registry and its nearest neighbors — the single most important table for keeping ten registries disjoint.

| Registry | Owns (the one thing) | Nearest neighbor(s) | The seam (what distinguishes them) |
|---|---|---|---|
| Capability | the *unit* of ability | Contract, API | Capability = the thing; Contract = its promise; API = its address. |
| Contract | the *semantic promise* | Schema, API | Contract = behavior guaranteed; Schema = data shape; API = how to call. |
| Schema | the *data structure* | Contract, Event | Schema = shape only; Contract = behavior; Event = when a shaped payload flows. |
| API | the *addressable operation* | Contract, Tool | API = where/how to call; Contract = what it promises; Tool = an agent-invokable wrapper of it. |
| Tool | the *invokable* | API, Agent | Tool = the callable an agent uses; API = the underlying surface; Agent = who calls. |
| Agent | the *executor + authority* | Tool, Prompt | Agent = who/what runs; Tool = what it invokes; Prompt = its instructions. |
| Prompt | the *instruction asset* | Agent, Knowledge | Prompt = the instruction; Agent = who runs it; Knowledge = the generalized truth it grounds on. |
| Event | the *event type* | Schema, (audit stream) | Event = taxonomy of what can happen; Schema = payload shape; instances = runtime data, not a registry. |
| Decision | the *decision event* | Knowledge, PO-4 | Decision = what was chosen (log); Knowledge = the generalization; PO-4 = the rules. |
| Knowledge | the *generalized learning* | Decision, Prompt | Knowledge = promoted default/convention; Decision = the specific events it came from; Prompt = an asset that applies it. |

No two rows own the same thing → **no duplicated metadata authority**.

## 13. Reference model — the metadata graph

1. **Every record has a stable, immutable ID.** IDs are the only thing registries share.
2. **Links are typed references by ID** (`belongs-to`, `fulfils`, `uses`, `wraps`, `grounds-on`, `promoted-from`, `refs-schema`). A reference names a target registry + ID; it never embeds the target's content.
3. **The ten registries compose into one directed metadata graph.** The Capability is the hub; the graph is queryable end-to-end ("which agents, via which tools, can invoke the APIs that fulfil this capability's contracts, and what events do they emit?").
4. **Referential integrity is fail-closed.** A reference to a missing/retired ID is an error surfaced by validation, never silently dropped — mirroring the kernel's fail-closed and the Genome's no-stranded-consumer rule.
5. **Discovery and Intelligence read the graph; only registry writes author it** (PO-3: those engines are AI-Workspace-owned readers).

## 14. Ownership & governance

- **Every registry model is ProjectOS-owned; every registry store is AI-Workspace-implemented** (PO-3 §7). This whole document is the ProjectOS-owned model set; Platform Intelligence / the metadata substrate is the implementation.
- **Consumers are many; owners are one** (Constitution). Registries are shared by consumption, never co-owned.
- **Change governance is per-record proportional** (PO-4 §8): adding/updating a record is FAST/REVIEWED; changing a *registry's model or a public contract/schema* is GOVERNED. Governance introduces no new trigger — it reuses the closed set.
- **Records are evidence-anchored** to the kernel audit where they assert facts (decisions, promotions), so metadata cannot be fabricated (PO-5 §0).

## 15. Versioning, lineage & compatibility

- **Semantic versioning across all registries** (MAJOR/MINOR/PATCH), aligned with Genome §18 — one model for the whole ecosystem.
- **Append-only history / lineage** on every registry: records are versioned, superseded-not-deleted; retirement preserves provenance (Genome §17 pattern). Decision and Knowledge registries are strictly append-only ledgers.
- **Compatibility bands** on Contract, Schema, API, Event (the interface-bearing registries): a change within a MAJOR is compatible; a breaking change is a governed, migration-pathed event (Genome §19–20).
- **Migration is non-destructive, one consumer at a time**, following the reference (`superseded-by`) forward — the same migration discipline as the Genome and the Constitution (§26 there).

## 16. Constitutional placement

Per the Constitution: this document is a **Supporting document (L2)** under the Genome and PO-3, and it **fulfils the "CR-1 (to be authored)" Register entry** — the Capability Registry is defined here as one of ten registries. Because the metadata layer is a coherent domain, the Constitution Register should carry a single entry, *"Ecosystem metadata architecture → PO-7 (L2)"*, owned ProjectOS-def / AIW-impl. **Adding/replacing that Register entry is a constitutional amendment** (Constitution §10) requiring Founder sign-off — flagged here, not performed (this assignment designs; it does not amend the Constitution).

---

## 17. Recommendations for implementation

Design-level only; implementation assigned separately. Sequenced by dependency.

1. **Build the Capability Registry first** — it is the anchor every other registry references and the standing Blocker (PO-2.5 M-1). Its record model + Genome binding seam is the critical path.
2. **Then Schema + Contract** — the interface substrate the API/Event/Tool registries reference; nothing invocation-layer is safe to build before its shapes and promises exist.
3. **Then API + Tool + Agent + Prompt** — the execution layer, in that order (each references the prior).
4. **Then Event + Decision + Knowledge** — the ledgers; Decision and Knowledge anchor to the kernel audit and the Genome knowledge layer.
5. **Enforce reference integrity from day one** — a registry without fail-closed ID validation will accumulate dangling references and silently rot; integrity is not a later feature.
6. **Do not duplicate across registries** — every implementation review checks the boundary matrix (§12); a field that copies a neighbor's content instead of referencing its ID is a review-blocking defect.
7. **Register once in the Constitution** — a single metadata-layer Register entry, by amendment, before the layer gains authority.

**Top risks & mitigations:** *registry overlap* → boundary matrix as a review gate (§12); *dangling references* → fail-closed integrity (§13.4); *metadata fabrication* → evidence-anchoring (§14); *duplication with runtime data* → registries hold *definitions/taxonomy*, not instances (Event/Decision seams).

---

## APPENDIX A — L2 VERIFICATION RECORD

Independent, delta-only, verdict-oriented review.

| Check | Verdict | Basis |
|---|---|---|
| All 10 registries defined | **PASS** | Capability §2 · Contract §3 · Schema §4 · API §5 · Tool §6 · Agent §7 · Prompt §8 · Event §9 · Decision §10 · Knowledge §11. |
| Boundaries non-overlapping (single source per metadata type) | **PASS** | Every registry has explicit holds / does-NOT-hold; §12 boundary matrix shows the distinguishing seam for each; no two own the same thing. |
| Reference, never copy (anti-duplication) | **PASS** | §0.2, §13: registries link by stable ID; embedding a neighbor's content is a review-blocking defect (§17.6). |
| Composes into one coherent architecture | **PASS** | Three planes (§1) + metadata graph (§13); Capability is the anchor; links are typed references. |
| Ownership correct | **PASS** | ProjectOS owns models, AI Workspace implements stores (§14, PO-3 §7); consumers many, owners one. |
| Governance consistent | **PASS** | Proportional per PO-4 (§14); breaking contract/schema GOVERNED; no new trigger; evidence-anchored. |
| Constitutional placement correct | **PASS** | L2 Supporting doc; fulfils CR-1 Register entry; amendment flagged not performed (§16). |
| Implementation-independent / implementation-ready | **PASS** | Registry *models* only (no code, no contracts authored); concrete enough to sequence implementation (§17). |

**Reviewer verdict: PASS.** No blocking issues. Ten registries, each the single source of truth for one metadata type, disjoint by the boundary matrix, linked by reference into one graph, owned and governed consistently with the corpus, and implementation-ready without containing implementation.

---

## APPENDIX B — RELATIONSHIP TO PRIOR SPECS

- **Genome v1** — the Capability Registry is the catalog the Genome binds to (Genome §9); registries supply the nouns, the Genome the genetics; versioning/lineage/compatibility are shared.
- **Methodology v2** — Knowledge and Decision registries are the structural home of the Knowledge Lifecycle (§12) and decision framework (§16).
- **PO-3** — fixes ownership: ProjectOS models, AI Workspace stores, Discovery/Intelligence read. This document is the ProjectOS-owned model set.
- **PO-4** — governs registry changes proportionally (breaking contract/schema = GOVERNED); Decision Registry is Decision Governance's ledger.
- **PO-5** — Platform Intelligence reads the metadata graph; Knowledge/Decision/Capability registries feed the health scores.
- **Constitution (PO-6)** — places this as an L2 Supporting document and requires a single Register entry by amendment (§16); single-source-per-type is the Constitution's single-source rule applied to metadata.
- **Kernel** — records asserting facts anchor to the hash-chained audit; fail-closed referential integrity mirrors kernel fail-closed.

---

*End of PO-7 Platform Metadata Architecture. Design only — no implementation, no code, no contracts authored, no repository changes. Ten registries, one source of truth each, linked by reference; future implementation is assigned separately, Capability Registry first.*
