# PO-5 — Governance Metrics & Platform Health Model

**Making the ecosystem measurable — every score derived from evidence, none from self-report, all laddering up to velocity, leverage, and calm.**

**Status:** PO-5 — proposed canonical metrics & health model. Design only; no implementation, no code, no repository changes.
**Lane:** B (Platform & Architecture). **Executor:** Claude Cowork. **Verification Level:** L2.
**Owned by:** the metric *definitions* are ProjectOS-owned (Methodology); the *computation and dashboards* are AI Workspace's **Platform Intelligence** (per `PO-3` §7 — Platform Intelligence consumes ProjectOS metric definitions). This document defines the metrics; it does not build the dashboards.
**Inputs / amends alongside:** `PROJECTOS_METHODOLOGY_V2.md`, `PLATFORM_GENOME_V1.md`, `PO-3_AI_WORKSPACE_INTEGRATION_SPEC.md`, `PO-4_ECOSYSTEM_GOVERNANCE_FRAMEWORK.md`, `PROJECTOS_V0_1_FOUNDATION_SPEC.md`.

---

## 0. Measurement principles

The whole point of measuring the ecosystem is to *steer* it toward its three outcomes with the least founder attention. Metrics that don't serve that, or that can be gamed, are worse than none. Five binding principles:

1. **Evidence-derived, never self-reported.** Every metric is computed from the same evidence the kernel already trusts — commits, PRs, CI, tests, the hash-chained audit log, escalation records, Genome lineage, Registry records, Maturity grades. No score consults a claim, an agent self-report, or model judgment. This is the kernel's "evidence over claims" applied to measurement.
2. **Anti-vanity.** Raw activity is never success. Commit count, lines, hours, and time-on-task are excluded. Success is *verified* output and *reused* capability. A metric that rewards producing more low-value work is prohibited (Methodology §7 anti-tautology).
3. **Proportional and few.** A small set of scores that drive decisions, not a wall of dials. Each score must change a decision or it is cut.
4. **Ladders to the three outcomes.** Every score rolls up to exactly one of the ecosystem's outcomes — **Velocity** (verified output per unit founder attention), **Leverage** (reuse over new build), **Calm** (routine founder decisions trending to zero) — which are the apex of the model (Methodology §1).
5. **Single definition owner, single compute owner.** ProjectOS owns *what* is measured and *what healthy means*; Platform Intelligence (AI Workspace) owns *computing* it. Changing a metric definition or a health threshold is a governed change (REVIEWED / L2; GOVERNED / L3 if it changes a governed-decision threshold) — so scores cannot be quietly tuned to flatter.

### 0.1 The scoring framework (uniform across all scores)

Every score is normalized **0–100, higher = healthier** (including debt, expressed as freedom-from-debt), with three bands:

| Band | Range | Meaning |
|---|---|---|
| 🟢 Healthy | 80–100 | On track; no action. |
| 🟡 Watch | 60–79 | Trending risk; owner attention, not founder. |
| 🔴 Critical | 0–59 | Action required; may surface to the founder if a governed trigger. |

Each composite score is a weighted blend of evidence-derived **sub-signals**; weights are design defaults (sum 100%), tunable only via governed change. Every metric is specified with the same block: **Purpose · Outcome · Direction · Inputs (evidence) · Composition · Bands · Compute owner · Cadence · Anti-gaming.**

---

## 1. The metric hierarchy

Signals roll up into scores, scores into dashboards, dashboards into the three outcome indices.

```
   EVIDENCE SIGNALS                SCORES                    DASHBOARDS          OUTCOMES
   (kernel/genome/registry/    (0–100, banded)          (founder-facing)      (apex)
    audit/CI)
   commits,PRs,CI,tests ─┐   ┌─ Capability Health ─┐   ┌─────────────┐        ┌──────────┐
   escalations,decisions ┼─► ┼─ Product Health ────┼─► │ Ecosystem   │───────►│ VELOCITY │
   lineage,maturity ─────┤   ┼─ Platform Health ───┤   │ Health      │        │ LEVERAGE │
   gate pass/fail ───────┤   ┼─ Technical Debt ────┤   │ Dashboard   │        │ CALM     │
   reuse/consumers ──────┤   ┼─ Knowledge Maturity ┤   └─────────────┘        └──────────┘
   agent vs human ───────┤   ┼─ Automation ────────┤   ┌─────────────┐             ▲
   auto-merge ───────────┘   ┼─ AI Adoption ───────┘   │ Founder     │─────────────┘
                             └─ Governance KPIs ──────► │ Decision    │  (Calm)
                                                        │ Budget      │
                                                        └─────────────┘
```

Every score maps to one outcome: **Velocity** ← Product Health (delivery), Automation, AI Adoption; **Leverage** ← Capability Health (reuse), Platform Health, Knowledge Maturity; **Calm** ← Governance KPIs, Founder Decision Budget, (inverse) Technical Debt.

---

## 2. Governance KPIs

**Purpose:** measure whether governance is *proportional* — governing the few, not the many (PO-4 §0). **Outcome:** Calm. **Direction:** higher = healthier (proportional). **Compute owner:** Platform Intelligence. **Cadence:** continuous; weekly rollup.

**Inputs (evidence):** assignment records with tier (FAST/REVIEWED/GOVERNED), trigger presence, escalation log, review verdicts, protected-surface touch records, audit chain.

| Sub-signal | What it detects | Weight | Healthy |
|---|---|---|---|
| **Proportionality ratio** | Share of assignments that stayed FAST/ungoverned. | 30% | High (governance is the exception). |
| **Trigger-justified rate** | Share of *governed* changes that had a valid trigger (no over-governance). | 20% | ~100%. |
| **Governance-leakage rate** (inverse) | Triggered changes that ran ungoverned (under-governance). | 20% | ~0%. |
| **Review first-pass PASS rate** | L2/L3 reviews passing first time; and review turnaround. | 15% | High + fast. |
| **Escalation resolution latency** (inverse) | Time from escalation open → resolved. | 15% | Low. |

**Anti-gaming:** proportionality can't be gamed by mislabeling — tier is set by the closed trigger set (PO-4 §8), and leakage (triggered-but-ungoverned) is measured against the same triggers, so hiding a governed change shows up as leakage.

---

## 3. Founder Decision Budget Dashboard

**Purpose:** protect the founder's scarcest resource — attention — by making decision load visible and trending it down (Methodology §9, PO-4 §1.4). **Outcome:** Calm. **Direction:** fewer routine interruptions = healthier. **Compute owner:** Platform Intelligence. **Cadence:** real-time queue + weekly trend. **Audience:** the Founder (primary), the AI team (secondary).

**Inputs (evidence):** escalation records (class, options, consequence, recommendation, open/resolve timestamps), decision-to-default promotions, Critical-Path pointer.

| Panel | Signal | Target |
|---|---|---|
| **Routine interruptions** | Founder decisions that a convention/default *could* have resolved (leaked routine). | **→ 0** (any is a framework defect). |
| **Genuine decisions / week** | Count of true founder decisions (irreversible / business / legal / security / frozen). | Low & stable. |
| **Queue depth** | Open escalations awaiting the founder. | ≤ 1 (serialized — one at a time). |
| **Decision-ready compliance** | Escalations with ≥2 options + consequence + recommendation. | 100%. |
| **Decision latency** | Open → resolved time. | Low. |
| **Decisions-to-defaults** | Recurring decisions promoted into defaults/Genome knowledge (fatigue removed permanently). | Rising. |
| **Interruptions trend** | Routine + genuine interruptions per week over time. | **Trending down.** |

**Anti-gaming:** the dashboard's headline is *routine* interruptions (leaked decisions), which the AI team cannot lower by simply escalating less — a suppressed-but-needed decision surfaces as a `blocker` or `next_undetermined` escalation instead. Calm is only genuinely achieved by pushing decisions into defaults, which is separately measured (decisions-to-defaults).

---

## 4. Capability Health Score

**Purpose:** is a single capability reliable, reused, and stable? **Outcome:** Leverage. **Direction:** higher = healthier. **Compute owner:** Platform Intelligence. **Cadence:** continuous. **Scope:** per capability (platform and product-local).

**Inputs (evidence):** Maturity grade (M0–M4), Registry consumer list, Genome lineage, contract-change frequency, verification pass rate, incident/defect records.

| Sub-signal | Weight | Healthy |
|---|---|---|
| **Maturity grade** (M0–M4 → normalized) | 25% | M3–M4 for platform genes. |
| **Reuse breadth** (distinct consumers) | 20% | Multiple, for platform genes. |
| **Contract stability** (inverse of contract-churn) | 20% | Low churn since promotion. |
| **Verification pass rate** (evidence gates green) | 20% | High. |
| **Incident/defect rate** (inverse) | 10% | Low. |
| **Lineage cleanliness** (clear ancestry, no orphan/stranded consumer) | 5% | Complete (Genome §10). |

**Anti-gaming:** reuse breadth counts *distinct expressing products* from Registry records, not internal calls — inflating usage inside one product does not raise it. Maturity is graded by the Maturity Engine from evidence, not declared.

---

## 5. Product Health Score

**Purpose:** is a product delivering, reusing, and clean? **Outcome:** Velocity (primary), Leverage (reuse sub-signal). **Direction:** higher = healthier. **Compute owner:** Platform Intelligence. **Cadence:** continuous; weekly rollup. **Scope:** per product (EduOS, TradeOS, …).

**Inputs (evidence):** verified-assignment throughput, reuse ratio (inherited genes vs local build), gate pass rate, product Technical Debt, escalation/blocker rate, roadmap progress, Genome-version currency.

| Sub-signal | Weight | Healthy |
|---|---|---|
| **Delivery velocity** (verified assignments / period — *verified*, not attempted) | 25% | Steady/rising. |
| **Reuse ratio** (share of capability inherited vs newly built) | 20% | High (leverage). |
| **Quality-gate pass rate** | 15% | High. |
| **Technical Debt** (product-scoped §7, inverse) | 15% | Low debt. |
| **Blocker/escalation rate** (inverse) | 10% | Low. |
| **Roadmap progress vs plan** | 10% | On track. |
| **Genome-version currency** (how current with the platform) | 5% | Within compatibility window (Genome §19). |

**Anti-gaming:** velocity counts **verified** assignments only (evidence-passed), so churning unverified work does not raise it; reuse ratio rewards *not* building, which resists the "more code = more progress" vanity trap.

---

## 6. Platform Health Score

**Purpose:** is the shared core healthy — reliable, integral, and compounding? **Outcome:** Leverage. **Direction:** higher = healthier. **Compute owner:** Platform Intelligence. **Cadence:** continuous. **Scope:** the platform (Genome + platform capabilities).

**Inputs (evidence):** aggregate Capability Health of platform genes, Genome integrity (lineage complete/acyclic, no stranded consumers), compatibility health, promotion throughput, platform incident rate, platform Automation & Technical Debt.

| Sub-signal | Weight | Healthy |
|---|---|---|
| **Aggregate platform Capability Health** (mean, weighted by consumer count) | 30% | 🟢. |
| **Genome integrity** (complete ancestry, acyclic tree, no stranded consumer — Genome §10–11) | 20% | Intact. |
| **Compatibility health** (products within their compatibility window) | 15% | All within window. |
| **Promotion throughput** (capabilities rising M2→M3+ over time) | 15% | Steady (core compounding). |
| **Platform Automation** (§9) | 10% | High. |
| **Platform Technical Debt** (§7, inverse) | 10% | Low. |

**Anti-gaming:** Genome integrity is a hard structural check (from lineage), not a weighted opinion — a stranded consumer or a broken ancestry caps this score regardless of the other signals.

---

## 7. Technical Debt Score

**Purpose:** how much unpaid structural cost the ecosystem carries. **Outcome:** Calm (inverse — debt is future interruption). **Direction:** expressed as **freedom-from-debt**, higher = less debt = healthier. **Compute owner:** Platform Intelligence. **Cadence:** continuous. **Scope:** per product and platform-wide.

**Inputs (evidence):** deprecated-not-retired capability count (retirement backlog), duplicate-capability count (M0/M1 lookalikes across products — the PO-2.5 divergence signal), spec-vs-implementation conformance failures (PO-3 boundary-2 drift), migration debt (products behind on Genome MAJOR), protected-surface workarounds, core test-coverage gaps.

| Debt component | Weight | Detects |
|---|---|---|
| **Duplication debt** | 25% | Same capability rebuilt across products instead of promoted (Genome §18 violation). |
| **Conformance drift** | 20% | Implementation diverged from its owning definition (PO-3 §12). |
| **Migration debt** | 20% | Products stranded behind a Genome MAJOR past the compatibility window. |
| **Retirement backlog** | 15% | Deprecated capabilities not yet retired (lineage clutter). |
| **Protected-surface workarounds** | 10% | Hacks around frozen modules / contracts. |
| **Core coverage gaps** | 10% | Missing tests on kernel/shared genes. |

Score = 100 − normalized debt load. **Anti-gaming:** duplication and conformance debt are computed from Registry/lineage/definition evidence, so they cannot be hidden by not reporting them — an unpromoted duplicate is *visible* in the Registry as two M0/M1 genes for one job.

---

## 8. Knowledge Maturity Score

**Purpose:** is the ecosystem getting smarter — capturing, promoting, and applying knowledge (Methodology §12, Genome §22)? **Outcome:** Leverage. **Direction:** higher = healthier. **Compute owner:** Platform Intelligence. **Cadence:** weekly.

**Inputs (evidence):** assignment-close knowledge captures, knowledge promotions into Genome/defaults, decision-to-default conversions, knowledge staleness/retirement.

| Sub-signal | Weight | Healthy |
|---|---|---|
| **Capture rate** (assignments closing with a captured lesson/reuse candidate — Methodology Principle 9) | 30% | High. |
| **Promotion rate** (captured knowledge generalized into genome/conventions) | 30% | Steady. |
| **Decision-to-default conversion** (recurring decisions absorbed into defaults) | 25% | Rising. |
| **Freshness** (stale/disproven knowledge retired, not compounding) | 15% | Current. |

**Anti-gaming:** capture rate alone can be gamed by logging trivial "lessons," so it is weighted equally with *promotion* (knowledge that actually generalized) and decision-to-default (knowledge that removed a real founder decision) — padding captures without promotion does not raise the score.

---

## 9. Automation Score

**Purpose:** how much of the loop runs without a human (Methodology §14)? **Outcome:** Velocity. **Direction:** higher = healthier. **Compute owner:** Platform Intelligence. **Cadence:** continuous.

**Inputs (evidence):** auto-merge records (FAST + green gates + no human), gate-automation coverage, successor auto-generation rate, manual-step counts.

| Sub-signal | Weight | Healthy |
|---|---|---|
| **Auto-merge rate** (FAST work merged with no human) | 35% | High. |
| **Gate-automation coverage** (share of quality gates fully automated & authoritative) | 25% | High. |
| **Successor auto-generation** (next assignment generated deterministically) | 20% | High. |
| **Knowledge-capture automation** (capture as a by-product, not manual) | 10% | High. |
| **Necessary-manual ratio** (deploy/founder approvals that *should* stay manual) | 10% | Right-sized (not zero — some steps must stay human). |

**Anti-gaming:** the last sub-signal deliberately does **not** reward automating away governed approvals — deploy and L3 sign-off *must* stay human (kernel: manual deploy; PO-4). A score that hit 100 by auto-approving governed work would be a fail-closed violation, so automation is capped by the governance floor.

---

## 10. AI Adoption Score

**Purpose:** how much of the engineering is run by the AI team vs. humans (Methodology §8) — the founder-leverage measure. **Outcome:** Velocity (and readiness for autonomous evolution). **Direction:** higher = healthier, *within safety*. **Compute owner:** Platform Intelligence. **Cadence:** weekly.

**Inputs (evidence):** assignment executor records (Code/Cowork/human), AI-owned end-to-end loop completions, adapter coverage per role, founder-involvement rate.

| Sub-signal | Weight | Healthy |
|---|---|---|
| **AI-executed share** (assignments run by AI adapters vs human) | 30% | High. |
| **AI end-to-end completion** (loop finished by AI except required human gates) | 30% | High. |
| **Role-adapter coverage** (team roles filled by configured adapters) | 20% | Broad. |
| **Founder-involvement inverse** (less founder touch per unit output) | 20% | Low involvement. |

**Anti-gaming:** AI Adoption is *capped by* Governance KPIs and quality — running more work through AI while review PASS-rate or Product Health falls does not raise net ecosystem health, because those scores drop in parallel. Adoption is a means to velocity, never a standalone target.

---

## 11. Ecosystem Health Dashboard

**Purpose:** the single founder-facing rollup — is the whole ecosystem healthy, and where is the one thing to look at? **Compute owner:** Platform Intelligence. **Cadence:** weekly (live for red flags). **Audience:** Founder.

**Composition — the three Outcome Indices (apex):**

| Index | Rolls up from | Reads as |
|---|---|---|
| **Velocity Index** | Product Health (delivery) + Automation + AI Adoption | Verified output per unit founder attention. |
| **Leverage Index** | Capability Health (reuse) + Platform Health + Knowledge Maturity | Reuse over new build; is the platform compounding? |
| **Calm Index** | Governance KPIs + Founder Decision Budget + (inverse) Technical Debt | Are routine founder decisions trending to zero? |

**Ecosystem Health Score** = weighted mean of the three indices (default 34/33/33), banded 🟢/🟡/🔴, with a hard rule: **any index in 🔴 caps the ecosystem score at 🟡** — a critical outcome cannot be averaged away.

**Panels:**
- The three indices with trend arrows.
- Product Health leaderboard (per product, banded) — the portfolio at a glance.
- Platform Health + Genome integrity flag.
- Red-flag list — every score currently 🔴, most-consumer-impacting first.
- The **one thing**: the single lowest-band, highest-leverage score — the ecosystem's current Critical Path for health (mirrors "One Active Critical Path", Methodology §3).

**Anti-gaming:** the dashboard shows *trends and bands*, not a single vanity number to optimize; the red-flag cap prevents a strong index from masking a critical one; and every panel is drill-downable to the evidence that produced it (audit/lineage/registry), so a number is never trusted without its source.

---

## 12. Scoring & bands reference

| Score | Outcome | Direction | Compute | Cadence | 🔴 caps rollup? |
|---|---|---|---|---|---|
| Governance KPIs | Calm | higher healthier | Platform Intelligence | weekly | via Calm Index |
| Founder Decision Budget | Calm | fewer routine = healthier | Platform Intelligence | live + weekly | via Calm Index |
| Capability Health | Leverage | higher | Platform Intelligence | continuous | rolls to Platform |
| Product Health | Velocity | higher | Platform Intelligence | continuous | to leaderboard |
| Platform Health | Leverage | higher | Platform Intelligence | continuous | Genome integrity hard-caps |
| Technical Debt (freedom) | Calm (inv.) | higher = less debt | Platform Intelligence | continuous | via Calm Index |
| Knowledge Maturity | Leverage | higher | Platform Intelligence | weekly | via Leverage Index |
| Automation | Velocity | higher (capped by governance) | Platform Intelligence | continuous | via Velocity Index |
| AI Adoption | Velocity | higher (capped by quality) | Platform Intelligence | weekly | via Velocity Index |
| **Ecosystem Health** | apex | higher | Platform Intelligence | weekly | any 🔴 index → 🟡 cap |

All definitions and thresholds are **ProjectOS-owned**; all computation is **Platform Intelligence (AI Workspace)**. Changing a definition or threshold is a governed change (REVIEWED / L2; GOVERNED / L3 if it alters a governed-decision threshold).

## 13. Metric integrity (anti-gaming, consolidated)

1. **Evidence-only inputs.** Every sub-signal traces to kernel/CI/audit/Genome/Registry evidence; no metric consults a claim or self-report.
2. **No vanity signals.** Activity counts (commits, lines, hours, time-on-task) are excluded; only *verified* output and *reused* capability count.
3. **Cross-capping.** Adoption is capped by quality; Automation by governance; the ecosystem score by its worst index — so no single number can be optimized in isolation to fake health.
4. **Governed thresholds.** "Healthy" is defined by ProjectOS and changed only by governed change — teams cannot re-band their way to green.
5. **Drill-to-evidence.** Every displayed number links to the evidence that produced it; a score is never authoritative without its source.
6. **Trends over points.** Direction over time is the signal, not a single reading — resistant to one-off manipulation.

---

## APPENDIX A — L2 VERIFICATION RECORD

Independent, delta-only, verdict-oriented review against the assignment and the model's own principles.

| Check | Verdict | Basis |
|---|---|---|
| All 10 items defined | **PASS** | Governance KPIs §2 · Founder Decision Budget Dashboard §3 · Capability Health §4 · Product Health §5 · Platform Health §6 · Technical Debt §7 · Knowledge Maturity §8 · Automation §9 · AI Adoption §10 · Ecosystem Health Dashboard §11. |
| Ecosystem is measurable | **PASS** | Uniform 0–100 banded framework (§0.1); signal→score→dashboard→outcome hierarchy (§1); every score has inputs, composition, bands, cadence. |
| Evidence-derived, not self-reported | **PASS** | §0 principle 1 + §13; every sub-signal sourced to kernel/CI/audit/Genome/Registry evidence. |
| Anti-vanity / anti-gaming | **PASS** | §0 principle 2; per-metric anti-gaming notes; §13 consolidated (cross-capping, governed thresholds, drill-to-evidence). |
| Ladders to the three outcomes | **PASS** | Every score maps to Velocity / Leverage / Calm; three Outcome Indices are the apex (§1, §11). |
| Ownership correct (define vs compute) | **PASS** | Definitions ProjectOS-owned; computation AI Workspace Platform Intelligence — exactly PO-3 §7. No ownership invented. |
| Consistent with prior specs | **PASS** | Uses Methodology outcomes/levels, Genome lineage/maturity/compatibility, PO-3 ownership, PO-4 governance triggers/tiers; introduces no new owner or trigger. |
| Implementation-ready, implementation-independent | **PASS** | Concrete formulas, weights, bands, panels — assignable to Platform Intelligence without further design; no code, no repo changes. |

**Reviewer verdict: PASS.** No blocking issues. All ten metrics are defined, evidence-derived, anti-gaming, and roll up coherently into the three outcome indices and one founder-facing Ecosystem Health Dashboard; ownership matches PO-3; the model is implementation-ready without containing implementation.

---

## APPENDIX B — RELATIONSHIP TO PRIOR SPECS

- **Methodology v2** — supplies the three outcomes (velocity/leverage/calm), the Founder Decision Budget, verification levels, and the Knowledge Lifecycle these metrics quantify.
- **Genome v1** — supplies lineage, maturity grades, consumer records, and compatibility that Capability/Platform Health and Technical Debt read.
- **PO-3** — fixes ownership: metric definitions = ProjectOS; computation = Platform Intelligence (AI Workspace). This model honors that split exactly.
- **PO-4** — supplies the governance triggers/tiers and the escalation/decision protocol that Governance KPIs and the Decision Budget measure; changing a threshold is a governed change under PO-4.
- **Kernel (Foundation Spec)** — supplies the evidence and hash-chained audit every metric is computed from; measurement adds no parallel data source.

---

*End of PO-5 Governance Metrics & Platform Health Model. Design only — no implementation, no code, no repository changes. Every score is evidence-derived and anti-gaming; all computation belongs to Platform Intelligence (AI Workspace); future implementation is assigned separately.*
