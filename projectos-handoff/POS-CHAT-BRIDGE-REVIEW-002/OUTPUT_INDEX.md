# Handoff Package Index — POS-CHAT-BRIDGE-REVIEW-002

package_parent_sha: 9ae651ed0ac727caf993e99a9c24a74d89ec8b16   (state described)
package_commit_sha: (this package's own commit — reported separately; a file cannot contain its own commit SHA)
Branch: main
review_question_hash: 2ee6515f3643cd2522054965e5a015a0cc27ed4a354447bf5b5821d605f7eaea

## Upload order into Claude Chat
OUTPUT_INDEX.md is ALWAYS part of the upload package (this file; upload it too, as the manifest of what was sent).
0. OUTPUT_INDEX.md           — this index; always included in the upload package
1. CURRENT_STATE.md          — orientation; read first
2. CANONICAL_MANIFEST.yaml   — what is authoritative (blob-hashed; PO-10/PO-11 proposed)
3. EVIDENCE_INDEX.yaml       — the evidence files + what is UNAVAILABLE
4. DECISION_REGISTER.md      — constraints already fixed
5. OPEN_BLOCKERS.md          — what is stuck (incl. BLK-004 Workspace.yaml)
6. REVIEW_QUESTIONS.md       — the ten committed questions (review_question_hash source)
7. CHAT_REVIEW_REQUEST.md    — the ask; answer only these ten
8. LAST_CHAT_DECISION.md     — empty placeholder; Chat writes verdicts here

Referenced canonical/evidence documents (upload if a question cites them): see EVIDENCE_INDEX.yaml.

## File inventory (git blob sha256; OUTPUT_INDEX.md is NOT self-hashed)
| File (repo-relative) | git blob sha256 |
|---|---|
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/CANONICAL_MANIFEST.yaml | 7300fca529f09b7b8349256315e5e58b7466591a0c5c3c66a50df3f67dcc07fa |
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/CHAT_REVIEW_REQUEST.md | 88ac87982aeb7c241ecea5541fc1b1eccdd19f9c11708879b49478db246bad4d |
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/CURRENT_STATE.md | 28c08696880123017daff2b053f227062274af9c1980abeb665b1ebe76ca4af4 |
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/DECISION_REGISTER.md | 87219731acdc077e741782257631d9dc6ced2b772024cfdb91c1a69698b299e9 |
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/EVIDENCE_INDEX.yaml | f403ffe5da972b8141138aa21b697966fc5440c9bb1a5767de16ccde2aef99db |
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/LAST_CHAT_DECISION.md | 9de33102d9622289ff13daba1d0683dfdc78439d85b5b043ae8e3b67dbe98ca4 |
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/OPEN_BLOCKERS.md | 5bfc39234ac5a3d798d1cdf9a7d13d0a3f04c07a8599cd7ead752caaca5bcc6b |
| projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/REVIEW_QUESTIONS.md | 2ee6515f3643cd2522054965e5a015a0cc27ed4a354447bf5b5821d605f7eaea |

## package_root_hash
ef8ca4c5e8bf7b9962ba9128ac7635963c78dae933fd00946fa0c8f528481515

## Root-hash algorithm (verbatim — reproduce with these exact steps)
Hash stored Git blob bytes only (core.autocrlf=true, so working-tree bytes differ;
per file: git cat-file blob <package_commit_sha>:<path> | sha256sum).

1. List all package files using repository-relative paths.
   (package files = all tracked files under projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/
    at the package commit, EXCLUDING OUTPUT_INDEX.md — it records the root hash and cannot
    hash itself without self-reference.)
2. Sort paths using LC_ALL=C byte ordering.
3. For each file emit exactly:
   <sha256><two spaces><repository-relative-path><LF>
4. Concatenate all emitted lines.
5. package_root_hash = SHA-256 of the concatenated byte stream.

Computed twice independently (index blobs pre-commit, HEAD blobs post-commit) and confirmed equal.

## Staleness / admissibility rule (C-6, fail closed)
- This package describes repository state at package_parent_sha (9ae651ed0ac727caf993e99a9c24a74d89ec8b16).
- The package is anchored at package_commit_sha (parent + exactly one commit).
- A Claude Chat decision is ADMISSIBLE only when, at the moment Cowork registers it,
  repository HEAD == package_commit_sha.
- If HEAD != package_commit_sha: the decision is VOID; the package must be regenerated;
  the root hash recomputed; a new package commit created; and REVIEW-002 re-run.
- Admissibility binds to package_commit_sha, NOT to package_parent_sha.
