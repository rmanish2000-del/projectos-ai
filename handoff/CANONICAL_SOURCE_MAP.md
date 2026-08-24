# Canonical Source Map

**Where every corpus document comes from, what its real status is, and which source wins.** Companion to `PROJECTOS_TO_AIW_HANDOFF_MANIFEST.yaml`.

---

## 1. Source-of-truth precedence (authoritative)

```
   ProjectOS repository (C:\ProjectOS-AI)        ← UPSTREAM, single source of truth
        │  vendored, hash-pinned
        ▼
   AI Workspace vendored snapshot                ← DOWNSTREAM copy (read-only)
        ▲
        └── on hash drift: ProjectOS wins; AIW re-vendors from upstream.

   NEVER source of truth:  Downloads · conversation history · email · any unverified path.
```

Rule: a file is authoritative **only** if its SHA-256 matches the manifest entry whose upstream is the ProjectOS repo. Anything else — even a byte-identical copy from Downloads — is untrusted until hash-matched to the manifest.

## 2. Status taxonomy (closed set)

| Status | Meaning | May AIW implement against it? |
|---|---|---|
| **PROPOSED_CANONICAL** | Authored, consistent, awaiting PO-10 sign-off + PO-11 execution. | **Design yes; cite-as-ratified no.** |
| **REFERENCE** | Non-binding finding of fact (T3). | Inform only. |
| **GOVERNANCE_INSTRUMENT** | Approval/process document (PO-10, PO-11). | Not a design input. |
| **SEED_UNVERIFIED** | Data records needing B3 verification. | **No** — excluded until verified. |
| **HELD** | Explicitly deferred (e.g., PO-9 NC-7). | No. |

**Critical honesty rule:** ratification (PO-11) has **not** been executed. Therefore **nothing is "ratified/canonical" yet** — the entire design corpus is `PROPOSED_CANONICAL`. No document is elevated because it is complete (constraint). AIW must treat status as given; it must not interpret or elevate it.

## 3. Per-document source & status

| Doc ID | Canonical name | Status | Tier | Build | Upstream path |
|---|---|---|---|---|---|
| PO-6 | ProjectOS Constitution v1.0 | PROPOSED_CANONICAL | T0 | spec | PROJECTOS_CONSTITUTION_V1.md |
| KERNEL | Kernel / Foundation Spec | PROPOSED_CANONICAL | T1 | **implemented** | PROJECTOS_V0_1_FOUNDATION_SPEC.md |
| PO-1 | Methodology v2.0 | PROPOSED_CANONICAL | T1 | spec | PROJECTOS_METHODOLOGY_V2.md |
| PO-2 | Platform Genome v1.0 | PROPOSED_CANONICAL | T1 | spec | PLATFORM_GENOME_V1.md |
| PO-3 | Ownership/Integration | PROPOSED_CANONICAL | T1 | spec | PO-3_AI_WORKSPACE_INTEGRATION_SPEC.md |
| PO-4 | Governance Framework | PROPOSED_CANONICAL | T1 | spec | PO-4_ECOSYSTEM_GOVERNANCE_FRAMEWORK.md |
| PO-5 | Metrics & Health | PROPOSED_CANONICAL | T1 | spec | PO-5_GOVERNANCE_METRICS_PLATFORM_HEALTH.md |
| PO-7 | Metadata Architecture (CR-1 spec) | PROPOSED_CANONICAL | T2 | spec | PO-7_PLATFORM_METADATA_ARCHITECTURE.md |
| RUNTIME | Workspace Runtime (P4) | PROPOSED_CANONICAL | T2 | spec | PROJECTOS_WORKSPACE_RUNTIME_SPEC.md |
| PO-8 | Corpus Integration | PROPOSED_CANONICAL | T2 | spec | FOUNDATIONAL_CORPUS_INTEGRATION.md |
| PO-9 | Language Standard | PROPOSED_CANONICAL | T2 | spec | PO-9_ECOSYSTEM_LANGUAGE_STANDARD.md |
| ROADMAP | Implementation Roadmap | PROPOSED_CANONICAL | T2 | spec | PROJECTOS_IMPLEMENTATION_ROADMAP.md |
| PO-2.5 | Consistency Review | REFERENCE | T3 | spec | PO-2.5_ARCHITECTURE_CONSISTENCY_REVIEW.md |
| PO-10 | Ratification Package | GOVERNANCE_INSTRUMENT | T3 | spec | PO-10_RATIFICATION_AND_CORRECTION_PACKAGE.md |
| PO-11 | Ratification Execution Plan | GOVERNANCE_INSTRUMENT | T3 | spec | PO-11_RATIFICATION_EXECUTION_PLAN.md |
| KERNEL-README/ARCH/CLI | Kernel docs | REFERENCE | T2 | **implemented** | README.md, docs/architecture.md, docs/cli.md |
| **CR-1 seed data** | seeded capability records | **SEED_UNVERIFIED** | — | — | **not present; external; excluded** |

Exact versions, hashes, bytes, and dependencies are in the manifest. This map is the human-readable precedence + status view.

## 4. What changes on ratification (not yet)

When PO-11 executes (a **future** authorized run, not part of this handoff): the six T1 documents become formally ratified, PO-7/8/9/RUNTIME registered, PO-2.5 recorded as Reference, and the naming corrections applied. **Until then, this map's `PROPOSED_CANONICAL` labels stand.** AIW re-vendors and updates status only after that run produces evidence — never on its own interpretation.
