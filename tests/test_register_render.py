"""Counts are rendered, never authored (REGISTER-RENDERER).

The enforcement test for DC-5's oldest gap: a wrong count in a governance
register is a build failure, not a note.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from projectos.infrastructure.register_render import audit, counts, main, parse, render

REGISTER = """# EXAMPLE REGISTER

| Rank | Class | Primary instances | Rule enforced by a test today? |
|---|---|---|---|
| 1 | `DC-1` TRUSTED-REPORT | {{count:DC-1}} | No. Memory only |
| 2 | `DC-2` SCOPE | {{count:DC-2}} | Partly |

Preamble: {{count:classes|words}} classes · {{count:instances}} primary instances.
{{count:enforcement:memory}} of {{count:classes}} rely on memory.

## DC-1 · TRUSTED-REPORT — {{count:DC-1}}

| id | Instance |
|---|---|
| **I-01** | first |
| **I-02** | second |
| **I-03** | third |

## DC-2 · SCOPE — {{count:DC-2}}

| id | Instance |
|---|---|
| **I-04** | fourth |
"""


class TestParseAndRender:
    def test_counts_come_from_the_rows(self) -> None:
        classes, enforcement = parse(REGISTER)
        table = counts(classes, enforcement)
        assert table == {"DC-1": 3, "DC-2": 1, "instances": 4, "classes": 2}
        assert enforcement == {"DC-1": "no. memory only", "DC-2": "partly"}

    def test_rendered_section_matches_the_rows(self) -> None:
        rendered = render(REGISTER)
        assert "two classes · 4 primary instances" in rendered
        assert "## DC-1 · TRUSTED-REPORT — 3" in rendered
        assert "1 of 2 rely on memory" in rendered
        assert "{{count:" not in rendered

    def test_words_suffix_spells_the_number(self) -> None:
        assert "two classes" in render(REGISTER)

    def test_unknown_marker_is_a_failure_not_a_blank(self) -> None:
        with pytest.raises(ValueError, match="unknown marker key"):
            render(REGISTER + "\n{{count:DC-99}}\n")

    def test_clean_register_audits_clean(self) -> None:
        assert audit(REGISTER) == []


class TestFailConditions:
    def test_duplicate_instance_id_fails(self) -> None:
        broken = REGISTER.replace("| **I-04** | fourth |", "| **I-03** | fourth |")
        assert any("duplicate instance id I-03" in f for f in audit(broken))

    def test_instance_id_gap_fails(self) -> None:
        broken = REGISTER.replace("| **I-04** | fourth |", "| **I-06** | fourth |")
        assert any("gap" in f for f in audit(broken))

    def test_class_with_no_instances_fails(self) -> None:
        broken = REGISTER + "\n## DC-3 · EMPTY — {{count:DC-3}}\n\nno rows here\n"
        assert any("DC-3 has no instances" in f for f in audit(broken))

    def test_planted_wrong_count_fails_the_build(self) -> None:
        # The mutation the whole tool exists for: someone types a number
        # into a counting sentence instead of a marker. Digits and words both.
        mutated = REGISTER.replace(
            "{{count:classes|words}} classes · {{count:instances}} primary instances",
            "Seven classes · 33 primary instances",
        )
        failures = audit(mutated)
        assert any("bare count literal" in f for f in failures)

    def test_spelled_out_wrong_count_fails_too(self) -> None:
        # Three of the seven originally-wrong counts were words, not digits.
        mutated = REGISTER.replace(
            "{{count:enforcement:memory}} of {{count:classes}} rely on memory",
            "Thirty-three of the classes rely on memory",
        )
        assert any("bare count literal" in f for f in audit(mutated))

    def test_decorated_instance_row_still_parses(self) -> None:
        # The live register marks some rows `| **I-27** ⭑ |`. Missing them
        # produced a phantom id-gap on the first real run; never again.
        decorated = REGISTER.replace("| **I-04** | fourth |", "| **I-04** ⭑ | fourth |")
        classes, _ = parse(decorated)
        assert classes["DC-2"] == ["I-04"]
        assert audit(decorated) == []

    def test_unbolded_id_is_a_cross_reference_not_an_instance(self) -> None:
        # The live register's secondary-class table lists `| I-03 doctor | ...`
        # rows; counting those doubled three ids on the first real run.
        with_refs = REGISTER + "\n| I-01 first, seen again | DC-2 | note |\n"
        classes, _ = parse(with_refs)
        assert classes["DC-1"] == ["I-01", "I-02", "I-03"]
        assert audit(with_refs) == []

    def test_ids_dates_and_section_refs_are_not_counts(self) -> None:
        benign = REGISTER + "\nSee I-03 and DC-2 (2026-08-15, §6, v7) for instances context.\n"
        assert audit(benign) == []


class TestCli:
    def test_missing_file_exits_2(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["Z:/nowhere/register.md"]) == 2

    def test_clean_file_exits_0_and_writes_rendered(self, tmp_path: Path) -> None:
        source = tmp_path / "register.md"
        source.write_text(REGISTER, encoding="utf-8")
        out = tmp_path / "rendered.md"
        assert main([str(source), str(out)]) == 0
        assert "4 primary instances" in out.read_text(encoding="utf-8")

    def test_mutated_file_exits_1(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        source = tmp_path / "register.md"
        source.write_text(
            REGISTER.replace("{{count:instances}} primary instances", "33 primary instances"),
            encoding="utf-8",
        )
        assert main([str(source)]) == 1
        assert "FAIL" in capsys.readouterr().out
