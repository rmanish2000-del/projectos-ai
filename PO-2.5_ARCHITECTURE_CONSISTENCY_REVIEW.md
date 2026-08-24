# PO-2.5 — Architecture Consistency Review

**Type:** Review only. No new design, no implementation. **Lane:** B (Cowork). **Date:** 2026-07-27.
**Artifacts reviewed:** Platform Genome v1.0, ProjectOS Methodology v2.0, Capability Registry (CR-1), AI Workspace — cross-checked against the kernel (`PROJECTOS_V0_1_FOUNDATION_SPEC.md`), the Workspace Runtime spec, and the **as-built** workspace (`Workspace.yaml`, `Shared/Packs/*`, `Projects/EduOS-AI/*`, `Projects/TradeOS-AI/*`, `.projectos/policies.yaml.txt`).
**Evidence basis:** all findings are grounded in files on disk under `C:\ProjectOS-AI` as of this date; each finding cites its source. Labels follow Verified / Reported / Absent.

---

## 0. Evidence note — two of the four reviewed artifacts do not exist on disk

Before the reports, one fact governs everything below and is itself the top finding:

- **Capability Registry (CR-1):** **Absent.** A repo-wide search for "Capability Registry", "Capability Maturity", "Capability Discovery", and "Platform Intelligence" returns hits **only inside `PROJECTOS_METHODOLOGY_V2.md` and `PLATFORM_GENOME_V1.md`** — the two documents I authored. There is no CR-1 specification, schema, or record store anywhere in the workspace, yet CR-1 is listed as an **input** to this line of assignments and is the system the Genome binds to.
- **AI Workspace:** **Absent as a specification.** The only file is `Vision 2030 - Enterprise AI Workspace.txt`, which is **0 bytes (empty, Verified)**. "AI Workspace" appears in prose only inside the Workspace Runtime spec and my two new specs. There is no AI Workspace operating-model or architecture document to review against.

Consequence: a true four-way consistency check is not currently possible. This review verifies consistency among the artifacts that **do** exist (Genome, Methodology, kernel, runtime, and the as-built products) and treats the two absent artifacts as **Missing Concepts** (Report 3) rather than asserting anything about their unwritten contents. This is a fail-closed posture: absent sources are reported, not assumed.

**Overall verdict:** The *designed* layer (kernel → runtime → Methodology v2 → Genome v1) is **internally consistent**. It is **not yet reconciled** with (a) the systems it references but that are undefined, and (b) the **as-built product reality**, which has independently evolved a different governance model and a drifted registration schema. The architecture is *consistent-in-design, unreconciled-with-reality*. The recommended sequence (Report 7) closes both gaps before any implementation.

---

## Report 1 — Conflict Report

Genuine contradictions where two authoritative sources say different things about the same rule.

| # | Severity | Conflict | Source A | Source B | Impact |
|---|---|---|---|---|---|
| **C-1** | **High** | **Next-assignment generation.** Methodology v2 mandates the system **auto-generates exactly one successor** after verified completion (§2 Principle 12, §5.3). EduOS's constitution mandates the opposite: **"Do not generate the next assignment unless requested."** | `PROJECTOS_METHODOLOGY_V2.md` §5.3 | `Projects/EduOS-AI/PROJECT_BOOTSTRAP.md` §11; `PROJECT_STATE.md` ("next assignment is generated only on founder request") | A product's live operating rule directly contradicts the canonical methodology. Whichever is "right", both cannot be canonical. |
| **C-2** | **High** | **Which operating model is canonical.** EduOS adopted a five-document governance suite that **explicitly "replaced the prior ProjectOS structure"**, and records that **"the founder judged it stronger than the prior ProjectOS model."** Methodology v2 asserts itself as *the* canonical operating model for all products. | `PROJECT_SOURCE.md` §7 (2026-07-23 entry); `FOUNDER_LEARNING.md` L-004 | `PROJECTOS_METHODOLOGY_V2.md` §0, §1 | Two competing "canonical" operating models exist; the newer methodology (mine) has not absorbed the model the founder actually preferred and is using in production. |
| **C-3** | **Medium** | **Project registration schema.** The Workspace Runtime spec proposed `repository.root` (relative) and `workflow.default_mode_floor`. The as-built `project.yaml` uses **`repository.path`** (absolute, e.g. `C:/TradeOS-AI`) and a **flat `workflow_mode: governed`**. | `PROJECTOS_WORKSPACE_RUNTIME_SPEC.md` §6.1 | `Projects/TradeOS-AI/project.yaml` | The spec and reality disagree on field names and path semantics; an implementation built from the spec would not read the existing files. |
| **C-4** | **Medium** | **Repository location model.** Runtime spec's default is `repo_root = the project directory` (code lives under `Projects/<name>/`). In reality, **code lives outside the workspace** (`C:/TradeOS-AI`, `C:\EduOS-AI`); the `Projects/<name>/` folder holds only docs/governance. | `PROJECTOS_WORKSPACE_RUNTIME_SPEC.md` §11.1 rule 3 | `PROJECT_STATE.md` open items; `TradeOS-AI/project.yaml` `repository.path: C:/TradeOS-AI` | Repository routing as designed points at the wrong place for real projects; the docs-vs-code split is unmodeled. |
| **C-5** | **Low** | **Domain risk triggers placement.** `.projectos/policies.yaml.txt` carries trading-specific GOVERNED triggers (`kelly_methodology`, `edge_methodology`, `execution_cost_engine`) at **workspace-root** level. The kernel and Genome require domain rules to live in a **pack / Domain DNA**, keeping the core domain-neutral. | `.projectos/policies.yaml.txt` (risk_triggers.GOVERNED) | Foundation Spec (kernel neutrality); `PLATFORM_GENOME_V1.md` §8, §11.2 | Domain vocabulary sits in a neutral layer — a (small) neutrality violation and a latent source of cross-product leakage. |

*No conflicts were found between the kernel, the runtime, the Methodology, and the Genome at the level of core invariants (one active assignment per repo, evidence-based verification, fail-closed, additive packs) — those four are mutually consistent. Every conflict above is design-vs-as-built, not design-vs-design, except C-1/C-2 which are methodology-vs-product-constitution.*

---

## Report 2 — Duplication Report

The same responsibility defined in more than one place (drift risk even where the copies currently agree).

| # | Severity | Duplicated responsibility | Where it is defined (multiple) | Note |
|---|---|---|---|---|
| **D-1** | **High** | **The product operating model** (working mode, decision framework, founder responsibilities, knowledge capture, state tracking). | (a) `PROJECTOS_METHODOLOGY_V2.md` (§8, §9, §12, §16); (b) EduOS `PROJECT_BOOTSTRAP.md` §11–12 + `HANDOFF/STATE/FOUNDER_LEARNING`; (c) kernel `.projectos/` state model; (d) user global preferences. | Four overlapping definitions of "how we operate." This is the root cause of C-1 and C-2. |
| **D-2** | **High** | **"One active assignment."** | Kernel INV-1 (Foundation Spec §7); Methodology v2 §2/§3; EduOS `PROJECT_BOOTSTRAP.md` §11. | One rule, three authorities — already drifted (they differ on next-assignment auto-generation, C-1). |
| **D-3** | **Medium** | **Workflow modes (FAST/REVIEWED/GOVERNED).** | Kernel `enums.py` (`WorkflowMode`); `.projectos/policies.yaml.txt`; Methodology v2 §7; consumed in `project.yaml` (`workflow_mode`). | Vocabulary agrees today; four definitions invite divergence (gate lists already differ between policies.yaml and Methodology §7). |
| **D-4** | **Medium** | **Verification / evidence discipline.** | Kernel evidence model (Foundation Spec §8); Methodology Verification Levels L0–L3 (§6); user prefs "Verified/Reported/Assumed/Proposed/Blocked"; EduOS uses the labels (`PROJECT_STATE.md`, `FOUNDER_LEARNING.md` L-002). | Consistent in spirit; two different vocabularies (L0–L3 vs. the five labels) describe overlapping ideas. |
| **D-5** | **Medium** | **The engine/content inheritance pattern.** EduOS independently built **"content-blind engine + versioned content packs"** with its own semver + `engineMinVersion` compatibility and a **"Pack Registry"** — structurally the same idea as the Genome's **Platform DNA + Domain DNA + versioning**. | EduOS `06-technical-architecture.md` §2, §4; `PLATFORM_GENOME_V1.md` §3, §6, §8, §18 | Concept reinvented per-product (different scope, but same pattern and overlapping vocabulary). Also a reuse opportunity: EduOS's pack architecture is a candidate platform capability. |
| **D-6** | **Low** | **"Product DNA."** | Genome §7 (identity + expressed genes + config); EduOS `PROJECT_SOURCE.md` (founder's evolving product strategy/"brain"). | Same term, two meanings (see Terminology, T-2). |

---

## Report 3 — Missing Concepts

Concepts referenced by the architecture but not defined anywhere on disk. These are the load-bearing gaps.

| # | Severity | Missing concept | Referenced by | Status |
|---|---|---|---|---|
| **M-1** | **Blocker** | **Capability Registry (CR-1)** — the catalog of capabilities (identity, maturity, consumers, status) the Genome binds to and the Methodology's capability-first model depends on. | Cited as an **input** to PO-2; `PLATFORM_GENOME_V1.md` §9, §23; `PROJECTOS_METHODOLOGY_V2.md` §10.1 | **Absent.** No spec, schema, or store exists. The Genome's core binding seam has nothing to bind to. |
| **M-2** | **High** | **Capability Maturity Engine** (M0–M4 grading) — the threshold source for every Genome evolution operation. | `PLATFORM_GENOME_V1.md` §12–17, §23; Methodology §10.2 | **Partially defined** only inside Methodology §10.2; no standalone spec; grading rules/authority unspecified. |
| **M-3** | **High** | **AI Workspace / AI Workspace HQ operating model** — named as "the implementation platform" and "control plane" the whole stack realizes. | Workspace Runtime spec; Genome §23; Methodology (implementation context) | **Absent.** Vision file is empty (0 bytes). The "implementation platform" has no document. |
| **M-4** | **Medium** | **Capability Discovery Engine** — surfaces reuse candidates; reads the family tree. | `PLATFORM_GENOME_V1.md` §23 (named only) | **Absent.** Named as a related system, never defined. |
| **M-5** | **Medium** | **Platform Intelligence** — analytics/insight substrate; proposes evolution operations. | `PLATFORM_GENOME_V1.md` §23–24 (named only) | **Absent.** Named, never defined. |
| **M-6** | **Medium** | **Capability DNA ↔ Registry record binding schema** — the concrete record shape the Genome references. | `PLATFORM_GENOME_V1.md` §9 (facet table, conceptual only) | **Not yet designed** (this was the proposed PO-3). Blocks any Genome or Registry implementation. |
| **M-7** | **Low** | **Docs-vs-code project topology** — how a project whose code lives outside the workspace is registered and routed. | Implied by `PROJECT_STATE.md` open items; `TradeOS-AI/project.yaml` | **Unmodeled** in the runtime spec (see C-4). |

---

## Report 4 — Wrong Ownership

Responsibilities located in the wrong layer relative to the plane/inheritance model.

| # | Severity | Responsibility | Currently owned by | Should be owned by | Basis |
|---|---|---|---|---|---|
| **O-1** | **High** | The **operating model** for a product (working mode, decision framework, knowledge capture). | EduOS product constitution (`PROJECT_BOOTSTRAP.md`), re-authored per product. | **Platform DNA** (inherited via Methodology v2), with only product-specific *expression* left to the product. | Genome §6, §11.2 (inherit, don't fork); Methodology plane separation §2.1. A product re-authoring the operating model is exactly the "fork" the Genome forbids. |
| **O-2** | **Medium** | **Domain risk triggers** (`kelly_methodology`, `edge_methodology`, …). | Workspace-root `.projectos/policies.yaml.txt`. | A **domain pack / Domain DNA** (e.g., the `trading` pack). | Kernel neutrality (Foundation Spec); Genome §8. Domain vocabulary in a neutral layer breaks "domain-neutral core." |
| **O-3** | **Medium** | **Capability maturity grading** (M0–M4). | Buried inside the Methodology (§10.2). | The **Capability Maturity Engine** as a distinct system the Genome consumes. | Genome §23 explicitly separates "readiness" (Maturity Engine) from "placement" (Genome); the grading rules should not live inside the process methodology. |
| **O-4** | **Low** | **Product strategy / "founder brain."** | EduOS `PROJECT_SOURCE.md` ("product DNA"). | Correctly product-owned — **but the name collides** with Genome "Product DNA." | Ownership is *right*; only the label is wrong (T-2). Flagged so the fix is a rename, not a move. |

*Note O-4 is the one "wrong ownership" entry that is actually correct ownership — included to prevent a mis-fix (do not move the founder-brain doc into the Genome; only rename to avoid the DNA collision).*

---

## Report 5 — Terminology Alignment

Terms carrying more than one meaning, or one meaning carried by more than one term.

| # | Severity | Term | Conflicting meanings on disk | Recommendation (naming only — no design) |
|---|---|---|---|---|
| **T-1** | **High** | **"Pack" / "Registry"** | "Pack" means: (a) ProjectOS **kernel domain pack** (`Shared/Packs/*`, rules+gates+templates); (b) Genome **Domain DNA pack**; (c) EduOS **content pack** (curriculum data, `kbc3-en.pack`). "Registry" means: (d) **Capability Registry** (Genome/Methodology); (e) EduOS backend **"Pack Registry"** (content-pack versions/entitlements). | Reserve **"pack"** for ProjectOS domain packs / Domain DNA; rename EduOS "content pack" → **"content bundle"** (or qualify as "EduOS content pack") and EduOS "Pack Registry" → **"Content Registry"**. Reserve **"Registry"** (unqualified) for the Capability Registry. |
| **T-2** | **Medium** | **"DNA" / "Product DNA"** | Genome: "Product DNA" = product identity + expressed genes + config. EduOS: "product DNA" (`PROJECT_SOURCE.md`) = founder's evolving product strategy. | Keep **"Product DNA"** for the Genome sense; rename the EduOS doc's subtitle → **"Product Brief"** or **"Founder Product Intent."** |
| **T-3** | **Medium** | **Two ladders for "how careful."** | Methodology **Verification Levels L0–L3**; kernel/policies **Workflow Modes FAST/REVIEWED/GOVERNED**; user-prefs **Verified/Reported/Assumed/Proposed/Blocked** labels. | Not a rename — a **mapping**: publish one canonical table binding modes ↔ levels ↔ evidence labels (Methodology §6 starts this; make it the single reference). |
| **T-4** | **Low** | **"Constitution" / "Bootstrap" / "Genome" / "Foundation."** | EduOS `PROJECT_BOOTSTRAP.md` calls itself "the constitution"; kernel spec is "Foundation"; Genome is the "permanent DNA." All claim permanence/foundation status. | Clarify the hierarchy in one place: Genome (ecosystem) ⊃ Methodology (operating model) ⊃ product constitution (product-local expression). |
| **T-5** | **Low** | **"Phase" numbering collision.** | ProjectOS phases (P1–P4: kernel/runtime); EduOS phases (P0–P6: product roadmap); these PO-x assignments. | Namespace them: `POS-Pn` (platform), `<product>-Pn` (product), `PO-n` (assignments). |

---

## Report 6 — Single Source of Truth (SSOT) Matrix

For each core concept: where it *should* be authoritative, where definitions currently exist, and the resulting status. "Duplicated" = defined authoritatively in >1 place (drift risk). "Absent" = no authoritative source.

| Concept | Canonical owner (target) | Definitions found on disk | SSOT status |
|---|---|---|---|
| Assignment lifecycle & invariants | **Kernel** (Foundation Spec) | Foundation Spec (authoritative); echoed in Methodology, EduOS constitution | ✅ Single (echoes are references) |
| One active assignment | **Kernel** INV-1 | Kernel; Methodology §2/§3; EduOS BOOTSTRAP §11 | ⚠️ **Duplicated** (already drifted — C-1) |
| Operating model (mode/decision/knowledge) | **Methodology v2** (as Platform DNA) | Methodology; EduOS 5-doc suite; kernel state model; user prefs | ❌ **Duplicated + conflicting** (D-1, C-2) |
| Workflow modes & gates | **Kernel enum + one policies source** | `enums.py`; `.projectos/policies.yaml.txt`; Methodology §7; `project.yaml` | ⚠️ **Duplicated** (D-3) |
| Verification depth | **Methodology §6 (levels)**, mapped to modes/labels | Methodology; kernel evidence; user-pref labels; EduOS usage | ⚠️ **Duplicated vocabularies** (D-4, T-3) |
| Project registration schema | **Workspace Runtime spec** | Runtime spec (proposed); `project.yaml` (as-built, drifted) | ❌ **Conflicting** (C-3) |
| Repository routing / topology | **Workspace Runtime spec** | Runtime spec; real external code roots | ❌ **Spec ≠ reality** (C-4, M-7) |
| Capability catalog | **Capability Registry (CR-1)** | *Referenced only* (Methodology §10.1, Genome §9/§23) | ❌ **Absent** (M-1) |
| Capability maturity grading | **Capability Maturity Engine** | Inside Methodology §10.2 only | ❌ **Mislocated / no standalone SSOT** (M-2, O-3) |
| Inheritance & lineage | **Platform Genome v1** | Genome (authoritative) | ✅ Single |
| Capability↔Registry binding | **CR-1 + Genome §9 (to be joined)** | Conceptual only (Genome §9) | ❌ **Absent** (M-6) |
| Implementation platform | **AI Workspace op-model** | Empty file only | ❌ **Absent** (M-3) |
| Discovery / Intelligence engines | **Their own specs** | Named only (Genome §23) | ❌ **Absent** (M-4, M-5) |
| Product strategy ("founder brain") | **Product-local** (EduOS SOURCE) | EduOS `PROJECT_SOURCE.md` | ✅ Single (rename only — T-2) |
| Product content architecture | **Product-local** (EduOS spec) | EduOS `06-technical-architecture.md` | ✅ Single (candidate to promote — D-5) |

**Reading of the matrix:** the *inheritance/lineage* and *kernel* concepts have clean single sources. The *operating model*, *registration schema*, and *repository routing* are duplicated or conflicting. The *capability catalog and its engines* and the *implementation platform* are outright absent. The absences (M-1, M-3) and the operating-model conflict (D-1/C-2) are the critical path.

---

## Report 7 — Recommended Sequence

Ordered to resolve blockers and conflicts before anything downstream builds on them. Each step is a **future assignment**, design/decision only (this review adds no new design itself). Dependencies noted.

1. **Founder decision — canonical operating model (resolves C-2, D-1, C-1).** Decide the single authority for "how we operate": adopt EduOS's five-document model *into* Methodology v2 as inherited Platform DNA, or keep Methodology v2 and re-express EduOS's docs as product-local expression. This is a genuine founder decision (it overrides a preference the founder already stated) and it unblocks most other findings. *Depends on: nothing. Blocks: 2, 3, 6.*
2. **Reconcile the next-assignment rule (resolves C-1).** Once (1) is decided, make auto-generate-one vs. generate-on-request consistent across Methodology and every product constitution. *Depends on: 1.*
3. **Define Capability Registry v1 (CR-1) (resolves M-1, and unblocks M-6).** The absent linchpin; the Genome cannot be implemented without it. Design the record model (identity, maturity, consumers, status) and the Genome §9 binding seam. *Depends on: 1 (naming/ownership settled). Blocks: Genome/Registry implementation.*
4. **Extract the Capability Maturity Engine as a distinct spec (resolves M-2, O-3).** Move M0–M4 grading rules out of Methodology §10.2 into their own system that the Genome consumes. *Depends on: 3.*
5. **Author the AI Workspace operating-model spec (resolves M-3).** Fill the empty Vision file with the actual implementation-platform/HQ model the stack realizes. *Depends on: 1.*
6. **Align the project-registration schema & repository topology (resolves C-3, C-4, M-7).** Reconcile the Workspace Runtime spec with the as-built `project.yaml` (`repository.path`, flat `workflow_mode`) and model the docs-in-workspace / code-outside-workspace topology. *Depends on: 1.*
7. **Terminology alignment pass (resolves T-1…T-5).** Publish one glossary: reserve "pack"/"Registry"/"DNA", rename EduOS "content pack"→"content bundle" and "product DNA"→"Product Brief", publish the modes↔levels↔labels mapping, namespace phase numbers. *Depends on: 3, 4, 5 (so names are final). Low risk, high clarity.*
8. **Relocate domain triggers into packs (resolves O-2, C-5).** Move trading-specific GOVERNED triggers from root `.projectos/policies.yaml.txt` into the `trading` Domain DNA pack. *Depends on: nothing; can run in parallel; small.*
9. **Define Discovery & Platform Intelligence (resolves M-4, M-5).** Lowest urgency — needed only when autonomous evolution is pursued (Genome §24). *Depends on: 3, 4.*

**Critical path:** 1 → 3 → 4/6 → 7. Steps 5, 8 run in parallel; step 9 is deferred. Nothing downstream (any Genome, Registry, or runtime *implementation*) should start before steps 1 and 3 land.

---

## Appendix — What is already consistent (for balance)

A review should record alignment as well as gaps:

- **Kernel ↔ Runtime ↔ Methodology ↔ Genome core invariants** are mutually consistent: one active assignment per repo, evidence-based verification, fail-closed, additive-only packs, deterministic successor. No design-vs-design conflict was found among the four platform specs.
- **EduOS states the correct plane split itself:** "ProjectOS governs *execution*; EduOS governs *learning*" (`00-overview.md`) — matching Methodology's business/engineering/governance separation. The ownership instinct at the product level is right; only the operating-model duplication (O-1) needs correcting.
- **Evidence-first discipline is uniform:** the Verified/Reported/Assumed/Proposed/Blocked labeling appears in the kernel philosophy, the user's preferences, and EduOS's live docs (`FOUNDER_LEARNING.md` L-002). This is a genuine, healthy single culture.
- **EduOS's content-blind engine + content packs independently validates the Genome's central pattern** (inheritable neutral core + versioned specialization data) — evidence the inheritance model is natural, not imposed. It is also the first concrete **promotion candidate** for the Registry.

---

*End of PO-2.5 Architecture Consistency Review. Review only — no new design, no implementation, no repository changes beyond this report. All findings are evidence-cited to files under `C:\ProjectOS-AI`; the two absent artifacts (Capability Registry, AI Workspace) are reported as Missing Concepts, not assumed.*
