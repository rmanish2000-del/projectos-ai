# Integrity Checks — Specification & Script Design

**Four checks that make the handoff verifiable and drift-detectable.** Design only — no script is executed by this assignment.

---

## 1. The four required checks

| Check | Detects | Pass condition |
|---|---|---|
| **1. Hash validation** | corruption / tampering / wrong copy | For every manifest entry, `sha256(file) == entry.sha256`. |
| **2. Missing-input detection** | absent required file | Every manifest `source_path` resolves to an existing file. |
| **3. Stale-copy detection** | downstream snapshot behind upstream | Vendored copy hash == upstream (ProjectOS) hash for the same doc_id; mismatch ⇒ stale. |
| **4. Broken cross-reference detection** | dangling dependency | Every `dependencies[]` id and every referenced doc_id exists in the manifest. |

All four are **fail-closed**: any failure blocks import/use and is reported; nothing proceeds on a red check (kernel discipline).

## 2. Script design (pseudocode — not executed)

```
load manifest.yaml
errors = []

# Check 1 — hash validation
for entry in manifest.documents:
    if not exists(entry.source_path):            errors += MISSING(entry.id)          # Check 2
    elif sha256(entry.source_path) != entry.sha256: errors += HASH_MISMATCH(entry.id)

# Check 3 — stale-copy (run where both upstream + vendored are reachable)
for entry in manifest.documents:
    if reachable(upstream(entry)) and sha256(vendored(entry)) != sha256(upstream(entry)):
        errors += STALE(entry.id)

# Check 4 — broken cross-reference
ids = { e.id for e in manifest.documents }
for entry in manifest.documents:
    for dep in entry.dependencies:
        if dep not in ids:                        errors += DANGLING_REF(entry.id, dep)

# CR-1 seed guard
if any seed record present in registry-bound location and not B3_VERIFIED:
    errors += UNVERIFIED_SEED_PRESENT

exit 0 if errors == [] else exit 1 (print errors)   # fail-closed
```

Reference implementations: a portable `sha256sum -c` checklist derived from the manifest (offline hash validation), plus a small YAML-driven checker for checks 2–4. Both are deterministic and side-effect-free.

## 3. `sha256sum`-compatible checklist (derivable)

The manifest is designed so a standard checklist can be generated mechanically:

```
34f30e70bd1f5a4832b70dbbd4a03d15867d1b1d6799184c47dd28297cc2e371  PROJECTOS_V0_1_FOUNDATION_SPEC.md
37c5466e5620e80160569ea12a71a61909346b3e749d3b44c360d830140a92f0  PROJECTOS_METHODOLOGY_V2.md
e5a8141adbbdd9903afdaa781d5c572c5746aab135357023bc252786fe3bf171  PLATFORM_GENOME_V1.md
884d68c309491acf3d7ee1db45c9829bdf0385d32a4beead22855b4eee44d504  PO-3_AI_WORKSPACE_INTEGRATION_SPEC.md
69efbb7faeb17316c3f1dbaf361a1daa1573577bf0e94b819d98bdca70114439  PO-4_ECOSYSTEM_GOVERNANCE_FRAMEWORK.md
0afc8a4ba74c60d889adab9770ac381740f9282c62d23d87f9d5dd0e6187cf2a  PO-5_GOVERNANCE_METRICS_PLATFORM_HEALTH.md
2b79891bae9061355d4c60c53cff27a9ea042a98e62d4ae891010e7818107c09  PROJECTOS_CONSTITUTION_V1.md
ffe8a56496fe96efaceb62d5f22442cb25736f283c88eea4bc08998edcc66852  PO-7_PLATFORM_METADATA_ARCHITECTURE.md
e598a993dae6f88d1cdcc9e187f20af7d2be5e6440f6a81c9b46abdc169d0e26  FOUNDATIONAL_CORPUS_INTEGRATION.md
7dff1d3a7fc4cce60d7ca5ed4dea4f82b571dd01b467020aa3e980860bdc5702  PO-9_ECOSYSTEM_LANGUAGE_STANDARD.md
bd47ad51e03ed8b1e8206fcc14515e90df71d41de157d917d171407533103d4e  PO-10_RATIFICATION_AND_CORRECTION_PACKAGE.md
17bdb1880e3dea8427b9b0ce5664496543af3e53ff60dd770a08ea8f98689bba  PO-11_RATIFICATION_EXECUTION_PLAN.md
e393539ac0207f48e8d05e1ec22600fbf5a58edcaab35faa7bc2cef910311fec  PROJECTOS_WORKSPACE_RUNTIME_SPEC.md
48af2b3f1aaae04b5e3db760c2dac51f506e37c1ac83b506b4153d1e4a7d6e27  PROJECTOS_IMPLEMENTATION_ROADMAP.md
993ca7d23ef57a914235a3cf6638b80abf04d1be84cc8c30e20c0fb2dfdb03fb  PO-2.5_ARCHITECTURE_CONSISTENCY_REVIEW.md
740ed50fc76bfdfff0312876a46df0f0ad3a36968dd0281adbccfaba159ac59b  README.md
285741a17e08d8279c8658fba86b9a700dc7b44ac49d11f63a889a03f60003e8  docs/architecture.md
e57ec306ab9a30e9a65b2bec47d221ab5e1c1c01dfa1de1604da0db1ac035910  docs/cli.md
```

Run `sha256sum -c <checklist>` against the ProjectOS repo (or the vendored copy) → every line must report `OK`. Any `FAILED` is a red gate.

## 4. When to run

- **On export** (ProjectOS side): checks 1, 2, 4 — the package is internally sound before handoff.
- **On import** (AIW side): checks 1, 2, 4 — the received copy is intact and self-consistent.
- **On sync / periodically**: check 3 — the vendored snapshot has not drifted from upstream.
