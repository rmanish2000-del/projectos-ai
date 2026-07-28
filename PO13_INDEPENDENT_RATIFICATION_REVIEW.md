# PO-13 — Independent Ratification Readiness Review

**An independent L3 review of PO-10 and PO-11 before founder sign-off. Verdict: FAIL — do not sign yet.**

**Assignment:** PO-13 — Independent Ratification Readiness Review. **Lane:** B — Independent Review. **Verification Level:** L3 Review. **Type:** Governance Assurance.
**Documents reviewed:** PO-10 (Ratification & Correction Package), PO-11 (Ratification Execution Plan). Neither was modified.
**Out of scope (honored):** no canonical edits, no ratification execution, no redesign, no new governance framework, no code.

---

## Provenance & independence

This review satisfies the L3 **independence requirement** the corpus itself mandates: "the Reviewer is never the author of the work under review" (PO-3) and "fresh context is the point of L2/L3 … independent verification must come from outside the authoring context" (Methodology §15, PO-9 §21 method).

- PO-10 and PO-11 were authored by **Claude Cowork**.
- This review was performed by an **independent fresh-context reviewer** that did **not** author those documents, read them cold, and was briefed to be adversarial. It read PO-10, PO-11, the Constitution, PO-8, PO-9, and the PO-12 handoff for cross-reference.
- The author (Cowork) compiled this document but **did not alter the reviewer's findings, severities, or verdict.** The review body below (§A–§H) is the independent reviewer's output, preserved faithfully — including its criticisms of the author's own work.

**Headline verdict: FAIL. Recommendation: do not sign PO-10/PO-11 yet.** Two blocker-class defects must be fixed and re-reviewed before founder authorization.

---

## A) Independent Assessment

PO-10 and PO-11 are well-organized, honestly-scoped proposals that correctly frame themselves as *proposals that modify nothing*, and they get most of the governance hygiene right: a genuine amendment basis (Constitution §10), an alias-first non-destructive migration model, a hash-chained ledger, per-operation rollback, and honest deferral of NC-7 and the FD-1-dependent work. However, read cold and adversarially, the package is **not execution-ready**. Two defects are disqualifying: (1) PO-10 declares that FD-1 *gates* CA-1's Methodology ratification, yet PO-11 sequences the Methodology ratification (A2) **before** the FD-1 decision is recorded (A5) and encodes no dependency between them, so a founder who Approves CA-1 but Holds FD-1 produces an incoherent, unauthorized state; and (2) neither document reckons with PO-12 — the "Critical" AI-Workspace handoff whose entire safety model is SHA-256 provenance — even though PO-11's Stage A and Stage C edit the exact files PO-12 pinned by hash, silently invalidating every hash the moment ratification runs. Add a verification-level mismatch (L3 amendments carried on an L2, non-independent self-review), a self-contradictory tier-relabel ordering, an out-of-scope Roadmap edit, and an orphan "publish new manifest" operation, and the correct disposition is **FAIL / do not sign yet**.

## B) Findings Register

| ID | Severity | Scope item(s) | Finding | Evidence | Recommendation |
|---|---|---|---|---|---|
| **F1** | **BLOCKER** | 2,3,9,11,14 | FD-1 is declared to *gate* CA-1's Methodology ratification, but PO-11 ratifies Methodology (A2) before FD-1 is recorded (A5), and A2 has no FD-1 dependency. The approval sheet lets the founder Approve CA-1 while Holding FD-1 — an impossible state (Methodology ratified canonical while the decision making it canonical is held). Ledger also records the effect (A2) before its cause (A5). | PO-10 §9 ("FD-1 (gates CA-1's Methodology ratification)"), §10 sheet (CA-1 and FD-1 as independent checkboxes); PO-11 §2 ops A2 (depends A1) and A5 (depends A2) | Make A2's Methodology component depend on the FD-1 resolution; record FD-1 (A5) before ratifying Methodology; on the sheet, bind CA-1-Methodology to FD-1 so they cannot be split. |
| **F2** | **BLOCKER** | 13,1 | PO-11 Stage A (Register/status edits to the Constitution) and Stage C (relabels to Constitution, Roadmap, PO-8, PO-9, PO-10, this doc, EduOS) mutate the exact files PO-12 hashed. Every PO-12 SHA-256 goes stale on execution; AIW's fail-closed integrity check then rejects the corpus, or consumes a pre-ratification snapshot. Neither PO-10 nor PO-11 references PO-12, sequences it, or schedules a re-hash. PO-11 D2 even publishes a *second, hashless* "Corpus v1.0 manifest," never reconciled with PO-12's. | PO-12 manifest lines 8–9, 30 ("HASHES ARE REAL… verify the hash before use"), guide §2/§6 ("A-007 consumes this package"); PO-11 §2 ops A3, C1–C6, D2; PO-11 §5 surface map | Sequence PO-12 handoff/import to run **after** PO-11 Stage D over the ratified files; add a terminal PO-11 step to regenerate PO-12's manifest hashes; state the ordering explicitly in both docs. |
| **F3** | MATERIAL | 2 | Constitution §10.1 requires amendments to be GOVERNED/**L3**. PO-11 labels itself Verification Level **L2**, and Stage A canonical edits get only an "L2 delta review." Both PO-10 and PO-11 close on self-authored "L2 REVIEW … PASS" appendices (same executor) — not independent verification of an L3 constitutional action. | PROJECTOS_CONSTITUTION §10.1; PO-11 line 6 + §11 Stage-A gate ("L2 delta review"); PO-10 App. A / PO-11 App. A (self-review) | Execute the amendment run at L3 with independent verification; do not rely on the authors' own L2 PASS stamps as the sign-off basis. |
| **F4** | MATERIAL | 3 | Transient tier-label inconsistency. PO-11 §3 shows Stage A writing Register rows as "PO-7 **(T2)**" etc., but T-labels are only introduced by C1 in Stage C. PO-11 §5 asserts relabels run "after Stage A (so the Register already carries T-labels)" — impossible, since C1 (which creates T) is *after* A. At Safe-Point A the Register (T) and hierarchy §3 (still L) disagree, so Stage A cannot pass its own consistency gate. | PO-11 §3 ("Tier labels L0–L4 → T0–T4 (after C1)") vs §5 ordering note; Constitution §3/§8 (still L0–L4) | Decide one order: either write Stage-A Register in L-labels and let C1 convert them, or move the tier relabel (C1) into Stage A ahead of registration. Fix the contradictory §5 justification. |
| **F5** | MATERIAL | 1,12 | The Roadmap (PROPOSED_CANONICAL, T2) is edited by C2 (milestone relabel) but appears in **no** PO-10 ratification/registration item and is absent from the §2 corpus set. architecture.md/cli.md — registered L2 in Constitution Appendix C — are also omitted from PO-10 §2. So execution edits/relies on canonical-tier docs outside the declared ratification scope. | PO-10 §2 corpus table (no Roadmap, no arch/cli); PO-11 §5 C2 ("Roadmap, PO-8"); PO-12 manifest ROADMAP=PROPOSED_CANONICAL T2 | Add the Roadmap (and arch.md/cli.md) to the ratification/registration scope or explicitly exclude them with rationale; no op may edit a canonical doc not in the approved set. |
| **F6** | MATERIAL | 12 | Op D2 "Publish Foundational Corpus v1.0 manifest (**new index doc**)" traces to no approved PO-10 item. PO-10 authorizes *setting* the corpus version and *recording* the event, not authoring a new canonical index document (which is itself Register-worthy). Orphan operation = scope creep. | PO-11 §2 D2; PO-10 §7/App. B (only "set Corpus v1.0" + "record the ratification") | Either add an explicit PO-10 item authorizing the manifest/index doc (and its Register placement) or drop D2 from the run. |
| **F7** | MATERIAL | 4 | C1's migration-surface map lists only "Constitution, PO-8, PO-10, this doc" as touched by the L→T relabel, but document-tier labels ("L1/L2/L3/L4") appear across the corpus (e.g., PO-8 §1 map, Constitution cross-refs, and any doc citing tiers). If the surface is under-enumerated, stale "L-tier" references survive → dangling/ambiguous labels the very migration exists to remove. | PO-11 §5 map row C1/NC-1; PO-8 §1/§2 use L0–L4 throughout | Derive the C1 surface by a corpus-wide grep for tier tokens before execution; the referential-integrity gate must fail if any un-aliased L-tier remains. |
| **F8** | MATERIAL | 4,10,12 | C5 (NC-4 product renames) and B3 (GC-3) edit EduOS **Local Expressions** (product-owned, protected under Constitution §2.8/§7) inside the platform ratification run, authorized only by the founder's platform sign-off — no product-owner consent path. Product-domain content edits are the product's to make. | PO-11 §2 B3, C5; §5 C5 ("EduOS … Content Bundle/Product Brief"); Constitution §2.8, §7 | Split product-local migrations into product-owned sub-assignments with the product's consent; keep the platform ratification to platform/canonical docs. |
| **F9** | MINOR | 3,7 | Atomicity is violated: A2 confers status on 6 docs and A3 registers 5 docs, each as a single op — contradicting §0.1 "one operation = one commit = one audit entry" and PO-10 §3's promise that any one CA can be held independently. A3's rollback even reads "revert *per-entry*." | PO-11 §0.1 vs §2 A2/A3; PO-10 §3 | Split A2 and A3 into one op per document so hold/rollback granularity matches the stated principle. |
| **F10** | MINOR | 11 | Target mismatch/undefined input: GC-1's file is `.projectos/policies.yaml**.txt**` in PO-10/PO-8 but `.projectos/policies.yaml` in PO-11 B1; and B1 moves triggers "→ trading Domain Pack," a destination that may not exist pre-Wave-1 (registries/packs unbuilt). | PO-10 §6 GC-1 & PO-8 §14 G-5 (`.txt`) vs PO-11 §2 B1; PO-8 §13/§17 (packs unbuilt until later waves) | Reconcile the filename; confirm the trading Domain Pack destination exists (or create it as an explicit prerequisite) before B1. |
| **F11** | MINOR | 2,3 | The version-bump treatment of the tier relabel (C1) is left open ("tracked as its own change"), with no MAJOR/MINOR determination, despite Constitution §11 treating hierarchy changes as potentially MAJOR. | PO-11 §4; Constitution §11 | State C1's semver classification and, if MAJOR, attach the §26 migration path and §27 conformance review. |
| **F12** | MINOR | 5 | The alias compatibility-window duration and the owner/trigger for eventual alias retirement are never specified; PO-9 §19 defers to "a compatibility window" that these plans never define. | PO-10 §8; PO-11 §5/§6; PO-9 §19 | Define the compatibility window and the governed step that retires aliases. |
| **F13** | MINOR | 14 | The approval sheet pre-checks ✅ Approve on every item — including the substantive FD-1 operating-model decision — biasing toward approval; there is no per-item "Amend" capture, and the CA-1↔FD-1 dependency (F1) is not surfaced to the founder. | PO-10 §10 sheet | Present unchecked choices with recommendations alongside (not pre-selected); add Amend fields; annotate the CA-1/FD-1 linkage. |
| **F14** | OBSERVATION | 8 | The "kernel tests green" guard is near-vacuous for a doc-only migration (markdown/Register edits cannot redden kernel tests); the real risk is corpus inconsistency, which the separate consistency gate handles. Guard is a cheap tripwire, not a safeguard — fine, but do not over-credit it. | PO-11 §0.5, §6, §7 | Keep the guard; rely on the consistency/referential-integrity gates as the substantive control. |
| **F15** | OBSERVATION | 7 | The ledger is "anchored to the kernel audit chain (Foundation Spec §8)," assuming the implemented kernel accepts non-assignment governance/ratification events — an unverified assumption about live code. | PO-11 §9 | Confirm the kernel audit chain can anchor governance events, or anchor the ledger independently and cross-reference. |

## C) Per-Item Verdicts (14)

1. **Package completeness** — Concern (F5, F2): Roadmap and arch/cli omitted from the ratified set though edited/registered elsewhere; PO-8's FD-2 silently absorbed.
2. **Constitutional authority** — Concern (F3, F1): §10 basis is real, but L3 requirement is carried on L2 non-independent self-review.
3. **Amendment sequencing** — Concern (F1, F4, F9): FD-1/CA-1 order inverted; self-contradictory tier-relabel ordering; non-atomic bundling.
4. **Naming migration safety** — Concern (F7, F8): surface map likely under-enumerated; product-doc edits swept into platform run.
5. **Alias / backward-compat** — OK, minor (F12): sound in principle; window/retirement undefined.
6. **Rollback completeness** — OK: every mutating op has a rollback; D1 append-only and D3-as-gate are correctly flagged (PO-11 §6).
7. **Audit-chain design** — OK, observation (F15, F9): hash-chained/append-only is sound; kernel-anchoring assumption unverified.
8. **Kernel-untouched guard** — OK, observation (F14): real but largely vacuous for doc-only edits.
9. **Founder checkpoints** — Concern (F1, F13): minimal-touch model is good, but a gating content decision (FD-1) is bundled into a one-click sheet.
10. **Held items** — OK: NC-7 held and GC-3 conditioned correctly; but see F8 (product edits not truly "held from the product").
11. **Missing dependencies** — Concern (F1, F10): FD-1→CA-1 gate not encoded; B1 destination/filename unresolved. (Note: GC-2 reconcile *direction* — spec adapts to as-built — is correct and well-handled.)
12. **Scope creep** — Concern (F6, F5, F8): D2 orphan op; Roadmap out-of-scope edit; product-local edits under platform authority.
13. **PO-12 sequencing** — **See F2 (BLOCKER):** ratification invalidates PO-12's hashes; ordering/re-issue absent.
14. **Approval sheet decision-ready** — Concern (F13, F1): readable and recommended, but pre-checked and hides the CA-1/FD-1 dependency.

## D) Quality-Check Results

1. **Constitution traceability** — **PASS.** Amendments cite real clauses (§10, §7, §11, §26, §27; §8.2 Register). *Caveat: the L3 verification level those clauses require is not met — see F3.*
2. **Amendment↔operation traceability** — **FAIL.** D2 (publish new manifest) is an orphan op with no PO-10 item (F6); CA-7 has no dedicated op (implied only); C2 edits the Roadmap, which is outside PO-10's scope (F5).
3. **Rollback traceability** — **PASS.** Every operation row states a rollback; irreversible append-only entries are explicitly flagged (PO-11 §6).
4. **Evidence completeness** — **PASS.** §8 defines a uniform evidence set (commit/diff/consistency-check/kernel-test/audit-hash) required to close each op; missing evidence = not complete.
5. **Cross-reference integrity** — **PASS (with concerns).** Most cited sections exist; but GC-1's target filename differs between PO-10 (`.yaml.txt`) and PO-11 (`.yaml`) (F10), the C1 surface map may under-enumerate (F7), and PO-8's FD-2 is not cross-referenced.

## E) Overall Verdict

**FAIL.** Two BLOCKER-class defects (F1: FD-1 gate not encoded / sequenced before CA-1; F2: PO-11 execution silently invalidates PO-12's hash provenance with no ordering or re-issue) make execution as written unauthorized and unsafe, compounded by material authority (F3), sequencing (F4), and scope (F5, F6) issues.

## F) Founder Sign-Off Recommendation

**Do not sign yet.** The package is close and the *direction* is sound, but signing now would authorize an execution run that (a) can ratify Methodology while its gating decision is held, and (b) knowingly breaks the "Critical" AIW handoff. Return PO-10/PO-11 for correction of the two blockers and the material findings, then re-review. Once the preconditions below are met, the disposition can move to **PASS WITH CONDITIONS**.

## G) Preconditions Checklist (must be true before execution may proceed)

1. **FD-1 gate encoded (F1):** A2's Methodology ratification depends on the FD-1 resolution; FD-1 is recorded (A5) before A2's Methodology component; the approval sheet binds CA-1-Methodology and FD-1 so they cannot be split.
2. **PO-12 ordering resolved (F2):** PO-12 handoff/import is explicitly sequenced *after* PO-11 Stage D; PO-11 adds a terminal step to regenerate PO-12's SHA-256 manifest; the PO-11 D2 manifest and PO-12 manifest are reconciled (one source of truth).
3. **Verification level corrected (F3):** the amendment run is executed at GOVERNED/L3 with an *independent* verification, not the authors' own L2 PASS appendices.
4. **Tier-relabel ordering fixed (F4):** a single, consistent order for writing vs relabeling tier tokens, such that Safe-Point A is genuinely consistent; the contradictory §5 justification removed.
5. **Scope closed (F5, F6):** the Roadmap (and arch.md/cli.md) are either in the ratification scope or explicitly excluded; D2's new index doc is either authorized by a PO-10 item (with Register placement) or dropped.
6. **Migration surface verified (F7):** the C1 (and every NC) surface map is regenerated from a corpus-wide token scan; the referential-integrity gate fails on any surviving un-aliased label.
7. **Product-owned edits separated (F8):** EduOS Local-Expression renames (C5) and the next-assignment alignment (B3) run as product-consented sub-assignments, not under platform authority alone.
8. **Atomicity restored (F9):** A2/A3 split to one op per document.
9. **Inputs resolved (F10):** GC-1 filename reconciled; the trading Domain Pack destination confirmed to exist or created as a prerequisite.
10. Minor items (F11–F13) addressed or explicitly accepted; F14–F15 acknowledged.

## H) Founder Summary (plain language)

These two documents ask you to formally bless the foundation ("make it official") and then lay out a careful, reversible plan to apply the cleanups. The plan is genuinely thoughtful — nothing is deleted, everything is logged, and every step can be undone. But two problems mean you should not sign it yet. First, the plan says a specific decision of yours (FD-1, "which operating model is canonical") must come *first*, yet the runbook actually ratifies that operating model *before* recording your decision — and the approval sheet even lets you approve the ratification while holding the decision, which is contradictory. Second, a separate "Critical" package (PO-12) that hands the corpus to the build team relies on exact file fingerprints; this ratification edits those very files, which will invalidate every fingerprint, and neither document notices or plans for it. Fix those two, tighten the scope and the verification level, and this becomes a sign-able package; as written, the recommendation is to send it back.

---

## Compiler's note (Cowork)

The findings above are the independent reviewer's, preserved verbatim. As author of PO-10/PO-11 I did not contest, soften, or remove any finding — including F1 and F2, which are defects in my own work. The verdict stands as issued: **FAIL / do not sign yet.** The two blockers (F1 FD-1 gating, F2 PO-12 hash invalidation) are, on inspection, correct and material; the fix is a bounded correction pass on PO-10/PO-11 (not a redesign — the direction is sound), followed by an independent re-review before founder authorization. Per the assignment's stopping point, no documents were modified and no correction was performed here.

---

*End of PO-13 Independent Ratification Readiness Review. Verdict: FAIL — do not sign PO-10/PO-11 yet. Independent, fresh-context review; no documents modified; correction and re-review are the next step before founder authorization.*
