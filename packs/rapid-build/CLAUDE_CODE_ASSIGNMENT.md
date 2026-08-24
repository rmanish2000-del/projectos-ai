# Rapid Build Assignment

Mode: FAST

Objective:
{{OBJECTIVE}}

Repository:
{{REPOSITORY}}

Current State:
Inspect the repository. Treat it as the source of truth.

Instructions:

Implement the objective end-to-end.

Reuse existing architecture.

Do not redesign completed modules.

Run:

- focused tests
- affected integration tests
- lint
- type checks
- build
- smoke verification

Fix all failures within scope.

If CI passes and no high-risk trigger exists:

- create/update PR
- merge
- delete feature branch

Update project state.

Generate exactly ONE next assignment.

Do not create ADRs, governance documents, architecture reviews, or planning documents unless this task changes:

- research mathematics
- statistical methodology
- risk engine
- security architecture
- legal/compliance
- frozen modules
- public contracts

Stop only if:

- founder decision required
- missing credentials
- missing external dependency
- genuine architecture conflict