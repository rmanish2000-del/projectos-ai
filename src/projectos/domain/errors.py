"""Typed kernel errors and the deterministic exit-code contract.

Spec section 13: exit codes are 0 ok, 1 rule failure, 2 invariant/validation error,
3 escalation required. The CLI maps exceptions to these codes; nothing else decides
an exit code.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    RULE_FAILURE = 1
    INVARIANT_ERROR = 2
    ESCALATION_REQUIRED = 3


class ProjectOSError(Exception):
    """Base class for every error the kernel raises deliberately."""

    exit_code: ExitCode = ExitCode.INVARIANT_ERROR

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def render(self) -> str:
        return self.message if self.detail is None else f"{self.message}\n  {self.detail}"


class ValidationError(ProjectOSError):
    """Schema or manifest validation failed. Fail closed (INV-6)."""

    exit_code = ExitCode.INVARIANT_ERROR


class InvariantViolation(ProjectOSError):
    """A kernel invariant (INV-1..7) would be broken by the requested operation."""

    exit_code = ExitCode.INVARIANT_ERROR


class IllegalTransition(InvariantViolation):
    """Transition not present in the exhaustive table (spec section 7.2)."""


class RuleFailure(ProjectOSError):
    """Verification produced at least one failing acceptance criterion."""

    exit_code = ExitCode.RULE_FAILURE


class AdapterError(ProjectOSError):
    """A repository adapter failed or lacks a required capability.

    Per INV-4 this always blocks; it never degrades into a pass.
    """

    exit_code = ExitCode.INVARIANT_ERROR


class UnsupportedCapability(AdapterError):
    """The configured adapter cannot answer this class of question."""


class EscalationRequired(ProjectOSError):
    """The kernel cannot proceed without a founder decision (spec section 9.1)."""

    exit_code = ExitCode.ESCALATION_REQUIRED


class AuditChainBroken(ProjectOSError):
    """Hash chain verification failed; the kernel halts (INV-5, INV-6)."""

    exit_code = ExitCode.ESCALATION_REQUIRED


class NotFoundError(ProjectOSError):
    exit_code = ExitCode.INVARIANT_ERROR
