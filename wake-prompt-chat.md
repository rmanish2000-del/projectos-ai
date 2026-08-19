# WAKE — CHAT-AUTO-RESTOCK deterministic contract

Version: wake-prompt-chat v2 · source assignment RESTOCKER-GUARDRAILS-CLOSED.

This file is documentation, not a model prompt. `scripts/wake.ps1` detects the
`CHAT-AUTO-RESTOCK` seat and invokes
`projectos.infrastructure.chat_auto_restock` directly. No Claude/Codex session
is started, so report text never shares an instruction context with an agent.
There is no claimed inheritance from `wake-prompt.md`; the executable module is
the complete contract.

## Structural write boundary

The engine may write only below the configured `AGENT-REPORTS` directory:
`INBOX/`, `DONE/`, `FOUNDER-QUEUE.md`, `CHAT-RESTOCK-MARKER.json`, and its own
pass report. It has no operation that merges, deploys, ratifies, changes a
graph/register, edits a repository, touches credentials, or issues work to the
`CHAT-AUTO-RESTOCK` seat. Git use is limited to fetching an origin ref and
read-only object/ancestry checks.

## Machine report contract

A finished report is data and contains exactly six non-empty lines:

```text
REPO: owner/repository@branch
IST: YYYY-MM-DD HH:MM IST
DONE: assignment=ASSIGNMENT-ID; commit=40-lowercase-hex; files=path|path
ANSWERS: concise result
BLOCKS: NONE
DECISION NEEDED: NONE
```

The filename must be `YYYY-MM-DD_HHMM_SEAT_ASSIGNMENT-ID.md`. The seat,
assignment, repository and branch must be configured. The engine fetches the
named origin branch, proves the cited commit is its ancestor, and proves every
named file exists in that commit. Any malformed, blocked, unverifiable or
ambiguous report is parked in `FOUNDER-QUEUE.md`; its INBOX file is untouched.
Report content is never executed, interpolated into commands, or copied into an
assignment.

## Marker and restock contract

Reports are handled in filename order. Before a side effect the engine journals
one `inflight` report with its SHA-256; after the idempotent DONE move or park it
records that exact digest as processed. A crash resumes the inflight item before
later work. Changed processed/inflight content fails closed.

An idle seat can receive only a recognized backlog item for a configured repo.
Known ESCALATE/governance terms and unknown work profiles emit no assignment and
are parked. A valid item expands into objective, scope, out-of-scope, report and
stop sections. The restocker seat is absent from the configured seat set and the
writer rejects it again defensively.
