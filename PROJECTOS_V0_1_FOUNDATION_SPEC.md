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

### 6.1 Immutable-field and state/history integrity (normative)

The immutability rule above was, until this amendment, enforced only *within* kernel code paths: no kernel operation edited scope, but nothing detected a *hand-edit* to an assignment file. A direct edit to `state.status` or to `acceptance_criteria`/`workflow_mode` therefore went undetected. v0.1 now binds these to the tamper-evident audit chain so a hand-edit halts the kernel.

**Immutable field set.** For an assignment past `DRAFT`, the *scope-defining* fields are immutable and are covered by an integrity digest: `id`, `schema_version`, `title`, `work_type`, `objective`, `owner`, `executor`, `workflow_mode`, `risk_flags`, `depends_on`, `context_refs`, `stopping_point`, `acceptance_criteria`, `evidence_required`, `next`, `origin_template`. Excluded (mutable by design): the entire `state` block, and the kernel-written annotations `classification_rule` and `rejection_reasons` — these carry no authority and no verification effect, and their tampering changes no outcome.

**Digest binding.** When an assignment leaves `DRAFT` (the `classify_ok` transition, at which `workflow_mode` is finalized), the kernel computes a SHA-256 digest over the canonical serialization of the immutable field set and records it in that transition's audit entry `data`. Because the audit entry is hash-chained, the digest cannot subsequently be altered without breaking §8.6.1.

**State/history consistency.** On every load (i.e. before every kernel operation, via the guard), for every assignment:

1. `state.status` MUST equal the `to_status` of the last entry in `state.history`; a `DRAFT` assignment MUST have empty history. A mismatch is a hand-edit.
2. For any assignment past `DRAFT`, the digest recomputed from the current immutable fields MUST equal the digest bound at `classify_ok`.

Any violation raises `AuditChainBroken` and halts the kernel (INV-6). This closes direct edits to `status`, `workflow_mode`, `acceptance_criteria`, and every other immutable field. Legitimate scope change remains cancel-and-reissue (decision D-5).

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
| ACTIVE | `block` (external blocker; reason required) | BLOCKED | owner/kernel |
| EVIDENCE_SUBMITTED | `verify_start` | VERIFYING | kernel (automatic) |
| VERIFYING | `all_criteria_pass` | VERIFIED | kernel only |
| VERIFYING | `any_criterion_fail` / `verifier_error` | REJECTED | kernel only (fail closed) |
| VERIFIED | `approvals_complete` | CLOSED | required approvers (per workflow mode) |
| VERIFIED | `review_reject` | REJECTED | reviewer/founder |
| REJECTED | `resume` | ACTIVE | kernel (with rejection reasons attached to briefing) |
| BLOCKED | `unblock` (deps restored) | READY | kernel |
| BLOCKED | `escalate` (blocker the owner cannot clear, §9.1 trigger 2) | ESCALATED | owner/kernel |
| ESCALATED | `founder_resolve(proceed)` | prior state | founder |
| ESCALATED | `founder_resolve(cancel)` | CANCELLED | founder |
| ESCALATED | `founder_resolve(rescope)` | CANCELLED + new DRAFT issued | founder |

Every transition writes an audit entry: `{event, from, to, actor, timestamp, assignment_id, evidence_refs?, reason?, prev_hash, hash}`.

#### 7.2.1 Normative conditions for the blocking transitions

The two blocking rows above are normative and carry conditions the table cannot
express. They exist because a blocker does not respect state boundaries: an
external dependency can fail while an assignment is already `ACTIVE`, and a
blocker the owner cannot clear is an escalation trigger in its own right
(§9.1 trigger 2). Both are deliberately narrow.

| Rule | `ACTIVE → block → BLOCKED` | `BLOCKED → escalate → ESCALATED` |
|---|---|---|
| **Source state** | `ACTIVE` only. Not `EVIDENCE_SUBMITTED` or `VERIFYING`: once evidence is submitted the kernel must reach a verdict, not park the assignment. | `BLOCKED` only. |
| **Target state** | `BLOCKED` | `ESCALATED` |
| **Authorized actors** | `owner`, `kernel`. Not `executor`: an agent may not park its own assignment to avoid a verdict. | `owner`, `kernel`. |
| **Required conditions** | A non-empty `reason` MUST be recorded. The kernel rejects a blocking request without one. | A decision-ready escalation record (§9.2) MUST exist or be created in the same operation, including ≥2 options with consequences. |
| **Evidence / approval** | None. Blocking records no evidence and confers no progress. | None beyond the escalation record. |
| **Effect on INV-1** | Releases the active slot: `BLOCKED` is not an active-slot state, so another assignment may then start. | No change; `ESCALATED` is not an active-slot state. |
| **Failure behaviour** | Fails closed. A missing reason, a non-`ACTIVE` source, or an unauthorized actor raises a typed error and writes nothing. | Fails closed. Validation of the escalation precedes any persistence, so a rejected escalation leaves no record. |
| **Return path** | `BLOCKED → unblock → READY`, permitted only once every dependency is `CLOSED`. | `ESCALATED → founder_resolve(...)`, per the rows above. |

No other transition may be added to the implementation without a corresponding row
in this table. The state-machine test suite asserts this correspondence in both
directions and fails if the implementation and this table diverge.

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

Append-only NDJSON, one entry per event, monthly rotation, SHA-256 hash chain (INV-5). `projectos audit verify` re-walks the chain. A broken chain halts the kernel and raises a founder escalation. Audit entries are committed to the repository like all state — GitHub history provides secondary tamper evidence. The precise guarantees of that chain, and its limits, are defined in §8.6.

### 8.6 Audit authenticity and the v0.1 trust boundary (normative)

The SHA-256 hash chain is an **unkeyed** integrity mechanism. Any process that can write `.projectos/` can also compute the next hash, so a correctly-linked *appended* entry is indistinguishable, to the chain alone, from a legitimately produced one. Earlier revisions of this section implied the chain detected deliberate append forgery. It does not. This subsection replaces that implication with a precise, layered statement of what v0.1 guarantees.

**Four distinct properties — do not conflate them:**

| Property | Question it answers | v0.1 mechanism | v0.1 status |
|---|---|---|---|
| **Corruption detection** | Was any *existing* entry altered, reordered, truncated, or deleted? | SHA-256 chain (INV-5) + `audit_ref` cross-check (§8.6.1) | **Guaranteed** — halts the kernel |
| **State/history consistency** | Does each assignment file agree with the events the log records for it? | State/history + immutable-field digest check (§6.1) | **Guaranteed** — halts the kernel |
| **Actor authorization** | Is a recorded approval/attestation attributed to an identity permitted to hold that role? | Read-time authority re-validation against the manifest (§8.6.2) | **Guaranteed** — an unauthorized entry grants nothing (fails closed) |
| **Cryptographic authenticity** | Was this entry actually produced by the named identity, and not forged by someone impersonating it? | none (would require signing keys) | **Not guaranteed — deferred to v0.2** |

**The v0.1 trust boundary is explicit.** A process that *both* (a) holds write access to `.projectos/` *and* (b) knows a manifest-authorized identity can append a hash-linked entry attributed to that identity which survives every v0.1 check. This is accepted, not fixed, in v0.1, for the same reason as Risk R-6: the threat model is a single founder on a local CLI, where such a process is running as the founder and can already alter any project state. v0.1 does **not** defend the audit log against its own privileged operator; it defends against accident, inconsistency, and *unauthorized-identity* forgery. Cryptographically-signed approval records (v0.2, Risk R-6/R-9) are the mechanism that closes authenticity.

What the correction *does* achieve: it moves append forgery from "append any entry and it counts" to "impersonate a *specific, named, manifest-authorized* identity." The trivial forgery — an approval attributed to an identity that is not authorized for the role — is detected and grants nothing (§8.6.2).

#### 8.6.1 Corruption detection (existing, retained)

`verify_chain` re-walks the whole chain: sequence contiguity from 1, each entry's `prev_hash` equal to the predecessor's `hash`, and each entry's recomputed `hash` equal to its stored `hash`. Independently, every `state.history[].audit_ref` in every assignment must resolve to a present log entry, and every transition the log records for a still-present assignment must appear in that assignment's history (§ integrity cross-check, P1.1). Any failure raises `AuditChainBroken` and halts the kernel (INV-6). This catches editing, reordering, truncating (tail or whole-file), and deleting existing entries. It does **not** catch a correctly-linked append (see above).

#### 8.6.2 Approval and attestation authority (normative)

An `approval_recorded` or `attestation_recorded` entry grants authority **only if** all of the following hold; otherwise it grants nothing (fails closed) and is treated as absent for the purpose of reaching CLOSED:

1. **Event/decision binding.** `approval_recorded` MUST carry `decision = approved`; `attestation_recorded` MUST carry `decision = attested`. Any other pairing grants nothing.
2. **Identity authorization**, evaluated against the manifest at verification time, for the entry's `role` and recorded `actor`, relative to the target assignment `A`:
   - `role = founder` → `actor` MUST equal `manifest.project.founder.id`.
   - `role = owner` → `actor` MUST equal `A.owner` **or** `manifest.project.founder.id`.
   - `role = reviewer` → `actor` MUST be listed in `manifest.owners` **and** MUST NOT equal `A.owner` (independence, §4.1).
3. **Chain membership.** The entry MUST be part of a chain that passes §8.6.1.

These are the same rules the kernel already enforces on the *write* path when recording an approval; §8.6.2 requires them to be re-enforced on the *read* path (verification and CLOSE evaluation), because a hand-appended entry never passed the write path. Because the checks require `manifest`, this validation MUST live in the application layer (verification/lifecycle), never in the infrastructure audit-log projection — the projection returns records; the kernel decides which ones count (§2.2 boundary rule).

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

### 10.1.1 Version compatibility (normative)

A pack declares two version facts, and both are enforced before the pack is usable:

| Field | Location | Constrains | Checked against |
|---|---|---|---|
| `version` | `pack.yaml` | the pack's own version | the manifest's `packs[].version` constraint |
| `requires_projectos` | `pack.yaml` | the kernel the pack supports | the executing kernel version |

Rules:

- Constraints are **PEP 440** (`>=0.1.0,<0.2.0`, `==0.1.0`, `*`). Whitespace between clauses is accepted and normalised to the comma form, so the `">=0.1.0 <0.2.0"` style used in §5 is valid. Syntax from other ecosystems (`^1.0.0`, `~>1.0`) is rejected, not approximated.
- A malformed version or an unsupported constraint is a **hard error** at pack construction; it cannot sit unnoticed inside a pack.
- **Prereleases are excluded** unless the constraint itself names a prerelease. `>=0.1.0` does not admit `0.2.0rc1`; `>=0.2.0rc1` does.
- `requires_projectos` is **optional** in schema v1, for packs authored before it existed. When absent, the pack loads and `validate` reports a warning; when present and unsatisfied, loading fails closed.
- Compatibility is enforced on the **loading** path, not only in the validation commands, so activation cannot bypass it.

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

### 13.1 Implemented surface (P1 series)

`init`, `validate`, `status`, `next`, `verify`, `complete`, `block`, `founder {list,escalate,resolve}`, `history`, and `pack validate`.

`validate` and `pack validate` are **non-mutating** by contract: they load, evaluate, and report. Neither writes state, installs a pack, nor activates one. Both delegate to a single application-layer validation service, which is also invoked by pack loading, so a pack cannot enter the kernel through a path that skips a check the commands apply.

Commands folded into the above rather than shipped separately: `start`/`resume` are driven by `next`; `submit` is folded into `verify`; `approve` is `complete`; `audit verify` is `history --verify`. `assignment new/show/classify`, `brief`, `reject`, and `pack list` are not implemented in the P1 series.

---

## 14. Security Boundaries

1. **Secrets:** never in `.projectos/`, manifests, packs, assignments, or audit logs. Tokens come from environment/OS keychain. `projectos validate` scans state files for secret patterns and fails on detection.
2. **Least privilege:** repo-scoped fine-grained token (§12); adapters get only their own config; packs get no credentials at all (they're data).
3. **Fail closed everywhere:** invalid schema, broken audit chain, adapter errors, unknown transitions, ambiguous evidence ⇒ block + typed error + (where §9.1 applies) escalation. No silent defaults to success.
4. **Identity and authority:** every approval records actor identity; founder-only actions validated against `manifest.founder.id`. Approval and attestation entries are authority-validated against manifest-authorized identities and roles on **both** the write and read paths (§8.6.2), so an entry attributed to an unauthorized identity grants nothing. v0.1 trusts local OS identity + git commit identity (single-founder threat model); it does **not** cryptographically prove that an entry attributed to an *authorized* identity was actually produced by it — impersonation by a process already holding repo + local-user credentials is an accepted v0.1 boundary, closed by signed records in v0.2 (Risk R-6/R-9, §8.6).
5. **Injection surface:** agent completion reports are untrusted input — parsed against a strict schema, never executed, never allowed to trigger transitions beyond `submit`. Assignment briefings instruct agents that only repository evidence counts, removing incentive to game reports.
6. **Audit and state integrity:** the unkeyed hash chain (INV-5) detects corruption, reordering, truncation, and deletion of existing entries (§8.6.1), but **not** a correctly-linked append (§8.6). Hand-edits to assignment scope, `state.status`, or workflow classification are detected via the immutable-field digest and state/history consistency checks (§6.1) and halt the kernel. Repository/GitHub history is a secondary witness, not a primary control.
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
8. **Integrity halting and authority (revised, §6.1/§8.6).** On untouched state, every kernel operation and `projectos history --verify` succeed. The kernel **halts** (`AuditChainBroken`, exit 3) when any of these is present: (a) a corrupted, reordered, truncated, or deleted audit chain; (b) an assignment whose `state.status` disagrees with its `history`; (c) an assignment past `DRAFT` whose immutable-field digest no longer matches the digest bound at `classify_ok` — i.e. a hand-edit to `status`, `workflow_mode`, `acceptance_criteria`, or any immutable field. Separately, an `approval_recorded`/`attestation_recorded` entry whose actor is not manifest-authorized for its role, or whose event/decision pairing is inconsistent, **grants no authority** (fails closed) and cannot move an assignment to `CLOSED`. The chain does **not** detect a correctly-linked append that impersonates a manifest-authorized identity; that is the explicit v0.1 trust boundary (§8.6), tested as a documented non-guarantee, not as a passing forgery.
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
| R-9 | **Audit append forgery** — a process with `.projectos/` write access appends a correctly hash-linked entry impersonating a manifest-authorized identity | Low | High-later | v0.1 boundary (§8.6): unkeyed chain cannot detect it. Mitigated in v0.1 to *unauthorized-identity* forgery only (read-time authority validation, §8.6.2). Authenticity against authorized-identity impersonation deferred to v0.2 signed approval records. Consciously accepted for the single-founder local model, where the forging process runs as the founder |
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
| D-7 | Audit authenticity is layered: v0.1 provides corruption detection, state/history consistency, and read-time authority validation; cryptographic authenticity (signed records) is deferred to v0.2 (§8.6, R-9) | An unkeyed chain cannot prevent a privileged operator forging an append. Honesty about the boundary beats a false guarantee. The single-founder local model makes authorized-identity impersonation an acceptable v0.1 residual; the trivial unauthorized-identity forgery is closed now |

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

---

## 21. Appendix — P1.5 Implementation Contract (Blockers 1–5)

Normative directives for the Claude Code assignment that fixes PR #4's five verified blockers. Each item lists the required code behaviour and the regression tests that must accompany it. **No further architecture decision is required for any blocker** — §6.1 and §8.6 above resolve the only open design question (append forgery). Every regression test must be demonstrated to FAIL against commit `2a67240` before the fix and PASS after (the established defect-proving discipline). No existing test may be weakened.

### 21.1 Blocker 1 — status forgery (architecture: settled, §6.1)

**Required behaviour.** The integrity check (application layer, run by the guard before every operation) MUST reject any assignment whose `state.status` ≠ `to_status` of the last `state.history` entry, and any `DRAFT` assignment with non-empty history. Failure raises `AuditChainBroken` (exit 3). Placement: application layer (it needs no manifest but belongs with the existing `verify_state`), never the infrastructure projection.

**Regression tests.** (a) drive an assignment to `ACTIVE`, hand-edit `status: closed`, assert `history --verify` and every write operation halt; (b) hand-edit a DRAFT to carry fabricated history, assert halt; (c) an untouched full lifecycle still verifies.

### 21.2 Blocker 2 — mutable scope/classification after DRAFT (architecture: settled, §6.1)

**Required behaviour.** At the `classify_ok` transition, compute a SHA-256 digest over the canonical serialization of the immutable field set (§6.1) and store it in that audit entry's `data`. On every load, for any assignment past `DRAFT`, recompute and compare; mismatch raises `AuditChainBroken`. The digest MUST be computed from the same canonical form the serializer already uses, so re-saving an unchanged assignment does not spuriously fail.

**Regression tests.** (a) swap an `acceptance_criteria` rule after classify, assert halt; (b) change `workflow_mode` reviewed→fast after classify, assert halt; (c) editing `rejection_reasons` or `classification_rule` (excluded fields) does NOT halt; (d) the normal REJECTED→resume→verify cycle, which legitimately rewrites `state` and `rejection_reasons`, still verifies.

### 21.3 Blocker 3 — append forgery (architecture: settled, §8.6.2)

**Required behaviour.** Approval/attestation authority is re-validated on the READ path, in the application layer, against the manifest, per §8.6.2: event/decision binding, and role→actor authorization (founder = founder.id; owner = assignment owner or founder; reviewer ∈ owners and ≠ assignment owner). An entry failing any check grants nothing. The infrastructure audit-log projection MUST NOT perform this check (no manifest there); it returns records, the verification engine filters them. This must not regress the P1.1 rule that a missing/non-canonical `decision` grants nothing.

**Regression tests.** (a) append a chain-valid `approval_recorded` with `actor` not in `manifest.owners`; assert it grants nothing and the assignment cannot reach `CLOSED`; (b) append a chain-valid `attestation_recorded` carrying `decision: approved`; assert it does not satisfy an `approval_recorded` criterion; (c) a legitimate approval by an authorized identity still closes; (d) **documented non-guarantee test**: an append impersonating a genuinely manifest-authorized identity IS accepted — assert this explicitly as the v0.1 boundary (§8.6), with a comment citing R-9, so the limit is visible and cannot silently regress into a claimed guarantee.

### 21.4 Blocker 4 — bundled-pack circular approval (classification: implementation defect)

This is an **implementation defect in the bundled `software-core` pack templates, not a design ambiguity.** Acceptance criteria are verified from repository evidence (§8.3); reviewer/founder sign-off is the separate CLOSE gate driven by workflow mode (§7.3). The `implement-kernel` and `harden-and-document` templates wrongly encode `approval_recorded` as an *acceptance criterion*, which cannot be satisfied because approval requires `VERIFIED` first — a deadlock reproduced at A-0002 in every scaffolded project.

**Required behaviour.** Bundled templates MUST express acceptance criteria over repository facts (e.g. `commit_exists`, `file_exists`, `ci_passed`) and rely on the assignment's workflow mode for reviewer/founder approval at CLOSE. `approval_recorded` remains a valid rule type for genuinely repository-external evidence, but MUST NOT be the criterion that gates `VERIFIED` in a generated pipeline template.

**Regression tests.** (a) a full `init`→(A-0001)→`next`→(A-0002)→`verify`→`complete` cycle reaches `CLOSED` on A-0002 using only committed evidence plus the mode-appropriate approval, with no hand-edit; (b) assert no bundled template uses `approval_recorded` as an acceptance-criterion rule.

### 21.5 Blocker 5 — untested audit guarantees (no architecture)

**Required behaviour.** The audit and authority guarantees must be individually tested such that removing any single production check fails at least one test.

**Regression tests.** (a) add `match=` (specific substrings) to the three `test_audit.py` tampering tests so each pins its own failure mode; (b) add tests that independently remove the `prev_hash`-link check and the sequence-contiguity check and assert each removal is caught; (c) add tests covering the eight mutation survivors the P1.4 review identified: `tests_passed` fail-open, `approval_recorded` decision widening, empty-criteria pass (INV-3), the two `verify_chain` checks, attestation-counts-as-approval, capability-default `False`→`True`, and the approval-projection role filter. Each test must fail against the corresponding one-line production mutation and pass on the real code.

### 21.6 Blockers requiring no further architecture decision

Confirmed: **Blockers 1, 2, 4, and 5 need no architecture decision.** 1 and 2 are settled by §6.1 (consistency + digest, no new mechanism beyond the existing chain). 4 is a pack-authoring correction. 5 is test work. Blocker 3 is the only one that touched the trust model, and it is settled by §8.6 (read-time authority validation + an explicit, tested v0.1 boundary). Claude Code may implement all five directly against this contract.
