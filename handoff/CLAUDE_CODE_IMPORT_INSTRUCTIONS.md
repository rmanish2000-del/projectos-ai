# Import Instructions for Claude Code

**How to import the ProjectOS corpus into AI Workspace deterministically, without interpreting governance status.** Bounded procedure. Import only — no implementation, no ratification, no seed verification.

---

## 0. Preconditions

- You have the handoff package: `PROJECTOS_TO_AIW_HANDOFF_MANIFEST.yaml` + the corpus files + these companions.
- The **ProjectOS repo is upstream source of truth**; Downloads / chat history are **not** valid sources (reject them).
- You will **not** interpret, elevate, or ratify status — you copy status verbatim from the manifest.

## 1. Steps

1. **Verify the package (fail-closed).** Run the integrity checks (`INTEGRITY_CHECKS.md`): hash-validate every file against the manifest, confirm no missing inputs, confirm no dangling cross-references. **Any red check ⇒ stop and report; do not import.**
2. **Place files** per `TARGET_REPOSITORY_LAYOUT.md` (confirm the exact AIW paths against AIW conventions first — the layout is recommended, not authoritative). Vendored, read-only.
3. **Copy status verbatim.** Each file keeps its manifest status (`PROPOSED_CANONICAL` / `REFERENCE` / `GOVERNANCE_INSTRUMENT`). **Do not label anything "ratified" or "canonical-final"** — ratification (PO-11) has not run. No silent status elevation.
4. **Carry the manifest into AIW** as the local source-of-truth record, so drift detection works downstream.
5. **CR-1: spec only.** Build the Capability Registry from the PO-7 specification. Create the `cr1/seed/` folder **empty of records**, with its README explaining seeds are excluded. **Do not import, persist, or invent any seed record.**
6. **Record import evidence.** Commit the vendored files + manifest; record the integrity-check result (all `OK`) as the import evidence. The import is complete only with green evidence.

## 2. Hard rules (constraints)

- **Downloads is never canonical.** Only files whose SHA-256 matches the manifest (upstream = ProjectOS repo) are trusted.
- **Reference by ID + hash; never copy without provenance.** Every imported file is traceable to a manifest entry.
- **No source is canonical merely because it is complete** — status comes from the manifest, not from your judgment.
- **Held stays held** (e.g., PO-9 NC-7). Do not act on held items.
- **No implementation, no registry persistence, no seed verification** during import — those are separate, later, bounded assignments.

## 3. Definition of done (import)

- All manifest files present in AIW at their target paths, hash-verified `OK`.
- Manifest carried into AIW; drift detection operable.
- Status copied verbatim; nothing elevated.
- CR-1 registry buildable from spec; `seed/` empty; no seed persisted.
- Import evidence (commit + green integrity check) recorded.

## 4. Next handoff

Per the assignment chain: **A-007 consumes this package.** After founder approval of the import, Claude Code receives a **bounded corpus-import assignment**, then — separately — the Capability Registry implementation (Roadmap Wave 1 / MS-0, still gated on FD-3). Seed verification (B3) runs only if seed records are later provided.
