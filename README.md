# ProjectOS AI

A repository-driven orchestration kernel that manages AI-and-human project work as
a sequence of **verified** assignments.

ProjectOS answers four questions at all times:

1. What is the one active assignment right now?
2. Who owns it, and which agent executes it?
3. Is it verifiably complete, according to repository evidence?
4. What is the next assignment, or what founder decision blocks it?

This repository implements **P1 — ProjectOS Core**, the domain-neutral kernel
defined in [`PROJECTOS_V0_1_FOUNDATION_SPEC.md`](PROJECTOS_V0_1_FOUNDATION_SPEC.md).

## The central idea

An agent reporting "done" is a *claim*, not evidence. A claim moves an assignment
to `EVIDENCE_SUBMITTED` and no further; the repository decides the rest. Every
acceptance criterion carries a machine-checkable rule, and the kernel evaluates
those rules against git facts. Verification never consults conversation content,
agent self-reports, or model judgment.

Everything fails closed. An adapter error, a missing capability, an ambiguous
result, a broken audit chain, or an unknown state transition all block; none of
them degrade into success.

## Install

```bash
python -m pip install -e ".[dev]"
```

Requires Python 3.11+ and `git` on `PATH`.

## Quick start

```bash
cd your-project
git init -b main .

projectos init \
  --project-id my-project \
  --name "My Project" \
  --founder-id you@example.com \
  --founder-name "Your Name"

projectos validate  # confirm the repository is well formed (changes nothing)
projectos next      # generate, classify, and activate the first assignment
projectos status    # where things stand
```

Do the work the briefing describes, commit it, then:

```bash
projectos verify                    # evaluate acceptance criteria against the repo
projectos complete --role owner     # record approval; closes when all are in
projectos next                      # generate the successor
```

## Commands

| Command | What it does |
|---|---|
| `projectos workspace init [PATH]` | Bootstrap a local-first multi-project workspace tree (idempotent) |
| `projectos init` | Scaffold `.projectos/` with a manifest and the `software-core` pack |
| `projectos validate` | Check manifest, packs, versions, and state. Changes nothing |
| `projectos pack validate <path>` | Check a pack directory without installing it |
| `projectos status` | Project, current assignment, blockers, open founder decisions |
| `projectos next` | Activate the ready assignment, resume a rejected one, or generate the successor |
| `projectos verify` | Ingest the completion claim and evaluate every acceptance criterion |
| `projectos complete` | Record an approval or attestation; closes when the mode's roles are satisfied |
| `projectos block` | Block an assignment (`--reason`) or clear it (`--unblock`) |
| `projectos founder` | `list`, `escalate`, `resolve` — the founder decision queue |
| `projectos history` | Read the audit log, or `--verify` the hash chain |

Full reference: [`docs/cli.md`](docs/cli.md).

### Exit codes

Deterministic, so agents can branch on them without parsing prose:

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Rule failure — verification rejected |
| `2` | Invariant or validation error |
| `3` | Escalation required — a founder decision is pending |

## What lives where

```
.projectos/
  manifest.yaml              project manifest
  packs/<name>/              installed packs (declarative YAML only)
  assignments/A-NNNN.yaml    one file per assignment
  active.yaml                pointer to the active assignment
  escalations/E-NNNN.yaml    founder-decision records
  audit/YYYY-MM.ndjson       append-only, hash-chained audit log
```

Everything ProjectOS knows lives under `.projectos/`. Deleting that directory
removes ProjectOS from a repository with zero residue — that is the portability
guarantee, and the kernel writes nowhere else.

A **workspace** (created by `projectos workspace init`) is the local-first layer
above individual projects — it holds `Shared/` packs and assets and a `Projects/`
registry. It is pure scaffolding: the generator writes only under the workspace
root and never touches the kernel.

## Architecture

Clean Architecture, dependencies pointing inward only:

```
cli/  ──────────►  application/  ──────────►  domain/
                        ▲                        ▲
                        └──── infrastructure/ ───┘
                             (implements ports)
```

- **`domain/`** — pure rules and immutable values. No I/O, no clock, no globals.
- **`application/`** — use cases and the port Protocols they depend on.
- **`infrastructure/`** — files, schemas, adapters, and the composition root.
- **`cli/`** — argument parsing and formatting. Every command maps 1:1 onto one
  kernel operation.

Details and rationale: [`docs/architecture.md`](docs/architecture.md).

## Scope of this phase

Implemented: manifest and assignment loaders, the state machine, assignment
lifecycle, evidence model, dependency graph, next-assignment engine, agent router,
founder escalation, verification engine, the CLI, JSON schemas, validation, tests,
and these docs.

Pack version compatibility is enforced: a pack declares `requires_projectos` (a
PEP 440 constraint) and the manifest constrains the pack's own `version`. Both are
checked on the loading path, so activation cannot bypass them.

Not implemented here, by design: the GitHub adapter (`pr_merged`, `ci_passed`,
`tests_passed` rules), which is spec phase P4. A manifest configured for the
`github` adapter fails closed with a message naming the missing capability rather
than silently falling back to weaker local-git evidence.

Also out of scope for this phase: any UI, web service, CI integration, editor
extension, MCP server, or direct Claude/ChatGPT integration.

## Development

```bash
python -m pytest      # 479 tests
python -m ruff check .
python -m mypy
```
