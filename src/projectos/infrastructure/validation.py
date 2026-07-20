"""JSON Schema validation and secret scanning (spec sections 5, 14.1).

Schemas are the outer gate: they reject unknown fields and wrong types before any
value reaches the domain, so domain constructors only need to enforce the
cross-field rules a schema cannot express.
"""

from __future__ import annotations

import json
import re
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from projectos.domain.errors import ValidationError

SCHEMA_PACKAGE = "projectos.infrastructure.schemas"

#: Patterns that must never appear in ProjectOS state files. Detection fails the
#: operation rather than redacting: a leaked secret is a founder-visible event
#: (spec 14.1, escalation trigger 9.1.3).
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub personal access token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI/Anthropic style key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Bearer token", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{20,}\b")),
    (
        "Inline password or secret assignment",
        re.compile(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"]?\S{8,}"),
    ),
)


@cache
def _validator(schema_name: str) -> Draft202012Validator:
    text = resources.files(SCHEMA_PACKAGE).joinpath(schema_name).read_text(encoding="utf-8")
    schema: dict[str, Any] = json.loads(text)
    return Draft202012Validator(schema)


def validate(data: Any, schema_name: str, *, source: str) -> None:
    """Validate `data` against a bundled schema. Reports every error, not just the
    first, so a malformed file can be fixed in one pass."""
    errors = sorted(_validator(schema_name).iter_errors(data), key=lambda e: list(e.path))
    if not errors:
        return
    lines = []
    for error in errors:
        location = "/".join(str(part) for part in error.path) or "(root)"
        lines.append(f"    at {location}: {error.message}")
    raise ValidationError(
        f"Schema validation failed for {source}",
        detail="\n".join(lines),
    )


def scan_for_secrets(text: str, *, source: str) -> None:
    """Fail closed if a state file appears to contain a credential."""
    for label, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            excerpt = match.group(0)
            redacted = f"{excerpt[:4]}…{excerpt[-2:]}" if len(excerpt) > 8 else "…"
            raise ValidationError(
                f"Possible secret detected in {source}: {label}",
                detail=(
                    f"Matched {redacted}. Secrets must never live in .projectos/ — "
                    "supply credentials via environment or OS keychain (spec 14.1)."
                ),
            )


def available_schemas() -> tuple[str, ...]:
    return (
        "manifest.schema.json",
        "assignment.schema.json",
        "pack.schema.json",
        "escalation.schema.json",
        "audit_entry.schema.json",
    )
