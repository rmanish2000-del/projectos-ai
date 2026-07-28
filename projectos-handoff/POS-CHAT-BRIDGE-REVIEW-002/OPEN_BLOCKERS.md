# Open Blockers

Generated: 2026-07-28T17:00:30+00:00
Terminology (fixes REVIEW-001 F-11): "blocker" here = WORK blocked. The manifest's
`document_status_blocked` is a DOCUMENT status and is unrelated.

| ID | Blocker | Blocks | Type | Owner | Since | Evidence | Needed to clear |
|---|---|---|---|---|---|---|---|
| BLK-001 | REVIEW-002 not yet run against a committed package | admissible governance decisions | founder-decision | Founder | 2026-07-28 | this package | Founder/Cowork run REVIEW-002 on package_commit_sha |
| BLK-002 | ProjectOS-vs-TAO ownership inside C:/TradeOS-AI undecided (kernel init held) | TradeOS kernel init; migration | founder-decision | Founder | 2026-07-24 | docs/workspace-registry.md | Founder decision: take over / mirror / coexist with TAO |
| BLK-003 | /Projects/ ignore excludes EduOS-AI authored architecture docs | corpus-boundary completeness | founder-decision | Founder | 2026-07-28 | .gitignore; C:/EduOS-AI own repo | Founder: confirm EduOS boundary or represent it here |
| BLK-004 | Workspace.yaml Registration-State Authority (see below) | reproducible registration state | founder-decision | Founder | 2026-07-28 | Workspace.yaml (gitignored); docs/workspace-registry.md | Founder rules Option A / B / C below |
| BLK-005 | Authoritative pack root undecided: Shared/Packs/ vs packs/ | pack resolution; domain-logic location | founder-decision | Founder | 2026-07-28 | Shared/Packs/** (38) vs packs/rapid-build/** (2) | Founder names the authoritative pack root |

## BLK-004 — Workspace.yaml Registration-State Authority (C-7)
Evidence: `Workspace.yaml` is gitignored (`/Workspace.yaml`), `content_type: decision`, and
encodes which projects and packs are registered. Registration decisions currently live only
in ignored, machine-local state (REVIEW-001 F-06). Founder options (no decision made here):
- **Option A** — Workspace.yaml is generated runtime state and remains ignored; a tracked canonical registration source must exist elsewhere.
- **Option B** — Workspace.yaml is decision-bearing canonical state and must be tracked.
- **Option C** — split tracked registration decisions from generated runtime state.

## Not blockers
- LAST_CHAT_DECISION.md empty — by design (Chat writes it).
