# Workspace registry — verified project registrations

A record of which real repositories are registered in the ProjectOS workspace, what was
verified about them, and how they relate. Every entry here is **repository evidence**,
gathered read-only; nothing in this file is inferred from intent or from a handoff
document.

Workspace state itself (`Workspace.yaml`, `Projects/<name>/project.yaml`) is local,
machine-specific, and deliberately **not tracked** — this document is the tracked record
of what was registered and why.

---

## TradeOS AI

| Field | Verified value |
|---|---|
| canonical local path | `C:\TradeOS-AI` |
| GitHub remote | `https://github.com/rmanish2000-del/tradeos-ai.git` |
| current branch | `main` |
| latest commit | `ac0c2f2` (2026-07-24) — *Merge pull request #28 from `feat/wp1-outcome-dataset`* |
| commit depth | 133 |
| clean / dirty | **dirty** — 8 uncommitted entries at audit time (all untracked; no tracked file modified) |
| `HANDOFF.md` | **absent** |
| `PROJECT_STATE.md` | **absent** — but `.tradeos/PROJECT_STATE.yaml` is present (untracked) |

### Registered as

| Resolution field | Value |
|---|---|
| project ID | `tradeos-ai` |
| project name | `TradeOS-AI` |
| repository path | `C:\TradeOS-AI` |
| selected packs | `rapid-build` |
| workflow mode | `governed` |
| active branch | `main` |
| `.projectos` location | *not initialised* — see [Kernel initialisation](#kernel-initialisation) |

`workflow_mode: governed` is chosen from repository evidence, not preference: the project
runs explicit founder gates (`.tradeos/FOUNDER_DECISIONS.md`, `DECISION_LOG.yaml`,
`QUALITY_GATES.md`) and its own rule that a tier-2 review "never auto" merges.

### Current milestone and active work

Two sources disagree, and `PROJECT_STATE.yaml` states its own tie-breaker — *"If this
file and git disagree, git wins and this file gets corrected."* So git governs:

* **`.tradeos/PROJECT_STATE.yaml`** (last updated ~2026-07-21) reports
  `current_milestone: WP-0`, `current_assignment: g0-closure`, status `READY_TO_MERGE`,
  awaiting a founder merge of PR #19.
* **Git evidence (authoritative)** shows that gate has since closed and work advanced:
  PR #19 merged (`261ebc1`), then PR #28 merged (`ac0c2f2`, 2026-07-24) delivering
  *WP-1.1 Outcome Dataset Builder*.

**Verified current state: milestone WP-1, with WP-1.1 landed on `main`.**
`.tradeos/PROJECT_STATE.yaml` is stale by its own rule and is the project's to correct —
ProjectOS does not write to it.

Stated goal (from `.tradeos/PROJECT_STATE.yaml`): *Phase 2A — certified
Outcome→Calibration pipeline for SENSEX intraday options, calibrated probability display
only, per frozen governance.*

---

## SensexPilot — a component, not a repository

**SensexPilot is not an independent repository. It is a component inside the TradeOS AI
repository**, established from evidence:

| Evidence | Finding |
|---|---|
| `C:\TradeOS-AI\SensexPilot\` | present — product and planning documents |
| `C:\TradeOS-AI\src\sensexpilot\` | present — the Python package (`__init__.py`, `engine.py`, `api/`, `ingest/`, `factors/`, …) |
| nested `.git` | **none** — neither path is its own repository |
| tracked by the TradeOS repo | **351 files** across both paths |
| packaging | `src/sensexpilot_console.egg-info` — packaged from within the same repository |
| `.tradeos/PROJECT_STATE.yaml` | names the project `SensexPilot (TradeOS AI)` |

Consequently **SensexPilot is deliberately not registered as a second ProjectOS project**.
Registering it separately would require inventing a repository path that does not exist,
which this audit explicitly refuses to do. It is operated through the `tradeos-ai`
registration.

### Other candidates examined and rejected

| Path | Finding |
|---|---|
| `C:\Projects\TradeOS-AI` | a **stale clone** of the same remote — 13 commits, last 2026-07-08, no `SensexPilot/`. Superseded by `C:\TradeOS-AI` (133 commits). Not registered. |
| `C:\Sensex Options TradeOS-AI` | **not a git repository** — a research/governance document folder (`backlog/`, `sprints/`, `strategies/`, `transcripts/`). Not a code repository; not registered. |
| `C:\dev\tradeos-data` | data directory, not a repository. Not registered. |

---

## Kernel initialisation

The ProjectOS kernel (`.projectos/`) has **not** been initialised inside
`C:\TradeOS-AI`. Registration writes only into the workspace and touches nothing in the
product repository.

This is a deliberate hold, not an oversight. `workspace init-project` would create a
second assignment/state system inside a repository that already runs its own live
orchestrator (`.tradeos/` — `PROJECT_STATE.yaml`, `MILESTONES.yaml`, `TASK_QUEUE.yaml`,
`DECISION_LOG.yaml`, `tao.py`), while that repository is mid-milestone and carries
uncommitted work. Whether ProjectOS should take over, mirror, or coexist with TAO is a
founder decision with governance consequences — not one to make as a side effect of an
audit.

Until that decision is recorded, `tradeos-ai` resolves six of the seven fields against
the live repository; `.projectos` location resolves once the kernel is initialised.
