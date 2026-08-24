"""P4.2 delta — project lookup by identifier.

The pack loader, workspace→kernel bridge, and registration were merged in PR #10.
The remaining scope item is "support lookup by project identifier": these tests
cover looking a registered project up by its `project.id` and by its registration
name, and the fail-closed rejection of a workspace with duplicate identifiers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from projectos.domain.errors import ValidationError
from projectos.infrastructure.workspace import bootstrap_workspace
from projectos.infrastructure.workspace_bridge import add_project, find_project
from projectos.infrastructure.workspace_manifest import resolve_workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "WS"
    bootstrap_workspace(root, name="Dogfood")
    return root


def test_lookup_by_project_id(workspace: Path) -> None:
    add_project(workspace, name="Alpha", pack="rapid-build", project_id="alpha-svc")

    resolved = resolve_workspace(workspace).by_id("alpha-svc")

    assert resolved is not None
    assert resolved.name == "Alpha"
    assert resolved.project_id == "alpha-svc"


def test_lookup_by_registration_name(workspace: Path) -> None:
    add_project(workspace, name="Alpha", pack="rapid-build", project_id="alpha-svc")

    resolved = resolve_workspace(workspace).by_name("Alpha")

    assert resolved is not None
    assert resolved.project_id == "alpha-svc"


def test_find_project_matches_id_or_name(workspace: Path) -> None:
    add_project(workspace, name="Alpha", pack="rapid-build", project_id="alpha-svc")

    assert find_project(workspace, "alpha-svc") is not None  # by id
    assert find_project(workspace, "Alpha") is not None  # by name
    assert find_project(workspace, "nope") is None


def test_lookup_of_the_p3_default_project(workspace: Path) -> None:
    """The P3 ExampleProject (id example-project) is looked up unchanged."""
    workspace_obj = resolve_workspace(workspace)

    assert workspace_obj.by_id("example-project") is not None
    assert workspace_obj.by_name("ExampleProject") is not None


def test_unknown_identifier_returns_none(workspace: Path) -> None:
    assert resolve_workspace(workspace).by_id("does-not-exist") is None


def test_duplicate_project_identifiers_are_rejected(workspace: Path) -> None:
    """Two projects sharing a project.id would make lookup-by-id ambiguous."""
    add_project(workspace, name="Alpha", pack="rapid-build", project_id="shared-id")
    add_project(workspace, name="Beta", pack="rapid-build", project_id="shared-id")

    with pytest.raises(ValidationError, match="Duplicate project identifier"):
        resolve_workspace(workspace)


def test_distinct_identifiers_resolve_independently(workspace: Path) -> None:
    add_project(workspace, name="Alpha", pack="rapid-build", project_id="alpha")
    add_project(workspace, name="Beta", pack="rapid-build", project_id="beta")

    workspace_obj = resolve_workspace(workspace)

    assert workspace_obj.by_id("alpha").name == "Alpha"
    assert workspace_obj.by_id("beta").name == "Beta"
    # ExampleProject + Alpha + Beta
    assert len(workspace_obj.projects) == 3


def test_resolved_project_exposes_name_and_id(workspace: Path) -> None:
    raw = yaml.safe_load(
        (workspace / "Projects" / "ExampleProject" / "project.yaml").read_text(encoding="utf-8")
    )
    resolved = resolve_workspace(workspace).by_name("ExampleProject")

    assert resolved.name == "ExampleProject"
    assert resolved.project_id == raw["project"]["id"]
