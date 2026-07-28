# PO-11 — Ratification Execution Plan

**The governed runbook that applies the approved PO-10 package — every change atomic, reversible, evidence-anchored, and non-destructive.**

**Status:** PO-11 — execution specification. **Design only.** Assumes the PO-10 package is founder-approved. This document **modifies no canonical document and executes no migration**; it specifies *how* a later execution run applies each item. Nothing here edits or runs anything.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Governed under:** Constitution (PO-6) §10 (amendments GOVERNED/L3); PO-4 §4 (evolution governance); PO-9 §19 (naming migration); PO-8 §17 / Roadmap Wave 0 (MS-0).
**Applies:** PO-10 items CA-1…CA-8, NC-1…NC-6, GC-1…GC-3, and the FD-1 resolution.

---

## 0. Execution principles

1. **One operation = one commit = one audit entry.** Every change is atomic and independently reversible; nothing is a bulk edit.
2. **Alias before relabel.** A rename adds the new term and an alias first, updates references, then deprecates the old term — references never break mid-migration (PO-9 §19).
3. **Fail-closed with safe-points.** After every operation a consistency check runs; on failure, execution **halts** at the last safe-point and escalates — it never proceeds over a red check.
4. **Non-destructive.** Deprecate/alias/supersede, never delete. Git history + the audit chain preserve every prior state.
5. **The kernel is never touched.** Ratification confers *status* and updates the *Register* and *labels* — it changes no kernel code. Kernel tests staying green is a guard on every stage.
6. **Dogfooded & evidence-anchored.** The execution runs as ProjectOS assignments; each operation closes only on repository evidence (commit, diff, check result, audit hash) — never a claim.
7. **Minimal founder touch.** The PO-10 sign-off authorizes the whole program; the founder is re-engaged only at the completion checkpoint or on an exception escalation (Decision Budget, PO-4 §2).

---

## 1. Execution overview — four stages

```
  CP-0 (PO-10 sign-off, authorizes all) 
     │
     ▼
  STAGE A — Amendments & Register   (edit the Constitution: status + Register)   [safe-point]
     ▼
  STAGE B — Governance corrections  (triggers→pack; runtime reconcile; next-assignment) [safe-point]
     ▼
  STAGE C — Naming migrations       (alias-first relabels, doc-by-doc)           [safe-point]
     ▼
  STAGE D — Finalize                (record ratification; publish Corpus v1.0 index) 
     ▼
  CP-final (completion confirmation)
```

Each stage is a governed sub-assignment; each operation within it is atomic. Stage boundaries are **safe-points** — the corpus is consistent there and execution can pause or roll back cleanly.

## 2. Execution Sequence (ordered operations)

Every operation: ID · action · target · depends · rollback. (Full executable register: Appendix B.)

| Op | Action | Target | Depends | Rollback |
|---|---|---|---|---|
| **A1** | Record the amendment set + open the ratification ledger | Audit chain | CP-0 | revert commit |
| **A2** | Confer T1 canonical status on Kernel, PO-1…PO-5 (CA-1) | Constitution status | A1 | revert |
| **A3** | Add Register entries: PO-7, Runtime, PO-8, PO-9 (T2); PO-2.5 (T3) (CA-2–CA-6) | Constitution Register (§3) | A2 | revert per-entry |
| **A4** | Retire "CR-1 (to be authored)" placeholder (CA-2) | Constitution Register | A3 | restore entry |
| **A5** | Record FD-1: Methodology v2 = canonical; EduOS suite = Local Expression | Constitution/Methodology status | A2 | revert |
| **A6** | Set corpus version = **Foundational Corpus v1.0** | Constitution | A2–A5 | revert |
| **B1** | Move trading domain triggers → trading Domain Pack (GC-1) | `.projectos/policies.yaml` → pack | A-safe-point | restore file |
| **B2** | Reconcile project.yaml/runtime (spec-side, additive) (GC-2) | Workspace Runtime spec | A-safe-point | revert spec |
| **B3** | Align product next-assignment rule to canonical Methodology (GC-3) | EduOS Local Expression | A5, B-safe | revert |
| **C1** | Relabel tiers **L→T** (alias L) (NC-1) | Constitution + refs | B-safe-point | revert; alias kept |
| **C2** | Relabel milestones **M→MS** (NC-2) | Roadmap | B-safe-point | revert |
| **C3** | Introduce **POS** entity code; keep PO- (NC-3) | corpus refs | B-safe-point | revert |
| **C4** | Namespace phases **POS-Pn / `<PRD>-Pn`** (NC-6) | corpus refs | C3 | revert |
| **C5** | Enforce reserved words; product renames → Content Bundle / Content Registry / Product Brief (NC-4) | product Local Expressions | C-safe | revert per-doc |
| **C6** | Deprecate ambiguous acronyms CR/PI (aliases) (NC-5) | corpus | C5 | revert |
| **D1** | Record completed ratification (CA-8) in ledger + audit chain | Audit chain | C-safe-point | n/a (append-only) |
| **D2** | Publish **Foundational Corpus v1.0** manifest (index of docs/tiers/versions) | new index doc | D1 | revert |
| **D3** | Full-corpus consistency check (exit gate) | whole corpus | D2 | halt on fail |

NC-7 (Experience/Design cluster) and any FD-1-dependent item the founder held are **not** in this sequence — they execute in a later run once their inputs land.

## 3. Register Update Plan (exact before → after)

The only canonical edits in Stage A are to the Constitution's own Register (PO-6 §8.2 + Appendix C). Precise changes (applied by the execution run, **not** here):

| Register row | Before | After |
|---|---|---|
| Kernel, PO-1…PO-5 | listed | listed **+ status: canonical (T1), Corpus v1.0** |
| Ecosystem metadata | "CR-1 (to be authored)" | **PO-7 (T2)** |
| Runtime/workspace resolution | implied | **Workspace Runtime spec (T2)** |
| Corpus integration | — | **PO-8 (T2)** |
| Ecosystem language | — | **PO-9 (T2)** |
| Consistency finding | — | **PO-2.5 (T3, Reference)** |
| Operating-model content | open (C-2) | **Methodology v2 canonical; product suites = Local Expression** |
| Corpus version | unset | **Foundational Corpus v1.0** |
| Tier labels | L0–L4 | **T0–T4** (after C1; L-labels aliased) |

Each row is one operation with its own commit, diff, and audit entry.

## 4. Constitutional Amendment Execution

- **Each amendment (CA-1…CA-8) is applied as one governed edit operation** to the Constitution, in the Stage-A order (A2…A6, D1). No amendment is applied by this document.
- **The Constitution version bumps once** for the whole ratification set — a MINOR bump (additive: registrations + status), except the tier relabel (C1) which is tracked as its own change. Recorded in the amendment history.
- **The amendment record** (what changed, why, actor, evidence) is written to the ratification ledger (§9) and hash-anchored to the audit chain — the amendment *is* an auditable event.
- **Entrenched principles are untouched** (Constitution §2.1–2.4): this ratification confers status and registers documents; it weakens no immutable principle, so it clears the highest bar trivially.

## 5. Naming Migration Execution

**Method (every NC):** (1) add the new label + alias for the old; (2) update references document-by-document; (3) deprecate the old label (kept as alias through the compatibility window). No hard rename; no broken reference.

**Migration-surface map — which documents each correction touches:**

| NC | Change | Documents touched | Alias |
|---|---|---|---|
| **C1 / NC-1** | tiers L0–L4 → T0–T4 | Constitution (defines), PO-8, PO-10, this doc | "L-tier" → "T-tier" |
| **C2 / NC-2** | milestones M0–M17 → MS-0…MS-17 | Roadmap, PO-8 | "M-n" → "MS-n" |
| **C3 / NC-3** | entity → POS; PO- = work items | all docs referencing "ProjectOS (PO)" | "PO (entity)" → "POS" |
| **C4 / NC-6** | phases → POS-Pn / `<PRD>-Pn` | Kernel docs, EduOS, Roadmap | "Pn" → namespaced |
| **C5 / NC-4** | reserved words; product renames | EduOS (`content pack`→Content Bundle, `product DNA`→Product Brief, `Pack Registry`→Content Registry) | old terms aliased |
| **C6 / NC-5** | retire CR / PI acronyms | corpus-wide | spelled-out / INT |

**Relabel mapping table** (the canonical substitution list the executor applies):

```
  L0→T0  L1→T1  L2→T2  L3→T3  L4→T4        (document tiers only; verification L0–L3 unchanged)
  Milestone M0→MS-0 … M17→MS-17            (maturity M0–M4 unchanged)
  "ProjectOS" entity → POS ; PO-<n> unchanged
  Kernel P1–P4 → POS-P1…P4 ; EduOS P0–P6 → EDU-P0…P6
  "content pack"→"Content Bundle" ; "product DNA"(EduOS)→"Product Brief" ; "Pack Registry"→"EDU:Content Registry"
  bare "CR"→spell out ; "PI"→"INT"/spell out
```

**Ordering:** relabels run **after** Stage A (so the Register already carries T-labels) and are applied to the *defining* document first, then its references, so no reference points at a not-yet-relabeled target.

## 6. Rollback Strategy

- **Mechanism:** the repo is git-backed and the ledger is hash-chained. Each operation is one commit tagged with its Op-ID; **rollback = `git revert <op-commit>` + an audit "rollback" entry**. State returns exactly to the prior safe-point.
- **Granularity:** per-operation (revert one op) or per-stage (revert to the stage's safe-point).
- **Triggers:** a failed verification check (§7), a discovered inconsistency, or a founder halt. Rollback is mandatory before proceeding past a red check (fail-closed).
- **Alias preservation:** naming rollbacks keep the alias, so even a reverted rename leaves references resolvable — rollback never breaks the corpus.
- **Kernel guard:** if kernel tests ever go red during a ratification op (they should not — the kernel is untouched), that op is rolled back immediately and escalated as an anomaly.
- **Irreversibility:** none. Every ratification operation is reversible-until-the-next-safe-point; the audit chain's append-only entries are the only non-revertible artifact (by design — they record that a rollback happened).

## 7. Verification Plan

Every operation has an **exit gate**; every stage has a **consistency gate**.

**Per-operation exit gate:**
1. The edit matches its spec (diff review — L2 delta review for canonical edits).
2. No dangling reference introduced (referential-integrity check across the corpus).
3. No new naming collision introduced (run the PO-9 collision check).
4. Kernel tests still green (guard).

**Per-stage consistency gate (the safe-point):** the automated **corpus consistency check** — the PO-2.5 review pattern, now a repeatable gate — confirms: one authoritative source per domain still holds (Constitution Register intact); no duplicated/dangling authority; every alias resolves; tier/level/milestone/maturity labels are collision-free; the corpus is still an acyclic DAG.

**Final gate (D3):** full-corpus consistency check passes clean; the Corpus v1.0 manifest matches the Register.

No operation or stage closes on a claim — each closes on the evidence in §8.

## 8. Evidence Requirements

Each operation must produce and record:

| Evidence | What it proves |
|---|---|
| **Commit** (tagged Op-ID) | the change was made, atomically |
| **Diff** | exactly what changed (canonical edits get an L2 delta review) |
| **Consistency-check result** | the corpus stayed valid (single-source, no dangling refs, no collisions) |
| **Kernel test result** | the kernel stayed green (guard) |
| **Audit entry hash** | the operation is anchored in the append-only ledger |

An operation with any evidence item missing or red is **not complete** and does not advance the sequence (fail-closed, kernel evidence discipline).

## 9. Audit Trail

- **A ratification ledger** records the whole program: opened at A1, one entry per operation, closed at D1. It is **hash-chained and append-only**, anchored to the kernel audit chain (Foundation Spec §8) — the same tamper-evident discipline the platform uses for assignments, now applied to its own ratification.
- **Entry schema (design-level):** `{ op_id, action, target, before_ref, after_ref, actor, evidence[], prev_hash, hash }`. Before/after are git refs (immutable), so any entry is independently verifiable.
- **This is the Decision/Event registry pattern (PO-7) applied to ratification** — decisions (each amendment) and events (each op) are recorded once, verifiably, and feed the audit history. No parallel bureaucracy: it reuses the kernel's chain.
- **The ledger is itself an evidence artifact** for CA-8 (the ratification record) and for any future consistency review.

## 10. Founder Approval Checkpoints

Designed for minimal founder touch (Decision Budget):

| Checkpoint | When | Founder action | Type |
|---|---|---|---|
| **CP-0** | Before A1 | **Sign PO-10** (already the authorization for the whole program) | Required (done at PO-10) |
| **CP-A (optional)** | After Stage A safe-point | *Optionally* review the amended Constitution before the naming sweep | Opt-in only |
| **CP-exception** | On any red gate | Resolve an escalation (halt/rollback/amend) | Only if triggered |
| **CP-final** | After D3 | Confirm ratification complete (informational) | Confirmation |

The default path is **one upfront sign-off (CP-0) → automated execution → one completion confirmation (CP-final)**, with the founder pulled in mid-stream only if a gate fails. CP-A is offered for a founder who wants to eyeball the amended Constitution before the relabels, but is not required — the relabels are non-destructive and already approved.

## 11. Execution Roadmap

The four stages as governed sub-assignments, dependency-ordered, mapped to Roadmap Wave 0 / MS-0.

| Stage | Sub-assignment | Contents | Gate | Lane |
|---|---|---|---|---|
| **A** | Amendments & Register | A1–A6 | Stage consistency gate + L2 delta review (canonical edits) | B |
| **B** | Governance corrections | B1–B3 | Stage consistency gate; GC-1 keeps core domain-neutral | A/B |
| **C** | Naming migrations | C1–C6 | Collision check clean; all aliases resolve | A |
| **D** | Finalize | D1–D3 | Full-corpus consistency clean; manifest matches Register | B |

Sequence: **A → B → C → D**, each starting only after the prior stage's safe-point is green. The whole program is Roadmap **Wave 0 (MS-0)** and precedes any build (Wave 1 / Capability Registry still needs FD-3).

---

## APPENDIX A — L2 REVIEW

| Check | Verdict | Basis |
|---|---|---|
| Execution sequence | **PASS** | §2 ordered atomic ops A1…D3; Appendix B executable register. |
| Register update plan | **PASS** | §3 exact before→after rows. |
| Constitutional amendment execution | **PASS** | §4 — each CA as one governed edit op + version bump + ledger record. |
| Naming migration execution | **PASS** | §5 — alias-first method, migration-surface map, relabel mapping, defining-doc-first order. |
| Rollback strategy | **PASS** | §6 — git revert + audit entry; per-op/per-stage; safe-points; alias-preserving; fail-closed. |
| Verification plan | **PASS** | §7 — per-op exit gate + per-stage consistency gate + final gate; kernel-green guard. |
| Evidence requirements | **PASS** | §8 — commit/diff/check/kernel/audit-hash per op; missing evidence = not complete. |
| Audit trail | **PASS** | §9 — hash-chained ratification ledger anchored to the kernel chain; entry schema. |
| Founder approval checkpoints | **PASS** | §10 — CP-0 authorizes; exception-only + CP-final; minimal touch. |
| Execution roadmap | **PASS** | §11 — stages as sub-assignments, gated, mapped to Wave 0/MS-0. |
| Modifies no canonical doc; executes nothing | **PASS** | Every change is specified and deferred to a future execution run; this doc edits and runs nothing (status line, §0). |
| Implementation-ready | **PASS** | Operation-level granularity + executable register (Appendix B) + explicit gates/evidence — a run team could execute without further design. |

**Reviewer verdict: PASS.** No blocking issues. The plan converts the approved package into an operation-level, reversible, evidence-anchored execution program with a kernel-untouched guard, minimal founder checkpoints, and a hash-chained audit trail — implementation-ready, while modifying and executing nothing.

---

## APPENDIX B — Operation Register (executable checklist)

The run team executes these top-to-bottom; each row is one commit + one ledger entry; do not advance past a red gate.

```
STAGE A  [ ] A1 open ledger        [ ] A2 T1 status (CA-1)     [ ] A3 register PO-7/RT/PO-8/PO-9/PO-2.5
         [ ] A4 retire CR-1 placeholder   [ ] A5 FD-1 record   [ ] A6 set Corpus v1.0     → SAFE-POINT A (consistency gate)
STAGE B  [ ] B1 triggers→trading pack (GC-1)   [ ] B2 runtime reconcile (GC-2)   [ ] B3 next-assignment align (GC-3)
                                                                                          → SAFE-POINT B (consistency gate)
STAGE C  [ ] C1 tiers L→T (NC-1)   [ ] C2 milestones M→MS (NC-2)   [ ] C3 entity POS (NC-3)
         [ ] C4 phases namespace (NC-6)   [ ] C5 reserved words + product renames (NC-4)   [ ] C6 retire CR/PI (NC-5)
                                                                                          → SAFE-POINT C (collision check)
STAGE D  [ ] D1 record ratification (CA-8)   [ ] D2 publish Corpus v1.0 manifest   [ ] D3 full-corpus consistency (EXIT GATE)
         → CP-final (founder confirmation)
HELD (not in this run):  NC-7 Experience/Design cluster ;  anything the founder marked Hold in PO-10
```

---

*End of PO-11 Ratification Execution Plan. Design only — modifies no canonical document and executes no migration. It specifies, at operation granularity, how the approved PO-10 package is applied: atomic, reversible, evidence-anchored, kernel-untouched. A separate authorized run executes it; this document stops at the specification.*
