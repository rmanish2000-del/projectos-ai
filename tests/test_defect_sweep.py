"""The standing defect-class sweep: observe and report, never fix
(THREE-KERNELS-RECONCILE)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from projectos.infrastructure.defect_sweep import (
    parse_runner_summary,
    run_defect_sweep,
)


def _register(tmp_path: Path, classes: dict) -> Path:
    path = tmp_path / "defect_register.json"
    path.write_text(json.dumps({"classes": classes}, indent=2) + "\n", encoding="utf-8")
    return path


def _records(tmp_path: Path) -> Path:
    return tmp_path / "records" / "sweeps.ndjson"


class TestParseRunnerSummary:
    def test_parsed_passed_count_is_green(self) -> None:
        green, detail = parse_runner_summary("collected 3 items\n\n3 passed in 0.12s\n")
        assert green is True
        assert "3 passed" in detail

    def test_failure_token_is_red(self) -> None:
        green, _ = parse_runner_summary("1 failed, 2 passed in 0.30s\n")
        assert green is False

    def test_error_token_is_red(self) -> None:
        green, _ = parse_runner_summary("2 errors during collection\n")
        assert green is False

    def test_unparseable_output_is_refused_not_green(self) -> None:
        # The observed-fact rule: no parsed summary, no verdict — never green.
        green, detail = parse_runner_summary("")
        assert green is None
        assert "refusing" in detail

    def test_exit_code_style_silence_is_refused(self) -> None:
        green, _ = parse_runner_summary("done ok")
        assert green is None


class TestSweep:
    def test_green_enforcement_test_observed_green(self, tmp_path: Path) -> None:
        (tmp_path / "tests_dc1.py").write_text("", encoding="utf-8")
        register = _register(
            tmp_path, {"DC-1": {"name": "observed-fact", "enforcement_test": "tests_dc1.py"}}
        )

        def runner(args: Sequence[str], cwd: Path) -> str:
            return "5 passed in 0.01s\n"

        report = run_defect_sweep(
            repo_root=tmp_path,
            register_path=register,
            records_path=_records(tmp_path),
            runner=runner,
        )
        assert report.open_classes == ("DC-1",)
        assert report.new_instances == ()
        assert report.missing_tests == ()
        assert report.standing_answer().kind == "NO_MATCH"

    def test_red_enforcement_test_is_a_new_instance(self, tmp_path: Path) -> None:
        (tmp_path / "tests_dc2.py").write_text("", encoding="utf-8")
        register = _register(tmp_path, {"DC-2": {"enforcement_test": "tests_dc2.py"}})

        report = run_defect_sweep(
            repo_root=tmp_path,
            register_path=register,
            records_path=_records(tmp_path),
            runner=lambda a, c: "1 failed in 0.02s\n",
        )
        assert report.new_instances == ("DC-2",)
        answer = report.standing_answer()
        assert answer.kind == "KNOWN_CLASS"
        assert answer.dc_class == "DC-2"

    def test_undeclared_test_counts_as_missing(self, tmp_path: Path) -> None:
        register = _register(tmp_path, {"DC-3": {"enforcement_test": None}})
        report = run_defect_sweep(
            repo_root=tmp_path,
            register_path=register,
            records_path=_records(tmp_path),
            runner=lambda a, c: "should never run",
        )
        assert report.missing_tests == ("DC-3",)

    def test_declared_but_gone_file_counts_as_missing(self, tmp_path: Path) -> None:
        # A declaration the tree no longer honours is not a test.
        register = _register(tmp_path, {"DC-4": {"enforcement_test": "gone.py"}})
        report = run_defect_sweep(
            repo_root=tmp_path,
            register_path=register,
            records_path=_records(tmp_path),
            runner=lambda a, c: "should never run",
        )
        assert report.missing_tests == ("DC-4",)
        observation = report.observations[0]
        assert observation.test_exists is False
        assert observation.test_green is None

    def test_unparseable_output_lands_in_unknown_and_watch(self, tmp_path: Path) -> None:
        (tmp_path / "tests_dc5.py").write_text("", encoding="utf-8")
        register = _register(tmp_path, {"DC-5": {"enforcement_test": "tests_dc5.py"}})
        report = run_defect_sweep(
            repo_root=tmp_path,
            register_path=register,
            records_path=_records(tmp_path),
            runner=lambda a, c: "mysterious silence",
        )
        assert report.unknown == ("DC-5",)
        assert report.standing_answer().kind == "WATCH"

    def test_register_gains_last_sweep_observed_fields_only(self, tmp_path: Path) -> None:
        (tmp_path / "tests_dc1.py").write_text("", encoding="utf-8")
        register = _register(
            tmp_path,
            {"DC-1": {"name": "kept", "source": "kept-too", "enforcement_test": "tests_dc1.py"}},
        )
        run_defect_sweep(
            repo_root=tmp_path,
            register_path=register,
            records_path=_records(tmp_path),
            runner=lambda a, c: "2 passed in 0.01s\n",
        )
        loaded = json.loads(register.read_text(encoding="utf-8"))
        row = loaded["classes"]["DC-1"]
        # Declarations untouched; only the observation block added.
        assert row["name"] == "kept"
        assert row["source"] == "kept-too"
        assert row["last_sweep"] == {
            "enforcement_test_exists": True,
            "enforcement_green": True,
        }

    def test_repeat_sweep_with_same_observation_is_byte_stable(self, tmp_path: Path) -> None:
        (tmp_path / "tests_dc1.py").write_text("", encoding="utf-8")
        register = _register(tmp_path, {"DC-1": {"enforcement_test": "tests_dc1.py"}})
        runner = lambda a, c: "2 passed in 0.01s\n"  # noqa: E731
        run_defect_sweep(
            repo_root=tmp_path, register_path=register,
            records_path=_records(tmp_path), runner=runner,
        )
        first = register.read_bytes()
        first_mtime = register.stat().st_mtime_ns
        run_defect_sweep(
            repo_root=tmp_path, register_path=register,
            records_path=_records(tmp_path), runner=runner,
        )
        assert register.read_bytes() == first
        assert register.stat().st_mtime_ns == first_mtime

    def test_records_file_is_append_only_and_self_contained(self, tmp_path: Path) -> None:
        (tmp_path / "tests_dc1.py").write_text("", encoding="utf-8")
        register = _register(tmp_path, {"DC-1": {"enforcement_test": "tests_dc1.py"}})
        records = _records(tmp_path)
        run_defect_sweep(
            repo_root=tmp_path, register_path=register,
            records_path=records, runner=lambda a, c: "1 passed in 0.01s\n",
        )
        run_defect_sweep(
            repo_root=tmp_path, register_path=register,
            records_path=records, runner=lambda a, c: "1 failed in 0.01s\n",
        )
        lines = [json.loads(line) for line in records.read_text(encoding="utf-8").splitlines()]
        assert len(lines) == 2
        for line in lines:
            assert line["node"] == "SWEEP-DC"
            assert line["at"]
            assert line["answer"]["kind"] in ("KNOWN_CLASS", "NO_MATCH", "WATCH")
        assert lines[0]["answer"]["kind"] == "NO_MATCH"
        assert lines[1]["answer"]["kind"] == "KNOWN_CLASS"

    def test_empty_register_still_answers(self, tmp_path: Path) -> None:
        register = _register(tmp_path, {})
        report = run_defect_sweep(
            repo_root=tmp_path,
            register_path=register,
            records_path=_records(tmp_path),
            runner=lambda a, c: "should never run",
        )
        assert report.open_classes == ()
        assert report.standing_answer().kind == "NO_MATCH"
