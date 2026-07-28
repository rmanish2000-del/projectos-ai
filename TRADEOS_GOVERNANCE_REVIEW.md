# TradeOS ↔ ProjectOS Governance Review (Bounded)

**Read-only review. No changes made.** TradeOS governance compared against the ProjectOS governance corpus.
**Reviewer:** Claude Cowork, Lane B. **Deliverables:** conflicts · missing governance · missing workflows · missing evidence chain · reusable platform components.

---

## 0. Evidence basis & access limitation (read first)

This review is **bounded by access**. TradeOS's substance lives in `C:\TradeOS-AI`, which is **not connected** to this session — only its directory *names* are visible; file contents are hidden. A folder-access request for its governance directories was issued and timed out unanswered.

| Evidence | Access | Used as |
|---|---|---|
| `Projects/TradeOS-AI/project.yaml` (ProjectOS registration) | **Verified** (read) | Fact |
| `Shared/Packs/trading/*` (trading Domain Pack) | **Verified** (read/sized) | Fact |
| `.projectos/policies.yaml.txt` (trading risk triggers) | **Verified** (read earlier) | Fact |
| `C:\TradeOS-AI` directory structure (~40 top-level dirs) | **Visible (names only)** | Inference |
| `C:\TradeOS-AI` file contents (`.tradeos`, `decisions`, `journal`, `risk`, `orchestrator`, `docs`) | **NOT accessible** | Unverifiable |

**Every finding is labelled:** `[V]` verified from a read file · `[I]` inferred from repository structure (needs content verification) · `[U]` unverifiable without access. **No file contents were invented** (CLAUDE.md: never invent a platform fact).

**To complete this review** at content level, grant read access to `C:\TradeOS-AI` (`.tradeos`, `docs`, `decisions`, `journal`, `risk`, `orchestrator`) — see §6.

### What is verifiable now
- TradeOS registered in ProjectOS as `id: tradeos-ai`, **`workflow_mode: governed`**, `repository.path: C:/TradeOS-AI`, `adapter: local_git` `[V]`.
- Its code/governance is **outside** the ProjectOS workspace (external repo) `[V]`.
- The ProjectOS-side **trading Domain Pack is an empty scaffold** (`project_rules.yaml` 82 B ≈ `rules: []`; `quality_gates.yaml` 82 B ≈ `gates: []`; `assignment_rules.md` a stub) `[V]`.
- Trading-domain risk triggers (`kelly_methodology`, `edge_methodology`, `execution_cost_engine`, `risk_engine`, `statistical_validation`, …) sit in the **workspace-root** `.projectos/policies.yaml.txt`, **not** in the trading pack `[V]`.
- `C:\TradeOS-AI` contains a dedicated **`.tradeos/`** dir plus `decisions/`, `journal/`, `risk/`, `orchestrator/`, `loop/`, `regime/`, `signals/`, `strategies/`, `portfolio/`, `execution/`, `backtesting/`, `replay/`, `research/`, `learning/`, `ai_layer/`, `deploy/`, `docs/`, `SensexPilot/`, … `[I]`.

---

## 1. Conflicts (TradeOS governance vs ProjectOS governance)

| # | Conflict | Basis | Impact |
|---|---|---|---|
| **CF-1** | **Two parallel governance roots.** TradeOS has its own `.tradeos/` governance/state directory — a system parallel to ProjectOS's `.projectos/` kernel. Whether `.tradeos` *is* a `.projectos` instance or a **separate governance system** is unverifiable, but its existence signals divergence. | `.tradeos/` exists `[I]`; ProjectOS kernel owns `.projectos/` `[V]` | Same divergence class PO-2.5 found for EduOS (D-1/C-2): a product running its own operating model instead of inheriting the platform's. If `.tradeos` ≠ `.projectos`, TradeOS is **not governed by the ProjectOS kernel**. |
| **CF-2** | **Code/governance outside the workspace.** TradeOS's real governance lives at `C:\TradeOS-AI` (external); the ProjectOS registration is a stub. | `project.yaml repository.path: C:/TradeOS-AI` `[V]` | The docs-in-workspace / code-outside pattern PO-2.5 flagged (C-4). ProjectOS cannot verify TradeOS governance from its own repo — governance-by-registration only. |
| **CF-3** | **Domain triggers misplaced (neutrality violation).** Trading risk triggers are at the ProjectOS workspace root, not in the trading Domain Pack (which is empty). | `.projectos/policies.yaml.txt` trading triggers `[V]`; trading pack empty `[V]` | PO-2.5 O-2 / PO-4 §6.6: domain vocabulary in the neutral core. Trading governance is split between root policies and (presumably) `.tradeos`, in neither of the two places ProjectOS expects (the pack, or an inherited kernel). |
| **CF-4** | **Continuous loop vs one-active-assignment.** TradeOS structure implies an always-on orchestration/execution loop; ProjectOS's kernel enforces **one active, discrete, evidence-gated assignment** (INV-1). | `orchestrator/`, `loop/`, `execution/`, `signals/` `[I]`; kernel INV-1 `[V]` | Genuine model tension: real-time trading is event-driven/continuous; the ProjectOS assignment lifecycle is discrete. Without a reconciling adapter, the two governance models conflict at the execution layer. |
| **CF-5** | **Governed-mode without verifiable gates.** TradeOS is registered `workflow_mode: governed` (the strictest ProjectOS mode: full suite + independent review + founder sign-off), yet the trading pack defines **no** quality gates and the gate definitions are external/unverifiable. | `workflow_mode: governed` `[V]`; empty pack `[V]` | A GOVERNED declaration with no registered gates is unenforceable from the ProjectOS side — the mode is asserted, not evidenced. |

---

## 2. Missing governance

| # | Missing | Basis | Note |
|---|---|---|---|
| **MG-1** | **Domain governance in the pack.** The trading Domain Pack carries no rules, gates, triggers, or templates. From ProjectOS's view TradeOS has *no* registered domain governance. | trading pack empty `[V]` | Per Genome §8 / PO-4, trading rules belong in Domain DNA (the pack). They are absent here (and misplaced at root, CF-3). |
| **MG-2** | **Platform inheritance.** No evidence TradeOS inherits the ProjectOS genome (Constitution, Methodology, verification levels L0–L3, escalation triggers, single-source ownership). It appears to run its own governance. | ratification not executed `[V]`; `.tradeos` bespoke `[I/U]` | TradeOS is a product that has **not** inherited the platform genome — the anti-fork principle (Genome §11) is not yet applied to it. |
| **MG-3** | **Verification-level mapping.** Whether TradeOS maps its work to ProjectOS L0–L3 verification (or has any equivalent proof-depth ladder) is unverifiable. | `[U]` | Trading (real money) demands ≥L3 on risk/execution paths; unclear if a comparable gate exists. |
| **MG-4** | **Single ownership / single-active-assignment.** Whether TradeOS enforces one-owner-per-capability (PO-3) and one-active-assignment (INV-1) is unverifiable; its multi-engine structure (`signals`/`execution`/`risk`/`portfolio`) suggests concurrent flows. | `[I/U]` | Concurrency is fine if lanes are modelled (Methodology §4), but needs verification that ownership/active-slot discipline holds. |
| **MG-5** | **Kill-switch / live-trading governance.** No verifiable governed control for halting live trading on risk-limit breach or model failure. | `[U]` | The single highest-stakes governance control for a trading platform; must exist and be GOVERNED. |

---

## 3. Missing workflows

| # | Missing workflow | Basis | Note |
|---|---|---|---|
| **MW-1** | **Continuous/event-driven workflow adapter.** ProjectOS models discrete assignments; trading needs signal→decision→risk-check→execution as a continuous loop. No adapter reconciling the two is registered. | kernel discrete `[V]`; `loop/`,`orchestrator/` `[I]` | This is the central workflow gap (see CF-4). Needed for TradeOS to run under ProjectOS governance without abandoning the assignment model. |
| **MW-2** | **Pre-live validation gate.** `backtesting/` + `replay/` imply a validation harness, but it is not expressed as a ProjectOS governed workflow (no-strategy-goes-live-without-passing-backtest-evidence). | `backtesting/`,`replay/` `[I]` | A natural GOVERNED gate: evidence-before-live. Not verified as a workflow. |
| **MW-3** | **Risk-breach escalation.** A workflow that escalates a risk-limit breach to a founder decision / kill-switch, mapped to ProjectOS escalation triggers, is not verifiable. | `risk/`,`alerts/` `[I]`; kernel escalation `[V]` | Maps to `security_risk`/`founder_decision` escalation; needs to exist and be governed. |
| **MW-4** | **Deploy governance for live trading.** `deploy/` exists, but a GOVERNED deploy workflow (manual approval, kill-switch, rollback) for money-moving releases is unverifiable. | `deploy/` `[I]`; kernel manual-deploy `[V]` | Trading deploys are the highest-risk deploys; ProjectOS requires manual/governed deploy — verify TradeOS matches. |
| **MW-5** | **Regime-change handling.** `regime/` implies market-regime detection; whether a governed workflow adapts risk/strategy on regime change is unverifiable. | `regime/` `[I]` | Domain-specific but governance-relevant (risk posture changes). |

---

## 4. Missing evidence chain

| # | Evidence-chain gap | Basis | Note |
|---|---|---|---|
| **EC-1** | **Parallel, possibly un-anchored trail.** TradeOS has `decisions/` + `journal/` — its own decision/evidence trail, parallel to ProjectOS's Decision Registry (PO-7) + hash-chained audit (kernel §8). Whether it is **append-only, hash-chained, tamper-evident** is unverifiable. | `decisions/`,`journal/` `[I]`; kernel audit `[V]` | If not hash-anchored, TradeOS's evidence is weaker than ProjectOS's fail-closed, tamper-evident standard. |
| **EC-2** | **Trade-level provenance chain.** Trading needs an immutable chain: signal → decision rationale → risk check → execution → fill → P&L attribution, timestamped and verifiable (audit/regulatory). Whether TradeOS's journal provides this end-to-end is unverifiable. | `[U]` | This is the domain's most important evidence requirement; ProjectOS's generic audit doesn't model it natively (candidate reusable component, RC-4). |
| **EC-3** | **Disjoint chains.** No verifiable bridge links TradeOS's decisions/journal to the ProjectOS audit chain — the two evidence systems are likely separate. | two roots `[I]` | ProjectOS cannot currently verify TradeOS completion by evidence (evidence-over-claims fails across the boundary). |
| **EC-4** | **Evidence-gated verification.** Whether TradeOS closes work only on evidence (not agent claims) — the ProjectOS core principle — is unverifiable. | `[U]` | Central to trust; must be confirmed. |

---

## 5. Reusable platform components (TradeOS → ProjectOS genome candidates)

Components in TradeOS that, if mature, are **promotion candidates** into the platform genome (Genome §13) — or, conversely, where TradeOS should inherit the platform's version. All `[I]`; maturity unverifiable pending access.

| # | Component | Reuse direction | Rationale |
|---|---|---|---|
| **RC-1** | **Risk-governance engine** (`risk/`) | TradeOS → platform capability | Risk-limit governance, breach escalation, and posture control are reusable across any risk-bearing domain (trading, solar/UrjaOps, ops). Strong platform-capability candidate; maps to ProjectOS GOVERNED triggers. |
| **RC-2** | **Continuous-execution workflow adapter** (`orchestrator/`,`loop/`) | TradeOS → platform (fills a gap) | ProjectOS lacks a continuous/event-driven workflow model (CF-4/MW-1). A generalized adapter would let the platform govern real-time work, not just discrete assignments — high-value gap-filler. |
| **RC-3** | **Backtest/replay validation harness** (`backtesting/`,`replay/`) | TradeOS → platform pattern | "Evidence-before-live" validation generalizes to any product needing pre-production proof gates (a reusable evidence-generation workflow). |
| **RC-4** | **Provenance/decision journal** (`decisions/`,`journal/`) | Reconcile with platform | Either promote TradeOS's trade-provenance chain as a specialization of the platform Decision/Event/Knowledge registries (PO-7), or have TradeOS inherit the platform's hash-chained audit. The stronger of the two should win (Maturity Engine decides). |
| **RC-5** | **Regime/AI signal layer** (`regime/`,`ai_layer/`,`signals/`) | Likely Domain DNA (not platform) | Trading-specific; belongs in the trading Domain Pack, not the neutral core. Flags CF-3's fix: this is where domain governance should live. |
| **RC-6** | **`.tradeos` governance model** | Reconcile with `.projectos` | If `.tradeos` is a mature governance system, it is the clearest case for the Maturity Engine / Genome to reconcile two governance kernels into one (promote the better, deprecate the other) — the anti-fork resolution. |

---

## 6. To complete this review (content-level)

This bounded review is grounded in verifiable ProjectOS-side facts plus the TradeOS repository structure. To verify the `[I]`/`[U]` findings at content level — is `.tradeos` a ProjectOS instance or a separate system? is the journal hash-chained? are the gates real? — **grant read access to `C:\TradeOS-AI`** (`.tradeos`, `docs`, `decisions`, `journal`, `risk`, `orchestrator`) and I will complete the content pass. Alternatively, connect that folder to the session.

**Highest-value things to confirm first:** (1) is TradeOS governed by `.projectos`/the ProjectOS kernel, or a separate `.tradeos` system (CF-1)? (2) is the trade evidence chain hash-anchored and tamper-evident (EC-1/EC-2)? (3) does a live-trading kill-switch exist and is it governed (MG-5/MW-4)?

---

*End of bounded TradeOS ↔ ProjectOS governance review. Read-only; no changes made. Findings are labelled Verified / Inferred-from-structure / Unverifiable; no file contents were invented. Content-level completion requires access to `C:\TradeOS-AI`.*
