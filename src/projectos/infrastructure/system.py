"""Clock and identity implementations.

Both are injected rather than read inline, which is what lets tests pin time and
identity and get byte-identical state files across runs.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

GIT_TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class SystemClock:
    """UTC, second precision, ISO-8601 with a trailing `Z`.

    Second precision is deliberate: audit timestamps are a human-readable record,
    and ordering is carried by the sequence number rather than by the clock.
    """

    def now_iso(self) -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True, slots=True)
class FixedClock:
    """A clock pinned to one instant, for tests and reproducible scaffolding."""

    instant: str

    def now_iso(self) -> str:
        return self.instant


@dataclass(frozen=True, slots=True)
class GitIdentityProvider:
    """The acting identity, resolved in the order the founder is most likely to
    have configured: an explicit override, then git's committer email, then the OS
    user (spec 14.4 — v0.1 trusts local identity; risk R-6)."""

    repo_root: str
    override: str | None = None

    def current(self) -> str:
        if self.override:
            return self.override
        environment = os.environ.get("PROJECTOS_IDENTITY")
        if environment:
            return environment
        email = self._git_email()
        if email:
            return email
        return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"

    def _git_email(self) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "-C", self.repo_root, "config", "user.email"],
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        value = completed.stdout.strip()
        return value or None


@dataclass(frozen=True, slots=True)
class StaticIdentityProvider:
    identity: str

    def current(self) -> str:
        return self.identity
