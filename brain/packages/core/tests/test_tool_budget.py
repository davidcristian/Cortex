"""Behavior tests for the per-tool dispatch price policy (ADR-0009 cost addendum).

The policy itself is a value: what a named tool costs, and what everything else costs. Its
consumers are tested where they consume it (``test_dispatch.py`` for the dispatcher's lookup,
``test_tool_loop.py`` for the loop actually spending it).
"""

import pytest

from cortex_core.tool_budget import DEFAULT_TOOL_COST, UNIFORM_COST, ToolCostPolicy


def test_a_priced_tool_costs_its_price_and_everything_else_costs_the_default() -> None:
    policy = ToolCostPolicy({"spawn_subagents": 8})
    assert policy.cost_of("spawn_subagents") == 8
    assert policy.cost_of("read_file") == DEFAULT_TOOL_COST


def test_the_uniform_policy_prices_every_tool_at_one() -> None:
    # The default every dispatcher gets: a budget of N is N calls, which is the plain count
    # the budget shipped as before prices existed.
    assert DEFAULT_TOOL_COST == 1
    assert UNIFORM_COST.cost_of("anything") == 1
    assert UNIFORM_COST.costs == {}


@pytest.mark.parametrize("cost", [0, -1])
def test_a_non_positive_price_is_rejected_rather_than_making_a_tool_free(cost: int) -> None:
    # A free tool is the one failure the budget cannot survive: the loop charges it nothing,
    # so it can be dispatched without limit, and the misconfiguration shows up as unbounded
    # external calls rather than as an error.
    with pytest.raises(ValueError, match=r"must be positive: \['send_email'\]"):
        ToolCostPolicy({"send_email": cost})


def test_every_bad_price_is_named_at_once_and_sorted() -> None:
    with pytest.raises(ValueError, match=r"\['a', 'b'\]"):
        ToolCostPolicy({"b": 0, "a": -3, "ok": 2})


def test_the_policy_does_not_alias_the_mapping_it_was_built_from() -> None:
    # A frozen dataclass holding a live dict would let whoever built it keep editing prices
    # after the fact, so the composition root's config object could not be trusted as a
    # snapshot. The policy copies, and its own mapping rejects writes.
    source = {"spawn_subagents": 8}
    policy = ToolCostPolicy(source)
    source["spawn_subagents"] = 1
    source["read_file"] = 1
    assert policy.cost_of("spawn_subagents") == 8
    assert policy.cost_of("read_file") == DEFAULT_TOOL_COST
    with pytest.raises(TypeError):
        policy.costs["read_file"] = 99  # pyright: ignore[reportIndexIssue]
