"""Behavior tests for the salience policies: which calls are dispatched (ADR-0009).

The rule under test is one sentence with two clauses: an identical call runs at most once per
round, and at most ``limit`` times per loop. The tests state each clause separately, because the
first is absolute (a twin the model chose before seeing either result returns nothing new) while
the second is a cap on a legitimate repeat.
"""

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
    """The off switch filters nothing, whatever the history holds."""
    call = _call(path="a.txt")
    assert ALWAYS_SALIENT.admits(call, _rounds([call], [call])) is True


def test_a_first_call_is_admitted_when_nothing_has_been_dispatched() -> None:
    """The empty history is the common case on a loop's first round."""
    assert REPEAT_SALIENCE.admits(_call(path="a.txt"), _rounds()) is True


def test_a_first_call_is_admitted_when_this_round_has_dispatched_nothing_yet() -> None:
    """A round in progress starts as an empty group, which is not a repeat of anything."""
    assert REPEAT_SALIENCE.admits(_call(path="a.txt"), _rounds([])) is True


def test_an_identical_call_in_the_same_round_is_refused() -> None:
    """The absolute clause: the model chose both before seeing either result."""
    first = _call(call_id="c1", path="a.txt")
    twin = _call(call_id="c2", path="a.txt")
    assert REPEAT_SALIENCE.admits(twin, _rounds([first])) is False


def test_a_different_tool_in_the_same_round_is_admitted() -> None:
    """Identity is the tool name first: another tool is never a repeat."""
    other_tool = _call(name="list_dir", path="a.txt")
    assert REPEAT_SALIENCE.admits(other_tool, _rounds([_call(path="a.txt")])) is True


def test_the_same_tool_with_different_arguments_in_the_same_round_is_admitted() -> None:
    """Identity is the arguments too: reading another path asks a different question."""
    assert REPEAT_SALIENCE.admits(_call(path="b.txt"), _rounds([_call(path="a.txt")])) is True


def test_a_repeat_in_a_later_round_is_admitted_once() -> None:
    """The model has read a result and asked again: a retry or a re-observation is legitimate."""
    call = _call(path="a.txt")
    assert REPEAT_SALIENCE.admits(call, _rounds([call], [])) is True


def test_a_third_identical_call_across_rounds_is_refused() -> None:
    """Past the cap the model is repeating itself, so the third identical call is not dispatched."""
    call = _call(path="a.txt")
    assert REPEAT_SALIENCE.admits(call, _rounds([call], [call], [])) is False


def test_the_cap_counts_identical_calls_only() -> None:
    """Other calls in the history never bring an unrelated call closer to its cap."""
    call = _call(path="a.txt")
    noise = _call(name="list_dir", path="b.txt")
    assert REPEAT_SALIENCE.admits(call, _rounds([call, noise], [noise, noise], [])) is True


def test_identity_ignores_the_call_id_and_the_turn_stamp() -> None:
    """What the model chose is the name and the arguments; the rest is the loop's bookkeeping."""
    stamped = ToolCall(
        id="c9", name="read_file", arguments={"path": "a.txt"}, stamp=TurnStamp(session_id="s1")
    )
    assert REPEAT_SALIENCE.admits(stamped, _rounds([_call(path="a.txt")])) is False


def test_arguments_compare_structurally_rather_than_by_key_order() -> None:
    """The same question spelled in another key order is the same question."""
    first = ToolCall(id="c1", name="send", arguments={"to": "a@b.c", "subject": "hi"})
    reordered = ToolCall(id="c2", name="send", arguments={"subject": "hi", "to": "a@b.c"})
    assert REPEAT_SALIENCE.admits(reordered, _rounds([first])) is False


def test_a_tighter_limit_refuses_the_second_call() -> None:
    """The cap comes from the policy instance rather than a constant inside the comparison."""
    call = _call(path="a.txt")
    assert RepeatSalience(limit=1).admits(call, _rounds([call], [])) is False


def test_the_default_limit_is_the_shared_constant() -> None:
    """The shipped policy is the documented number, so the ADR and the code cannot drift."""
    assert RepeatSalience().limit == MAX_IDENTICAL_DISPATCHES


@pytest.mark.parametrize("limit", [0, -1])
def test_a_non_positive_limit_is_rejected_at_construction(limit: int) -> None:
    """A limit of zero would block even the first call, so a non-positive limit raises here."""
    with pytest.raises(ValueError, match="salience limit must be positive"):
        RepeatSalience(limit=limit)
