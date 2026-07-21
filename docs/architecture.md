# ProjectOS Core — architecture

Implementation notes for the kernel defined in
[`PROJECTOS_V0_1_FOUNDATION_SPEC.md`](../PROJECTOS_V0_1_FOUNDATION_SPEC.md). The
spec is the source of truth; this document explains how the code realises it and
why particular choices were made.

## Layering

```
                    ┌──────────────────────────────┐
   cli/             │ argument parsing, formatting │
                    └──────────────┬───────────────┘
                                   │ calls
                    ┌──────────────▼───────────────┐
   application/     │ LifecycleService             │
                    │ VerificationEngine           │
                    │ ports (Protocols)            │
                    └──────────────┬───────────────┘
                                   │ uses
                    ┌──────────────▼───────────────┐
   domain/          │ state machine, rules, values │
                    └──────────────────────────────┘
                                   ▲
                                   │ implements ports
                    ┌──────────────┴───────────────┐
   infrastructure/  │ files, schemas, adapters, DI │
                    └──────────────────────────────┘
```

**Dependencies point inward only.** `domain/` imports nothing from the other three
layers. `application/` declares what it needs as Protocols in `ports.py`;
`infrastructure/` supplies implementations. The composition root
(`infrastructure/container.py`) is the only place that wires concrete types
together — there are no module-level singletons and no global state, so a caller
can build a fully independent kernel over a temporary directory.

## Module map

### `domain/` — pure, immutable, no I/O

| Module | Responsibility |
|---|---|
| `enums.py` | Every closed vocabulary. Values outside these sets are rejected at the schema boundary. |
| `errors.py` | Typed errors, each carrying its exit code. |
| `ids.py` | `AssignmentId` / `EscalationId` as value objects with total parsing. |
| `manifest.py` | Project manifest and its cross-field rules. |
| `assignment.py` | The assignment value and its transformations. |
| `evidence.py` | Rules, facts, claims, and results — four distinct concepts. |
| `state_machine.py` | The exhaustive transition table (spec §7.2). |
| `classification.py` | Deterministic workflow-risk classification. |
| `approvals.py` | Which roles must approve, per mode. |
| `dependency.py` | Dependency satisfaction and cycle detection. |
| `rule_engine.py` | Evaluates one rule against one fact. |
| `routing.py` | Executor validation and briefing generation. |
| `next_engine.py` | Successor resolution. |
| `escalation.py` | Founder-decision records. |
| `audit.py` | Hash-chained audit entries. |
| `pack.py` | Project-pack model. |

### `application/`

- **`ports.py`** — Protocols for clock, identity, repositories, audit log, and the
  repository adapter.
- **`verification.py`** — asks the adapter for facts, hands them to the rule
  engine, collects results.
- **`lifecycle.py`** — the kernel's single write path.

### `infrastructure/`

File-backed repositories, the NDJSON audit log, JSON Schema validation, the
local-git adapter, `.projectos/` layout, scaffolding, and the composition root.

## Key design decisions

### Immutable values, one write path

Assignments are frozen dataclasses. Every lifecycle operation returns a *new*
assignment rather than mutating one, and every state change goes through
`LifecycleService._transition`, which enforces the transition table, writes the
audit entry, and persists the assignment as a single unit.

Nothing else in the codebase may change an assignment's status. That is what makes
the audit log complete rather than merely well-intentioned: there is no code path
that changes state without appending to it.

### The state machine is a closed table

`TRANSITIONS` corresponds row-for-row with spec §7.2. Lookup is total: any
`(status, event)` pair absent from the table raises `IllegalTransition`. The test
suite asserts this exhaustively — it enumerates the full Cartesian product of
states and events and requires every undeclared combination to be rejected, so a
future edit cannot quietly widen the machine.

The actor permission column is enforced too. Only the founder may cancel an
`ACTIVE` assignment; only the kernel may decide a verification outcome.

`ESCALATED → prior state` is a sentinel resolved by the caller from the
assignment's own history, because the destination is not a property of the table.

### Three concepts that must not blur

- **`EvidenceRule`** — what the owner asked to be true. Authored, immutable.
- **`RepositoryFact`** — what the adapter observed. Facts, never verdicts.
- **`CriterionResult`** — the kernel's verdict, produced only by the rule engine.

A `CompletionClaim` is none of these. Adapters report; the kernel decides.

Some comparisons deliberately live in the kernel rather than the adapter — whether
a PR has enough approvals, whether a CI conclusion counts as success. Those are
decisions, so they belong to `rule_engine.py`.

### Fail-closed, everywhere

`CriterionOutcome` has two members. There is no "unknown" that means success.
Every path that could produce uncertainty converges on `FAIL`:

- adapter raises → `FAIL`, reason names the error
- adapter lacks the capability → `FAIL`, reason names the capability
- fact absent → `FAIL`
- assignment has no criteria → cannot be constructed at all (INV-3 would be
  unsatisfiable)

Failures are collected, never short-circuited, so one run reports everything that
is missing.

### The audit chain

Each entry hashes its canonical payload together with the previous entry's hash.
Canonicalisation is JSON with sorted keys and no insignificant whitespace, so the
same logical entry always hashes identically.

`verify_chain` re-walks the whole chain rather than only the tail — a tamperer who
can rewrite one entry can rewrite the tail too.

**Chain integrity alone is not enough.** Any prefix of a valid chain is itself a
valid chain, so truncating the tail — or deleting the newest monthly file, or the
whole log — leaves something that verifies. The anchor comes from outside the log:
every transition records the hash of the authorising entry in
`TransitionRecord.audit_ref`, and `application/integrity.py` cross-checks in both
directions:

* every `audit_ref` an assignment cites must be present in the log (catches a
  truncated or deleted log), and
* every transition the log records must appear in the assignment's history
  (catches history edited out of a state file).

Every kernel operation runs this check before writing, so tampering halts the
kernel (INV-6) rather than being noticed later.

Files rotate monthly for filing convenience, but the chain runs continuously across
them: starting a fresh file does not escape verification.

### State/history consistency and immutable fields (§6.1)

The cross-check above catches *dropped* entries but not a direct edit to an
assignment's own fields. Two further checks in `application/integrity.py` close
that, and run on every load:

- **State/history consistency** — a hand-set `status: closed` no longer agrees with
  the last recorded transition, so `state.status` must equal the `to_status` of
  `history[-1]` (a fresh DRAFT has empty history).
- **Immutable-field digest** — at `classify_ok` the kernel binds a SHA-256 digest of
  the assignment's scope-defining fields (`domain/digest.py`) into the hash-chained
  audit entry. On load it recomputes and compares, so editing acceptance criteria,
  `workflow_mode`, a rule parameter, or any immutable field after DRAFT halts the
  kernel. Scope change remains cancel-and-reissue (decision D-5).

### Audit authenticity: what the chain does and does not prove (§8.6)

The chain is **unkeyed**, so a process that can write `.projectos/` can compute a
valid next hash and *append* a correctly-linked entry. The chain cannot detect that
by itself, and the spec (§8.6) says so plainly. v0.1 layers three properties it
*can* guarantee, and names the one it cannot:

- corruption detection and state/history consistency (above) — **halt**;
- **actor authorization** — an `approval_recorded`/`attestation_recorded` entry is
  counted only if its event/decision pairing is consistent and its actor is
  manifest-authorized for the role, re-validated on the read path (verification and
  the CLOSE gate) using the same `is_authorized` predicate as the write path. A
  forged approval attributed to an unknown identity grants nothing;
- **cryptographic authenticity** — proving an entry attributed to an *authorized*
  identity was really produced by it — is **not** provided; a signed-records item is
  deferred to v0.2 (R-9). In the single-founder local model the forging process runs
  as the founder, so this is a conscious acceptance, not an oversight.

Reviewer authority is bound to `manifest.owners`: a reviewer must be a manifest
owner other than the assignment's owner. There is no separate reviewer registry, so
this is the only authorization list, and it is what makes an appended reviewer
approval from an unknown identity forgeable-in-name-only rather than accepted.

### Invariants and where they live

| Invariant | Enforced by |
|---|---|
| INV-1 one active assignment | `_assert_active_slot_free`, called from `start`, `resume`, and founder proceed-resolution |
| INV-2 one owner, one executor | `create` validates against the manifest; `routing.validate_routing` |
| INV-3 no VERIFIED without evidence | `VerificationReport.passed` requires a non-empty, fully passing set |
| INV-4 fail closed | `state_machine.lookup`, `rule_engine`, adapter error handling, `verifier_error` on any unexpected exception |
| INV-5 append-only hash chain | `audit.seal_next` / `verify_chain` |
| INV-6 halt on broken state | `LifecycleService._guard` → `integrity.verify_state` on every operation |
| INV-7 one successor | `generate_next` returns at most one assignment |

### Active slot vs. current assignment

Two related but distinct ideas, kept apart deliberately:

- **Active slot** (INV-1): `ACTIVE`, `EVIDENCE_SUBMITTED`, `VERIFYING`. This is the
  execution slot, and at most one assignment may occupy it.
- **Current assignment**: the above plus `VERIFIED` and `REJECTED`. An assignment
  awaiting approval or awaiting a fix is still the thing you are working on.

Commands like `complete` and `verify` default to the *current* assignment, which is
what makes them ergonomic without weakening INV-1.

### Packs are data

Packs are declarative YAML with no executable code. Every extension point is
additive: a pack can raise a classification, add a governed trigger, or add an
escalation trigger, but there is no representation for removing one.

Classification is **monotonic**: the project default is the floor, every rule is
evaluated, and the maximum severity wins. Returning on the first rule that fired
was a defect — a pack marking a work type REVIEWED could pull an assignment below
a GOVERNED project default, or below a level the owner had raised it to.

`template_binding.py` refuses any template that tries to set `id`, `state`, or
`origin_template` — a pack cannot mint an identifier or pre-approve itself.

### Determinism

Several choices exist purely to keep the repository deterministic:

- Clock and identity are injected, never read inline.
- YAML is dumped with fixed key order and atomic writes, so re-saving an unchanged
  value produces a byte-identical file and `git diff` on `.projectos/` shows only
  real changes.
- Next-assignment resolution is a pure function of state plus pack.
- Dependency topological ordering breaks ties by identifier.

### Repository adapters

The `local-git` adapter reads committed history through `git`, so evidence reflects
what was committed rather than what happens to be in the working tree. It declares
`pr`, `ci`, and `artifacts` as `False`; rules needing those fail closed with a
message naming the capability.

There is no working-tree fallback. An earlier version fell back to plain filesystem
existence whenever git could not answer, which meant a directory that was not a
repository at all reported untracked files as evidence. Absence of a repository is
an `AdapterError`, not an absence of evidence — conflating the two is fail-open.

The GitHub adapter is spec phase P4. Rather than omit it, this phase ships
`UnavailableGitHubAdapter`, which declares no capabilities and raises on every
query. A manifest configured for `github` therefore fails closed with an actionable
message instead of silently degrading to weaker evidence than the acceptance
criteria asked for.

## Testing strategy

479 tests, organised by the guarantee each defends:

| File | Focus |
|---|---|
| `test_regressions_p1_1.py` | One test per P1.1 audit defect; each verified to fail against the pre-fix code |
| `test_regressions_p1_2.py` | P1.2 contract completion; tests labelled `@REGRESSION` / `@CONTROL` by measured pre-fix outcome |
| `test_regressions_p1_6.py` | P1.6 integrity remediation; `@REGRESSION` blocker fixes + `@MUTATION` guards for the eight P1.4 survivors |
| `test_state_machine.py` | Transition coverage against a hand-written spec table, including every illegal combination |
| `test_audit.py` | Hash chain against realistic tampering — edit, delete, reorder, forge |
| `test_verification.py` | Fail-closed behaviour and the fabricated-claim guarantee |
| `test_lifecycle.py` | Invariants and the v0.1 acceptance criteria end to end |
| `test_schemas.py` | Schema gates, round-trips, and secret scanning |
| `validation_service` coverage | Reusable validation shared by `validate`, `pack validate`, and pack loading |
| `test_local_git_adapter.py` | Facts from committed history; honest capabilities |
| `test_cli.py` | The exit-code contract |

Every test builds its own repository under `tmp_path` with a pinned clock and known
identity, so nothing depends on the machine's git config, wall clock, or test
ordering.

**Expectations come from outside the implementation.** `test_state_machine.py`
holds the transition table transcribed by hand from spec §7.2 (including the two
blocking rows made normative in §7.2.1). Deriving expectations from `TRANSITIONS`
made the test self-referential: rewiring a destination in the table produced zero
failures, so the component the docstring calls "the frozen core" was the one the
suite verified least. Every production transition must now appear in the
hand-written spec table, in both directions — P1.2 folded the earlier informal
`KERNEL_EXTENSIONS` rows into the normative spec, so no row can be added silently.

## Traceability to v0.1 acceptance criteria

| # | Criterion | Covered by |
|---|---|---|
| 1 | `init` produces a valid `.projectos/` | `test_init_creates_a_valid_projectos_directory` |
| 2 | Second `start` fails with exit 2 | `test_only_one_assignment_may_be_active` |
| 3 | Fabricated report ends REJECTED | `test_fabricated_claim_without_evidence_is_rejected` |
| 4 | Three modes, rule printed | `test_risk_flag_drives_governed_classification` and neighbours |
| 5 | `depends_on` gating | `test_open_dependency_prevents_ready` |
| 6 | Deterministic successor or `NEXT_UNDETERMINED` | `test_next_generation_is_deterministic`, `test_undetermined_next_opens_a_decision_ready_escalation` |
| 7 | Escalation options required; resolution re-drives | `test_escalation_without_options_is_rejected`, `test_escalation_freezes_the_assignment_until_resolved` |
| 8 | Audit verify passes clean, fails after edit | `test_tampered_audit_file_halts_the_kernel`, plus `test_tail_truncation_is_detected` and `test_history_removed_from_an_assignment_file_is_detected` for state files |
| 9 | No CLOSE without human approval | `test_merge_work_always_requires_founder_approval` |
| 10 | Correct briefings; code evidence rejected on document work | `test_code_evidence_on_document_work_is_rejected` |

Criteria 4 and 9 are partially exercised here; full end-to-end coverage of the
GOVERNED merge path depends on the GitHub adapter (P4).

## Known limitations

- **GitHub adapter not implemented** — `pr_merged`, `ci_passed`, and `tests_passed`
  fail closed. Spec phase P4.
- **Identity is trusted locally** — v0.1 accepts local OS/git identity for
  approvals. This is spec risk R-6, consciously accepted for the single-founder
  threat model; signed approvals are a v0.2 item.
- **State files are not auto-committed** — `commit_state` from spec §11 is not
  wired up; commit `.projectos/` alongside your work for now. Note this means
  §8.5's "GitHub history provides secondary tamper evidence" does not hold
  automatically. The `audit_ref` cross-check is the primary defence.
- **Evidence must be committed** — the local-git adapter reads committed history
  only. Work in the working tree is not evidence, by design.
- **Phase is fixed to `foundation`** — multi-phase pipelines are modelled in the
  pack schema but the engine reads only the one phase.
