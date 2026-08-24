# Target Repository Layout (AI Workspace)

**Where each handoff file lands inside AI Workspace, and how it is classified.** Companion to the manifest.

> **Honesty note (never invent a platform fact):** the exact AI Workspace repository structure is **not available to this assignment** (the AIW repo is not connected here; only the ProjectOS repo is). The layout below is a **recommended** structure consistent with the ProjectOS Naming Standard (PO-9) and common vendoring conventions. **Confirm against AIW's actual conventions before placement**; treat the paths as proposed, not authoritative.

---

## 1. Recommended target tree

```
<ai-workspace-repo>/
└── docs/
    └── projectos-corpus/                 # vendored, read-only; ProjectOS is upstream
        ├── MANIFEST.yaml                  # copy of PROJECTOS_TO_AIW_HANDOFF_MANIFEST.yaml
        ├── HANDOFF_GUIDE.md
        ├── CANONICAL_SOURCE_MAP.md
        ├── INTEGRITY_CHECKS.md
        ├── canonical/                     # T0–T1 (PROPOSED_CANONICAL)
        │   ├── PO-6_constitution.md
        │   ├── KERNEL_foundation_spec.md
        │   ├── PO-1_methodology.md
        │   ├── PO-2_genome.md
        │   ├── PO-3_ownership.md
        │   ├── PO-4_governance.md
        │   └── PO-5_metrics.md
        ├── supporting/                    # T2 (PROPOSED_CANONICAL)
        │   ├── PO-7_metadata_architecture.md
        │   ├── RUNTIME_workspace_runtime.md
        │   ├── PO-8_corpus_integration.md
        │   ├── PO-9_language_standard.md
        │   └── ROADMAP_implementation.md
        ├── reference/                     # T3 (REFERENCE)
        │   ├── PO-2.5_consistency_review.md
        │   ├── kernel_README.md
        │   ├── kernel_architecture.md
        │   └── kernel_cli.md
        ├── governance/                    # GOVERNANCE_INSTRUMENT (proposed)
        │   ├── PO-10_ratification_package.md
        │   └── PO-11_ratification_execution_plan.md
        └── cr1/
            ├── CR1_SPEC_AND_SEED_STATUS.md
            ├── B3_SEED_VERIFICATION_CONTRACT.md
            └── seed/
                └── README.md             # EMPTY of records; explains seeds are excluded until B3
```

Filenames may be normalized to the PO-9 ID scheme (`PO-6`, `KERNEL`, …); keep the manifest `source_path` → target mapping so drift detection can pair them.

## 2. Per-file handoff classification

Every corpus file is a **VENDORED_SNAPSHOT**: AI Workspace stores a pinned, hash-verified copy; ProjectOS remains the upstream source of truth.

| Classification | Meaning | Applies to |
|---|---|---|
| **VENDORED_SNAPSHOT** | Pinned copy in AIW, hash-verified against the manifest; re-vendored on upstream change. | **All corpus documents.** |
| **EXTERNAL_CANONICAL_REFERENCE** | Referenced by ID+hash without copying. | (not used — AIW must be self-contained per the verified gap) |
| **GENERATED_EXPORT** | Produced by a build step from an upstream source. | (not used in v1; all files are hand-authored) |
| **SYNCHRONIZED_MIRROR** | Auto-synced copy. | (not used in v1 — sync is manual/gated via drift detection, §3) |
| **EXCLUDED_PENDING_B3_VERIFICATION** | Not copied; held out until verified. | **CR-1 seeded data** (none present). |

Rationale for vendoring everything: the verified gap is that AIW *cannot reach documents outside its repo*. A vendored snapshot makes AIW self-contained while the manifest hash keeps it honest about drift.

## 3. Update & drift-detection rules

1. **ProjectOS is upstream; AIW is downstream** (precedence, Source Map §1). AIW never edits a vendored file in place — it re-vendors.
2. **Drift = hash mismatch.** A vendored file whose SHA-256 ≠ the manifest entry is *stale* (upstream changed) or *tampered* (local edit). Either way it is flagged and re-vendored from upstream.
3. **Re-vendoring is manual/gated, not silent.** When ProjectOS updates a document (new hash), a bounded re-vendor assignment updates the AIW snapshot + manifest together. No auto-sync elevates or mutates status.
4. **Status travels with the file.** The manifest status is copied verbatim; AIW never re-labels. When ratification executes upstream, a re-vendor updates status downstream — never before.
5. **CR-1 seed/ stays empty** until B3 verification produces verified records; the `seed/README.md` documents why.
