"""YAML reading and writing for ProjectOS state files.

Two properties matter here and are enforced rather than assumed:

* **Safety** — `yaml.safe_load` only; state files are data and must never be able
  to construct Python objects.
* **Determinism** — a fixed dump configuration with insertion order preserved, so
  re-saving an unchanged value produces a byte-identical file and `git diff` shows
  only real changes.

Every read scans for secrets before parsing (spec 14.1), so a credential committed
into state is caught on the next kernel operation rather than at review time.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from projectos.domain.errors import NotFoundError, ValidationError
from projectos.infrastructure.validation import scan_for_secrets


class _DeterministicDumper(yaml.SafeDumper):
    """Preserves mapping insertion order rather than sorting keys alphabetically,
    so files read in the field order the schema documents."""


def _represent_str(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    style = "|" if "\n" in data.strip() else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_DeterministicDumper.add_representer(str, _represent_str)


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise NotFoundError(f"File not found: {path}")
    text = path.read_text(encoding="utf-8")
    scan_for_secrets(text, source=str(path))
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValidationError(f"Malformed YAML in {path}", detail=str(exc)) from exc


def write_yaml(path: Path, data: Any, *, header: str | None = None) -> None:
    body = yaml.dump(
        data,
        Dumper=_DeterministicDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=100,
    )
    scan_for_secrets(body, source=str(path))
    text = f"# {header}\n{body}" if header else body
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, text)


def _atomic_write(path: Path, text: str) -> None:
    """Write via a temporary file in the same directory, then replace.

    A crash mid-write leaves the previous file intact rather than a truncated one,
    which matters because a half-written state file would halt the kernel (INV-6).
    """
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)
