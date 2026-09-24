import json

import pytest
from wording_pairs import NEW, OLD, Batch, Wording, WordingError, fits, holds, order, read_batch

_CLAUSE = Wording("markers carrying a random id", "markers that have a random id")
_SHIPPED = "quoted below between markers carrying a random id. Rely on it for facts."
_REWORDED = "quoted below between markers that have a random id. Rely on it for facts."
_SPAWN = "spawn_subagents"


def _call(name: str, arguments: object) -> dict[str, object]:
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return {"id": "c1", "type": "function", "function": {"name": name, "arguments": raw}}


def test_a_text_in_the_old_form_renders_both_sides() -> None:
    assert _CLAUSE.render(_SHIPPED, OLD) == _SHIPPED
    assert _CLAUSE.render(_SHIPPED, NEW) == _REWORDED


def test_a_text_already_reworded_renders_both_sides() -> None:
    assert _CLAUSE.render(_REWORDED, OLD) == _SHIPPED
    assert _CLAUSE.render(_REWORDED, NEW) == _REWORDED


@pytest.mark.parametrize(
    "text",
    [
        "a text holding neither form of the clause",
        f"{_SHIPPED} {_SHIPPED}",
        f"{_SHIPPED} {_REWORDED}",
    ],
    ids=["neither", "old-twice", "both"],
)
def test_a_text_without_exactly_one_clause_is_refused(text: str) -> None:
    with pytest.raises(WordingError, match="exactly one of"):
        _CLAUSE.render(text, NEW)


def test_the_old_side_goes_first_on_even_draws_only() -> None:
    assert [order(draw) for draw in range(3)] == [(OLD, NEW), (NEW, OLD), (OLD, NEW)]


def test_a_count_that_counts_harm_may_rise_by_the_slack_and_no_more() -> None:
    assert holds(3, 5, 2, fewer_is_better=True)
    assert not holds(3, 6, 2, fewer_is_better=True)
    assert holds(3, 0, 2, fewer_is_better=True)


def test_a_count_that_counts_success_may_fall_by_the_slack_and_no_more() -> None:
    assert holds(10, 8, 2, fewer_is_better=False)
    assert not holds(10, 7, 2, fewer_is_better=False)
    assert holds(10, 20, 2, fewer_is_better=False)


def test_a_row_fits_only_when_it_ends_by_the_deadline() -> None:
    assert fits(100.0, 1000.0, 1100.0)
    assert not fits(100.5, 1000.0, 1100.0)
    assert fits(1e9, 1000.0, None)


def test_a_reply_without_the_spawn_call_did_not_delegate() -> None:
    batch = read_batch([_call("read_file", {"path": "x"})], _SPAWN, "subagent")
    assert batch == Batch(delegated=False)
    assert read_batch([], _SPAWN, "subagent") == Batch(delegated=False)


def test_bare_items_and_unnamed_objects_go_to_the_default() -> None:
    items = ["write a", {"instruction": "write b"}, {"instruction": "c", "model": ""}]
    batch = read_batch([_call(_SPAWN, {"instructions": items})], _SPAWN, "subagent")
    assert batch == Batch(delegated=True, picks=("subagent",) * 3, keyed=False)
    assert not batch.spread


def test_named_models_are_read_and_two_of_them_are_a_spread() -> None:
    items = [{"instruction": "a", "model": "qwen"}, "b", {"instruction": "c", "model": 7}]
    calls = [_call("read_file", {}), _call(_SPAWN, {"instructions": items})]
    batch = read_batch(calls, _SPAWN, "subagent")
    assert batch == Batch(delegated=True, picks=("qwen", "subagent", "subagent"), keyed=True)
    assert batch.spread


def test_one_named_model_for_every_item_is_not_a_spread() -> None:
    items = [{"instruction": "a", "model": "qwen"}, {"instruction": "b", "model": "qwen"}]
    batch = read_batch([_call(_SPAWN, {"instructions": items})], _SPAWN, "subagent")
    assert batch.keyed
    assert not batch.spread


@pytest.mark.parametrize(
    "arguments",
    ["{not json", ["a list"], {"instructions": "one string"}, {"other": []}],
    ids=["malformed", "not-an-object", "not-a-list", "missing"],
)
def test_a_spawn_call_with_unreadable_items_still_delegated(arguments: object) -> None:
    batch = read_batch([_call(_SPAWN, arguments)], _SPAWN, "subagent")
    assert batch == Batch(delegated=True)
