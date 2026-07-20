"""Loading a pack from an arbitrary directory (spec section 13, `pack validate`).

Separate from :class:`FilePackRepository`, which loads packs a manifest already
requires from inside `.projectos/packs/`. `pack validate <path>` has to work on a
pack that is not installed — that is the point of validating before installing.

Reading only. Nothing here copies, installs, registers, or activates a pack.
"""

from __future__ import annotations

from pathlib import Path

from projectos.domain.errors import NotFoundError
from projectos.domain.pack import Pack, PackTemplate
from projectos.infrastructure.serialization import pack_from_dict, require_mapping
from projectos.infrastructure.yaml_io import read_yaml

PACK_MANIFEST = "pack.yaml"


def load_pack_from_directory(directory: Path) -> Pack:
    """Read and parse a pack from `directory`, without installing it."""
    if not directory.is_dir():
        raise NotFoundError(
            f"No such pack directory: {directory}",
            detail="Pass the directory containing pack.yaml.",
        )

    pack_file = directory / PACK_MANIFEST
    if not pack_file.is_file():
        raise NotFoundError(
            f"No {PACK_MANIFEST} in {directory}",
            detail="A pack is a directory containing pack.yaml and an optional templates/.",
        )

    raw = require_mapping(read_yaml(pack_file), source=str(pack_file))
    return pack_from_dict(raw, load_templates(directory), source=str(pack_file))


def load_templates(directory: Path) -> tuple[PackTemplate, ...]:
    """Read `templates/*.yaml`, sorted so loading is deterministic."""
    templates_dir = directory / "templates"
    if not templates_dir.is_dir():
        return ()
    return tuple(
        PackTemplate(
            name=path.stem,
            body=require_mapping(read_yaml(path), source=str(path)),
        )
        for path in sorted(templates_dir.glob("*.yaml"))
    )
