"""Deterministic CHAT-AUTO-RESTOCK engine.

The restocker is deliberately not an agent.  Report and backlog text are data
consumed by this parser; no model receives them and no arbitrary command is
constructed from them.  Its write surface is limited to four paths below the
configured Drive reports directory: INBOX, DONE, FOUNDER-QUEUE.md and its own
marker/report files.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, cast
from zoneinfo import ZoneInfo

RESTOCKER_SEAT = "CHAT-AUTO-RESTOCK"
MARKER_NAME = "CHAT-RESTOCK-MARKER.json"
QUEUE_NAME = "FOUNDER-QUEUE.md"
REPORT_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}_\d{4})_([A-Z][A-Z0-9-]*)_(.+)\.md$")
REPO_RE = re.compile(
    r"^REPO: (?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@"
    r"(?P<branch>[A-Za-z0-9][A-Za-z0-9._/-]*)$"
)
IST_RE = re.compile(r"^IST: \d{4}-\d{2}-\d{2} \d{2}:\d{2} IST$")
DONE_RE = re.compile(
    r"^DONE: assignment=(?P<assignment>[A-Z0-9][A-Z0-9-]*); "
    r"commit=(?P<commit>[0-9a-f]{40}); files=(?P<files>[^;\r\n]+)$"
)
POOL_ITEM_RE = re.compile(
    r"^(?P<id>[A-Z][A-Z0-9-]*-P\d+)(?:\s*=\s*|\s*:\s*|\s+)(?P<body>.+)$"
)

# These are nouns and verbs at the founder boundary, not a complete semantic
# classifier.  Unknown work also fails closed in _work_profile; this list is a
# second, explicit barrier for known ESCALATE and governance surfaces.
FORBIDDEN_ASSIGNMENT_TERMS = (
    "ratif",
    "merge",
    "deploy",
    "publish",
    "release to production",
    "move money",
    "spend",
    "refund",
    "transmit order",
    "credential",
    "authorisation",
    "authorization",
    "login",
    "legal position",
    "bind a rule",
    "allow-list",
    "allowlist",
    "parameter_registry",
    "declaration register",
    "register",
    "dependency graph",
    "seat graph",
    "seat-boot",
    "doctrine",
)


class RestockError(RuntimeError):
    """A fail-closed restocker error safe to print and queue."""


@dataclass(frozen=True)
class Repository:
    full_name: str
    root: Path


@dataclass(frozen=True)
class Config:
    seats: tuple[str, ...]
    repositories: Mapping[str, Repository]

    @classmethod
    def load(cls, path: Path) -> Config:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("version") != 1:
            raise RestockError("config_version")
        seats = tuple(raw.get("seats", ()))
        if RESTOCKER_SEAT in seats or len(seats) != len(set(seats)):
            raise RestockError("config_seats")
        if not seats or any(not re.fullmatch(r"[A-Z][A-Z0-9-]*", seat) for seat in seats):
            raise RestockError("config_seats")
        repos: dict[str, Repository] = {}
        for full_name, item in raw.get("repositories", {}).items():
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", full_name):
                raise RestockError("config_repository")
            repos[full_name] = Repository(full_name, Path(item["root"]))
        if not repos:
            raise RestockError("config_repositories")
        return cls(seats, repos)


@dataclass(frozen=True)
class ReportClaim:
    filename: str
    seat: str
    assignment: str
    repo: str
    branch: str
    commit: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class PoolItem:
    seat: str
    item_id: str
    body: str
    repo: str
    profile: str


# Free-text pool rows never become instructions directly.  Each executable
# item is pinned here, including its exact source text and concrete work class.
# A new/edited row emits nothing until this reviewed manifest and its tests are
# changed.  C-P1 and A-P1 are intentionally absent: their pool text points at a
# separate assignment/founder STOP rather than autonomous work.
APPROVED_POOL_ITEMS: Mapping[str, tuple[str, str, str, str]] = {
    "C-P2": (
        "CODEX",
        "warrant-mcp test-coverage expansion: enumerate untested paths in the bypass "
        "surface, add tests only (no behaviour changes).",
        "rmanish2000-del/warrant-mcp",
        "tests",
    ),
    "C-P3": (
        "CODEX",
        "TradeOS tape-integrity checker: standalone script that scans a day's parquet "
        "for gaps/duplicate timestamps, report format per repo conventions.",
        "rmanish2000-del/tradeos-ai",
        "tool",
    ),
    "G-P1": (
        "GROK",
        "Launch-week intel: what made recent HN/dev-tool launches in the agent-safety "
        "space get traction (5 examples, what their post did right/wrong, "
        "Reported/Verified graded) — feeds warrant-mcp launch.",
        "rmanish2000-del/warrant-mcp",
        "research",
    ),
    "G-P2": (
        "GROK",
        "Competitor watch brief v1: warrant-mcp adjacent tools (agent "
        "permission/guardrail layers) — who exists, pricing, positioning gaps.",
        "rmanish2000-del/warrant-mcp",
        "research",
    ),
    "G-P3": (
        "GROK",
        "aiworkspacehq.com copy QA: read the LIVE site as a stranger; list every claim "
        "a buyer could misread (report only, no copy edits — content authority stays "
        "founder's).",
        "rmanish2000-del/aiworkspace-hq-web",
        "audit",
    ),
}


@dataclass
class PassSummary:
    verified: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)
    parked: list[str] = field(default_factory=list)
    restocked: list[str] = field(default_factory=list)


RunGit = Callable[[Sequence[str], Path], subprocess.CompletedProcess[str]]


def _run_git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True, check=False
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_source(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)[:180]


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


@contextlib.contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    """Hold one OS-released lock for the whole pass; never leave a stale lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt

            if path.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                locking = getattr(msvcrt, "locking")  # noqa: B009 -- Windows-only API
                lock_nonblocking = getattr(msvcrt, "LK_NBLCK")  # noqa: B009
                locking(handle.fileno(), lock_nonblocking, 1)
            except OSError as exc:
                raise RestockError("pass_already_running") from exc
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RestockError("pass_already_running") from exc
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                locking = getattr(msvcrt, "locking")  # noqa: B009 -- Windows-only API
                unlock = getattr(msvcrt, "LK_UNLCK")  # noqa: B009
                locking(handle.fileno(), unlock, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "processed": {}, "inflight": None, "consumed": []}
    try:
        raw_state: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RestockError("marker_invalid") from exc
    if not isinstance(raw_state, dict):
        raise RestockError("marker_invalid")
    state = cast(dict[str, Any], raw_state)
    if state.get("version") != 1 or not isinstance(state.get("processed"), dict):
        raise RestockError("marker_invalid")
    if not isinstance(state.get("consumed", []), list):
        raise RestockError("marker_invalid")
    return state


def _write_state(path: Path, state: Mapping[str, Any]) -> None:
    _atomic_text(path, json.dumps(state, sort_keys=True, indent=2) + "\n")


def parse_report(path: Path, config: Config) -> ReportClaim:
    """Parse the six-line machine contract; all other report prose is inert."""
    match = REPORT_RE.fullmatch(path.name)
    if match is None:
        raise RestockError("report_filename")
    _, seat, assignment_from_name = match.groups()
    if seat not in config.seats or seat == RESTOCKER_SEAT:
        raise RestockError("report_seat")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) != 6:
        raise RestockError("report_schema")
    repo_match = REPO_RE.fullmatch(lines[0])
    done_match = DONE_RE.fullmatch(lines[2])
    if repo_match is None or IST_RE.fullmatch(lines[1]) is None or done_match is None:
        raise RestockError("report_schema")
    if not lines[3].startswith("ANSWERS:"):
        raise RestockError("report_schema")
    if lines[4] != "BLOCKS: NONE" or lines[5] != "DECISION NEEDED: NONE":
        raise RestockError("report_not_done")
    assignment = done_match.group("assignment")
    if assignment != assignment_from_name:
        raise RestockError("assignment_mismatch")
    repo = repo_match.group("repo")
    if repo not in config.repositories:
        raise RestockError("repo_not_allowed")
    raw_files = tuple(
        part.strip().replace("\\", "/") for part in done_match.group("files").split("|")
    )
    if not raw_files or any(not part for part in raw_files):
        raise RestockError("files_missing")
    files: list[str] = []
    for value in raw_files:
        pure = PurePosixPath(value)
        if pure.is_absolute() or ".." in pure.parts or ".git" in pure.parts:
            raise RestockError("file_path_invalid")
        files.append(str(pure))
    return ReportClaim(
        path.name,
        seat,
        assignment,
        repo,
        repo_match.group("branch"),
        done_match.group("commit"),
        tuple(files),
    )


def verify_claim(claim: ReportClaim, config: Config, run_git: RunGit = _run_git) -> None:
    """Verify files at a commit that is reachable from the named origin branch."""
    repository = config.repositories[claim.repo]
    if not repository.root.is_dir():
        raise RestockError("repo_root_missing")
    branch_ref = f"refs/heads/{claim.branch}"
    fetch = run_git(["fetch", "--quiet", "--no-tags", "origin", branch_ref], repository.root)
    if fetch.returncode != 0:
        raise RestockError("origin_fetch_failed")
    fetched = run_git(["rev-parse", "--verify", "FETCH_HEAD^{commit}"], repository.root)
    if fetched.returncode != 0:
        raise RestockError("origin_ref_missing")
    ancestor = run_git(
        ["merge-base", "--is-ancestor", claim.commit, fetched.stdout.strip()], repository.root
    )
    if ancestor.returncode != 0:
        raise RestockError("commit_not_on_origin")
    for relative in claim.files:
        present = run_git(["cat-file", "-e", f"{claim.commit}:{relative}"], repository.root)
        if present.returncode != 0:
            raise RestockError("file_not_in_commit")


def _find_assignment(directory: Path, seat: str, assignment: str) -> list[Path]:
    suffix = f"_{seat}_{assignment}.md"
    return sorted(path for path in directory.glob("*.md") if path.name.endswith(suffix))


def _move_assignment(claim: ReportClaim, inbox: Path, done: Path) -> str:
    source = _find_assignment(inbox, claim.seat, claim.assignment)
    destination = _find_assignment(done, claim.seat, claim.assignment)
    if len(source) > 1 or len(destination) > 1:
        raise RestockError("assignment_ambiguous")
    if not source:
        if destination:
            return destination[0].name  # idempotent crash recovery
        raise RestockError("assignment_missing")
    done.mkdir(parents=True, exist_ok=True)
    target = done / source[0].name
    if target.exists():
        if _digest(target) != _digest(source[0]):
            raise RestockError("done_collision")
        source[0].unlink()
        return target.name
    os.replace(source[0], target)
    return target.name


def _append_founder_queue(queue: Path, stamp: str, source: str, reason: str) -> None:
    queue.parent.mkdir(parents=True, exist_ok=True)
    safe_source = _safe_source(source)
    safe_reason = _safe_source(reason)
    key = f"source: {safe_source} · code: {safe_reason}"
    existing = queue.read_text(encoding="utf-8-sig") if queue.exists() else "# FOUNDER-QUEUE\n"
    if key in existing:
        return
    line = f"- [ ] {stamp} IST · CHAT-AUTO-RESTOCK · review parked item · {key}\n"
    _atomic_text(queue, existing.rstrip("\n") + "\n" + line)


def _repo_for_item(body: str, repositories: Mapping[str, Repository]) -> str:
    lowered = body.casefold()
    ordered = (
        ("warrant-mcp", "rmanish2000-del/warrant-mcp"),
        ("aiworkspacehq", "rmanish2000-del/aiworkspace-hq-web"),
        ("web", "rmanish2000-del/aiworkspace-hq-web"),
        ("tradeos", "rmanish2000-del/tradeos-ai"),
        ("projectos", "rmanish2000-del/projectos-ai"),
        ("warrant", "rmanish2000-del/warrant"),
        ("aiw", "rmanish2000-del/aiworkspace-core"),
    )
    for token, repo in ordered:
        if token in lowered and repo in repositories:
            return repo
    raise RestockError("pool_repo_ambiguous")


def _work_profile(body: str) -> str:
    lowered = body.casefold()
    if any(term in lowered for term in FORBIDDEN_ASSIGNMENT_TERMS):
        raise RestockError("pool_escalate_or_governance")
    if "test" in lowered or "coverage" in lowered:
        return "tests"
    if "checker" in lowered or "script" in lowered:
        return "tool"
    if "audit" in lowered or " qa" in lowered or "review" in lowered:
        return "audit"
    if "research" in lowered or "intel" in lowered or "competitor" in lowered:
        return "research"
    if "draft" in lowered or "proposal only" in lowered:
        return "draft"
    raise RestockError("pool_objective_not_concrete")


def parse_pool(content: str, config: Config) -> list[PoolItem]:
    """Extract data rows only. Markdown outside a seat section is ignored."""
    current: str | None = None
    items: list[PoolItem] = []
    for raw in content.splitlines():
        if raw.startswith("### "):
            candidate = raw[4:].split(" ", 1)[0].strip().rstrip(":")
            current = candidate if candidate in config.seats else None
            continue
        match = POOL_ITEM_RE.fullmatch(raw.strip())
        if current is None or match is None:
            continue
        item_id = match.group("id")
        body = " ".join(match.group("body").split())
        if item_id.startswith(f"{RESTOCKER_SEAT}-") or current == RESTOCKER_SEAT:
            raise RestockError("self_issue")
        approved = APPROVED_POOL_ITEMS.get(item_id)
        if approved is None:
            continue
        expected_seat, expected_body, repo, profile = approved
        if current != expected_seat or body != expected_body:
            raise RestockError("pool_item_not_allowlisted")
        if repo not in config.repositories:
            raise RestockError("pool_repo_not_configured")
        # Defence in depth: even reviewed manifest text is checked against the
        # canonical boundary vocabulary before it reaches a file.
        _work_profile(body)
        items.append(PoolItem(current, item_id, expected_body, repo, profile))
    return items


def _assignment_body(item: PoolItem, stamp: str) -> str:
    if item.seat == RESTOCKER_SEAT:
        raise RestockError("self_issue")
    profile_scope = {
        "tests": (
            "- Enumerate the currently untested paths named by the objective.\n"
            "- Add focused regression tests for those paths and run the narrowest relevant suite.\n"
            "- Change tests only; any required production-code change is a STOP."
        ),
        "tool": (
            "- Implement the single checker/script named by the objective in the named "
            "repository.\n"
            "- Add focused tests for success, malformed input, and the named integrity failures.\n"
            "- Follow existing repository CLI and report conventions."
        ),
        "audit": (
            "- Inspect exactly the surface named by the objective.\n"
            "- Produce a cited findings file; do not edit the audited product surface.\n"
            "- Separate observed evidence from inference."
        ),
        "research": (
            "- Research exactly the market/question named by the objective.\n"
            "- Produce a source-cited findings file in the named repository.\n"
            "- Grade factual claims as Reported or Verified."
        ),
        "draft": (
            "- Produce only the draft/proposal named by the objective.\n"
            "- Include assumptions and unresolved decisions explicitly.\n"
            "- Do not implement or bind the proposal."
        ),
    }[item.profile]
    return (
        f"Issued by CHAT-AUTO-RESTOCK, {stamp} IST\n\n"
        f"# ASSIGNMENT — {item.item_id}\n\n"
        f"Seat: {item.seat}\nRepo: {item.repo}\nSource: BACKLOG-POOL/{item.item_id}\n\n"
        "## Objective\n\n"
        f"{item.body}\n\n"
        "## Scope\n\n"
        f"{profile_scope}\n\n"
        "## Out of scope\n\n"
        "- Merge, deploy, publish, spend, credentials, authorisations, legal acts, "
        "graph/register edits, and allow-list changes.\n"
        "- Work outside the named repository or beyond this one backlog item.\n\n"
        "## Report\n\n"
        "Write exactly six non-empty lines to AGENT-REPORTS:\n"
        f"REPO: {item.repo}@<branch>\n"
        "IST: YYYY-MM-DD HH:MM IST\n"
        f"DONE: assignment={item.item_id}; commit=<40-lowercase-hex>; "
        "files=<repo-relative-path>|<repo-relative-path>\n"
        "ANSWERS: <concise result>\n"
        "BLOCKS: NONE\n"
        "DECISION NEEDED: NONE\n\n"
        "## Stop\n\n"
        "Stop after the focused tests and report. Do not take a second item. If any "
        "boundary is hit, report BLOCKED and move nothing.\n"
    )


def _latest_pool(reports_dir: Path) -> Path | None:
    candidates = sorted(reports_dir.glob("*_CHAT_BACKLOG-POOL-*.md"))
    return candidates[-1] if candidates else None


class Restocker:
    def __init__(
        self,
        reports_dir: Path,
        config: Config,
        *,
        run_git: RunGit = _run_git,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.reports_dir = reports_dir
        self.inbox = reports_dir / "INBOX"
        self.done = reports_dir / "DONE"
        self.queue = reports_dir / QUEUE_NAME
        self.marker = reports_dir / MARKER_NAME
        self.config = config
        self.run_git = run_git
        self.now = now or (lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

    def _stamp(self) -> str:
        return self.now().strftime("%Y-%m-%d_%H%M")

    def _candidate_reports(self, state: Mapping[str, Any]) -> list[Path]:
        processed = state["processed"]
        paths: list[Path] = []
        for path in sorted(self.reports_dir.glob("*.md")):
            match = REPORT_RE.fullmatch(path.name)
            if match is None or match.group(2) not in self.config.seats:
                continue
            digest = _digest(path)
            if path.name in processed:
                if processed[path.name] != digest:
                    raise RestockError("processed_report_changed")
                continue
            paths.append(path)
        return paths

    def _process_report(self, path: Path, summary: PassSummary) -> None:
        try:
            claim = parse_report(path, self.config)
            verify_claim(claim, self.config, self.run_git)
            moved = _move_assignment(claim, self.inbox, self.done)
        except RestockError as exc:
            _append_founder_queue(self.queue, self._stamp(), path.name, str(exc))
            summary.parked.append(f"{path.name}:{exc}")
            return
        summary.verified.append(path.name)
        summary.moved.append(moved)

    def _restock(self, state: dict[str, Any], summary: PassSummary) -> None:
        pool = _latest_pool(self.reports_dir)
        if pool is None:
            return
        consumed = set(state.get("consumed", []))
        try:
            items = parse_pool(pool.read_text(encoding="utf-8-sig"), self.config)
        except RestockError as exc:
            _append_founder_queue(self.queue, self._stamp(), pool.name, str(exc))
            return
        for seat in self.config.seats:
            if any(f"_{seat}_" in path.name for path in self.inbox.glob("*.md")):
                continue
            item = next(
                (
                    value
                    for value in items
                    if value.seat == seat and value.item_id not in consumed
                ),
                None,
            )
            if item is None:
                continue
            if seat == RESTOCKER_SEAT:
                raise RestockError("self_issue")
            if any(
                item.item_id in path.name
                for folder in (self.inbox, self.done)
                for path in folder.glob("*.md")
            ):
                consumed.add(item.item_id)
                continue
            filename = f"{self._stamp()}_{seat}_{item.item_id}.md"
            target = self.inbox / filename
            self.inbox.mkdir(parents=True, exist_ok=True)
            target.write_text(_assignment_body(item, self._stamp()), encoding="utf-8", newline="\n")
            consumed.add(item.item_id)
            summary.restocked.append(filename)
        state["consumed"] = sorted(consumed)

    def _write_report(self, summary: PassSummary) -> Path:
        filename = f"{self._stamp()}_{RESTOCKER_SEAT}_PASS.md"
        target = self.reports_dir / filename
        values = (
            f"DONE: verified={len(summary.verified)}; moved={len(summary.moved)}; "
            f"restocked={len(summary.restocked)}",
            f"ANSWERS: parked={len(summary.parked)}",
            "BLOCKS: NONE",
            "DECISION NEEDED: " + ("FOUNDER-QUEUE" if summary.parked else "NONE"),
        )
        _atomic_text(target, "\n".join(values) + "\n")
        return target

    def run(self) -> PassSummary:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        with _exclusive_lock(self.reports_dir / ".CHAT-RESTOCK.lock"):
            return self._run_locked()

    def _run_locked(self) -> PassSummary:
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.done.mkdir(parents=True, exist_ok=True)
        state = _load_state(self.marker)
        candidates = self._candidate_reports(state)
        inflight = state.get("inflight")
        if inflight is not None:
            paths = [path for path in candidates if path.name == inflight.get("name")]
            if not paths or _digest(paths[0]) != inflight.get("digest"):
                raise RestockError("inflight_report_changed_or_missing")
            candidates = paths + [path for path in candidates if path != paths[0]]
        summary = PassSummary()
        for path in candidates:
            digest = _digest(path)
            state["inflight"] = {"name": path.name, "digest": digest}
            _write_state(self.marker, state)  # journal before any side effect
            self._process_report(path, summary)
            state["processed"][path.name] = digest
            state["inflight"] = None
            _write_state(self.marker, state)  # commit exactly this item, in order
        self._restock(state, summary)
        _write_state(self.marker, state)
        self._write_report(summary)
        return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one deterministic restock pass")
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        Restocker(args.reports_dir, Config.load(args.config)).run()
    except (OSError, RestockError) as exc:
        print(f"CHAT-AUTO-RESTOCK FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
