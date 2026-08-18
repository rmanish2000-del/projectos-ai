# PROJECTOS Seat — Operating Notes

Practices this seat holds itself to, written here so they survive a session
boundary (SR-1: a practice that lives only in a report expires with the
session). Ordered by assignment REGISTER-RESIDUALS-AND-DUPLICATES item 4.

## Re-read the INBOX before every pickup

**Rule: list `G:\My Drive\AGENT-REPORTS\INBOX` immediately before taking any
assignment — before every pickup, not just before every report.**

Why it exists, on the record: on 2026-08-17 this seat read the INBOX at
19:36, worked the known queue, and picked up REGISTER-RENDERER at ~01:11
without re-listing. A higher-precedence assignment (KEYRING-SMOKE, issued
23:20, explicitly ordering "this takes precedence") had arrived in between
and was not seen until after the lower-precedence work was done. Acting on a
believed queue instead of a re-observed one is DC-1 at the process level.
The work survived; the ordering did not.

Corollaries:

- The filename stamp orders the queue, but the LISTING is the queue — a
  remembered queue is a report about the queue.
- A pickup begins with a claim file (`claimed_by` / `repo_root` /
  `assignment`) written to `G:\My Drive\AGENT-REPORTS\` before any work.
- Oldest first among files carrying this seat's tag or ALL, unless a chat
  routing from the founder orders a specific sequence.

## Companion practices (rulings this seat executes under)

- **Reports go to Drive only** — one line in chat: the filename. Four lines
  in chat only when the Drive write fails, said plainly (founder,
  2026-08-17).
- **Timestamps come from the fleet clock helper**
  (`projectos.infrastructure.fleet_clock`), never typed from belief. For
  Drive-written objects the anchor is Drive's own `createdTime`; local
  writes anchor to the local clock; neither is ever derived from the other
  or from a filename (FIVE-CONTRADICTIONS-RESOLVED item 1).
- **The head of a superseded chain is what the INDEX says** — never mtime,
  never a filename suffix (document amendment doctrine, SWEEP-2 ruling e).
  When the index is stale, the staleness is a finding to report, not a
  license to guess.
- **An unrecognised seat tag is REFUSED, never guessed**
  (SEAT-VOCABULARY rule 2; vocabulary is seven seats).
- **Architectural boundaries route to Chat; only the eight ESCALATE-tier
  acts are the founder's** (FIVE-CONTRADICTIONS-RESOLVED item 3; the eight
  live in `src/projectos/domain/tiers.py` as ratified).
