# Founder Governance Package v1

**One decision package for the founder — integrating PO-10 (what to approve), PO-11 (how it executes), PO-12 (the AI Workspace handoff), and PO-13 (the independent review).**

**Prepared by:** Claude Cowork (ProjectOS), Lane B. **Type:** Founder decision package. **No implementation.**
**Headline:** The independent review (PO-13) returned **FAIL** with two blockers. **You should NOT sign the ratification approval sheet yet.** This package gives you the decisions you *can* make now, the one you shouldn't, and the corrected path.

---

## 1. Where things stand (one screen)

| Thing | State | Evidence |
|---|---|---|
| **Foundational corpus** (Constitution, Kernel, Methodology, Genome, PO-3/4/5/7/8/9, Runtime, Roadmap) | Authored, internally consistent, committed | 18 docs in repo; real SHA-256 in PO-12 manifest |
| **Kernel** | **Implemented** (working code) | `src/projectos`, 479 tests |
| **Ratification package (PO-10)** | Proposed — **not sign-ready** | PO-13 FAIL |
| **Execution runbook (PO-11)** | Proposed — **2 blockers** | PO-13 F1, F2 |
| **AI Workspace handoff (PO-12)** | Prepared with real hashes; **sequencing must follow ratification** | PO-13 F2 |
| **Independent review (PO-13)** | **FAIL / do not sign yet** | PO13 review, committed |
| **Ratification executed?** | **No** — nothing canonical has been edited | — |

Nothing is broken and nothing is lost — the design is sound. The blockers are ordering/sequencing defects in the *ratification plan*, not in the corpus itself.

## 2. Why not sign yet — the independent verdict (PO-13)

An independent, fresh-context reviewer (not the author) reviewed PO-10/PO-11 and returned **FAIL** on two blockers:

- **B1 (F1) — the FD-1 gate is inverted.** The plan says your operating-model decision (FD-1) must come *first*, but the runbook would ratify the Methodology *before* recording your decision, and the sign-off sheet lets you approve ratification while the decision is still held. Contradictory — must be fixed.
- **B2 (F2) — ratification silently breaks the AI Workspace handoff.** PO-12's safety rests on exact file fingerprints (hashes). The ratification edits those very files, invalidating every fingerprint, and neither plan noticed or planned a re-hash. Order must change: ratify first, then re-issue the handoff with fresh hashes.

Plus six material findings (verification level should be L3 not L2, a self-contradictory relabel order, the Roadmap edited outside approved scope, an orphan operation, an under-counted rename surface, and product-owned EduOS edits swept into the platform run). None require redesign — all are a bounded correction pass.

## 3. Decisions available to you NOW

Three productive decisions you can make immediately, plus one thing to explicitly *not* do. These are decision-ready and serialized.

### D1 — Canonical operating model (FD-1)  ·  DECIDE NOW
This is the decision that *unblocks* B1. Which operating-model content is canonical?

| Option | Consequence |
|---|---|
| **(A) Methodology v2 canonical; EduOS's 5-doc constitution = Local Expression** *(recommended)* | The Constitution already makes product constitutions Local Expressions (§7). Clean, no override; unblocks B1. |
| (B) Fold EduOS's model into the canonical Methodology | Larger rewrite of Methodology; delays ratification. |
| (C) Hold | B1 stays blocked; ratification cannot proceed. |

**Recommendation: (A).**

### D2 — Portfolio priority / Critical Path (FD-4)  ·  DECIDE NOW (independent)
Which product leads the eventual first platform cutover — **EduOS**, **TradeOS**, or **platform build first**? This doesn't block ratification; it sets the one Critical Path so lanes don't contend. *(No default forced — your call.)*

### D3 — Authorize the correction pass (PO-14)  ·  AUTHORIZE (low risk)
Authorize Cowork to fix the two blockers + six material findings in PO-10/PO-11 (bounded correction, not redesign), then send the corrected plan for an **independent re-review**. Nothing canonical is edited by this; it only repairs the *plan*.

### D4 — Ratification approval sheet  ·  DO **NOT** SIGN YET
Per PO-13, signing now would authorize an unsafe run (ratify-before-decision; break the handoff). **Withhold signature until D3's correction pass passes independent re-review.** This is the one action to defer.

### D5 — NC-7 external terms  ·  OPTIONAL
Whenever convenient, define the four external terms (Enterprise Experience System, Experience System, Encounter Intelligence, Design System) so the naming standard's last held item closes. Not blocking.

## 4. The corrected path (what happens after your decisions)

```
  D1 (FD-1) + D2 (FD-4) decided ─┐
  D3 authorize PO-14 correction  │
             │                   │
             ▼                   │
  PO-14: fix B1 (encode FD-1→CA-1 gate), B2 (sequence PO-12 after ratify + re-hash step),
         + 6 material findings (L3, relabel order, scope, orphan op, surface, product edits)
             │
             ▼
  Independent re-review  ──►  PASS? ──no──► correct again
             │ yes
             ▼
  Founder signs the CORRECTED ratification approval sheet  (the sign-off deferred in D4)
             │
             ▼
  Execute ratification (PO-11 stages A→D, atomic, reversible, evidence-logged)
             │
             ▼
  RE-ISSUE PO-12 handoff with fresh hashes  ──►  Claude Code imports to AI Workspace
             │
             ▼
  Wave 1 build: Capability Registry (MS-0)   [still gated on your FD-3 "authorize build"]
```

The corpus is done; this is the safe road from *design* to *ratified + handed off + building*.

## 5. Consolidated Decision Register

| # | Decision | Status | Your action | Recommendation |
|---|---|---|---|---|
| **FD-1** | Canonical operating model | Open — **gating** | Decide (D1) | Option A |
| **FD-4** | Portfolio priority / Critical Path | Open | Decide (D2) | Your call |
| **PO-14** | Authorize correction pass | Awaiting | Authorize (D3) | Yes |
| **Ratification sign-off** | **Blocked (PO-13 FAIL)** | Deferred (D4) | **Do not sign yet** | Wait for re-review |
| **FD-3** | Authorize Wave 1 build | Open — later | After ratification | After handoff re-issued |
| **NC-7** | 4 external term definitions | Held | Define when ready (D5) | Optional |

## 6. What your decisions do — and don't

- **Deciding D1/D2 and authorizing D3** unblocks the correction and sets direction. It edits **no** canonical document, runs **no** ratification, writes **no** code.
- **Not signing D4** keeps the canonical corpus untouched and safe until the plan is corrected and independently re-reviewed.
- Ratification, the AIW import, and the build all remain **downstream** of a clean re-review — nothing irreversible happens on your decisions here.

---

## Provenance & integrity note

This package integrates four source documents faithfully: **PO-10** (approval scope), **PO-11** (execution runbook), **PO-12** (handoff, real hashes), and **PO-13** (independent FAIL verdict, 2 blockers + 6 material findings). It does **not** overturn or soften PO-13 — the FAIL stands, and this package is built around it rather than against it. No canonical document was modified; no ratification was executed. The recommendation to **not sign yet** is the honest consequence of the independent review, even though it defers the founder sign-off my earlier turns had pointed toward.

*Prepared for founder decision. No implementation. Stops after delivery of this package.*
