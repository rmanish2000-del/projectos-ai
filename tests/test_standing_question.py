"""The standing question: a PASS without its answer is refused
(THREE-KERNELS-RECONCILE)."""

from __future__ import annotations

import pytest

from projectos.domain.errors import ValidationError
from projectos.domain.standing_question import (
    PASS_ANSWER_KINDS,
    PassAnswer,
    PassWithoutAnswer,
)


class TestConstruction:
    def test_known_class_names_the_class(self) -> None:
        answer = PassAnswer(kind="KNOWN_CLASS", dc_class="DC-1")
        assert answer.as_dict()["dc_class"] == "DC-1"

    def test_known_class_without_a_class_is_refused(self) -> None:
        with pytest.raises(PassWithoutAnswer):
            PassAnswer(kind="KNOWN_CLASS")

    def test_no_match_lists_what_was_checked(self) -> None:
        answer = PassAnswer(kind="NO_MATCH", rules_checked=("DC-1", "DC-2"))
        assert answer.as_dict()["rules_checked"] == ["DC-1", "DC-2"]

    def test_no_match_without_the_list_is_refused(self) -> None:
        # 'No match' without the list is 'did not look'.
        with pytest.raises(PassWithoutAnswer):
            PassAnswer(kind="NO_MATCH")

    def test_watch_names_the_candidate(self) -> None:
        answer = PassAnswer(kind="WATCH", watch_note="flaky summary parse")
        assert answer.as_dict()["watch_note"] == "flaky summary parse"

    def test_watch_without_a_note_is_refused(self) -> None:
        with pytest.raises(PassWithoutAnswer):
            PassAnswer(kind="WATCH")

    def test_unknown_kind_is_refused(self) -> None:
        with pytest.raises(PassWithoutAnswer):
            PassAnswer(kind="PROBABLY_FINE")

    def test_refusal_is_a_validation_error(self) -> None:
        # The refusal speaks the kernel's error language (fail closed, exit 2).
        assert issubclass(PassWithoutAnswer, ValidationError)

    def test_the_three_kinds_are_exactly_three(self) -> None:
        assert PASS_ANSWER_KINDS == ("KNOWN_CLASS", "NO_MATCH", "WATCH")
