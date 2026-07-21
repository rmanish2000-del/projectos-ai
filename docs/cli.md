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
