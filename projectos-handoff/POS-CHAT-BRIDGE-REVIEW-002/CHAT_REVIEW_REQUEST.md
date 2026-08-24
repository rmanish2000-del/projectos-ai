# Claude Chat Review Request — POS-CHAT-BRIDGE-REVIEW-002

| Field | Value |
|---|---|
| Assignment ID | POS-CHAT-BRIDGE-REVIEW-002 |
| Requester | Founder (via POS-CC-CHAT-BRIDGE-CORRECTION-002) |
| Date | 2026-07-28 |
| Decision authority | Founder ratifies; Claude Chat is the independent architecture & governance reviewer within delegated scope. A verdict is registrable only after Cowork registers it (R3). |
| Required evidence | See EVIDENCE_INDEX.yaml (docs/workspace-registry.md, .gitignore, policies/policies.yaml, POS-COW-CHAT-BRIDGE-001-SPEC.md; PO-10 approval and CI evidence marked UNAVAILABLE). |
| Required output | For each of the ten committed questions: a verdict labelled Verified / Inferred / Missing, written to LAST_CHAT_DECISION.md stamped with package_commit_sha, package_root_hash and review_question_hash. |
| Stopping point | Chat answers ONLY the ten committed questions; makes no repository assertion; creates no assignment; writes verdicts to LAST_CHAT_DECISION.md. |
| Questions committed | Questions committed at 9ae651ed0ac727caf993e99a9c24a74d89ec8b16 for REVIEW-002 (file: projectos-handoff/POS-CHAT-BRIDGE-REVIEW-002/REVIEW_QUESTIONS.md). |
| review_question_hash | 2ee6515f3643cd2522054965e5a015a0cc27ed4a354447bf5b5821d605f7eaea (SHA-256 of the committed REVIEW_QUESTIONS.md git blob) |

## Admissibility of REVIEW-001
REVIEW-001 was conducted without committed questions and is ADVISORY ONLY. It is not
admissible as governance evidence. These questions are committed for REVIEW-002 only and
did not govern REVIEW-001.

## The ten questions Claude Chat must review (verbatim, committed)
Answer only these. Refuse any question whose evidence was not delivered (a refusal is a
valid, auditable output).

1. Does the package provide enough verified repository context for Claude Chat to make architecture and governance decisions without inventing ProjectOS facts?

2. Are the canonical, proposed, blocked, superseded and unknown classifications internally consistent with the manifest evidence?

3. Do any documents appear incorrectly classified as Proposed merely because they lack an explicit status marker?

4. Are any load-bearing canonical documents, decisions, blockers, governance instruments or active work items missing?

5. Are the 61 documents without self-declared status a governance defect requiring correction, or is conservative Proposed classification sufficient?

6. Does the package preserve repository provenance through commit SHA, file hashes and ignored-content disclosures?

7. Do Projects/ and Workspace.yaml create a remaining corpus-integrity risk?

8. Is the bridge suitable for ongoing use, or must it be corrected before Claude Chat relies on it?

9. Define the exact operating rule for:
   - Cowork preparing repository evidence;
   - Chat making architecture and governance decisions;
   - Cowork registering Chat decisions;
   - Code implementing approved work.

10. Identify any blocker that must be fixed before this bridge becomes operational.

## What Claude Chat must NOT do
- No repository access; state this. Never assert a repository fact.
- Answer only the committed questions above; do not infer or add questions.
- Do not treat `proposed` documents as decided; do not promote status.
- Do not create assignments or approve work it would itself perform.
