"""One command births a new fleet-aligned project (PROJECT-BOOTSTRAP).

``projectos new <NAME> --desc "<one line>"`` scaffolds, in order: the local
repo (git init, templated first commit), the private GitHub repo (gh CLI,
remote wired, pushed — PRIVATE ONLY: a public repo is EXPOSING, ESCALATE
entry 4, the founder's to ratify), the Drive project root per the
FLEET-PROTOCOL folder contract (AGENT-REPORTS + /DOCS, INBOX, DONE), the
three first assignments into the new INBOX, the FLEET-ROOT.md row (created
with its header on first use; rows land as "pending founder ratification"
because a root is IN the protocol only when FLEET-ROOT says so), and the
3-line SEAT-BOOT pointer — the only founder paste.

Templates live in ``templates/project-pack/`` at the ProjectOS repo root:
one source, versioned; fixing a template fixes every future project.
Tokens: ``__NAME__``, ``__SLUG__``, ``__DESC__``, ``__DATE__``.

Every step is recorded with its outcome. Failure is fail-closed per step —
a failed step stops the sequence and the result names what completed, so a
partial scaffold is visible and reversible rather than half-adopted.
"""

from __future__ import annotations

import re
import shutil
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from projectos.domain.errors import ValidationError
from projectos.infrastructure.fleet_clock import now_ist

#: Name rule: a Windows-safe, registry-safe project name. Fail closed on
#: anything else — a scaffold with a mangled name is a permanent artifact.
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,39}$")

TEMPLATE_FILES = {
    "README_FOR_AI.md.tmpl": "README_FOR_AI.md",
    "wake-prompt.md.tmpl": "wake-prompt.md",
    "build_order.json.tmpl": "build_order.json",
    "gitignore.tmpl": ".gitignore",
    "docs-README.md.tmpl": "docs/README.md",
}
INBOX_TEMPLATES = ("CHAT-01.md.tmpl", "COWORK-01.md.tmpl", "CODE-01.md.tmpl")

#: A run callable: (args, cwd) -> (exit_code, combined_output).
Runner = Callable[[list[str], Path], tuple[int, str]]


def _default_runner(args: list[str], cwd: Path) -> tuple[int, str]:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False, timeout=300)
    return done.returncode, (done.stdout + done.stderr).strip()


def default_templates_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "templates" / "project-pack"


@dataclass(frozen=True, slots=True)
class Step:
    step: str
    ok: bool
    detail: str


@dataclass(slots=True)
class ScaffoldResult:
    name: str
    steps: list[Step] = field(default_factory=list)
    pointer_text: str = ""

    @property
    def ok(self) -> bool:
        return all(step.ok for step in self.steps)

    def record(self, step: str, ok: bool, detail: str) -> bool:
        self.steps.append(Step(step, ok, detail))
        return ok


def _fill(text: str, tokens: dict[str, str]) -> str:
    for key, value in tokens.items():
        text = text.replace(key, value)
    return text


def scaffold_project(
    name: str,
    desc: str,
    *,
    projects_parent: Path = Path("C:/"),
    drive_root: Path = Path("G:/My Drive"),
    templates_dir: Path | None = None,
    run: Runner = _default_runner,
    github_owner: str = "rmanish2000-del",
) -> ScaffoldResult:
    """Create everything. Stops at the first failed step; never overwrites."""
    if not _NAME.match(name):
        raise ValidationError(
            f"project name {name!r} is invalid",
            detail="Letters, digits and hyphens; starts with a letter; max 40 chars.",
        )
    if not desc.strip():
        raise ValidationError("a project needs its one-line description")

    templates = templates_dir or default_templates_dir()
    local = projects_parent / name
    drive = drive_root / name
    slug = name.lower()
    tokens = {
        "__NAME__": name,
        "__SLUG__": slug,
        "__DESC__": desc.strip(),
        "__DATE__": now_ist().strftime("%Y-%m-%d"),
    }
    result = ScaffoldResult(name=name)

    # -- refuse to touch anything that already exists (fail closed) -----------
    if local.exists():
        result.record("local", False, f"{local} already exists — refusing to overwrite")
        return result
    if drive.exists():
        result.record("drive", False, f"{drive} already exists — refusing to overwrite")
        return result
    if not templates.is_dir():
        result.record("templates", False, f"no template pack at {templates}")
        return result

    # -- 1. local repo ---------------------------------------------------------
    for tmpl, target in TEMPLATE_FILES.items():
        source = templates / tmpl
        if not source.exists():
            result.record("templates", False, f"missing template {tmpl}")
            return result
        destination = local / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            _fill(source.read_text(encoding="utf-8"), tokens), encoding="utf-8", newline="\n"
        )
    result.record("local", True, f"{local} written from {len(TEMPLATE_FILES)} templates")

    for args in (
        ["git", "init", "-b", "main"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", f"chore({slug}): fleet-aligned scaffold — {desc.strip()}"],
    ):
        code, output = run(args, local)
        if code != 0:
            result.record("git", False, f"{' '.join(args)} -> {code}: {output[:200]}")
            return result
    result.record("git", True, "init, first commit on main")

    # -- 2. private GitHub repo, pushed ---------------------------------------
    code, output = run(
        ["gh", "repo", "create", f"{github_owner}/{slug}", "--private",
         "--source", ".", "--push"],
        local,
    )
    if code != 0:
        result.record("github", False, f"gh repo create -> {code}: {output[:200]}")
        return result
    result.record("github", True, f"private repo {github_owner}/{slug}, pushed")

    # -- 3. Drive root per the folder contract --------------------------------
    for folder in ("AGENT-REPORTS/DOCS", "INBOX", "DONE"):
        (drive / folder).mkdir(parents=True, exist_ok=True)
    result.record("drive", True, f"{drive}: AGENT-REPORTS(/DOCS), INBOX, DONE")

    # -- 4. first assignments into the new INBOX ------------------------------
    stamp = now_ist().strftime("%Y-%m-%d_%H%M")
    for tmpl in INBOX_TEMPLATES:
        source = templates / "inbox" / tmpl
        if not source.exists():
            result.record("inbox", False, f"missing inbox template {tmpl}")
            return result
        staged = drive / "INBOX" / f"{stamp}_{tmpl.removesuffix('.md.tmpl')}_{name}.md"
        staged.write_text(
            _fill(source.read_text(encoding="utf-8"), tokens), encoding="utf-8", newline="\n"
        )
    result.record("inbox", True, f"CHAT-01, COWORK-01, CODE-01 staged in {drive / 'INBOX'}")

    # -- 5. FLEET-ROOT row (sole declaration; pending founder ratification) ---
    fleet_root = drive_root / "FLEET-ROOT.md"
    if not fleet_root.exists():
        fleet_root.write_text(
            "# FLEET-ROOT — the only declaration of project roots\n\n"
            "A project root that exists in Drive but not in this file is not in\n"
            "the protocol (FLEET-PROTOCOL-V1 §1.3). Rows are appended by the\n"
            "scaffolder as PENDING; a root is ratified only by the founder.\n\n"
            "| Project | Root | Folder ids | Seats | Status |\n|---|---|---|---|---|\n",
            encoding="utf-8",
            newline="\n",
        )
    with fleet_root.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            f"| {name} | G:/My Drive/{name} | <to be assigned> x4 | "
            f"CHAT, COWORK, CODE | PENDING founder ratification ({tokens['__DATE__']}) |\n"
        )
    result.record("fleet-root", True, f"row appended to {fleet_root} as PENDING")

    # -- 6. the 3-line pointer — the only founder paste ------------------------
    pointer = _fill((templates / "pointer.txt.tmpl").read_text(encoding="utf-8"), tokens)
    (drive / "AGENT-REPORTS" / "DOCS" / "SEAT-BOOT-POINTER.txt").write_text(
        pointer, encoding="utf-8", newline="\n"
    )
    task_template = _fill((templates / "wake-task.cmd.tmpl").read_text(encoding="utf-8"), tokens)
    (local / "docs" / "wake-task.cmd").write_text(task_template, encoding="utf-8", newline="\n")
    code, _ = run(["git", "add", "-A"], local)
    code2, output = run(["git", "commit", "-m", f"docs({slug}): wake task template"], local)
    code3, output3 = run(["git", "push", "origin", "main"], local)
    if code or code2 or code3:
        result.record(
            "pointer", False, f"task-template commit/push failed: {(output + output3)[:200]}"
        )
        return result
    result.pointer_text = pointer
    result.record(
        "pointer",
        True,
        "pointer written to Drive DOCS; wake task template committed (NOT registered)",
    )
    return result


def _rmtree_force(path: Path) -> None:
    """rmtree that clears the read-only bit and retries — git marks every
    object file read-only on Windows, so a plain rmtree dies on ``.git``."""

    def _onerror(func: Callable[[str], object], failed: str, _exc: object) -> None:
        Path(failed).chmod(stat.S_IWRITE)
        func(failed)

    shutil.rmtree(path, onerror=_onerror)


def delete_project(
    name: str,
    *,
    projects_parent: Path = Path("C:/"),
    drive_root: Path = Path("G:/My Drive"),
    run: Runner = _default_runner,
    github_owner: str = "rmanish2000-del",
) -> list[Step]:
    """Tear a scaffold down completely (dry-run cleanup). Local and Drive are
    removed directly; the GitHub deletion is attempted and its outcome
    recorded honestly — the token may lack delete_repo scope, in which case
    the step reports BLOCKED rather than pretending."""
    steps: list[Step] = []
    local = projects_parent / name
    if local.exists():
        _rmtree_force(local)
    steps.append(Step("local", not local.exists(), f"{local} removed"))
    drive = drive_root / name
    if drive.exists():
        _rmtree_force(drive)
    steps.append(Step("drive", not drive.exists(), f"{drive} removed"))
    fleet_root = drive_root / "FLEET-ROOT.md"
    if fleet_root.exists():
        kept = [
            line
            for line in fleet_root.read_text(encoding="utf-8").splitlines()
            if not line.startswith(f"| {name} |")
        ]
        fleet_root.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
        steps.append(Step("fleet-root", True, "row removed"))
    code, output = run(
        ["gh", "repo", "delete", f"{github_owner}/{name.lower()}", "--yes"], Path.cwd()
    )
    detail = (
        "deleted" if code == 0 else f"BLOCKED (needs delete_repo scope or founder): {output[:160]}"
    )
    steps.append(Step("github", code == 0, detail))
    return steps


def _main(argv: list[str] | None = None) -> int:
    """``py -3.11 -m projectos.infrastructure.project_bootstrap delete <NAME>``.

    Teardown lives behind ``-m projectos`` deliberately: a headless wake's
    allowlist admits no other deletion tool, and keeping it off the main CLI
    surface keeps "delete a project" a dry-run cleanup act, not a routine
    command sitting next to ``new``.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="projectos.infrastructure.project_bootstrap")
    sub = parser.add_subparsers(dest="command", required=True)
    delete = sub.add_parser("delete", help="Tear a scaffold down completely (dry-run cleanup).")
    delete.add_argument("name", help="Project name as scaffolded.")
    args = parser.parse_args(argv)

    ok = True
    for step in delete_project(args.name):
        marker = "ok " if step.ok else "FAIL"
        print(f"[{marker}] {step.step}: {step.detail}")
        ok = ok and step.ok
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover — argv shell over delete_project
    raise SystemExit(_main())
