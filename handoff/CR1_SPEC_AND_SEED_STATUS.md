# CR-1 — Specification vs Seeded Data Status

**The single job of this document: make it impossible to confuse the Capability Registry *specification* with *seeded capability records*.** They have different natures, different evidence status, and different handling.

---

## 1. The distinction (never collapse these)

| | CR-1 **Specification** | CR-1 **Seeded Data** |
|---|---|---|
| **What it is** | The design of the Capability Registry — record model, fields, the Genome binding seam. | Concrete capability *records* (rows) claimed to describe real capabilities. |
| **Where it lives** | **Inside PO-7** (`PO-7_PLATFORM_METADATA_ARCHITECTURE.md` §2 Capability Registry, §9 Capability DNA model). | **Nowhere in this handoff.** Not in the ProjectOS repo (verified — no seed/record file exists). |
| **Status** | `PROPOSED_CANONICAL` (design; pending ratification). | `SEED_UNVERIFIED` — data requiring repository verification. |
| **Evidence** | Authored, L2-reviewed, internally consistent. | **None accepted.** Records are claims until B3-verified against evidence. |
| **May AIW use it?** | Design the registry against the spec — yes. | **No.** Must NOT enter any registry until B3 verification passes. |
| **Handoff class** | VENDORED_SNAPSHOT (as part of PO-7). | EXCLUDED_PENDING_B3_VERIFICATION. |

## 2. Why they are packaged separately

Merging a specification with unverified seed data is how fabricated platform facts enter a system. The spec says *what a capability record looks like*; a seed record *asserts a capability exists at a maturity grade*. The second is an evidence claim (PO-5: evidence over claims; CLAUDE.md: never invent a platform fact). Treating a seed as spec would let an unverified assertion inherit the spec's canonical-in-waiting status — a silent status elevation, forbidden by the constraints.

## 3. Current facts (verified)

- **CR-1 specification is present** — inside PO-7 (hash in the manifest). It is the authoritative design for the Capability Registry.
- **CR-1 seeded data is absent** — a repo-wide search for seed/registry-record files found none. There are **zero** verified capability records to hand off.
- Therefore this handoff contains the **spec only**. Any seed records the founder or Claude Code may hold elsewhere (Downloads, AIW working copies, prior exports) are **out of scope, unverified, and excluded**.

## 4. Rules for AIW / Claude Code

1. **Build the registry from the PO-7 specification**, not from any seed data.
2. **Do not import, persist, or register any seeded capability record** until the B3 verification assignment (see `B3_SEED_VERIFICATION_CONTRACT.md`) has verified it against evidence.
3. **Do not invent capability records** to populate the registry — an empty verified registry is correct; a full unverified one is a defect.
4. If seed records surface, route them to B3; record each as `SEED_UNVERIFIED` until B3 returns `VERIFIED` with evidence.
5. **Never elevate a seed to canonical because the spec is complete** — spec completeness says nothing about data validity.
