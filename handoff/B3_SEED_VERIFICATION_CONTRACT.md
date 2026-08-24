# B3 — Seeded Capability Record Verification Assignment (Contract)

**The exact, bounded assignment required to verify seeded capability records before any of them may enter an AI Workspace registry.** This is a *contract for a future assignment* — B3 is **not executed here** (out of scope).

---

## 1. Why B3 exists

CR-1 seeded data are **claims** ("capability X exists at maturity M2 with these consumers"). The platform's first principle is evidence over claims (PO-5), and CLAUDE.md forbids inventing platform facts. So no seed record may become a registry record until an assignment verifies it against repository evidence. B3 is that assignment.

## 2. Contract

| Field | Value |
|---|---|
| **ID** | B3 (Seed Verification) |
| **Owner / Executor** | Claude Code (implementation), with an independent L2 reviewer |
| **Lane / Level** | A (or B if contract-affecting) / **L2** (independent review), **L3** if a seed asserts an M4/foundational capability |
| **Trigger** | Any seeded capability record proposed for registry entry |
| **Input** | A set of candidate seed records + their claimed provenance (source, author, basis) |
| **Precondition** | The Capability Registry is implemented per PO-7 spec; the seed set is provided from a named source (never Downloads-as-canonical) |

## 3. Method (per record — fail-closed)

For each seed record, verify against evidence and assign an outcome:

1. **Provenance check** — the record cites a real, named source; unsourced ⇒ **REJECT**.
2. **Existence check** — the capability it names actually exists (in code / a repo / a shipped product); no evidence ⇒ **REJECT**.
3. **Maturity check** — its claimed M-grade is derivable from evidence (usage, stability, contract), not asserted; unsupported grade ⇒ downgrade to the evidenced grade or **REJECT**.
4. **Contract/DNA check** — its fields conform to the PO-7 Capability Registry record model; malformed ⇒ **REJECT**.
5. **Uniqueness check** — not a duplicate of an existing registered capability (would be a Genome-§18 violation) ⇒ **MERGE or REJECT**.

A record passes only if **all** checks pass with evidence. Ambiguity ⇒ REJECT (fail-closed).

## 4. Outcome & output

| Outcome | Meaning |
|---|---|
| **VERIFIED** | All checks pass with cited evidence; eligible for registry entry. |
| **DOWNGRADED** | Verified at a lower maturity than claimed; entered at the evidenced grade. |
| **REJECTED** | Failed a check; **not** entered; reason recorded. |

**Output:** a verification report — one row per seed record with outcome + evidence refs — plus the set of `VERIFIED` records cleared for registry persistence. Rejected/held records are recorded, never silently dropped.

## 5. Acceptance & stopping point

- **Acceptance:** every seed record has an explicit outcome backed by evidence; no record enters the registry without `VERIFIED`; the report is L2-reviewed.
- **Stopping point:** stop after the verification report + the cleared record set. Registry *persistence* of verified records is a separate, subsequent step.
- **Constraint:** B3 never invents, completes, or infers a record; absence of evidence is REJECT, not assumption.

## 6. Relationship to this handoff

This handoff carries **zero** seed records (none exist in the ProjectOS repo). B3 runs only *if and when* seed records are provided from a named source. Until then, the AIW registry is built empty from the PO-7 spec — which is the correct state.
