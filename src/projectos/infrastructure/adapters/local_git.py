"""Local-git repository adapter (spec section 11).

Facts only: this adapter reports what it observed and never decides whether a
criterion passed. Capabilities it lacks (PRs, CI, artifacts) are declared as
`False` so the verification engine fails those rules closed with a message naming
the missing capability, rather than silently skipping them.

Reads are performed through `git` so that evidence reflects committed history
rather than the working tree. There is no working-tree fallback: a path or commit
that is not committed is not evidence, and a directory that is not a git repository
at all raises `AdapterError` rather than reporting untracked files as facts.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from projectos.domain.enums import RuleType
from projectos.domain.errors import AdapterError, UnsupportedCapability
from projectos.domain.evidence import EvidenceRule, RepositoryFact

GIT_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class LocalGitAdapter:
    repo_root: Path
    default_branch: str = "main"

    def capabilities(self) -> dict[str, bool]:
        return {"pr": False, "ci": False, "artifacts": False}

    def query(self, rule: EvidenceRule) -> RepositoryFact:
        if rule.type is RuleType.FILE_EXISTS:
            return self._file_exists(rule)
        if rule.type is RuleType.FILE_CONTAINS:
            return self._file_contains(rule)
        if rule.type is RuleType.COMMIT_EXISTS:
            return self._commit_exists(rule)
        raise UnsupportedCapability(
            f"local-git adapter cannot evaluate {rule.type.value}",
            detail="Configure the github adapter for PR, CI, and artifact evidence.",
        )

    # -- rules -----------------------------------------------------------------

    def _file_exists(self, rule: EvidenceRule) -> RepositoryFact:
        path = str(rule.params["path"])
        ref = str(rule.params.get("at_ref", self.default_branch))
        self._require_repository()

        blob = self._show(f"{ref}:{path}")
        if blob is not None:
            return RepositoryFact(
                kind="file", found=True, detail=f"{path} present at {ref}", data={"ref": ref}
            )
        return RepositoryFact(
            kind="file", found=False, detail=f"{path} not committed at {ref}"
        )

    def _file_contains(self, rule: EvidenceRule) -> RepositoryFact:
        path = str(rule.params["path"])
        pattern = str(rule.params["pattern"])
        ref = str(rule.params.get("at_ref", self.default_branch))
        self._require_repository()

        content = self._show(f"{ref}:{path}")
        if content is None:
            return RepositoryFact(
                kind="file", found=False, detail=f"{path} not committed at {ref}"
            )

        matcher = self._compile(pattern)
        assert matcher is not None  # pattern is a required parameter
        matched = matcher.search(content) is not None

        return RepositoryFact(
            kind="file_content",
            found=matched,
            detail=(
                f"pattern {pattern!r} {'found' if matched else 'not found'} in {path} at {ref}"
            ),
        )

    def _commit_exists(self, rule: EvidenceRule) -> RepositoryFact:
        branch = str(rule.params.get("branch", self.default_branch))
        self._require_repository()
        args = ["log", "--format=%H%x1f%an%x1f%s", branch]
        if "since" in rule.params:
            args.append(f"--since={rule.params['since']}")
        if "author" in rule.params:
            args.append(f"--author={rule.params['author']}")

        output = self._git(args, allow_failure=True)
        if output is None:
            return RepositoryFact(
                kind="commit", found=False, detail=f"branch {branch!r} has no readable history"
            )

        message_pattern = rule.params.get("message_pattern")
        matcher = self._compile(message_pattern)
        for line in output.splitlines():
            sha, _author, subject = line.split("\x1f", 2)
            if matcher is None or matcher.search(subject):
                return RepositoryFact(
                    kind="commit",
                    found=True,
                    detail=f"commit {sha[:8]} on {branch}: {subject}",
                    data={"sha": sha, "subject": subject},
                )

        described = f" matching {message_pattern!r}" if message_pattern else ""
        return RepositoryFact(
            kind="commit", found=False, detail=f"no commit{described} on {branch}"
        )

    # -- git plumbing ----------------------------------------------------------

    @staticmethod
    def _compile(pattern: object) -> re.Pattern[str] | None:
        """Compile an authored regex, converting a bad one into a typed error.

        An uncaught `re.error` would escape the adapter and abort verification
        mid-transition; raising `AdapterError` keeps it on the fail-closed path.
        """
        if pattern is None:
            return None
        try:
            # MULTILINE so `^`/`$` anchor to lines within a file blob; harmless on
            # the single-line commit subjects the same helper compiles.
            return re.compile(str(pattern), re.MULTILINE)
        except re.error as exc:
            raise AdapterError(
                f"Invalid regex in acceptance criterion: {pattern!r}", detail=str(exc)
            ) from exc

    def _require_repository(self) -> None:
        """Fail closed unless this really is a git repository.

        Previously any git failure fell back to reading the working tree, so a
        directory that was not a repository at all reported untracked files as
        evidence. Absence of a repository is an adapter error, not an absence of
        evidence — the two must not be conflated.
        """
        if self._git(["rev-parse", "--git-dir"], allow_failure=True) is None:
            raise AdapterError(
                f"{self.repo_root} is not a git repository",
                detail=(
                    "The local-git adapter reads evidence from committed history. "
                    "Run `git init` and commit the work before verifying."
                ),
            )

    def _show(self, spec: str) -> str | None:
        return self._git(["show", spec], allow_failure=True)

    def _git(self, args: list[str], *, allow_failure: bool = False) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.repo_root), *args],
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AdapterError(
                "git executable not found on PATH",
                detail="The local-git adapter requires git to read repository facts.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(
                f"git command timed out after {GIT_TIMEOUT_SECONDS}s",
                detail=f"Command: git {' '.join(args)}",
            ) from exc

        if completed.returncode != 0:
            if allow_failure:
                return None
            raise AdapterError(
                f"git command failed: git {' '.join(args)}",
                detail=completed.stderr.strip() or "no stderr output",
            )
        return completed.stdout
