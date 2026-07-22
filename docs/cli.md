# ProjectOS CLI reference

Every command is a thin wrapper over exactly one kernel operation. Exit codes are
deterministic so agents can branch on them without parsing prose.

## Global options

| Option | Meaning |
|---|---|
| `--repo PATH` | Repository root. Default: discovered by walking up from the working directory to the nearest `.projectos/`. |
| `--identity ID` | Acting identity for this command. Default: `PROJECTOS_IDENTITY`, then `git config user.email`, then the OS user. |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Rule failure — verification rejected |
| `2` | Invariant or validation error |
| `3` | Escalation required — a founder decision is pending |

---

## `projectos init`

Scaffold `.projectos/` with a manifest and the bundled `software-core` pack.

```bash
projectos init \
  --project-id my-project \
  --name "My Project" \
  --founder-id you@example.com \
  --founder-name "Your Name" \
  [--description "..."] \
  [--adapter local_git|github] \
  [--default-branch main] \
  [--github-owner ORG --github-repo REPO] \
  [--force]
```

`--project-id` must be kebab-case. `--force` overwrites an existing manifest;
without it, re-running `init` on a live project is refused so its assignments and
audit chain cannot be orphaned.

The `github` adapter is not implemented in this phase and fails closed on every
evidence query. Use `local_git` unless you are on a later phase.

## `projectos workspace init`

Bootstrap a local-first **workspace** — the directory that holds many ProjectOS
projects and the shared assets they draw on. This is a layer above the per-project
`.projectos/` that `init` scaffolds.

```bash
projectos workspace init [PATH] [--name NAME] [--force]
```

`PATH` is the workspace root (default `./Workspace`), created if missing. `--name`
sets the workspace name (default: the directory name).

The generator lays down:

```
<PATH>/
  Workspace.yaml            registers projects and shared pack locations
  ProjectOS/
  Shared/
    Packs/                  rapid-build, software, trading, renewable,
                            legal, website, documentation
    Templates/  Policies/  Prompts/  Knowledge/
  Projects/
    ExampleProject/project.yaml
```

Each pack skeleton contains `README.md`, `project_rules.yaml`,
`assignment_rules.md`, `quality_gates.yaml`, `deployment.md`, and `templates/`.

**Idempotent.** Running it again creates only what is missing and preserves every
existing file — a second run is a visible no-op (`created: 0`). `--force` overwrites
the generated starter files. Always exits `0`. Writes only under `PATH`; no network.

## `projectos workspace add-project`

Register a project in an existing workspace. Idempotent; writes only under the
workspace.

```bash
projectos workspace add-project <name> [--workspace PATH] [--pack rapid-build] \
  [--project-id ID] [--description "..."] \
  [--repo PATH | --repo-remote URL [--repo-branch BRANCH]] [--force]
```

Appends the project to `Workspace.yaml` and writes `Projects/<name>/project.yaml`.
The project's repository is recorded either as a local `--repo` path (which the
bridge also hosts the kernel in) or as `--repo-remote` metadata for a repository
that lives elsewhere and is not written into. `--pack` names the pack backing the
project (default `rapid-build`, the one pack that ships loadable).

## `projectos workspace init-project`

Scaffold a registered project's ProjectOS kernel from its workspace pack, so the
kernel can run against it. Idempotent — it will not overwrite an existing
`.projectos/` without `--force`.

```bash
projectos workspace init-project <name> [--workspace PATH] \
  --founder-id <id> --founder-name <name> [--force]
```

Writes `.projectos/` into the project's repository (its `--repo` path, or the
project directory) and installs the workspace pack. Afterwards
`projectos --repo <repository> next` operates the project normally.

## `projectos workspace list`

Read-only status for every registered project.

```bash
projectos workspace list [--workspace PATH]
```

Shows each project's id, pack, repository path, whether its kernel is initialised,
and its active assignment.

## `projectos workspace discover`

Discover projects under the workspace's `Projects/` area, validate each, and report
its registration status. The standard onboarding mechanism: drop a project directory
into the workspace and let discovery find and register it, rather than running
`add-project` by hand for each one.

```bash
projectos workspace discover [--workspace PATH] [--register] [--dry-run]
```

The walk is depth-bounded (never recurses infinitely), visits directories in sorted
order, treats a directory containing `project.yaml` as a candidate and a boundary
(its contents are not scanned for nested projects), and skips dot-directories and
common vendor directories (`node_modules`, `venv`, …). Each candidate is classified
as **registered**, **unregistered**, **invalid** (its `project.yaml` failed
validation), **duplicate-identifier**, or **duplicate-repository**.

Report-only by default and under `--dry-run`. With `--register` (and not `--dry-run`)
it registers the valid, unregistered candidates: it appends each to `Workspace.yaml`
and never overwrites an existing registration or a discovered project's own
`project.yaml`. `--dry-run` overrides `--register`, so a dry run always leaves state
untouched. Re-running after a register is a visible no-op (idempotent).

## `projectos workspace status`

Print a concise, deterministic, read-only **operational status**: is the workspace
safe to operate, what is incomplete, and what is broken. It is the operational
counterpart to `handoff` (and derives from the same read-model), not a duplicate of
it — where `handoff` reports full context, `status` interprets it into a condition,
counts, and an actionable problem list.

```bash
projectos workspace status [--workspace PATH] [--project ID|NAME]
```

Reports an overall **condition** — `healthy`, `warning`, or `failure` — plus counts
(registered projects, initialised projects, projects with an active assignment,
available configured packs, integrity failures, warnings), a per-project line in
stable identifier order (initialised state, active assignment, repository-metadata
availability, pack availability, integrity), and the problems behind the condition.
`--project` marks one project as the focus; counts stay workspace-wide.

Severity: **failure** is invalid or broken state that makes operation unsafe — a
malformed workspace/project manifest, a broken audit chain, an unresolved focus;
**warning** is valid-but-incomplete — an uninitialised kernel, a missing configured
pack directory, an unavailable pack; **healthy** is neither. The command is
**read-only** (no mutation, registration, assignment generation, repository write, or
network) and exits `3` on a failure condition, `0` otherwise (a warning is still
operational). A missing workspace fails closed; a malformed manifest is reported *as*
a failure condition rather than crashing, so `status` always prints a status.

## `projectos workspace doctor`

Run deterministic, read-only **diagnostics** and print safe, advisory remediation
guidance. Where `status` reports a condition and a flat problem list, `doctor`
re-presents the same read-model as named checks — each with a stable id, a
`PASS`/`WARN`/`FAIL`/`SKIP` result, the affected scope, a concise explanation, and,
where one genuinely exists, a suggested action referencing only verified ProjectOS
commands. It runs no new collection: it derives from the P8 status read-model (which
reuses the P7 handoff), so it never re-reads the workspace independently.

```bash
projectos workspace doctor [--workspace PATH] [--project ID|NAME]
```

Checks: `workspace-manifest` (manifests resolve and validate; unique identifiers and
repositories — a malformed manifest, duplicate id, or duplicate registration fails
here), `project-focus`, `configured-packs` (each configured pack directory present),
and per project `project-identifier`, `kernel-initialised`, `project-pack`,
`audit-integrity` (audit chain and assignment-state readable and consistent), and
`repository-metadata`. `--project` narrows the per-project checks to one project;
workspace checks always run.

Diagnostics are ordered deterministically: failures first, then warnings, passes, and
neutral skips; within a result, workspace-scoped before project-scoped, projects by
stable identifier, then by check id. Suggested actions are **advisory only** — they
reference existing read-only or scaffolding commands (`projectos workspace
init-project`, `projectos workspace status`, `projectos pack validate`, `projectos
history --verify`), never a destructive or unverified command, and never a repair the
CLI does not actually provide (there is no `--fix`). The command is **strictly
read-only** (no manifest write, registration, initialisation, assignment generation,
audit change, or network) and exits `3` on a `FAIL` outcome, `0` for `PASS` or `WARN`
(a warning is still operational). A missing workspace fails closed.

## `projectos workspace queue`

Print a deterministic, read-only **assignment queue**: for each project, the
assignments its kernel has persisted, partitioned by state. ProjectOS Core already
persists assignments (`.projectos/assignments/*.yaml` with a state-machine status and
an active-slot pointer); this command adds no new store — it is a *view* that reuses
the P7 handoff resolution and reads each project's existing
`kernel.assignments.list_all()`.

```bash
projectos workspace queue [--workspace PATH] [--project ID|NAME]
```

Each project's assignments are bucketed into **active** (the INV-1 active-slot
states — active, evidence-submitted, verifying), **ready**, **blocked** (blocked or
escalated), **completed** (closed), and **other** (draft, verified, rejected,
cancelled — each carrying its exact status, so the partition is total and nothing is
dropped). A header line aggregates the counts across the workspace. `--project`
narrows to one project by id or name.

Ordering is deterministic: projects by stable identifier, assignments by their
zero-padded id within each bucket; no timestamps. The command is **read-only** (it
neither generates nor mutates assignments — generation stays with `projectos next`)
and exits `3` when a project's persisted state could not be read, `0` otherwise (a
blocked assignment is normal queue state, not a failure). A missing workspace or an
unresolved `--project` fails closed.

## `projectos workspace handoff`

Print a deterministic, read-only **handoff** — the minimum repository-backed context
a fresh AI coding session needs to continue ProjectOS work safely, so the brief is
derived from committed contracts instead of assembled by hand.

```bash
projectos workspace handoff [--workspace PATH] [--project ID|NAME]
```

Resolves the workspace and reports, for each registered project (ordered by stable
identifier): its id and registration name, pack, declared repository metadata
(adapter / remote / branch / path), the kernel location and whether it is
initialised, the current in-flight assignment, and the audit-chain integrity result.
`--project` focuses on one project by its `project.id` (or registration name),
project-first.

Every value comes from an existing contract; nothing is fabricated. Missing optional
information is shown explicitly as `unavailable` with a reason (e.g. no repository
declared, kernel not initialised, no assignment in flight). Output is deterministic —
stable ordering, no timestamps, no environment noise — so identical state produces
identical output.

The command is **read-only**: it never mutates the workspace, registers a project,
generates an assignment, writes to a repository, or touches the network. A malformed
workspace or project manifest fails closed (the error names the offending file); a
per-project state or broken-chain fault is reported against that project as
`integrity FAILURE` and surfaced through exit code `3`, without blanking the rest of
the handoff.

## The rapid-build pack

`workspace init` ships one **loadable** pack, `rapid-build` (the others are
skeletons for a pack author to fill in). It is the fast, minimal domain: a
`foundation` pipeline of `define-task` → `build-task`, both FAST (the owner closes).
`projectos pack validate Shared/Packs/rapid-build` passes, and a project created
from it generates assignments through the normal `next` flow.

### Workspace manifest schemas

The workspace is read back into typed values by the Workspace Runtime loader
(`infrastructure/workspace_manifest.py`), validated against bundled JSON Schemas.
Every field beyond the required ones is optional, so a workspace created by an
earlier `workspace init` loads unchanged.

`Workspace.yaml` — `workspace_manifest.schema.json`:

| Field | Required | Meaning |
|---|---|---|
| `schema_version` | yes | Must be `1`. |
| `workspace.name` | yes | Workspace name. |
| `projectos` | no | Path to the workspace ProjectOS directory. |
| `shared.{packs,templates,policies,prompts,knowledge}` | no | Paths to shared asset directories. |
| `packs[]` | no | Available packs, each `{name, path}`. |
| `projects[]` | no | Registered projects, each `{name, path}`. |

`Projects/<name>/project.yaml` — `project_manifest.schema.json`:

| Field | Required | Meaning |
|---|---|---|
| `schema_version` | yes | Must be `1`. |
| `project.id` | yes | Kebab-case project id. |
| `project.name` | yes | Project name. |
| `project.description` | no | One-line description. |
| `pack` | no | The pack this project uses. |
| `repository` | no | The project's repository — `{adapter, remote, default_branch, path}`, all optional. A repository is a property of the project; the runtime resolves the workspace, then its projects, then each project's repository. |

Loading fails closed: a manifest that violates its schema, is not a YAML mapping,
or breaks a cross-field rule (a duplicate project or pack name) raises a validation
error rather than being partially accepted. Loading is read-only — it never writes,
activates, or touches the ProjectOS kernel.

## `projectos validate`

Check the manifest, packs, version compatibility, and assignment state. **Changes
nothing.**

```bash
projectos validate
```

Reports every finding in one run rather than stopping at the first. Errors fail
validation; warnings do not.

| Result | Exit |
|---|---|
| No errors (warnings allowed) | `0` |
| One or more errors | `2` |

Checks performed: manifest schema and cross-field rules, pack schema and internal
referential integrity, pack version constraints in both directions (§10.1.1),
template binding, assignment ownership and routing, dependency references, INV-1
across the registry, and a secret scan of every state file it reads.

## `projectos pack validate`

Check a pack directory without installing or activating it.

```bash
projectos pack validate path/to/pack
```

Validates the pack manifest schema, required fields, evidence-rule definitions
(by binding every template exactly as `next` would), workflow and transition
references, authority declarations, the pack version, ProjectOS compatibility
constraints, and internal referential integrity.

Exit codes as for `validate`. The command never writes, installs, or activates.

## `projectos status`

Project summary, current assignment, blockers, and open founder decisions.

```bash
projectos status [--brief]
```

`--brief` also prints the current assignment's executor briefing.

Returns `3` when a founder decision is open, otherwise `0`.

## `projectos next`

The "what do I do now" command. Behaviour depends on the state:

| State | What happens |
|---|---|
| Something is active | Reports it and stops (INV-1) |
| A `READY` assignment exists | Starts it and prints the briefing |
| The current assignment is `REJECTED` | Resumes it, carrying the rejection reasons into a fresh briefing |
| The last assignment closed | Generates the successor, classifies it, and starts it |
| No successor can be determined | Opens a `NEXT_UNDETERMINED` escalation, returns `3` |

```bash
projectos next [--dry-run]
```

`--dry-run` shows what would be generated without writing state.

Resolution order is the spec's: the closed assignment's explicit `next` block,
then the pack pipeline for the phase, then escalation.

## `projectos verify`

Ingest the completion claim and evaluate every acceptance criterion against
repository facts.

```bash
projectos verify [ASSIGNMENT_ID] [--report FILE]
```

Verifying an `ACTIVE` assignment stages the claim first (`ACTIVE →
EVIDENCE_SUBMITTED → VERIFYING`), then evaluates. A claim is never evidence: an
absent `--report` verifies exactly as harshly as a detailed one.

Prints a per-criterion report. Failures are collected, not short-circuited, so one
run tells you everything that is missing.

Returns `0` when verified, `1` when rejected.

### Completion report format

```yaml
summary: "Implemented the kernel skeleton and added tests."
evidence:
  - class: commit          # commit | pr | ci_run | test_report | artifact | approval
    reference: a1b2c3d4
    note: "kernel skeleton"
  - class: pr
    reference: "42"
```

Reports are untrusted input: parsed against a strict shape, never executed, and
never able to trigger a transition beyond `submit`.

## `projectos complete`

Record an approval. Closes the assignment once the workflow mode's required roles
have all approved.

```bash
projectos complete [ASSIGNMENT_ID] [--role owner|reviewer|founder] [--attest]
```

Required roles per mode:

| Mode | Required to close |
|---|---|
| `fast` | owner |
| `reviewed` | reviewer (must not be the assignment's owner) |
| `governed` | reviewer **and** founder |

`merge`, `deployment`, and `external_action` work always additionally requires
founder approval — the kernel has no code path that merges or deploys.

`--attest` records a human attestation instead of an approval, satisfying a
`human_attestation` rule for facts outside the repository. Attestations are
audit-logged with the attesting identity.

## `projectos block`

```bash
projectos block [ASSIGNMENT_ID] --reason "..."
projectos block [ASSIGNMENT_ID] --unblock
```

`--reason` is mandatory: a blocker without a stated cause cannot be cleared by
anyone else. `--unblock` returns the assignment to `READY`, and refuses while any
dependency is still open.

## `projectos founder`

The founder decision queue.

```bash
projectos founder list
projectos founder escalate --summary "..." --option "ID|DESCRIPTION|CONSEQUENCE" ...
projectos founder resolve E-0001 --decision O1 [--outcome proceed|cancel|rescope]
```

Escalations require at least two options, each with a consequence. The kernel
rejects anything less — the founder's queue carries decisions, not commentary.

```bash
projectos founder escalate \
  --summary "The pack pipeline has no template for the integration phase." \
  --trigger next_undetermined \
  --option "O1|Extend the pipeline|Generation resumes automatically." \
  --option "O2|Author the assignment by hand|Immediate progress; pipeline stays incomplete." \
  --recommend O1
```

Only the manifest's founder may resolve. Resolution re-drives the state machine:
`proceed` returns the assignment to its pre-escalation status, `cancel` and
`rescope` cancel it.

`list` and `escalate` return `3`; `resolve` returns `0`.

## `projectos history`

```bash
projectos history [--assignment A-0001] [--limit N] [--verify]
```

`--verify` re-walks the SHA-256 hash chain. A broken chain returns `3` and halts
the kernel — every other command checks the chain before writing, so tampering
surfaces on the next operation rather than at review time.

---

## Pack version compatibility

A pack declares two versions, and both are enforced before it can be used:

```yaml
# pack.yaml
version: 0.1.0                       # this pack's own version
requires_projectos: ">=0.1.0,<0.2.0" # the kernel versions it supports
```

```yaml
# .projectos/manifest.yaml
packs:
  - name: software-core
    version: ">=0.1.0 <0.2.0"        # which pack versions this project accepts
```

- Constraints are PEP 440. Whitespace between clauses is accepted; `^1.0.0` and
  `~>1.0` are rejected rather than approximated.
- A malformed version or unsupported constraint is a hard error.
- Prereleases are excluded unless the constraint names one: `>=0.1.0` does not
  accept `0.2.0rc1`, but `>=0.2.0rc1` does.
- `requires_projectos` is optional; when absent, `validate` warns. When present
  and unsatisfied, loading fails closed.
- Enforcement lives on the loading path, so `next`, `status`, and every other
  command that consumes pack data is covered — not just the validation commands.

---

## A full cycle

```bash
git init -b main .
projectos init --project-id demo --name Demo \
  --founder-id you@example.com --founder-name "You"

projectos next                      # A-0001 generated, classified, started
# ... do the work, commit it ...
projectos verify                    # exit 1 while evidence is missing
git add -A && git commit -m "add spec"
projectos next                      # resume the rejected assignment
projectos verify                    # exit 0
projectos complete --role owner     # A-0001 CLOSED
projectos next                      # A-0002 generated from the pipeline
projectos history --verify          # chain intact
```
