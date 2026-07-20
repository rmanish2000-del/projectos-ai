"""Version compatibility between packs and the executing kernel (spec section 10).

Constraint parsing uses `packaging`, the PEP 440 reference implementation, rather
than a hand-rolled comparator. Version ranges are exactly the kind of thing that
looks simple and is not: prerelease ordering, boundary inclusivity, and epoch
handling all have subtle rules, and a partial parser that silently mis-handles one
of them would let an incompatible pack load.

Two constraints are enforced, and they are different questions:

* the manifest's `packs[].version` constrains **which pack version** the project
  expects, checked against the pack's own `version`; and
* the pack's `requires_projectos` constrains **which kernel** the pack supports,
  checked against :data:`KERNEL_VERSION`.

Both must hold. Either failing is a hard error, not a warning: loading a pack whose
compatibility is unknown would put unverified rules into the governance path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from projectos import __version__
from projectos.domain.errors import ValidationError

#: The executing kernel version, re-exported so callers never hardcode a literal.
KERNEL_VERSION: str = __version__

#: Constraint meaning "any version". Explicit rather than an empty string so an
#: accidentally blank constraint is a parse error instead of a silent wildcard.
ANY_VERSION = "*"

#: Whitespace between clauses is accepted and normalised to the PEP 440 comma form,
#: because spec section 5 writes constraints as `">=0.1.0 <0.2.0"`. This is a
#: normalisation of an accepted syntax, not a second parser: everything after it is
#: `packaging`.
_CLAUSE_SEPARATOR = re.compile(r"\s*,\s*|\s+")


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    subject: str
    version: str
    constraint: str
    compatible: bool
    reason: str

    def describe(self) -> str:
        verdict = "compatible" if self.compatible else "INCOMPATIBLE"
        return f"{self.subject} {self.version} vs {self.constraint!r}: {verdict} — {self.reason}"


def parse_constraint(raw: str, *, source: str) -> SpecifierSet | None:
    """Parse a version constraint, or raise :class:`ValidationError`.

    Returns None for the explicit wildcard. Unsupported syntaxes from other
    ecosystems (npm's `^`, Ruby's `~>`) are rejected here rather than being
    approximated, so an author gets a clear error instead of a silent mismatch.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError(
            f"{source}: version constraint must be a non-empty string",
            detail=f"Use {ANY_VERSION!r} to accept any version.",
        )

    text = raw.strip()
    if text == ANY_VERSION:
        return None

    normalised = ",".join(part for part in _CLAUSE_SEPARATOR.split(text) if part)
    try:
        return SpecifierSet(normalised)
    except InvalidSpecifier as exc:
        raise ValidationError(
            f"{source}: unsupported version constraint {raw!r}",
            detail=(
                f"{exc}. ProjectOS uses PEP 440 constraints, for example "
                "'>=0.1.0,<0.2.0', '==0.1.0', or '*'. Caret and tilde-arrow "
                "syntaxes from other ecosystems are not supported."
            ),
        ) from exc


def parse_version(raw: str, *, source: str) -> Version:
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError(f"{source}: version must be a non-empty string")
    try:
        return Version(raw.strip())
    except InvalidVersion as exc:
        raise ValidationError(
            f"{source}: malformed version {raw!r}",
            detail=f"{exc}. Versions follow PEP 440, for example '0.1.0' or '1.2.0rc1'.",
        ) from exc


def check(
    *, subject: str, version: str, constraint: str, source: str
) -> CompatibilityResult:
    """Check one version against one constraint.

    Prereleases are excluded unless the constraint itself mentions one. That is
    `packaging`'s default and it is the conservative reading: a pack declaring
    `>=0.1.0` is asking for a released kernel, so `0.2.0rc1` does not satisfy it
    unless the author opts in with, for example, `>=0.2.0rc1`.
    """
    parsed_version = parse_version(version, source=source)
    specifier = parse_constraint(constraint, source=source)

    if specifier is None:
        return CompatibilityResult(
            subject=subject,
            version=version,
            constraint=constraint,
            compatible=True,
            reason="constraint accepts any version",
        )

    # `prereleases` is passed explicitly rather than left to the library default.
    # The default admits a prerelease for an open-ended constraint — `>=0.1.0`
    # accepts `0.2.0rc1` — which is the opposite of the policy stated above. Pinning
    # it here makes the behaviour ours and testable rather than inherited.
    allow_prereleases = bool(specifier.prereleases)
    compatible = specifier.contains(parsed_version, prereleases=allow_prereleases)
    if compatible:
        reason = "version satisfies the constraint"
    elif parsed_version.is_prerelease:
        reason = (
            "prerelease versions are excluded unless the constraint names a "
            "prerelease explicitly"
        )
    else:
        reason = "version falls outside the constraint"

    return CompatibilityResult(
        subject=subject,
        version=version,
        constraint=constraint,
        compatible=compatible,
        reason=reason,
    )
