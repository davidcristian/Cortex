from collections.abc import Sequence

import pytest

from cortex_core import (
    ALWAYS_SALIENT,
    MAX_IDENTICAL_DISPATCHES,
    REPEAT_SALIENCE,
    RepeatSalience,
    ToolCall,
    TurnStamp,
)


def _call(name: str = "read_file", call_id: str = "c1", **arguments: object) -> ToolCall:
    return ToolCall(id=call_id, name=name, arguments=arguments)


def _rounds(*rounds: Sequence[ToolCall]) -> Sequence[Sequence[ToolCall]]:
    return rounds


def test_always_salient_admits_a_call_it_has_already_seen_twice() -> None:
    call = _call(path="a.txt")
    assert ALWAYS_SALIENT.admits(call, _rounds([call], [call])) is True


def test_a_first_call_is_admitted_when_nothing_has_been_dispatched() -> None:
    assert REPEAT_SALIENCE.admits(_call(path="a.txt"), _rounds()) is True


def test_a_first_call_is_admitted_when_this_round_has_dispatched_nothing_yet() -> None:
    assert REPEAT_SALIENCE.admits(_call(path="a.txt"), _rounds([])) is True


def test_an_identical_call_in_the_same_round_is_refused() -> None:
    first = _call(call_id="c1", path="a.txt")
    twin = _call(call_id="c2", path="a.txt")
    assert REPEAT_SALIENCE.admits(twin, _rounds([first])) is False


def test_a_different_tool_in_the_same_round_is_admitted() -> None:
    other_tool = _call(name="list_dir", path="a.txt")
    assert REPEAT_SALIENCE.admits(other_tool, _rounds([_call(path="a.txt")])) is True


def test_the_same_tool_with_different_arguments_in_the_same_round_is_admitted() -> None:
    assert REPEAT_SALIENCE.admits(_call(path="b.txt"), _rounds([_call(path="a.txt")])) is True


def test_a_repeat_in_a_later_round_is_admitted_once() -> None:
    call = _call(path="a.txt")
    assert REPEAT_SALIENCE.admits(call, _rounds([call], [])) is True


def test_a_third_identical_call_across_rounds_is_refused() -> None:
    call = _call(path="a.txt")
    assert REPEAT_SALIENCE.admits(call, _rounds([call], [call], [])) is False


def test_the_cap_counts_identical_calls_only() -> None:
    call = _call(path="a.txt")
    noise = _call(name="list_dir", path="b.txt")
    assert REPEAT_SALIENCE.admits(call, _rounds([call, noise], [noise, noise], [])) is True


def test_identity_ignores_the_call_id_and_the_turn_stamp() -> None:
    stamped = ToolCall(
        id="c9", name="read_file", arguments={"path": "a.txt"}, stamp=TurnStamp(session_id="s1")
    )
    assert REPEAT_SALIENCE.admits(stamped, _rounds([_call(path="a.txt")])) is False


def test_arguments_compare_structurally_rather_than_by_key_order() -> None:
    first = ToolCall(id="c1", name="send", arguments={"to": "a@b.c", "subject": "hi"})
    reordered = ToolCall(id="c2", name="send", arguments={"subject": "hi", "to": "a@b.c"})
    assert REPEAT_SALIENCE.admits(reordered, _rounds([first])) is False


def test_a_tighter_limit_refuses_the_second_call() -> None:
    call = _call(path="a.txt")
    assert RepeatSalience(limit=1).admits(call, _rounds([call], [])) is False


def test_the_default_limit_is_the_shared_constant() -> None:
    assert RepeatSalience().limit == MAX_IDENTICAL_DISPATCHES


@pytest.mark.parametrize("limit", [0, -1])
def test_a_non_positive_limit_is_rejected_at_construction(limit: int) -> None:
    with pytest.raises(ValueError, match="salience limit must be positive"):
        RepeatSalience(limit=limit)
