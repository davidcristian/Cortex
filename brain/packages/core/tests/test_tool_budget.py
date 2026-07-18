"""Behavior tests for the dispatch budget: the pool, and the per-tool prices spent from it.

The policy itself is a value: what a named tool costs, and what everything else costs. The pool
is a handle. Their consumers are tested where they consume them (``test_dispatch.py`` for the
dispatcher's lookup, ``test_tool_loop.py`` for the loop actually spending it, ``test_spawn.py``
for a batch of subagents sharing one turn's pool).
"""

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


def test_a_fresh_pool_starts_open_at_the_module_bound() -> None:
    budget = DispatchBudget()
    assert (budget.limit, budget.spent, budget.closed) == (MAX_TOOL_DISPATCHES, 0, False)


def test_charging_spends_what_fits_and_reports_that_the_call_may_run() -> None:
    budget = DispatchBudget(limit=5)
    assert budget.charge(3) is True
    assert budget.charge(2) is True  # exactly to the limit still fits
    assert (budget.spent, budget.closed) == (5, False)


def test_a_charge_that_does_not_fit_is_refused_and_costs_nothing() -> None:
    # Refusals are free: closure, not the arithmetic, is what makes the refusal stick, so the
    # spend a turn reports stays the spend it actually made.
    budget = DispatchBudget(limit=4)
    assert budget.charge(3) is True
    assert budget.charge(2) is False
    assert (budget.spent, budget.closed) == (3, True)


def test_a_closed_pool_refuses_a_charge_that_would_still_have_fit() -> None:
    # ADR-0009 cost addendum decision 3, now at the turn's scale: the trailing 1 fits in the
    # unspent unit, and is refused anyway, because BUDGET_EXHAUSTED_MSG told the model to stop
    # calling tools and a pool that kept admitting small calls would make that a lie.
    budget = DispatchBudget(limit=4)
    assert [budget.charge(3), budget.charge(3), budget.charge(1)] == [True, False, False]
    assert budget.spent == 3


def test_a_pool_is_a_handle_not_a_value_so_two_of_them_are_never_the_same_one() -> None:
    # Identity comparison is the point: two turns holding equal-looking budgets must not be
    # mistaken for two references to one pool, which is exactly the bug this object exists to
    # prevent at a larger scale.
    assert DispatchBudget(limit=3) != DispatchBudget(limit=3)


def test_a_pool_resumed_at_a_persisted_position_carries_what_was_left_and_nothing_more() -> None:
    # The swap's requirement (ADR-0030 decision 4 step 4): the deep model gets the allowance
    # the escalating turn had left, so a handoff cannot refill a turn's spend.
    resumed = DispatchBudget.resume(remaining=1, closed=False)
    assert (resumed.limit, resumed.spent, resumed.closed) == (1, 0, False)
    assert [resumed.charge(1), resumed.charge(1)] == [True, False]


def test_a_pool_that_had_already_closed_stays_closed_when_it_is_resumed() -> None:
    # Otherwise a turn that ran itself out of tools would be handed a fresh licence by the very
    # act of swapping models, which is the one thing the carried position exists to prevent.
    resumed = DispatchBudget.resume(remaining=0, closed=True)
    assert resumed.closed is True
    assert resumed.charge(1) is False
