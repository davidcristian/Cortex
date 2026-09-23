import pytest

from cortex_core.tool_budget import (
    DEFAULT_TOOL_COST,
    MAX_TOOL_DISPATCHES,
    UNIFORM_COST,
    DispatchBudget,
    ToolCostPolicy,
)


def test_a_priced_tool_costs_its_price_and_everything_else_costs_the_default() -> None:
    policy = ToolCostPolicy({"spawn_subagents": 8})
    assert policy.cost_of("spawn_subagents") == 8
    assert policy.cost_of("read_file") == DEFAULT_TOOL_COST


def test_the_uniform_policy_prices_every_tool_at_one() -> None:
    assert DEFAULT_TOOL_COST == 1
    assert UNIFORM_COST.cost_of("anything") == 1
    assert UNIFORM_COST.costs == {}


@pytest.mark.parametrize("cost", [0, -1])
def test_a_non_positive_price_is_rejected_rather_than_making_a_tool_free(cost: int) -> None:
    with pytest.raises(ValueError, match=r"must be positive: \['send_email'\]"):
        ToolCostPolicy({"send_email": cost})


def test_every_bad_price_is_named_at_once_and_sorted() -> None:
    with pytest.raises(ValueError, match=r"\['a', 'b'\]"):
        ToolCostPolicy({"b": 0, "a": -3, "ok": 2})


def test_the_policy_does_not_alias_the_mapping_it_was_built_from() -> None:
    source = {"spawn_subagents": 8}
    policy = ToolCostPolicy(source)
    source["spawn_subagents"] = 1
    source["read_file"] = 1
    assert policy.cost_of("spawn_subagents") == 8
    assert policy.cost_of("read_file") == DEFAULT_TOOL_COST
    with pytest.raises(TypeError):
        policy.costs["read_file"] = 99  # pyright: ignore[reportIndexIssue]


def test_a_fresh_pool_starts_open_at_the_module_bound() -> None:
    budget = DispatchBudget()
    assert (budget.limit, budget.spent, budget.closed) == (MAX_TOOL_DISPATCHES, 0, False)


def test_charging_spends_what_fits_and_reports_that_the_call_may_run() -> None:
    budget = DispatchBudget(limit=5)
    assert budget.charge(3) is True
    assert budget.charge(2) is True
    assert (budget.spent, budget.closed) == (5, False)


def test_a_charge_that_does_not_fit_is_refused_and_costs_nothing() -> None:
    budget = DispatchBudget(limit=4)
    assert budget.charge(3) is True
    assert budget.charge(2) is False
    assert (budget.spent, budget.closed) == (3, True)


def test_a_closed_pool_refuses_a_charge_that_would_still_have_fit() -> None:
    budget = DispatchBudget(limit=4)
    assert [budget.charge(3), budget.charge(3), budget.charge(1)] == [True, False, False]
    assert budget.spent == 3


def test_a_pool_is_a_handle_not_a_value_so_two_of_them_are_never_the_same_one() -> None:
    assert DispatchBudget(limit=3) != DispatchBudget(limit=3)


def test_a_pool_resumed_at_a_persisted_position_keeps_what_was_left_and_nothing_more() -> None:
    resumed = DispatchBudget.resume(remaining=1, closed=False)
    assert (resumed.limit, resumed.spent, resumed.closed) == (1, 0, False)
    assert [resumed.charge(1), resumed.charge(1)] == [True, False]


def test_a_pool_that_had_already_closed_stays_closed_when_it_is_resumed() -> None:
    resumed = DispatchBudget.resume(remaining=0, closed=True)
    assert resumed.closed is True
    assert resumed.charge(1) is False
