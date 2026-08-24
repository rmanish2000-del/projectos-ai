# FOUNDER-QUEUE — the one place founder decisions wait

Convention for `G:\My Drive\AGENT-REPORTS\FOUNDER-QUEUE.md`, the single
rolling file where the CHAT-AUTO-RESTOCK seat parks everything only the
founder can decide. The founder reads ONE file instead of hunting decision
lines across reports. Ordered by assignment CHAT-AUTO-RESTOCK-SEAT
(founder GO, 2026-08-18).

## The contract

- **One file, rolling, append-only for seats.** The restocker (and any
  seat, in time) APPENDS lines; nothing but the founder resolves them.
  Seats never delete, reorder, or rewrite an existing line — the queue's
  history is part of its value.
- **One line per item**, format:
  `- [ ] <stamp IST> · <FROM> · <what needs deciding, one sentence> · source: <report/assignment filename>`
- **The founder resolves by ticking** (`- [x]`) and optionally adding
  `→ <ruling>` on the same line, or by issuing an assignment that
  supersedes the question. A ticked line is resolved; the restocker never
  re-adds it.
- **No duplicates:** before appending, the writer checks the line is not
  already present (same source + same question = same line). A question
  re-raised gets its original line, not a twin.
- **What belongs here:** ESCALATE-tier asks (the ratified eight), graph or
  register changes, ratifications, verify-mismatches (a report whose
  claims did not check out), backlog items that cannot be made concrete
  without a decision, and anything a wake refused under its guardrails.
- **What does NOT belong here:** ordinary seat questions answerable by
  Chat (those go in reports' DECISION NEEDED), and work items (those go
  to INBOX or the backlog pool).

The rolling file is seeded once with its header; from then on it only
grows and gets ticked. If it is ever missing, the restocker recreates it
from this convention and notes that in its pass report.
