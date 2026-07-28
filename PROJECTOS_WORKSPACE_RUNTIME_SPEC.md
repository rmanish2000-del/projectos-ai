# ProjectOS Workspace Runtime — specification

**Status:** P4 Architecture Amendment — proposed. Design only; no implementation.
**Relationship to the kernel:** This document amends and extends
[`PROJECTOS_V0_1_FOUNDATION_SPEC.md`](PROJECTOS_V0_1_FOUNDATION_SPEC.md) ("the
Foundation Spec" / "the kernel"). Where the two disagree on a kernel-internal
concern, the Foundation Spec governs. This document is authoritative only for the
**Workspace Runtime** — the layer *above* the kernel.
**Scope:** Defines the Workspace Runtime that resolves, from a local-first
workspace of many projects, exactly one active project and its one active
assignment, and routes work to the correct repository and agent. It embeds **no
domain logic** (domain rules stay in packs) and adds **no new kernel write
paths**.

---

## 0. Position in the stack

```
┌───────────────────────────────────────────────────────────────┐
│ Workspace Runtime  (this spec — P4)                            │
│   reads Workspace.yaml + project registrations                 │
│   resolves: active project → repo → kernel → active assignment │
│   resolves: pack set, workflow mode floor, agent adapter map   │
│   NEVER mutates .projectos/ state; delegates every write        │
└───────────────────────────┬───────────────────────────────────┘
                             │ selects a repo_root, then calls
                             ▼
┌───────────────────────────────────────────────────────────────┐
│ ProjectOS Core / Kernel  (Foundation Spec — P1)                │
│   build_kernel(repo_root) → one kernel bound to ONE repository │
│   owns: assignments, state machine, evidence, audit, INV-1..7  │
└───────────────────────────────────────────────────────────────┘
```

The kernel already answers, for a single repository, "what is the one active
assignment, who owns it, is it verifiably complete, what is next" (Foundation
Spec §1). The kernel is **bound to exactly one repository**: `build_kernel(repo_root)`
in `infrastructure/container.py` wires a kernel over one `.projectos/` and knows
nothing of sibling projects. The P3 workspace bootstrap
(`infrastructure/workspace.py`) lays down a multi-project directory tree but is
**pure scaffolding** — it writes files and stops; nothing reads `Workspace.yaml`
back at runtime.

The Workspace Runtime closes that gap. It is the component that, given a workspace
root, decides **which** repository's kernel is live, loads the pack set that
project draws on, resolves the workflow-mode floor and the concrete agent
bindings, and then hands off to the existing kernel. It is the multiplexer above
the kernel; it is not a second kernel.

---

## 1. Design principles

These extend, and never relax, the kernel's principles (Foundation Spec §2).

1. **Kernel neutrality.** The Runtime carries no domain rules and no
   assignment-lifecycle logic. Anything that decides *how work is verified,
   classified, or sequenced* belongs to the kernel or to a pack. The Runtime only
   decides *which* kernel, *which* repo, *which* packs, and *which* agent binding.
2. **Local-first.** Resolution reads only the local filesystem. No network, no
   service, no daemon. (Matches `workspace.py` load-bearing property #1.)
3. **Deterministic.** The same workspace tree plus the same explicit inputs
   always resolves to the same active project, active assignment, pack set, mode
   floor, repo route, and agent map. No wall-clock or ordering dependence.
4. **Fail-closed.** Ambiguity never resolves to a silent choice. An unresolvable
   active project, an unreadable registration, a repo that is not a repository, or
   an agent role with no adapter → a typed failure or a founder escalation, never
   a guess. (Matches kernel INV-4.)
5. **Additive & backward-compatible.** Every field this spec adds to
   `Workspace.yaml` or `project.yaml` is optional with a documented default that
   reproduces P3 behaviour. A `Workspace.yaml` emitted by the P3 bootstrap must
   resolve without edits. (§13.)
6. **One write authority.** The Runtime performs at most **workspace-scoped**
   writes (its own pointer/cache under `ProjectOS/`). It performs **zero** writes
   under any project's `.projectos/`; those go through the kernel's single write
   path (`LifecycleService`) exactly as today.
7. **Read-only over projects by default.** Resolving state must never
   activate, start, verify, or close anything. Mutation happens only when a caller
   explicitly invokes a kernel operation through the Runtime.

### 1.1 Workspace Runtime invariants

| ID | Invariant | Rationale |
|---|---|---|
| **WR-INV-1** | At most one **active project** in a workspace at any time. | Combined with kernel INV-1 (one active assignment per repo), this yields the founder-facing guarantee of exactly one active assignment across the whole workspace. |
| **WR-INV-2** | The Runtime never writes under any `.projectos/`. All project-state mutation is delegated to that project's kernel. | Preserves the audit-chain completeness guarantee (Foundation Spec §8.6): the kernel remains the only mutator. |
| **WR-INV-3** | Active-project, pack-set, mode-floor, repo-route, and agent-map resolution are pure functions of the workspace tree plus explicit inputs. | Determinism; reproducible `git diff` on workspace state. |
| **WR-INV-4** | Resolution fails closed. No default silently selects a project, repo, or agent when the inputs are ambiguous or malformed. | Safety; consistent with kernel fail-closed. |
| **WR-INV-5** | Every new schema field is optional; absence resolves to a default equal to P3 behaviour. | Backward compatibility (§13). |
| **WR-INV-6** | The Runtime raises the workflow-mode floor for the kernel but can never lower a mode the kernel or a pack computes. | Mirrors "packs may raise but never lower" (Foundation Spec §7.3); the Runtime is one more monotonic raiser, not an override. |

---

## 2. Terminology

| Term | Meaning |
|---|---|
| **Workspace** | The local-first root directory holding many projects, shared assets, and a home for workspace-level ProjectOS state. Identified by a `Workspace.yaml` at its root. |
| **Workspace Runtime** (Runtime) | The component specified here: it reads the workspace, resolves context, and routes to kernels. |
| **Runtime context** | The immutable, fully-resolved value the Runtime produces for one invocation (§5). |
| **Project registration** | A project's `project.yaml` under `Projects/<name>/`, plus its `Workspace.yaml` `projects[]` entry (§6). |
| **Bound repository** | The repository (a directory containing, or destined to contain, `.projectos/`) a registered project resolves to (§11). |
| **Active project** | The single registered project whose kernel currently holds the workspace's active assignment (§7). |
| **Agent adapter** | A workspace-level, configurable binding from a kernel `ExecutorType` (`cowork` / `code` / `human`) to a concrete agent implementation (Claude Cowork, Claude Code, ChatGPT/Chat, a named human, or a future agent) (§12). |
| **Mode floor** | The minimum `WorkflowMode` the Runtime asserts for a project before the kernel and packs apply their own (only-ever-raising) classification (§10). |

---

## 3. Layer boundary — what the Runtime may and may not do

| Concern | Owner | Note |
|---|---|---|
| Assignment lifecycle, state machine, evidence, verification, audit | **Kernel** | Unchanged. Foundation Spec §§6–9. |
| Classifying an assignment's workflow mode from risk flags / triggers | **Kernel + packs** | Runtime may only supply a *floor* input (§10). |
| Successor (next-assignment) resolution | **Kernel + packs** | Runtime does not sequence assignments. |
| Executor validation (`validate_routing`) | **Kernel** | Runtime supplies the *enabled* agent set; kernel still validates. |
| Which repository is live | **Runtime** | New. §11. |
| Which project is active | **Runtime** | New. §7. |
| Which packs a project draws on, and from where | **Runtime + kernel** | Runtime resolves the sources; kernel loads/enforces compatibility. §9. |
| Mapping `ExecutorType` → concrete agent (Claude Code / Cowork / Chat / human) | **Runtime** | New. §12. Kernel stays neutral. |
| Workspace-level defaults (default mode floor, default agent map, shared pack roots) | **Runtime** | New. Declared in `Workspace.yaml`. |

The Runtime **must not**: create/parse assignments, decide verification, write
audit entries, open or resolve escalations on its own authority (it may *surface*
a kernel-produced escalation and it may raise a **workspace-scope** escalation for
"active project undetermined", §7.4), or embed any domain-specific vocabulary.

---

## 4. `Workspace.yaml` schema

The P3 bootstrap already emits a `Workspace.yaml` at `schema_version: 1`
(`workspace.py::_workspace_manifest`). This spec **keeps `schema_version: 1`** and
extends it **additively**: every field below that P3 does not already emit is
**optional**, and its absence resolves to the P3-equivalent default (§13,
WR-INV-5). No breaking change is introduced, so no version bump is required. A
future breaking change would introduce `schema_version: 2` with a documented
upgrade; that is out of scope here.

### 4.1 Fields

Fields marked **[P3]** are already emitted by the bootstrap and keep identical
meaning. Fields marked **[P4]** are new and optional.

| Path | Req. | Since | Meaning / default |
|---|---|---|---|
| `schema_version` | required | [P3] | Const `1`. |
| `workspace.name` | required | [P3] | Human-readable workspace name. |
| `workspace.id` | optional | [P4] | Kebab-case stable id. Default: slug of `workspace.name`. |
| `projectos` | required | [P3] | Path to the workspace-level ProjectOS home dir (default `ProjectOS`). Runtime state lives here (§5.3). |
| `shared.packs` | required | [P3] | Path to the shared pack root (default `Shared/Packs`). |
| `shared.templates` / `.policies` / `.prompts` / `.knowledge` | required | [P3] | Shared asset roots. Kept verbatim. |
| `packs[]` | optional | [P3] | Workspace-registered packs, each `{name, path}` (path relative to workspace root). This is the **pack catalog** (§9). |
| `projects[]` | optional | [P3] | Registered projects, each `{name, path, ...}` (§4.2, §6). |
| `defaults.workflow.default_mode_floor` | optional | [P4] | Workspace mode floor: `fast` \| `reviewed` \| `governed`. Default `fast`. §10. |
| `defaults.agents[]` | optional | [P4] | Workspace-default agent adapter map (§12). Default: identity map (`cowork`→cowork, `code`→code, `human`→human). |
| `defaults.pack[]` | optional | [P4] | Pack names every project inherits unless it opts out. Default: empty. §9. |
| `active_project` | optional | [P4] | Declared active project name. One input to active-project resolution (§7); the workspace pointer file takes precedence over it. |

### 4.2 `projects[]` entry (extends P3)

```yaml
projects:
  - name: ExampleProject          # [P3] display name; must match Projects/<name>/
    path: Projects/ExampleProject # [P3] path to the project registration dir
    # ---- [P4], all optional ----
    id: example-project           # stable id; default = project.yaml project.id
    repository: Projects/ExampleProject   # bound repo root (§11); default = path
    packs: [rapid-build]          # project-level pack selection; default from project.yaml/defaults
    workflow: { default_mode_floor: reviewed }   # per-project floor; raises workspace floor only
    agents:                       # per-project agent overrides (§12)
      - { executor: code, adapter: claude-code }
```

### 4.3 Illustrative resolved-form (informative)

```yaml
schema_version: 1
workspace: { name: ProjectOS-AI Workspace, id: projectos-ai-workspace }
projectos: ProjectOS
shared: { packs: Shared/Packs, templates: Shared/Templates, policies: Shared/Policies,
          prompts: Shared/Prompts, knowledge: Shared/Knowledge }
defaults:
  workflow: { default_mode_floor: fast }
  agents:
    - { executor: cowork, adapter: claude-cowork }
    - { executor: code,   adapter: claude-code }
    - { executor: human,  adapter: founder }
packs:
  - { name: rapid-build, path: Shared/Packs/rapid-build }
  - { name: software,    path: Shared/Packs/software }
projects:
  - { name: ExampleProject, path: Projects/ExampleProject, repository: Projects/ExampleProject }
```

---

## 5. Runtime context model

The **Runtime context** is the immutable value produced by one resolution pass. It
is the Runtime's analogue of the kernel's `Kernel` composition object — a fully
wired, read-only snapshot. Nothing downstream reads the filesystem again for the
duration of an invocation; everything reads the context.

### 5.1 Shape (declarative)

```
RuntimeContext
├─ workspace_root            : path (absolute, resolved)
├─ workspace                 : WorkspaceManifest        # parsed Workspace.yaml (§4)
├─ projects                  : [ResolvedProject]        # every registration, resolved (§6)
├─ active_project            : ResolvedProject | None   # §7; None ⇒ undetermined (§7.4)
├─ pack_catalog              : { name -> PackSource }   # §9; where each pack lives
├─ agent_map (workspace)     : { ExecutorType -> AgentAdapterRef }   # §12 default map
└─ diagnostics               : [Finding]                # non-fatal notes; fatal ⇒ raise

ResolvedProject
├─ id                        : str
├─ name                      : str
├─ registration_path         : path        # Projects/<name>/project.yaml
├─ repo_root                 : path         # §11 bound repository
├─ has_projectos             : bool         # repo_root/.projectos/manifest.yaml present?
├─ declared_packs            : [str]        # §9 (project ∪ workspace defaults)
├─ mode_floor                : WorkflowMode # §10 (max of workspace & project floors)
├─ agent_map                 : { ExecutorType -> AgentAdapterRef }  # §12 (workspace ⊕ project)
└─ kernel_builder            : () -> Kernel # deferred; build_kernel(repo_root) (§8, §11)
```

### 5.2 Properties

- **Immutable.** Constructed once per invocation; never mutated. Mirrors the
  kernel's frozen-value discipline (Foundation Spec §6).
- **Lazy kernels.** `kernel_builder` is *deferred*: resolving context does not
  build any kernel (building one reads a repo's manifest and can fail closed).
  Only the active project's kernel is built, and only when an operation needs it
  (§8). This keeps a `status` over a 50-project workspace cheap and ensures a
  broken sibling project never blocks resolution of the active one.
- **Total.** Every registered project appears in `projects[]` even if it fails
  to resolve; a failed project carries its `Finding` and a `None` `repo_root`, so
  `workspace status` can list it as broken rather than the whole pass aborting —
  except when the *active* project is the broken one (fail closed, WR-INV-4).

### 5.3 Runtime state on disk

Workspace-scoped Runtime state lives under the existing `ProjectOS/` home
directory (already reserved by P3 as "workspace-level ProjectOS assets"). It is
the **only** place the Runtime writes.

| File | Purpose | Written when |
|---|---|---|
| `ProjectOS/active.yaml` | Active-project pointer: `{ active_project: <name|null> }`. Authoritative input to §7. | On explicit `workspace use <project>` (and cleared when that project has no work). |
| `ProjectOS/runtime.lock` | Advisory single-writer lock for workspace-scoped writes. | During a workspace-scope write. |

`ProjectOS/active.yaml` mirrors the kernel's per-repo `active.yaml` pattern
(`paths.py::active_pointer`) one level up, and is likewise **derived** — it is a
convenience pointer, never the sole source of truth: if it names a project that no
longer exists, resolution ignores it and falls through (§7.2) rather than failing.

---

## 6. Project registration model

A project is registered by two facts that must agree:

1. an entry in `Workspace.yaml` `projects[]` (`{name, path, ...}`), and
2. a `project.yaml` at `<path>/project.yaml`.

### 6.1 `project.yaml` (extends the P3 sample)

P3 emits (`workspace.py::_example_project_yaml`):

```yaml
schema_version: 1
project: { id: example-project, name: ExampleProject, description: ... }
pack: rapid-build
```

P4 extends it additively; `pack` (singular string) is retained and interpreted as
a one-element `packs` list for backward compatibility:

| Path | Req. | Since | Meaning / default |
|---|---|---|---|
| `schema_version` | required | [P3] | Const `1`. |
| `project.id` | required | [P3] | Kebab-case stable id; immutable. |
| `project.name` | required | [P3] | Display name; should match the dir. |
| `project.description` | optional | [P3] | — |
| `pack` | optional | [P3] | Single pack name. Treated as `packs: [<pack>]`. |
| `packs[]` | optional | [P4] | Ordered pack names (manifest order = last-wins, matching `PackSet`). If both `pack` and `packs` appear, `packs` wins and `pack` must be its first element or a `Finding` is raised. |
| `repository.root` | optional | [P4] | Bound repo root, relative to the project dir. Default `.` (the project dir is the repo). §11. |
| `repository.adapter` | optional | [P4] | `local_git` \| `github`. Informational at the workspace layer; the kernel's own manifest remains authoritative. Default: unset (defer to kernel). |
| `workflow.default_mode_floor` | optional | [P4] | Per-project floor. §10. |
| `agents[]` | optional | [P4] | Per-project agent overrides. §12. |

### 6.2 Registration validation (fail-closed)

A registration is **valid** iff: the `projects[]` entry exists; `<path>` is a
directory under the workspace root; `<path>/project.yaml` parses; `project.id` is
kebab-case; and the `name`/`id` are unique across the workspace. A duplicate id, a
missing directory, or an unreadable `project.yaml` produces an ERROR `Finding`; if
that project is not the active one, resolution continues and lists it as broken
(§5.2); if it is (or is being selected as) the active one, resolution raises.

The registration model deliberately does **not** describe the project's
assignments, packs' rules, or state — those live in the bound repository's
`.projectos/` and are the kernel's, not the Runtime's.

---

## 7. Active project resolution

**Goal:** select at most one active project, deterministically and fail-closed
(WR-INV-1, WR-INV-3, WR-INV-4).

### 7.1 Resolution order

Evaluated top-to-bottom; first rule that yields a project wins.

1. **Explicit override.** A caller-supplied `--project <name|id>` (CLI/API). If it
   names no valid registration → raise (fail closed).
2. **Workspace pointer.** `ProjectOS/active.yaml` `active_project`, when it names a
   currently-valid registration. A stale pointer (project removed) is ignored and
   resolution falls through.
3. **Declared active.** `Workspace.yaml` `active_project`, when valid.
4. **Sole project.** If exactly one project is registered, it is active.
5. **Work-bearing uniqueness.** If exactly one registered project's kernel holds a
   *current* assignment (kernel `current()` — ACTIVE/EVIDENCE_SUBMITTED/VERIFYING/
   VERIFIED/REJECTED, Foundation Spec §"Active slot vs current"), that project is
   active. If two or more do, → **undetermined** (§7.4). *(This rule requires
   building those projects' kernels; it is evaluated only when rules 1–4 do not
   resolve, and its cost is bounded by the number of registered projects.)*
6. **Otherwise undetermined** (§7.4).

Rule 5 is the only rule that inspects kernel state; it is last-but-one so the
cheap deterministic rules dominate and the expensive scan is a fallback.

### 7.2 Determinism

Given identical inputs (workspace tree, pointer file, explicit override) the
result is identical. No rule depends on filesystem enumeration order: registrations
are considered in `Workspace.yaml` `projects[]` declaration order, and ties in
rule 5 do **not** break by order — they escalate (§7.4). This matches the kernel's
"ambiguity is FAIL by construction" stance (Foundation Spec, `CriterionOutcome`).

### 7.3 Selecting an active project (the write)

`workspace use <project>` sets `ProjectOS/active.yaml`. This is a
**workspace-scope** write (WR-INV-2 permits it; it is not under any `.projectos/`).
It does not start, activate, or otherwise touch the project's assignments — the
project's kernel still governs its own INV-1 slot.

WR-INV-1 is enforced at selection time by construction: `active.yaml` holds a
single value, so at most one project is ever pointed to.

### 7.4 Undetermined active project

When resolution yields no project **and** the caller's operation requires one
(e.g. `workspace next`, `workspace status --active`), the Runtime raises a
**workspace-scope escalation** with trigger analogous to the kernel's
`NEXT_UNDETERMINED` — surfaced through the same exit-code contract (exit `3`,
Foundation Spec §13) — presenting the registered projects as options. This is the
only escalation the Runtime originates. Read-only, whole-workspace operations
(`workspace status` with no active project) do **not** escalate; they report "no
active project — run `workspace use <project>`" and exit `0`.

---

## 8. Active assignment resolution

The Runtime **does not re-implement** active-assignment logic. It resolves the
active project (§7), builds that project's kernel via the deferred
`kernel_builder` (= `build_kernel(repo_root)`, §11), and delegates:

- **The one active assignment** = `kernel.lifecycle.active()` for the active
  project (kernel INV-1 guarantees at most one).
- **The current assignment** (for `verify`/`complete` ergonomics) =
  `kernel.lifecycle.current()`.
- **Briefing, next, verify, complete, block, founder, history** = the identical
  kernel operations, now reachable through a workspace-aware entry point that first
  fixes the active project.

**Composite invariant.** WR-INV-1 (one active *project*) × kernel INV-1 (one
active *assignment per repo*) ⇒ **exactly one active assignment across the entire
workspace**. The Runtime adds no new way to make an assignment active; it only
constrains *which* kernel's slot is in view. If the active project has no active
assignment, the workspace has none — there is no cross-project queue.

The Runtime never reads or writes assignment files directly (WR-INV-2). A
`workspace status` that wants a one-line-per-project overview calls each resolved
project's kernel read APIs (`current()`, `blocked()`, `open_escalations()`) — all
read-only — and never touches `.projectos/` bytes itself.

---

## 9. Pack loading model

Packs remain **declarative data, loaded and compatibility-checked by the kernel**
(Foundation Spec §10; `pack.py`, `pack_loading.py`). The Runtime's job is only to
resolve **which packs a project uses and where their source lives**, then make
those sources available to the project's kernel. The Runtime does not parse pack
rules, does not union extension points (that is `PackSet`), and does not enforce
`requires_projectos` (that is the kernel loader).

### 9.1 The three pack locations

| Location | Role | Authority |
|---|---|---|
| `Shared/Packs/<name>/` (workspace) | **Catalog / source of truth for authored packs.** Shared across projects. Listed in `Workspace.yaml` `packs[]`. | Runtime resolves; pack author edits. |
| `<repo>/.projectos/packs/<name>/` (project) | **Installed pack** the kernel actually loads (`FilePackRepository`, Foundation Spec §"What lives where"). | Kernel loads & enforces. |
| A pack directory passed to `pack validate <path>` | Uninstalled pack under review (`load_pack_from_directory`). | Kernel validates, no install. |

### 9.2 Resolution (declarative)

For a project, the **effective pack list** is, in order (last-wins on name
collision, matching `PackSet` semantics):

1. `Workspace.yaml` `defaults.pack[]` (workspace-wide inheritance), then
2. the project's `packs[]` (or singular `pack`) from `project.yaml` / its
   `projects[]` entry.

Each name resolves to a **source** by lookup in the `pack_catalog` (from
`Workspace.yaml` `packs[]`, path relative to workspace root). A name with no
catalog entry → ERROR `Finding` (fail closed when the project is active).

### 9.3 Install is explicit, kernel-owned, and additive

The Runtime **never auto-installs**. A pack becomes loadable by a project only when
its source is present under that project's `.projectos/packs/<name>/`. The Runtime
defines the *intent* (effective pack list + resolved sources); a distinct,
explicit action — `workspace sync-packs <project>` (P4-runtime CLI, §14) — copies
the resolved sources into the project's `.projectos/packs/`. That copy is the same
declarative-YAML install the kernel already understands; compatibility
(`requires_projectos`, manifest version constraints) is checked by the **kernel's**
loading path exactly as today, so activation cannot bypass it (README "Pack version
compatibility is enforced").

This keeps the kernel's guarantee intact: the packs a kernel loads are the ones in
its own `.projectos/`, resolved deterministically, and the Runtime is only a
resolver + copier, never a second enforcement point.

---

## 10. Workflow mode resolution

The kernel classifies each assignment's `WorkflowMode` monotonically:
project-manifest default is the floor, every pack rule may only **raise** it, and
the maximum wins (`enums.py::WorkflowMode.raised_to`; architecture.md
"Classification is monotonic"). The Runtime adds **one more floor input, above the
project**, and nothing else.

### 10.1 The mode floor

```
effective_floor(project) =
    max(                       # by WorkflowMode.rank: fast < reviewed < governed
        workspace.defaults.workflow.default_mode_floor  (default fast),
        project.workflow.default_mode_floor             (default fast)
    )
```

The Runtime passes `effective_floor(project)` to the project's kernel as the
**minimum** `WorkflowMode` for classification. The kernel then applies the
manifest default and every pack rule, each of which may raise but never lower
(WR-INV-6). Concretely: `resolved_mode = max(effective_floor, manifest_default,
pack_rules...)`.

### 10.2 What the Runtime must not do

- It must **not** lower a mode. A workspace floor of `fast` never pulls a
  `governed` pack rule down; `max` guarantees this.
- It must **not** invent triggers or risk vocabulary. Governed triggers remain the
  kernel set plus pack additions (`manifest.py::KERNEL_GOVERNED_TRIGGERS`,
  `pack.governed_triggers_add`). The workspace floor is a blunt minimum, not a
  trigger.
- It must **not** map the informal `policies.yaml` routing (`claude_code` /
  `claude_cowork` per mode) onto the kernel. That mapping is an **agent-routing**
  concern (§12), separate from mode classification. Mode decides *strictness*;
  agent routing decides *who executes*.

### 10.3 Relationship to `.projectos/policies.yaml`

The workspace may carry an informal `policies.yaml` (as in
`.projectos/policies.yaml.txt`) describing FAST/REVIEWED/GOVERNED gates and
per-mode routing. In this spec that file is **advisory/human-facing** at the
workspace layer: the Runtime may read its `default_mode` as a candidate for
`workspace.defaults.workflow.default_mode_floor`, but the **normative** floor is
the `Workspace.yaml` field. The kernel's `WorkflowMode` remains the single source
of truth for classification; `policies.yaml` never overrides it.

---

## 11. Repository routing

Every registered project resolves to exactly one **bound repository** — the
directory the kernel is built over.

### 11.1 Resolution

```
repo_root(project) =
    1. project.yaml  repository.root  (relative to project dir), else
    2. projects[] entry  repository   (relative to workspace root), else
    3. the project registration directory itself   # P3-compatible default
    ─ then resolve to an absolute path.
```

Rule 3 is the backward-compatible default: a P3 project (`Projects/ExampleProject/`
with only `project.yaml` and no repo binding) is its own repo root, which is
exactly what `discover_repo_root` would find when run there.

### 11.2 Binding to the kernel

The Runtime builds the kernel with the **existing** entry point, unchanged:

```
kernel = build_kernel(repo_root(project))     # infrastructure/container.py
```

The Runtime passes only `repo_root`. It does **not** choose the repository adapter
— `build_kernel` reads the project's own `.projectos/manifest.yaml` and selects
`LocalGitAdapter` or `UnavailableGitHubAdapter` per `RepositoryConfig` exactly as
today (`container.py::_build_adapter`). `project.yaml repository.adapter`, if
present, is advisory only; the kernel manifest is authoritative. This preserves the
kernel's fail-closed GitHub behaviour without the Runtime duplicating adapter
logic.

### 11.3 Fail-closed conditions

- `repo_root` does not exist, or is not a directory → ERROR; active-project
  resolution fails closed if this is the active project.
- `repo_root` has no `.projectos/manifest.yaml` (`has_projectos == false`) → the
  project is **registered but un-initialised**. Read-only listing shows it as
  "needs `projectos init`"; any operation requiring the kernel raises the kernel's
  own not-found/validation error (exit `2`). The Runtime does not auto-`init`.
- Two projects resolving to the **same** `repo_root` → ERROR `Finding` (a repo is
  owned by one project registration; sharing would split INV-1 accounting).

---

## 12. AI ownership routing (agent adapters)

The kernel's executor vocabulary is the closed set `cowork | code | human`
(`enums.py::ExecutorType`), and routing is a **validation** (`routing.py`): the
work type has a default executor and a permitted set; packs may narrow, never
broaden; the manifest declares which executors are *enabled*. **This spec does not
change any of that.** Instead it adds a workspace-level, configurable **agent
adapter map** that binds each abstract `ExecutorType` to a concrete agent — so the
kernel stays domain- and vendor-neutral while the workspace decides that `code`
means "Claude Code", `cowork` means "Claude Cowork", and a future project could
bind `code` to "ChatGPT" or a human reviewer.

### 12.1 Adapter registry

Concrete agents the workspace knows about (extensible; the Runtime treats these as
opaque named references — it does **not** call any agent):

| Adapter ref | Concrete agent | Notes |
|---|---|---|
| `claude-code` | Claude Code | Default binding for `code`. |
| `claude-cowork` | Claude Cowork | Default binding for `cowork`. |
| `chat` | ChatGPT / a chat agent | Optional; binds `code` or `cowork` where a project chooses. |
| `founder` / `<identity-id>` | A named human | Binds `human`; the id must be a manifest owner in the bound repo for any approval it records. |
| `<future>` | Future agents | Additive; adding a ref never changes existing bindings. |

### 12.2 The map and its resolution

```
AgentAdapterRef binding declared as: { executor: <ExecutorType>, adapter: <ref> }

effective_agent_map(project) =
    workspace.defaults.agents[]        (default: identity map cowork/code/human)
      ⊕ project.agents[]               (per-project override; last-wins per executor)
```

The map is a **presentation/dispatch binding**, applied *after* the kernel has
routed. The flow for one assignment:

1. Kernel decides the `ExecutorType` (default-per-work-type, pack narrowing,
   manifest-enabled — `routing.validate_routing`). **Unchanged.**
2. Runtime looks up `effective_agent_map(active_project)[executor]` to name the
   concrete agent the briefing is handed to.
3. The kernel briefing (`routing.brief`, with its four invariant rules) is rendered
   unchanged; the Runtime only annotates *which concrete agent* receives it.

### 12.3 Constraints (fail-closed, kernel-preserving)

- **Enabled-set consistency.** An `executor` may be bound only if it is in the
  bound repo manifest's `agents` (enabled) set. Binding a disabled executor →
  ERROR `Finding`. The Runtime supplies the manifest's enabled set to the kernel's
  `validate_routing`; it never widens it.
- **Total coverage.** Every `ExecutorType` the project can route to must have a
  binding. A missing binding for a reachable executor → fail closed (WR-INV-4),
  never a silent default to a vendor.
- **Human authority unchanged.** An agent ref bound to `human` that records an
  approval must still be a manifest owner in the bound repo; the kernel's
  authorization check (`is_authorized`, Foundation Spec §8.6) is the gate, not the
  Runtime. The adapter map cannot grant authority.
- **No execution in the Runtime.** The Runtime resolves and names bindings; it does
  not invoke Claude Code, Cowork, Chat, or any agent. Invocation is the caller's
  (or a later phase's) concern, out of scope here.

### 12.4 Relationship to `policies.yaml` routing

The informal `policies.yaml` `routing` block (`FAST → owner: claude_code`,
`GOVERNED → owner: claude_cowork, implementer: claude_code`) is a **per-mode
convention** that a pack or the workspace default map may encode, but it is not a
kernel rule. Where a project wants mode-sensitive ownership, it is expressed as
pack executor-narrowing (kernel-enforced) plus the agent map (Runtime binding) —
not as a Runtime override of kernel routing. The Runtime never changes the
`ExecutorType` the kernel selected.

---

## 13. Backward compatibility with the P3 workspace bootstrap

The P3 bootstrap (`infrastructure/workspace.py`) and its CLI
(`projectos workspace init`) are **unchanged and remain the way a workspace is
created**. This spec is purely additive over what P3 emits. The compatibility
contract:

1. **Schema stays v1.** No version bump. Every field P3 emits
   (`schema_version`, `workspace.name`, `projectos`, `shared.*`, `packs[].{name,
   path}`, `projects[].{name, path}`, and the sample `project.yaml` with singular
   `pack`) keeps identical meaning (WR-INV-5). This follows the precedent already
   in the codebase, where `pack.requires_projectos` was made "optional in schema
   v1 for backward compatibility" (`pack.py`).
2. **New fields are optional with P3-equal defaults.** Absence resolves to:
   mode floor `fast`; agent map = identity (`cowork/code/human`); repo root = the
   project directory; declared packs = the singular `pack` (or `defaults.pack[]`);
   active project = resolved by §7 rules 2–6. Therefore a workspace created by
   today's `workspace init`, with **no edits**, resolves to a valid Runtime
   context: one project (`ExampleProject`), bound to its own directory as repo
   root, `rapid-build` pack, `fast` floor, default agent map.
3. **Idempotent bootstrap preserved.** The P3 generator's create-or-keep behaviour
   and "second run is a visible no-op" property are untouched; the Runtime reads
   what the bootstrap writes and never rewrites it.
4. **`singular pack` bridge.** `project.yaml: pack: <name>` is read as
   `packs: [<name>]`. If a project later adds `packs[]`, `pack` becomes redundant;
   a mismatch (where `pack` is not the first `packs[]` element) is a `Finding`, not
   a silent reconciliation.
5. **No new mandatory files.** `ProjectOS/active.yaml` and `runtime.lock` (§5.3)
   are created on first workspace-scope write, not required to exist. Their absence
   means "no explicit active pointer", handled by §7 fall-through. A workspace that
   never runs a Runtime command is byte-identical to what P3 produced.
6. **CLI additivity.** New `workspace` subcommands (§14) are added under the
   existing `workspace` parser; the existing `workspace init` is unchanged. No
   existing exit code or flag changes.

---

## 14. CLI / entry-point surface (proposed, informative — no implementation)

New capabilities are surfaced as additive `workspace` subcommands, each a thin
wrapper over one Runtime resolution + (where applicable) one delegated kernel
operation, obeying the existing deterministic exit-code contract (`0` ok, `1` rule
failure, `2` invariant/validation, `3` escalation — Foundation Spec §13). Listed
for design completeness only; **not implemented in this assignment.**

| Command | Resolves | Delegates to kernel |
|---|---|---|
| `workspace status [--active]` | context; active project (§7) | read-only `current/blocked/open_escalations` per project |
| `workspace use <project>` | validates registration | none (workspace-scope write, §7.3) |
| `workspace list` | all registrations (§6) | none |
| `workspace next` | active project (§7) | `lifecycle` next/start on that kernel (§8) |
| `workspace verify` / `complete` / `block` / `founder` / `history` | active project | the identically-named kernel op on the active project |
| `workspace sync-packs <project>` | effective pack sources (§9.2) | copies sources into that project's `.projectos/packs/` (§9.3) |

`--project <name|id>` is a global override (§7 rule 1) accepted by every
work-directed subcommand. When the workspace root differs from the cwd, a
`--workspace <path>` flag (default: nearest ancestor containing `Workspace.yaml`,
by analogy to `discover_repo_root`) selects it.

---

## 15. Failure model (consolidated)

| Situation | Resolution | Exit |
|---|---|---|
| No active project, operation needs one | Workspace escalation, options = registrations (§7.4) | `3` |
| No active project, read-only whole-workspace op | Report "no active project"; no escalation | `0` |
| Active project registration malformed / dir missing | Typed validation error, fail closed (§6.2) | `2` |
| Active project un-initialised (`no .projectos/`) | Kernel not-found on any kernel op; listing shows "needs init" | `2` |
| Pack name not in catalog for active project | Validation error (§9.2) | `2` |
| `executor` bound to a disabled/absent agent, or a reachable executor unbound | Validation error, fail closed (§12.3) | `2` |
| Two projects → same repo_root | Validation error (§11.3) | `2` |
| Kernel-originated rule failure / escalation | Surfaced unchanged from the delegated op | `1` / `3` |

Every fatal condition is a **typed error** or a **surfaced kernel result** — the
Runtime introduces no new silent path (WR-INV-4).

---

## 16. Traceability — the ten required deliverable items

| # | Objective | Section |
|---|---|---|
| 1 | `Workspace.yaml` schema | §4 (fields, additive v1, resolved-form) |
| 2 | Runtime context model | §5 (shape, properties, on-disk state) |
| 3 | Project registration model | §6 (`project.yaml`, validation) |
| 4 | Active project resolution | §7 (ordered rules, determinism, undetermined) |
| 5 | Active assignment resolution | §8 (delegation to kernel; composite invariant) |
| 6 | Pack loading model | §9 (three locations, resolution, explicit install) |
| 7 | Workflow mode resolution | §10 (mode floor, monotonic raise-only) |
| 8 | Repository routing | §11 (repo_root resolution, `build_kernel` binding) |
| 9 | AI ownership routing (Claude Code / Chat / Cowork) | §12 (agent adapter map) |
| 10 | Backward compatibility with P3 bootstrap | §13 (compatibility contract) |

---

## 17. Boundaries / non-goals

- No implementation, no code, no CLI wiring is delivered here (§14 is informative).
- No changes to the kernel's state machine, evidence model, audit chain, or
  `ExecutorType` vocabulary.
- No agent invocation, no network, no service, no daemon, no UI.
- No domain logic: renewable, legal, trading, and other domain rules remain in
  packs; the Runtime is domain-neutral.
- No auto-`init`, no auto pack-install, no auto-selection of an active project on
  ambiguity.
- Multi-phase pack pipelines, signed approvals, and the GitHub adapter remain as
  the Foundation Spec schedules them; the Runtime neither requires nor blocks them.

---

## 18. Handoff to implementation

The implementable units this spec authorises, in dependency order, each small and
kernel-delegating:

1. `WorkspaceManifest` + `project.yaml` loaders (parse §4/§6, additive v1,
   fail-closed validation) — infrastructure, read-only.
2. `RuntimeContext` resolver (§5) with deferred `kernel_builder` and the pack
   catalog (§9.2), reusing `build_kernel` unchanged (§11.2).
3. Active-project resolver (§7) + `ProjectOS/active.yaml` pointer (§5.3, §7.3).
4. Mode-floor input (§10.1) and agent-adapter map (§12.2), passed to existing
   kernel classification/routing without modifying them.
5. `workspace` subcommands (§14) as thin wrappers over 1–4 plus delegated kernel
   ops, honouring the existing exit-code contract.

Each unit is testable in isolation against a temporary workspace tree with pinned
inputs, mirroring the kernel's test discipline (architecture.md "Testing
strategy"), and none of them adds a write path under `.projectos/`.

---

READY FOR CLAUDE CODE
