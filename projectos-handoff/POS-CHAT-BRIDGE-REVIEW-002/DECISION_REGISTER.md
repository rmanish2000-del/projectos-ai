# Founder Decision Register — Active

Generated: 2026-07-28T17:00:30+00:00
Describes state at package_parent_sha: 9ae651ed0ac727caf993e99a9c24a74d89ec8b16
Source of truth: repository documents cited under Evidence. Conversation memory is NOT evidence.
Identifier note (fixes REVIEW-001 F-14): assignment decisions D-001/D-002 are registered here as FD-001/FD-002; the FD- prefix is canonical in this register.

| ID | Decision | Date | Status | Evidence (repo path + SHA) | Affects |
|---|---|---|---|---|---|
| FD-001 (= D-001) | packs/rapid-build/ pack definitions -> TRACK (files are `*.md` after rename from `*.md.txt`) | 2026-07-28 | Active | .gitignore + packs/rapid-build/*.md @ ceda197 | pack library |
| FD-002 (= D-002) | .projectos/ -> SPLIT: policy tracked at /policies/, runtime ignored | 2026-07-28 | Active | policies/policies.yaml @ 8ce7f65 | policy, gitignore |
| FD-003 | TradeOS-AI registered; workflow_mode = governed | 2026-07-24 | Active | docs/workspace-registry.md @ 73e69ea | workspace registry |
| FD-004 | SensexPilot is a component inside C:/TradeOS-AI, NOT a separate repo | 2026-07-24 | Active | docs/workspace-registry.md @ 73e69ea | workspace registry |

## Corrections applied in this register
- **F-15 (FD-001 extension):** decision text now reads `*.md` (the committed reality), noting the rename from the `*.md.txt` artefact.
- **F-12 / F-02 reconciliation (former FD-005):** the 'ProjectOS kernel NOT initialised inside C:/TradeOS-AI' item was previously recorded as an Active *decision* (FD-005) AND as blocker BLK-002. A pending hold is a blocker, not a settled decision. It is now tracked ONLY as **BLK-002** (OPEN_BLOCKERS.md) and removed from the active-decision list.

## Superseded decisions
| ID | Decision | Superseded by | Date |
|---|---|---|---|
| — | none in repository | — | — |

## Asserted in conversation but NOT in the repository — Reported (unverified), not decisions
- PO-10 / PO-11 ratification — no approval evidence found; both classified `proposed` (C-2).
