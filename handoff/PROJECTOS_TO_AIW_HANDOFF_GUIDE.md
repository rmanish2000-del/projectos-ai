# ProjectOS → AI Workspace — Canonical Corpus Handoff Guide

**The repository-ready package that lets AI Workspace consume the approved ProjectOS corpus with verified provenance — never by copying from Downloads, chat history, or unverified locations.**

**Assignment:** PO-12 — Canonical Corpus Publication & AI Workspace Handoff Pack. **Lane:** B / Cowork / L2. **Priority:** Critical.
**Solves the verified gap:** PO-7, PO-8, PO-9, the implementation roadmap, and CR-1 material are absent from the AI Workspace repository; AIW cannot safely implement against documents that exist only outside its repo. This package provides source-controlled, hash-verified snapshots with explicit status.
**Out of scope (honored):** no constitutional amendment, no ratification execution, no canonical text edits, no implementation code, no seed verification, no registry persistence, no silent status elevation.

---

## 1. What this package is

A deterministic handoff bundle: an inventory manifest with **real SHA-256 hashes** of every corpus file, plus the rules for placing, verifying, and updating them in AI Workspace — with explicit, honest status for each (proposed / reference / governance / held / seed).

**The package (8 files):**

| File | Role |
|---|---|
| `PROJECTOS_TO_AIW_HANDOFF_MANIFEST.yaml` | Machine-readable inventory: id, version, status, tier, owner, path, **hash**, deps. |
| `PROJECTOS_TO_AIW_HANDOFF_GUIDE.md` | This guide + the L2 verification report (§5). |
| `CANONICAL_SOURCE_MAP.md` | Source-of-truth precedence + status taxonomy + per-doc status. |
| `CR1_SPEC_AND_SEED_STATUS.md` | The spec-vs-seed separation (ambiguity removed). |
| `TARGET_REPOSITORY_LAYOUT.md` | Recommended AIW paths + vendored/export/reference/mirror classification + drift rules. |
| `INTEGRITY_CHECKS.md` | Hash / missing-input / stale-copy / broken-reference checks + script design + `sha256sum` checklist. |
| `B3_SEED_VERIFICATION_CONTRACT.md` | The exact assignment to verify seed records before registry entry. |
| `CLAUDE_CODE_IMPORT_INSTRUCTIONS.md` | Bounded import procedure — import without interpreting governance status. |

## 2. The three ideas that make it safe

1. **Provenance by hash.** Every file is referenced by ID + SHA-256 over the actual ProjectOS repo file. A copy is trusted only if its hash matches — so Downloads, chat exports, and stray copies are automatically untrusted.
2. **Honest status.** Ratification (PO-11) has **not** executed, so nothing is "ratified." The design corpus is `PROPOSED_CANONICAL` — safe to design against, never citable as ratified. No document is elevated because it is complete.
3. **Spec ≠ data.** The Capability Registry **specification** (inside PO-7) is handed off; **seeded records** are not — they don't exist in the repo and must be B3-verified before any use.

## 3. How AI Workspace consumes it (summary)

Verify hashes (fail-closed) → place vendored, read-only, per the layout → copy status verbatim (no elevation) → build CR-1 from spec with an **empty** seed folder → record import evidence. Full procedure: `CLAUDE_CODE_IMPORT_INSTRUCTIONS.md`.

## 4. Expected-output mapping (assignment → this package)

| # | Expected output | Delivered as |
|---|---|---|
| 1 | PROJECTOS_TO_AIW_HANDOFF_MANIFEST.yaml | ✅ that file |
| 2 | PROJECTOS_TO_AIW_HANDOFF_GUIDE.md | ✅ this file |
| 3 | CANONICAL_SOURCE_MAP.md | ✅ that file |
| 4 | CR1_SPEC_AND_SEED_STATUS.md | ✅ that file |
| 5 | TARGET_REPOSITORY_LAYOUT.md | ✅ that file |
| 6 | Integrity-check specification / script design | ✅ INTEGRITY_CHECKS.md |
| 7 | B3 verification assignment contract | ✅ B3_SEED_VERIFICATION_CONTRACT.md |
| 8 | Import instructions for Claude Code | ✅ CLAUDE_CODE_IMPORT_INSTRUCTIONS.md |
| 9 | Final L2 verification report | ✅ §5 below |

Scope items 1–13 are all covered: inventory (manifest); recorded fields (manifest); status separation (Source Map + CR-1 status); deterministic manifest (sorted, hashed); target paths (Layout); handoff classification (Layout §2); update/drift rules (Layout §3); precedence (Source Map §1); CR-1 packaged separately (CR-1 status); B3 identified (B3 contract); integrity checks (Integrity); import instructions (Import); no false ratification (throughout).

## 5. L2 Verification Report (Deliverable 9)

Independent, verdict-oriented review against the acceptance criteria, quality checks, and definition of done.

| Check | Verdict | Basis |
|---|---|---|
| Every manifest entry verified against an actual file | **PASS** | 18 files staged from the ProjectOS repo; each manifest `source_path` corresponds to a staged, existing file. |
| All hashes verified (real, not fabricated) | **PASS** | SHA-256 computed in-container over the staged repo files; byte sizes cross-check the device-reported sizes exactly. |
| All cross-references verified | **PASS** | Every `dependencies[]` id resolves to a manifest document_id (checked); no dangling refs. |
| Status verified against PO-10 / PO-11 | **PASS** | Ratification NOT executed ⇒ all design docs `PROPOSED_CANONICAL`, PO-2.5 `REFERENCE`, PO-10/11 `GOVERNANCE_INSTRUMENT`; nothing labelled ratified (no silent elevation). |
| Target locations vs AIW conventions | **PASS (with flag)** | Layout is explicitly **recommended, not authoritative** — AIW repo not reachable here; flagged to confirm against AIW conventions (never invent a platform fact). |
| Complete, deterministic corpus handoff | **PASS** | All required corpus docs inventoried; manifest sorted by id, closed status vocabulary, explicit fields. |
| Every required design input has a verified source + hash | **PASS** | §manifest — 18 entries, each hashed. |
| Missing / held inputs visible | **PASS** | CR-1 seed `SEED_UNVERIFIED`/excluded; PO-9 NC-7 held; both surfaced. |
| CR-1 spec/data distinction preserved | **PASS** | CR1_SPEC_AND_SEED_STATUS.md; spec in PO-7, data excluded, B3 gate defined. |
| Update drift detectable | **PASS** | Integrity check 3 (stale-copy) + Layout §3 drift rules; hash mismatch = drift. |
| Claude Code can import without interpreting governance status | **PASS** | Import instructions copy status verbatim; hard rules forbid elevation. |
| No canonical document modified | **PASS** | This package only reads/hashes corpus files and writes new handoff files under `handoff/`; no canonical text edited; ratification not executed. |

**Reviewer verdict: PASS.** No blocking issues. The handoff is deterministic and provenance-bearing (real hashes), status is honest (nothing ratified), the CR-1 spec/seed split is unambiguous, drift is detectable, and Claude Code can import without interpreting or elevating governance status — while modifying no canonical document and executing nothing.

## 6. Stopping point

Package delivered. **Not done here (by design):** ratification execution, file import into AIW, seed verification, implementation. Per the dependency chain, **A-007 consumes this package**; after approval, Claude Code receives a bounded corpus-import assignment before registry implementation (which remains gated on FD-3).
