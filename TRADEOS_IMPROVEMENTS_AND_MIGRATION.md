# TradeOS → ProjectOS — Governance Improvements Review & Migration Architecture

**Part A:** today's TradeOS governance work, reviewed for changes worthy of ProjectOS. **Part B:** the architecture for migrating the approved ones into ProjectOS after founder approval.
**Read-only. No edits to any canonical or TradeOS document. Part B is architecture only — no execution.**
**Reviewer:** Claude Cowork, Lane B. **Verification level:** L2.

---

## 0. Evidence basis

Access to `C:\TradeOS-AI` governance was granted this session; findings are grounded in **files actually read today**, not inference:

`.tradeos/WORKFLOW_RULES.md` · `.tradeos/QUALITY_GATES.md` · `.tradeos/ORCHESTRATOR.md` (TAO v1.0) · `.tradeos/AGENTS.md` · `.tradeos/FOUNDER_DECISIONS.md` (TAO tick 2026-07-28 07:55Z) · `.tradeos/reviews/feat-fe1-founder-journal-d808311.md` (today's T2 review) · `docs/FE1R_LIMITATIONS_AND_RESIDUAL_RISK.md` · `docs/SESSION_OVERRIDE_POLICY.md` · `docs/SESSION_RECONCILIATION_RUNBOOK.md` · `docs/DAILY_RISK_POLICY.md`.

**Today's work = the Founder Edition (FE-1R) release** — session-scoped daily-risk governance, audited override, reconciliation gate, residual-risk disclosure, exact-money domain, blocked-loud reference data — plus the standing TAO orchestration governance. The bar applied: **only patterns that are domain-neutral, reusable, and either fill a gap in the ProjectOS corpus or harden an existing rule.** TradeOS-specific trading logic (Kelly, edge, SENSEX calendar) is excluded — it is Domain DNA, not platform.

---

## PART A — ProjectOS-worthy improvements

Each: what TradeOS does · evidence · why worthy (gap filled / rule hardened) · ProjectOS target. Ranked ★★★ (must promote) to ★ (worthy).

### A.1 Governance

| ID | Improvement | Evidence | Why worthy | ProjectOS target |
|---|---|---|---|---|
| **G-1 ★★★** | **Review tier computed from the diff, chosen by no one** — T0/T1/T2 derived mechanically from diff contents; **path-based skipping prohibited** by a recorded lesson ("WP-0.2 shipped two Major defects that touched no frozen path and passed every gate"). | `WORKFLOW_RULES.md` R2 | ProjectOS PO-4 has a trigger gate but leaves tier selection to the owner. TradeOS makes it **deterministic and non-gameable**, and encodes a learned anti-skip rule. Hardens PO-4 §8. | PO-4 (governance) + PO-5 (the learned-rule metric) |
| **G-2 ★★★** | **Separation of duties — the implementer never self-routes.** The actor that wrote the diff never computes its own review tier, marks its own task COMPLETE, activates its own next task, or reviews its own work. Proposal allowed; activation belongs to the tick. | `WORKFLOW_RULES.md` R5; `ORCHESTRATOR.md` "who does what"; `AGENTS.md` | ProjectOS says reviewer ≠ author (PO-3); TradeOS extends it to **routing, completion, and activation** — a full separation-of-duties rule. Directly relevant to PO-13's finding that L3 review must be independent. | PO-3 / PO-4 |
| **G-3 ★★★** | **Declared inviolable human-authority boundary.** Every governance doc ends with a "Future AI Workspace boundary" clause naming acts **no remote/AI service may ever perform** — create an override, clear a lockout, make the reconciliation confirmation, assert unknown risk is zero. | override §11, reconciliation §9, daily-risk §11, residual-risk §15 | **Novel — ProjectOS has no per-capability "what the platform/AI may never do."** A capability that declares its inviolable human acts is a powerful, reusable ownership/governance primitive. Complements PO-3 ownership. | PO-3 (ownership) + PO-4 |
| **G-4 ★★** | **Ship blocked-loud rather than fabricate.** Reference data shipped `verified:false`, version `*-0.0.0-BLOCKED`, so every query **fails closed** until the founder supplies verified facts. "A wrong holiday reads as an ordinary trading day — the silent failure the whole design exists to prevent. So the gap is loud." | residual-risk §2; daily-risk §5; FE1R review N-1 | Turns "never invent a platform fact" into a **shipping discipline**: ship inert-and-loud, never faked. ProjectOS has fail-closed but not this release pattern. | PO-4 + never-invent-a-fact rule |

### A.2 Methodology

| ID | Improvement | Evidence | Why worthy | ProjectOS target |
|---|---|---|---|---|
| **M-1 ★★★** | **`needs_revision ×2` ⇒ re-plan, don't retry — the *assignment* is wrong.** Two rejections on one task escalate and force **re-scope, not re-issue**; no `§Revision` brief is written. | `WORKFLOW_RULES.md` R1; `ORCHESTRATOR.md` escalation; today's review "R1 consequence" | ProjectOS's reject→fix→resubmit loop has **no "the assignment itself is wrong" escape** — it can retry a mis-scoped task forever. This rule is a genuine methodology gap-filler. | Methodology (assignment lifecycle / rejection) |
| **M-2 ★★★** | **One founder file, with cost-of-delay tracking.** `FOUNDER_DECISIONS.md` is "the only file the founder must read" — refreshed each tick, options+consequences+recommendation, and it tracks **how much each open decision costs as it ages** ("this is the tick where it started costing money … cost has roughly quintupled since this morning"). | `FOUNDER_DECISIONS.md`; `AGENTS.md` Founder role | Operationalizes PO-5's Founder Decision Budget into a **concrete artifact** and adds **cost-of-open-decision** as a live metric — stronger than the current metric definition. | Methodology §9 + PO-5 (Decision Budget) |
| **M-3 ★★** | **Repository is memory; state file is single source of truth; git wins on conflict, with the correction logged.** "If git and `PROJECT_STATE.yaml` disagree, git wins, the state file is corrected, and the correction is noted in `FOUNDER_DECISIONS.md`." Every tick runs `tao.py validate` (CONSISTENT on entry/exit). | `ORCHESTRATOR.md`; `FOUNDER_DECISIONS.md` tick notes | Concrete state-reconciliation-with-audit pattern; hardens ProjectOS "repository is source of truth" into an enforced, logged reconciliation. | Kernel / Methodology |

### A.3 Verification

| ID | Improvement | Evidence | Why worthy | ProjectOS target |
|---|---|---|---|---|
| **V-1 ★★★** | **Certification ≠ gates-green.** "These gates prove code health only. They certify nothing … 'Tests passed' is never evidence of a valid model." Domain-validity certification is a **separate authority** (C6 + approver) from mechanical gates. | `QUALITY_GATES.md`; today's review N-3, §"health-number" | ProjectOS's verification levels don't cleanly separate **code-health gates** from **domain-validity certification**. A distinct "certified-valid" grade (above gates-green) is a real verification-model improvement. | PO-5 / verification model |
| **V-2 ★★★** | **Evidence-grade taxonomy for facts/data.** `FOUNDER_ASSERTED < CORROBORATED < EXCHANGE_VERIFIED / BROKER_VERIFIED`, each fact carrying `source_grade`, `last_verified_at`, a staleness window, and a version stamped onto every record so a later revision cannot rewrite a past entry. | residual-risk §3–4; reconciliation record fields; override record fields | **Novel — a maturity ladder for *data/facts*,** parallel to capability maturity M0–M4. Fits PO-7's Schema/Event registries and the never-invent-a-fact rule exactly. | PO-7 (registries) + PO-5 |
| **V-3 ★★★** | **Independent review, executed and counted — with carried-finding continuity.** Gates re-run in a **real `git clone`** (not an archive — one test false-fails in a tarball), **counted from junit-xml, not eyeballed**; the review is delta-only, tracks findings across rounds (F-1…F-7 *carried* vs *new*), and refuses to re-litigate. | today's review (whole doc); `AGENTS.md` Cowork role | Stronger than ProjectOS's L2/L3 review spec: adds **carried-finding continuity across review rounds** and **artifact-counted evidence**. Reinforces PO-13's independence lesson. | Methodology §15 / PO-4 review framework |
| **V-4 ★★** | **Fail-closed defaults + "tested-but-unreachable = false-green".** The review caught two safety inputs defaulting to the reassuring answer (inverting fail-closed) and flagged **nine "declared-but-unconsumed controls"** — "green tests and working features have stopped meaning the same thing." | today's review M-1, m-3; daily-risk §5 | Two reusable verification checks: (a) **safety inputs must default to refusing**; (b) **passing tests on unreachable code is a false green**. Neither is in the ProjectOS verification model. | PO-5 / verification checks |

### A.4 Workflow

| ID | Improvement | Evidence | Why worthy | ProjectOS target |
|---|---|---|---|---|
| **W-1 ★★★** | **Required Residual-Risk disclosure per governed release.** A shipped, ranked "what this does **not** guarantee" register — severity + mitigation + **which test backs each claim** ("This document exists to be uncomfortable. Read this before trusting the software with money"). | `FE1R_LIMITATIONS_AND_RESIDUAL_RISK.md` (whole) | ProjectOS produces governance records but has no mandatory **residual-risk / limits-of-the-guarantee** artifact tied to a GOVERNED release. A strong, honest workflow addition. | PO-4 (governed-release record) |
| **W-2 ★★** | **Audited escape-hatch pattern.** The override raises a self-imposed limit but **cannot fabricate available risk, cannot treat unknown as zero, is session-scoped, expires by derivation, and leaves the original limit + breach permanently visible** — "explains a decision; must never erase the evidence it was needed." | `SESSION_OVERRIDE_POLICY.md` | A reusable governance primitive: *a governed way to exceed a self-imposed constraint that makes the exception expensive, legible, and permanently evidenced.* Applies to any platform limit/gate. | PO-4 (governance) |
| **W-3 ★★** | **Reconciliation gate: forward progress conditional on looking back.** The next session's budget is unlocked **only** after the prior session is founder-confirmed `RECONCILED`; `MISMATCH` never self-clears; absence of a record = `PENDING`, never agreement. | `SESSION_RECONCILIATION_RUNBOOK.md`; daily-risk §3 | A reusable workflow: *a period cannot close clean until its evidence was actually reviewed.* Generalizes to milestone/close gates. | Methodology / PO-4 |
| **W-4 ★** | **Derive state from facts, never from a flag a process must flip.** Override expiry is computed at read-time from `session_id`, not a stored boolean — "a flag needs a process to flip it, and a process that does not run leaves an override alive past its session." | override §4; reconciliation §4 | A determinism/robustness principle already latent in ProjectOS (derived active-pointer); worth codifying as a rule. | Kernel / Methodology (determinism) |

**Not promoted (correctly Domain DNA, not platform):** the exact-INR money domain (`money.py`), SENSEX calendar/instrument providers, Kelly/edge/EV machinery, the ₹20,000 limit itself. These belong in the trading Domain Pack (and are the correct home for the misplaced root triggers flagged in the prior review, PO-2.5 O-2).

---

## PART B — Migration Architecture (into ProjectOS, after founder approval)

**Architecture only. No edits, no execution.** This defines *how* an approved TradeOS improvement becomes part of ProjectOS. It reuses the platform's own promotion + governance machinery — a TradeOS governance improvement is a **product-local capability promoted into the genome** (Genome §13), governed exactly like any platform change.

### B.1 The promotion pipeline (per approved improvement)

```
 (0) Founder approves the improvement subset (this document's Part A is the candidate list)
        │
 (1) INTAKE      capture the improvement + its TradeOS evidence (file, hash — PO-12 provenance discipline)
        │
 (2) GENERALIZE  strip trading specifics → domain-neutral platform form (Genome §13 generalize-before-promote).
        │        Domain remainder stays in the trading Domain Pack.
 (3) CLASSIFY     route to exactly one ProjectOS canonical doc (§B.2 routing table) → sets owner + tier
        │
 (4) VERIFY       B3-style evidence check: the improvement is proven in TradeOS, not asserted; grade its maturity
        │        (V-2's evidence-grade taxonomy applies to the improvement itself)
 (5) GOVERN       GOVERNED / L3 (it changes the platform) + INDEPENDENT review (PO-13 pattern) + founder sign-off
        │
 (6) PACKAGE      a PO-10-style amendment entry (proposed, modifies nothing yet)
        │
 (7) EXECUTE      a PO-11-style atomic, reversible, evidence-logged edit — one improvement = one op = one ledger entry
        │
 (8) INHERIT      once in the genome, all products inherit it; TradeOS then INHERITS the platform version
                  and deprecates its local fork (anti-fork; Genome §11/§18)
```

Every migration is itself a governed change under the ratified corpus — so it inherits the PO-10 / PO-11 / PO-13 discipline this program already built (independent review included). Nothing is edited by this plan; it is the pipeline the approved subset would run through.

### B.2 Per-improvement routing table (architecture)

| Improvement | ProjectOS target doc | Owner (PO-3) | Governance tier | Migration form |
|---|---|---|---|---|
| G-1 diff-computed review tier + anti-skip | PO-4 §8 | ProjectOS | GOVERNED/L3 | amend the trigger-gate rule |
| G-2 separation of duties | PO-3 / PO-4 | ProjectOS | GOVERNED/L3 | add the "never self-route" rule |
| G-3 inviolable human-authority boundary | PO-3 (ownership) | ProjectOS | GOVERNED/L3 | new ownership primitive (per-capability "never-do" set) |
| G-4 ship-blocked-loud | PO-4 + never-invent-a-fact | ProjectOS | REVIEWED/L2 | add release discipline |
| M-1 needs_revision ×2 ⇒ re-plan | Methodology (lifecycle) | ProjectOS | GOVERNED/L3 | amend rejection loop |
| M-2 one founder file + cost-of-delay | Methodology §9 + PO-5 | ProjectOS | REVIEWED/L2 | artifact + new metric |
| M-3 git-wins state reconciliation | Kernel/Methodology | ProjectOS | REVIEWED/L2 | codify reconciliation-with-audit |
| V-1 certification ≠ gates | PO-5 / verification | ProjectOS | GOVERNED/L3 | add a certified-valid grade above gates-green |
| V-2 evidence-grade taxonomy for facts | PO-7 (Schema/Event) + PO-5 | ProjectOS | GOVERNED/L3 | new data-provenance grade (parallel to M0–M4) |
| V-3 review: counted + carried findings | Methodology §15 | ProjectOS | REVIEWED/L2 | harden review framework |
| V-4 fail-closed defaults + false-green | PO-5 checks | ProjectOS | REVIEWED/L2 | add two verification checks |
| W-1 residual-risk disclosure | PO-4 (governed release) | ProjectOS | REVIEWED/L2 | new required artifact |
| W-2 audited escape-hatch | PO-4 | ProjectOS | REVIEWED/L2 | governance primitive |
| W-3 reconciliation gate | Methodology/PO-4 | ProjectOS | REVIEWED/L2 | milestone-close pattern |
| W-4 derive-state-not-flag | Kernel/Methodology | ProjectOS | REVIEWED/L2 | determinism rule |

### B.3 Constraints & sequencing

1. **Conditioned on founder approval.** The pipeline runs only on the improvements the founder approves; Part A is the candidate list, not an approved set.
2. **Governed like everything else.** Each promotion is GOVERNED/L3 (it changes the platform), independently reviewed (PO-13 pattern), packaged (PO-10 style) and executed atomically/reversibly (PO-11 style). No shortcut because it "came from a working product."
3. **Generalize before promote.** Only the domain-neutral form enters the genome; the trading remainder stays in the trading Domain Pack. A capability carrying trading assumptions is not promotable (Genome §13).
4. **Non-destructive, one at a time.** One improvement = one governed sub-assignment = one reversible edit = one ledger entry. Independent findings isolate to their improvement.
5. **Ordering by leverage:** promote the ★★★ governance/methodology/verification rules first (they harden the corpus the rest depends on); then the ★★ workflow patterns; V-2 (evidence-grade) and G-3 (inviolable boundary) are the two novel primitives worth early attention.
6. **This migration is also the fork-resolution.** The prior review (PO-2.5 CF-1) flagged TradeOS running its own `.tradeos` governance parallel to ProjectOS — and TradeOS's own open decision **ESC-001 ("which state file is canonical?")** is the local mirror of that. Promoting the good `.tradeos` patterns **up** into ProjectOS, then having TradeOS **inherit** them, is the anti-fork path that resolves both at once. (Recommendation is architectural: reconcile toward one governance kernel; the direction is a founder decision.)

### B.4 Dependency / handoff

Runs after: (a) founder approval of the Part A subset, and (b) the ratification correction pass (PO-13 blockers F1/F2) — since these promotions edit canonical docs, they should ride the **corrected** ratification/execution machinery, not the current flawed one. Each promoted improvement then flows to products by inheritance, and TradeOS deprecates its local fork.

---

## Appendix — L2 verification note

Findings in Part A are each cited to a file read this session (§0); no TradeOS content was invented. Part B reuses the ProjectOS promotion/governance machinery without proposing any edit or execution. Domain-specific material is explicitly excluded from promotion (kept as Domain DNA). The migration is conditioned on founder approval and on the corrected ratification machinery. **Read-only; no canonical or TradeOS document was modified.**

*Prepared by Claude Cowork. Part A: improvements review. Part B: migration architecture. No edits; no execution; both await founder approval of the improvement subset.*
