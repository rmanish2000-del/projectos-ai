# PROJECTOS AI — v0.1 FOUNDATION SPECIFICATION

| Field | Value |
|---|---|
| Document | PROJECTOS_V0_1_FOUNDATION_SPEC.md |
| Version | 0.1.0-draft.1 |
| Status | Architecture specification — no implementation |
| Date | 2026-07-20 |
| Author role | Chief Architect / Product Owner (Claude Cowork) |
| Scope authority | This document is the single source of truth for ProjectOS AI v0.1 architecture. Repository evidence overrides conversation memory. |

---

## 1. Product Boundary

### 1.1 What ProjectOS AI v0.1 IS

ProjectOS AI is a **repository-driven orchestration kernel** that manages the lifecycle of AI-and-human project work as a sequence of verified assignments. It answers exactly four questions at all times:

1. **What is the one active assignment right now?**
2. **Who owns it, and which agent executes it?**
3. **Is it verifiably complete, according to repository evidence?**
4. **What is the next assignment, or what founder decision blocks it?**

v0.1 manages **one project, one repository, one active assignment**, with automatic next-assignment generation after verified completion.

### 1.2 What ProjectOS AI is NOT

- **Not an executor.** It never writes code, drafts legal filings, or performs domain work. Executors (Claude Code, Claude Cowork, ChatGPT, humans) do the work; ProjectOS routes, tracks, and verifies.
- **Not a CI/CD system.** It reads CI results as evidence; it never runs builds or deploys. Merge and deployment are always manual human approvals in v0.1.
- **Not a project-management SaaS.** No web UI, no notifications platform, no multi-tenant service in v0.1. The repository is the database; the CLI is the interface.
- **Not domain-aware.** The kernel contains zero software/legal/energy/agriculture logic. All domain rules live in project packs.
- **Not a chat memory.** Conversation claims are never state. Only repository-committed state and verified evidence are authoritative.

### 1.3 Business rationale

The founder runs many concurrent ventures (TradeOS AI, SensexPilot, UrjaOps, PM-KUSUM Ops, Legal Engineering, Foodgod FPO, drone operations). Each currently depends on conversational continuity with AI agents, which is unreliable and unauditable. ProjectOS converts that into a deterministic, auditable, repository-backed operating system, so any agent (or any future agent) can pick up exactly where the last one stopped, and the founder's attention is spent only on genuine decisions. The platform is the reusable asset; every project pack multiplies its value.

---

## 2. System Architecture and Ownership Boundaries

### 2.1 Component map

```
┌─────────────────────────────────────────────────────────────────┐
│  USER INTERFACE (v0.1: CLI only)                                │
│  projectos <command>  — thin; no business logic                 │
└───────────────┬─────────────────────────────────────────────────┘
                │ calls
┌───────────────▼─────────────────────────────────────────────────┐
│  PROJECTOS CORE (orchestration kernel — domain-neutral)         │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────────────┐  │
│  │ Assignment     │ │ State Machine  │ │ Evidence Verifier    │  │
│  │ Lifecycle Mgr  │ │ Engine         │ │ (rule evaluator)     │  │
│  └───────────────┘ └────────────────┘ └──────────────────────┘  │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────────────┐  │
│  │ Risk/Workflow  │ │ Escalation     │ │ Audit Log            │  │
│  │ Classifier     │ │ Manager        │ │ (append-only)        │  │
│  └───────────────┘ └────────────────┘ └──────────────────────┘  │
│  ┌───────────────┐ ┌────────────────┐                           │
│  │ Pack Loader    │ │ Adapter        │                           │
│  │ (validation)   │ │ Registry       │                           │
│  └───────────────┘ └────────────────┘                           │
└───────┬───────────────────┬─────────────────────────┬───────────┘
        │ Pack Interface    │ Agent Adapter Interface │ Repo Adapter Interface
┌───────▼────────┐  ┌───────▼────────────┐  ┌─────────▼───────────┐
│ PROJECT PACKS  │  │ AGENT ADAPTERS     │  │ REPOSITORY ADAPTERS │
│ (declarative   │  │ cowork | code |    │  │ github | local-git  │
│  domain rules) │  │ human  | (future:  │  │                     │
│                │  │ chatgpt, custom)   │  │                     │
└────────────────┘  └────────────────────┘  └─────────┬───────────┘
                                                      │
                                            ┌─────────▼───────────┐
                                            │ PROJECT STATE +     │
                                            │ EVIDENCE            │
                                            │ (in the repository) │
                                            └─────────────────────┘
```

### 2.2 Ownership boundaries (explicit separation)

| Layer | Owns | Must never contain | Changed by |
|---|---|---|---|
| **ProjectOS Core** | State machine, schemas, verification rules engine, escalation logic, audit log format, adapter/pack contracts | Domain logic, agent-specific prompts, GitHub API calls, project state | Governed workflow only (frozen architecture) |
| **Agent adapters** | Translation between kernel assignments and a specific agent's input/output format (assignment briefing generation, completion-report ingestion) | State transitions, verification decisions, domain rules | Reviewed workflow |
| **Repository adapters** | Reading/writing repo facts (commits, PRs, CI status, files) through one narrow interface | Verification *decisions* (they report facts; the kernel decides), state machine logic | Reviewed workflow |
| **Project packs** | Domain vocabulary, risk-classification overrides, assignment templates, acceptance-criteria templates, escalation triggers specific to the domain | Executable code (v0.1 packs are declarative YAML only), kernel modifications | Fast workflow (pack authoring), Governed if pack touches legal/risk rules |
| **Project state** | Manifest, assignment records, state-machine snapshots, escalation records, audit log — all files in the repository under `.projectos/` | Secrets, credentials, generated work products | Kernel only (humans/agents never hand-edit; hand edits are detectable via audit hash chain) |
| **Evidence** | Immutable references to commits, PRs, CI runs, artifacts, approval records | Copies of large artifacts (references only), unverifiable claims | Produced by executors; recorded by kernel; never mutated |
| **User interface** | Command parsing, output formatting | Any logic; every UI action maps 1:1 to a kernel operation | Fast workflow |

**Boundary rule:** dependencies point inward only. UI → Core ← Adapters/Packs. Core imports nothing from adapters, packs, or UI. Adapters never import each other. Packs are data, not code.

### 2.3 Repository layout owned by ProjectOS

```
<project-repo>/
  .projectos/
    manifest.yaml            # project manifest (§3)
    packs/<pack-name>/       # installed project pack(s) (declarative)
    assignments/
      A-0001.yaml            # one file per assignment (schema §4)
      A-0002.yaml
    active.yaml              # pointer: the single active assignment + state snapshot
    escalations/
      E-0001.yaml            # founder-decision records (§9)
    audit/
      2026-07.ndjson         # append-only audit log, monthly files (§8.5)
  <normal project content>   # untouched by ProjectOS
```

Everything ProjectOS knows lives in `.projectos/`. Deleting that directory removes ProjectOS from a repo with zero residue — this is the portability guarantee.

---

## 3. Domain-Neutral Orchestration Kernel

### 3.1 Kernel responsibilities (complete list)

1. Load and validate the project manifest and installed pack(s).
2. Maintain the assignment registry and the **single-active-assignment invariant**.
3. Execute the task state machine (§5) — all transitions deterministic, auditable, fail-closed.
4. Classify each assignment into a workflow mode (§7) using kernel defaults + pack overrides.
5. Route the active assignment to the correct agent adapter (Cowork / Code / human).
6. Verify completion claims against repository evidence via the repository adapter (§8).
7. Generate the next assignment after verified completion (§3.3).
8. Manage founder escalations and block/unblock deterministically (§9).
9. Append every state-affecting event to the audit log with a hash chain.

### 3.2 Kernel invariants (enforced, fail-closed)

- **INV-1** At most one assignment is in an active state (`ACTIVE`, `EVIDENCE_SUBMITTED`, `VERIFYING`) at any time.
- **INV-2** Every assignment has exactly one owner (a human identity) and exactly one executor agent.
- **INV-3** No transition to `VERIFIED` without every acceptance criterion mapped to at least one passing evidence check.
- **INV-4** Any verification error, adapter failure, or ambiguous evidence result blocks the transition (fail closed) and surfaces a typed error; it never defaults to success.
- **INV-5** Audit log is append-only; each entry contains the SHA-256 of the previous entry (tamper-evident chain).
- **INV-6** Kernel state changes occur only through kernel operations; the kernel refuses to operate if state files fail schema validation or the audit chain is broken (→ `ESCALATED` to founder).
- **INV-7** No parallel workstreams: next-assignment generation produces exactly one `READY` assignment.

### 3.3 Automatic next-assignment generation

After an assignment reaches `CLOSED`:

1. Kernel evaluates the assignment's declared `next` block (explicit successor), else
2. Evaluates the pack's assignment-template pipeline for the project phase, else
3. Emits a `NEXT_UNDETERMINED` escalation to the founder.

Generation is deterministic: same state + same pack ⇒ same next assignment. The generated assignment enters `DRAFT`, is auto-classified (§7), and moves to `READY` only if its dependencies (§4, `depends_on`) are all `CLOSED` and no escalation blocks it.

---

## 4. Agent-Role Model

### 4.1 Roles (kernel-level, domain-neutral)

| Role | Cardinality per assignment | Description | v0.1 binding |
|---|---|---|---|
| **Founder** | 1 per project | Ultimate decision authority. Resolves escalations, approves governed work, approves merge/deploy. | Manish (from manifest) |
| **Owner** | exactly 1 per assignment | Human accountable for the assignment outcome. May be the founder. | Founder by default |
| **Executor** | exactly 1 per assignment | The agent that performs the work: `cowork`, `code`, or `human` (v0.1); `chatgpt`, custom (future) | Via agent adapter |
| **Reviewer** | 0 (fast) / 1 (reviewed, governed) | Independent checker. Must not be the executor of the same assignment. May be a human or a different agent instance. | Human or second agent session |
| **Verifier** | always the kernel | Mechanically checks evidence against acceptance criteria. Not a person or an LLM judgment. | Kernel + repo adapter |

### 4.2 Routing rules (Cowork/Code routing)

Executor selection is declared per assignment and validated by the kernel against the assignment's `work_type`:

| `work_type` | Default executor | Rationale |
|---|---|---|
| `architecture`, `specification`, `research`, `analysis`, `document` | `cowork` | Document/decision work; no code changes permitted (kernel rejects code-touching evidence from these types) |
| `implementation`, `refactor`, `test`, `fix` | `code` | Repository code changes; evidence must include commits/PR |
| `approval`, `deployment`, `merge`, `external_action` | `human` | Actions ProjectOS must never automate in v0.1 |

A pack may narrow but never broaden these defaults (e.g., a legal pack may force `document` work to `human` review).

### 4.3 Agent adapter contract (summary; full interface §11 pattern)

Every agent adapter implements exactly:

- `brief(assignment) -> AssignmentBriefing` — renders the assignment (objective, constraints, acceptance criteria, stopping point) in the target agent's input format. The briefing always embeds: "one active assignment, stop at the stopping point, report evidence references, do not self-verify."
- `ingest(report) -> CompletionClaim` — parses the agent's completion report into structured claims + evidence references. **A claim is never evidence.** Ingestion only stages claims for kernel verification.

Adapters are stateless. They hold no history and make no transitions.

---

## 5. Project Manifest Schema

`.projectos/manifest.yaml` — one per repository. Kernel refuses to run without a valid manifest.

```yaml
# manifest.yaml — schema version 1
schema_version: 1
project:
  id: projectos-ai            # kebab-case, immutable
  name: "ProjectOS AI"
  description: "Reusable AI-project orchestration platform"
  founder:
    name: "Manish"
    id: rmanish2000@gmail.com # identity used for approvals
owners:                       # humans who may own assignments
  - id: rmanish2000@gmail.com
    name: "Manish"
packs:                        # installed project packs (order = precedence, last wins on overrides)
  - name: software-core
    version: ">=0.1.0 <0.2.0"
repository:
  adapter: github             # github | local-git
  config:
    remote: origin
    default_branch: main
    github:
      owner: <org>
      repo: <repo>
      # token supplied via environment/keychain — NEVER in this file (§14)
agents:                       # enabled agent adapters
  - type: cowork
  - type: code
  - type: human
workflow:
  default_mode: fast          # fast | reviewed | governed
  governed_triggers:          # kernel-level triggers; packs may ADD, never remove
    - frozen_architecture
    - research_mathematics
    - risk_model
    - legal_filing
    - security_boundary
    - breaking_contract
approvals:
  merge: manual               # v0.1: must be "manual"
  deploy: manual              # v0.1: must be "manual"
audit:
  hash_algorithm: sha256
```

**Validation rules (fail closed):** unknown fields rejected; `approvals.merge`/`deploy` must equal `manual` in schema v1; at least one owner; founder must be in owners; every pack resolvable and schema-valid.

---

## 6. Assignment Schema

`.projectos/assignments/A-NNNN.yaml` — immutable identity, mutable state section only via kernel.

```yaml
# assignment schema version 1
schema_version: 1
id: A-0001                     # monotonically increasing, kernel-issued
title: "Design ProjectOS v0.1 foundation"
work_type: architecture        # §4.2 vocabulary
objective: >
  One-paragraph outcome statement. What done means in business terms.
context_refs:                  # repository paths / URLs the executor must read
  - path: docs/vision.md
owner: rmanish2000@gmail.com   # exactly one (INV-2)
executor: cowork               # cowork | code | human
workflow_mode: reviewed        # fast | reviewed | governed (kernel-classified; §7)
risk_flags: []                 # e.g. [security_boundary] — drive classification
depends_on: []                 # assignment IDs; all must be CLOSED before READY
stopping_point: >
  Explicit statement of where the executor must stop.
acceptance_criteria:           # every criterion MUST carry a verification rule
  - id: AC-1
    statement: "Spec document exists at PROJECTOS_V0_1_FOUNDATION_SPEC.md"
    verify:
      type: file_exists        # §8.2 evidence-rule vocabulary
      path: PROJECTOS_V0_1_FOUNDATION_SPEC.md
  - id: AC-2
    statement: "Spec committed to main via PR with founder approval"
    verify:
      type: pr_merged
      approvals_required: 1
      approver_role: founder
evidence_required:             # minimum evidence classes (§8.1)
  - commit
  - approval
next:                          # optional deterministic successor (§3.3)
  template: implement-kernel-skeleton   # pack template name
state:                         # KERNEL-MANAGED — never hand-edited
  status: ready                # §7 state machine states
  history: []                  # transition records (who/when/event/audit_ref)
```

**Immutability rule:** after an assignment leaves `DRAFT`, only `state` may change. Changing scope requires cancelling (`CANCELLED`) and issuing a new assignment — this keeps the audit trail honest.

---

## 7. Task State Machine and Workflow-Risk Classification

### 7.1 States

| State | Meaning |
|---|---|
| `DRAFT` | Created (manually or auto-generated); editable; not classified-final |
| `READY` | Classified, dependencies CLOSED, no blocking escalation; eligible to become active |
| `ACTIVE` | The one assignment being executed (INV-1) |
| `EVIDENCE_SUBMITTED` | Executor's completion claim + evidence references ingested |
| `VERIFYING` | Kernel evaluating evidence rules against repository facts |
| `VERIFIED` | All acceptance criteria pass; awaiting required human approvals (review/governance/merge) |
| `CLOSED` | Approvals complete; triggers next-assignment generation |
| `REJECTED` | Verification or review failed; returns to `ACTIVE` with recorded reasons |
| `BLOCKED` | Dependency regression or external blocker; not executable |
| `ESCALATED` | Awaiting founder decision; nothing proceeds on this assignment |
| `CANCELLED` | Terminal; superseded or withdrawn; reason recorded |

### 7.2 Transition table (exhaustive — anything not listed is illegal and fails closed)

| From | Event | To | Actor allowed |
|---|---|---|---|
| DRAFT | `classify_ok` (deps CLOSED, no block) | READY | kernel |
| DRAFT | `cancel` | CANCELLED | owner/founder |
| READY | `start` | ACTIVE | kernel (CLI `start`), only if no other active assignment |
| READY | `block` / `escalate` | BLOCKED / ESCALATED | kernel |
| ACTIVE | `submit` (claim ingested) | EVIDENCE_SUBMITTED | executor via adapter |
| ACTIVE | `escalate` | ESCALATED | executor/owner/kernel |
| ACTIVE | `cancel` | CANCELLED | founder only |
| EVIDENCE_SUBMITTED | `verify_start` | VERIFYING | kernel (automatic) |
| VERIFYING | `all_criteria_pass` | VERIFIED | kernel only |
| VERIFYING | `any_criterion_fail` / `verifier_error` | REJECTED | kernel only (fail closed) |
| VERIFIED | `approvals_complete` | CLOSED | required approvers (per workflow mode) |
| VERIFIED | `review_reject` | REJECTED | reviewer/founder |
| REJECTED | `resume` | ACTIVE | kernel (with rejection reasons attached to briefing) |
| BLOCKED | `unblock` (deps restored) | READY | kernel |
| ESCALATED | `founder_resolve(proceed)` | prior state | founder |
| ESCALATED | `founder_resolve(cancel)` | CANCELLED | founder |
| ESCALATED | `founder_resolve(rescope)` | CANCELLED + new DRAFT issued | founder |

Every transition writes an audit entry: `{event, from, to, actor, timestamp, assignment_id, evidence_refs?, reason?, prev_hash, hash}`.

### 7.3 Workflow-risk classification (deterministic)

Three modes; classification is computed, not chosen ad hoc:

| Mode | Trigger rule (evaluated in order) | Review requirement | Approval to CLOSE |
|---|---|---|---|
| **GOVERNED** | Any `risk_flags` ∩ `workflow.governed_triggers` ≠ ∅ (kernel list §5 + pack additions) | Independent reviewer **and** founder | Founder explicit approval record |
| **REVIEWED** | Pack marks the `work_type`/template as high-risk, OR assignment touches paths matching pack-declared protected globs, OR owner manually raises | Independent reviewer (≠ executor) | Reviewer approval record |
| **FAST** | Everything else (default — ordinary work ships fast) | None | Owner confirmation (may be same command as verification pass) |

Rules: packs may **raise** a classification, never lower it. The founder may raise any assignment; lowering a GOVERNED classification is itself a governed action requiring an escalation record. Classification result and the rule that fired are recorded in the audit log — no silent judgment calls, no repetitive review cycles for FAST work.

---

## 8. Evidence and Verification Model

### 8.1 Evidence classes

| Class | Reference form | Provided by |
|---|---|---|
| `commit` | SHA + branch | repo adapter |
| `pr` | PR number + state + merge SHA | repo adapter (github) |
| `ci_run` | check-run/workflow id + conclusion | repo adapter (github) |
| `test_report` | CI artifact reference + summary digest | repo adapter |
| `artifact` | repo path + blob SHA at a commit | repo adapter |
| `approval` | signed approval record in `.projectos/audit/` (actor, role, assignment, decision, timestamp) | kernel, on explicit CLI action by the approver |

### 8.2 Evidence-rule vocabulary (v0.1 verifier)

Each acceptance criterion carries one rule. v0.1 ships exactly these rule types:

- `file_exists {path, at_ref?}` — blob present at ref (default: default branch head)
- `file_contains {path, pattern}` — regex present in blob
- `commit_exists {message_pattern?, author?, since?}` — matching commit on branch
- `pr_merged {number?, approvals_required, approver_role}` — merged PR with approvals
- `ci_passed {workflow?, ref}` — CI conclusion == success for ref
- `tests_passed {report_path?}` — test report artifact parses green
- `approval_recorded {role, decision: approved}` — approval record exists in audit log
- `human_attestation {role}` — explicit recorded attestation for facts outside the repo (external filings, physical-world actions); always audit-logged; packs must prefer machine-checkable rules

### 8.3 Verification algorithm (deterministic, fail-closed)

```
for each acceptance_criterion in assignment:
    facts = repo_adapter.query(criterion.verify)      # facts only
    result = rule_engine.evaluate(criterion.verify, facts)
    if result != PASS: overall = FAIL (collect all failures, do not short-circuit reporting)
if adapter error / timeout / ambiguity: overall = FAIL (typed error, retryable)
overall PASS  -> VERIFIED
overall FAIL  -> REJECTED with per-criterion report
```

The verifier never consults conversation content, agent self-reports, or LLM judgment. An AI report saying "done" moves state only to `EVIDENCE_SUBMITTED`; the repository decides the rest.

### 8.4 Manual merge and deployment approval

`pr_merged` and any `deployment` work_type always require a human `approval_recorded` evidence rule in v0.1. The kernel has no code path that merges or deploys.

### 8.5 Audit history

Append-only NDJSON, one entry per event, monthly rotation, SHA-256 hash chain (INV-5). `projectos audit verify` re-walks the chain. A broken chain halts the kernel and raises a founder escalation. Audit entries are committed to the repository like all state — GitHub history provides secondary tamper evidence.

---

## 9. Founder-Decision Escalation Model

### 9.1 Escalation triggers (exhaustive; anything else must NOT escalate)

1. Genuine founder decisions: scope, money, external commitments, strategy forks declared `founder_decision` by pack or assignment.
2. Blockers the owner cannot clear (dependency dead-ends, `NEXT_UNDETERMINED`).
3. Security risks (secrets exposure, boundary violations, suspicious repo activity).
4. Legal risks (filings, liability, regulatory triggers — flagged by packs).
5. Architecture conflicts (change requests against frozen architecture; broken audit chain; invariant violations).

### 9.2 Escalation record — `.projectos/escalations/E-NNNN.yaml`

```yaml
schema_version: 1
id: E-0001
assignment_id: A-0007        # or null for project-level
trigger: architecture_conflict   # closed vocabulary of §9.1
summary: "One-paragraph, decision-ready statement"
options:                     # ≥2 options, each with consequence; prepared by kernel/executor
  - id: O1
    description: "..."
    consequence: "..."
  - id: O2
    description: "..."
    consequence: "..."
recommendation: O1           # optional
state: open                  # open | resolved
resolution:                  # founder-only
  decision: null             # option id or free-form directive
  decided_by: null
  decided_at: null
```

### 9.3 Rules

- An open escalation on the active assignment freezes it in `ESCALATED`; project-level escalations block next-assignment generation.
- Escalations must be **decision-ready**: summary + options + consequences. The kernel rejects escalations without options (prevents "thinking out loud" escalation spam).
- Resolution is recorded, audit-logged, and deterministically re-drives the state machine (§7.2).
- Anything not matching §9.1 is handled at owner level — the founder's queue stays short by design.

---

## 10. Project-Pack Interface

### 10.1 Contract

A pack is a **declarative directory** — YAML + markdown templates, zero executable code in v0.1:

```
packs/<name>/
  pack.yaml
  templates/
    <template-name>.yaml     # assignment templates (schema §6 minus kernel-issued fields)
```

```yaml
# pack.yaml — schema version 1
schema_version: 1
name: software-core
version: 0.1.0
domain: software             # informational
vocabulary:                  # domain terms usable in risk_flags
  risk_flags: [breaking_contract, schema_migration]
classification:              # may RAISE only (§7.3)
  reviewed_work_types: [implementation, refactor]
  protected_paths: [".projectos/**", "src/kernel/**"]
  governed_triggers_add: [schema_migration]
escalation_triggers_add: []  # pack-specific founder-decision declarations
pipeline:                    # ordered next-assignment templates per phase (§3.3)
  - phase: foundation
    templates: [design-spec, implement-kernel-skeleton, ...]
```

### 10.2 Guarantees

- Kernel validates packs at load; invalid pack ⇒ kernel refuses to run (fail closed).
- Packs cannot: modify kernel behavior beyond the declared extension points, lower classifications, suppress escalation triggers, or execute code.
- Future domains (TradeOS AI, UrjaOps, PM-KUSUM Ops, Legal Engineering, Foodgod FPO, drones) are pure pack authoring + manifest config — zero kernel changes. This is the reusability contract.

---

## 11. Repository Adapter Interface

Narrow, read-mostly, facts-only:

```
interface RepositoryAdapter:
  # READ (facts for verification)
  get_file(path, ref?) -> Blob | NotFound
  list_commits(branch, filter?) -> [CommitFact]
  get_pr(number?) / list_prs(state) -> [PrFact]          # github only; local-git returns Unsupported
  get_ci_status(ref, workflow?) -> CiFact | Unsupported
  get_artifact(ci_run, name) -> ArtifactRef | Unsupported

  # WRITE (ProjectOS state only — never project content)
  commit_state(paths_under=".projectos/", message) -> CommitFact

  # META
  capabilities() -> {pr: bool, ci: bool, artifacts: bool}
```

Rules: adapters return **facts**, never verdicts; `Unsupported` capability makes any rule needing it fail closed (with a clear error telling the founder which capability is missing); all state writes are ordinary commits so GitHub history mirrors the audit trail. v0.1 ships `github` (full) and `local-git` (no PR/CI — degraded but functional for offline work).

---

## 12. GitHub Integration Boundary

| ProjectOS MAY (via adapter) | ProjectOS MUST NEVER (v0.1) |
|---|---|
| Read commits, branches, files at refs | Merge any PR |
| Read PR metadata, reviews, approvals | Trigger deployments |
| Read Actions/check runs and artifacts | Create/close PRs on behalf of humans |
| Commit files under `.projectos/` | Force-push, rewrite history, or delete branches |
| — | Write outside `.projectos/` |
| — | Administer repo settings, webhooks, tokens |

Token scope: fine-grained PAT limited to the one repository, `contents: read/write`, `pull_requests: read`, `actions: read`. No org-level scopes. Executors (Claude Code) use their own credentials and boundaries — ProjectOS's token is for orchestration state and evidence reads only.

---

## 13. CLI Surface (v0.1 — complete command set)

```
projectos init                      # scaffold .projectos/ from manifest answers
projectos validate                  # manifest + packs + state schema check
projectos status                    # project, active assignment, blockers, open escalations
projectos assignment new [--template T | --interactive]     # -> DRAFT
projectos assignment show <id>
projectos assignment classify <id>  # DRAFT -> READY (runs §7.3; prints rule fired)
projectos start <id>                # READY -> ACTIVE (enforces INV-1); emits agent briefing
projectos brief                     # re-emit current briefing for the active assignment
projectos submit <id> --report <file>    # ingest completion claim -> EVIDENCE_SUBMITTED
projectos verify <id>               # run verifier -> VERIFIED | REJECTED (per-criterion report)
projectos approve <id> --role owner|reviewer|founder    # record approval; auto-CLOSE when complete
projectos reject <id> --reason "..."                    # review rejection -> REJECTED
projectos next                      # show/generate next assignment after CLOSED
projectos escalate [--assignment <id>] --interactive     # build decision-ready escalation
projectos resolve <eid> --decision <opt|text>            # founder resolution
projectos audit show [--assignment <id>] | verify
projectos pack validate <path> | list
```

Every command is a thin wrapper over one kernel operation; exit codes are deterministic (0 ok, 1 rule failure, 2 invariant/validation error, 3 escalation required) so the CLI is scriptable by agents.

---

## 14. Security Boundaries

1. **Secrets:** never in `.projectos/`, manifests, packs, assignments, or audit logs. Tokens come from environment/OS keychain. `projectos validate` scans state files for secret patterns and fails on detection.
2. **Least privilege:** repo-scoped fine-grained token (§12); adapters get only their own config; packs get no credentials at all (they're data).
3. **Fail closed everywhere:** invalid schema, broken audit chain, adapter errors, unknown transitions, ambiguous evidence ⇒ block + typed error + (where §9.1 applies) escalation. No silent defaults to success.
4. **Identity and authority:** every approval records actor identity; founder-only actions validated against `manifest.founder.id`. v0.1 trusts local OS identity + git commit identity (single-founder threat model); cryptographic signing is a v0.2 hardening item (Risk R-6).
5. **Injection surface:** agent completion reports are untrusted input — parsed against a strict schema, never executed, never allowed to trigger transitions beyond `submit`. Assignment briefings instruct agents that only repository evidence counts, removing incentive to game reports.
6. **Audit integrity:** hash chain (INV-5) + repository history as second witness. Hand-edits to state files break validation and halt the kernel.
7. **Blast radius:** ProjectOS writes only under `.projectos/`; worst-case compromise of the orchestration token cannot merge, deploy, or alter project code.

---

## 15. v0.1 Acceptance Criteria (for ProjectOS itself)

v0.1 is done when, on one real repository:

1. `projectos init` + `validate` produce a valid `.projectos/` with manifest and one pack.
2. Exactly one assignment can be ACTIVE; attempting a second `start` fails with exit code 2 (INV-1).
3. An assignment authored with acceptance criteria in the §8.2 vocabulary is verified purely from git/GitHub facts: a fabricated "done" report with no matching evidence ends in `REJECTED`.
4. FAST, REVIEWED, and GOVERNED assignments each complete their distinct approval paths; classification prints the rule that fired.
5. `depends_on` gating works: a DRAFT with an open dependency cannot reach READY.
6. On `CLOSED`, `projectos next` deterministically generates the successor from the pack pipeline, or raises `NEXT_UNDETERMINED`.
7. An escalation created without options is rejected; a valid one freezes the assignment until `resolve`, and resolution re-drives the state machine.
8. `projectos audit verify` passes on an untouched log and fails (halting the kernel) after any manual edit to a state file.
9. A merge-requiring assignment cannot reach `CLOSED` without a recorded human approval; no kernel code path calls merge/deploy APIs.
10. Cowork-routed (`architecture`) and Code-routed (`implementation`) assignments emit correct briefings, and code-touching evidence on an architecture assignment is rejected.

---

## 16. MVP Implementation Sequence

Each phase is one-or-few assignments under ProjectOS's own governance (dogfooding from Phase 2 onward). No parallel workstreams.

| Phase | Deliverable | Workflow mode | Exit evidence |
|---|---|---|---|
| **P1 — Schemas & validation** | Manifest, assignment, pack, escalation, audit schemas + validators; `init`, `validate` | REVIEWED | Schema test suite green in CI |
| **P2 — State machine & audit** | Transition engine with full §7.2 table, invariants INV-1..7, hash-chained audit log; `status`, `assignment new/show/classify`, `start` | GOVERNED (this is the frozen core) | Exhaustive transition tests incl. all illegal-transition rejections |
| **P3 — Local-git adapter & verifier** | Repo adapter (local-git), rule engine for `file_exists`, `file_contains`, `commit_exists`, `approval_recorded`, `human_attestation`; `submit`, `verify`, `approve`, `reject` | REVIEWED | AC-3 style end-to-end test: fake claim → REJECTED |
| **P4 — GitHub adapter** | `pr_merged`, `ci_passed`, `tests_passed` rules; token scoping | REVIEWED | Live test against a scratch GitHub repo |
| **P5 — Packs & next-generation** | Pack loader/validator, `software-core` pack, pipeline-driven `next`; `pack validate/list` | REVIEWED | v0.1 acceptance criterion 6 |
| **P6 — Escalation & agent adapters** | Escalation manager, `escalate`/`resolve`; cowork/code/human briefing + report ingestion; `brief` | REVIEWED | Criteria 7 and 10 |
| **P7 — Hardening & v0.1 cut** | Secret scanning, exit-code contract, docs (README, runbook), full §15 acceptance pass | GOVERNED (release) | All 10 acceptance criteria green; founder approval record |

Dependency chain is strictly P1→P7. Estimated complexity: P2 and P3 are the heavy phases; everything else is thin by design.

---

## 17. Risks

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | **Over-engineering the kernel** — governance machinery heavier than the work it manages | Med | High | v0.1 rule vocabulary is closed and small; FAST is the default mode; no new abstraction without a pack that needs it |
| R-2 | **Evidence gaming** — executor commits trivial files to satisfy shallow rules | Med | Med | Criteria authored by owner not executor; REVIEWED mode for code; `human_attestation` discouraged in favor of CI-backed rules |
| R-3 | **State/reality drift** — humans act outside ProjectOS (direct merges, side work) | High | Med | Adapter reads ground truth from GitHub at verify time; drift surfaces as failed criteria, not silent corruption |
| R-4 | **Single-founder bottleneck** — GOVERNED queue stalls progress | Med | Med | §9.3 decision-ready rule; only §9.1 triggers escalate; everything else stays at owner level |
| R-5 | **Adapter API instability** (GitHub API changes) | Low | Med | Narrow §11 interface; capability flags; local-git fallback keeps the kernel operable |
| R-6 | **Identity spoofing** in approvals (v0.1 trusts local identity) | Low | High-later | Acceptable for single-founder v0.1; signed approvals scheduled v0.2; risk recorded here so it is a conscious acceptance |
| R-7 | **Pack sprawl / domain leakage into core** under delivery pressure | Med | High | §2.2 boundary rule + GOVERNED classification on any `src/kernel/**` change (protected path) |
| R-8 | **`human_attestation` becomes a rubber stamp** for non-repo domains (legal, agriculture) | Med | Med | Attestations are audit-logged with actor identity; pack authors must justify each attestation-based criterion; future packs can bind external evidence sources via adapters |

---

## 18. Decision Log (resolved by this specification)

| # | Decision | Rationale |
|---|---|---|
| D-1 | State lives in-repo under `.projectos/`, not a separate control repo | One source of truth; portability; GitHub history as audit witness. Revisit at multi-project (v0.2+) |
| D-2 | Kernel is a local CLI, not a hosted service | Zero infrastructure cost/risk for one founder; deterministic; agents can shell out to it. Service wrapper is additive later |
| D-3 | Packs are declarative-only in v0.1 | Executable packs would blow the security boundary before governance machinery exists to review them |
| D-4 | Verification is mechanical rules, never LLM judgment | Determinism, auditability, fail-closed semantics are impossible with judgment-based verification |
| D-5 | Scope changes require cancel-and-reissue, not editing | Immutable assignments keep audit trail and acceptance criteria honest |
| D-6 | v0.1 targets exactly one repository and one project | Matches assignment mandate; multi-project orchestration deferred until the single-project loop is proven |

## 19. Unresolved Founder Decisions (non-blocking — defaults stand unless overridden)

None of these block Claude Code from beginning Phase P1; each has a stated default that will be implemented unless the founder overrides before the affected phase.

| # | Decision | Default in effect | Needed before |
|---|---|---|---|
| F-1 | Implementation language for the kernel | TypeScript (strong typing, schema tooling, single runtime with future UI; Python acceptable alternative) | P1 start |
| F-2 | Which real repository hosts ProjectOS AI itself (GitHub org/repo name) | New private repo `projectos-ai` under founder's account | P1 start |
| F-3 | License / commercial posture (private, source-available, OSS core + paid packs) | Private, all rights reserved until product-market signal | v0.1 release (P7) |
| F-4 | First external dogfood project after self-hosting (TradeOS AI vs PM-KUSUM Ops vs Legal Engineering) | Decide at P7; no architectural impact | Post-v0.1 |

---

## 20. Final Verdict

All 15 mandated definition areas are specified; all required v0.1 capabilities (one repository, one active assignment, automatic next-assignment generation, Cowork/Code routing, fast/reviewed/governed modes, dependency tracking, acceptance criteria, git evidence verification, founder escalation, audit history, manual merge/deployment approval) have owning sections, schemas, and acceptance criteria. Remaining founder decisions carry stated defaults and do not gate Phase P1.

**READY FOR CLAUDE CODE**

*Stopping point reached per assignment: the Claude Code implementation assignment is intentionally not generated here.*
