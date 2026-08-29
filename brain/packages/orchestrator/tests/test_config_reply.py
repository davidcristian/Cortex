"""The deployment's bounds on a user-facing reply: what each setting reduces to.

The whole module's job is to produce ``None`` or a ``GenerationBounds``, so every case here is a
setting and the port value it becomes. The one that matters is the default, because ``None`` is
what keeps an unasked deployment's request byte-identical to the one this repo has always sent.
"""

import pytest

from cortex_core import GenerationBounds
from cortex_orchestrator.config_reply import ReplyBoundsConfig


def test_an_unset_deployment_asks_for_no_bounds_at_all() -> None:
    """Neither knob set is the request this repo shipped, so the port is handed nothing."""
    assert ReplyBoundsConfig().bounds() is None


def test_a_cap_alone_is_carried_with_thinking_left_where_the_template_put_it() -> None:
    assert ReplyBoundsConfig(max_tokens=2048).bounds() == GenerationBounds(
        max_tokens=2048, thinking=True
    )


def test_thinking_off_alone_carries_no_cap() -> None:
    """The lever for the wait rather than for the length: no cap, no deliberation."""
    assert ReplyBoundsConfig(thinking=False).bounds() == GenerationBounds(
        max_tokens=None, thinking=False
    )


def test_both_knobs_travel_together_as_one_value() -> None:
    assert ReplyBoundsConfig(max_tokens=512, thinking=False).bounds() == GenerationBounds(
        max_tokens=512, thinking=False
    )


def test_a_negative_cap_is_refused_at_the_edge_rather_than_at_the_server() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        ReplyBoundsConfig(max_tokens=-1)


def test_a_trace_budget_alone_is_carried_with_the_other_two_left_alone() -> None:
    """The dial's middle, per request (ADR-0005 request-lever addendum).

    A deployment that wants its reply sooner without giving the deliberation up sets this and
    nothing else, and what reaches the port is the count with both other knobs untouched.
    """
    assert ReplyBoundsConfig(trace_tokens=128).bounds() == GenerationBounds(
        max_tokens=None, thinking=True, trace_tokens=128
    )


def test_a_trace_budget_of_zero_is_a_setting_and_not_an_absence() -> None:
    """Zero ends the thought at once, so it must survive the reduction that answers ``None``.

    The sentinel for "nobody asked" cannot be the falsy value, which is the same trap the model
    host's own budget names: a reading that folded the two would hand this deployment the
    unbounded trace it deliberately turned off.
    """
    assert ReplyBoundsConfig(trace_tokens=0).bounds() == GenerationBounds(
        max_tokens=None, thinking=True, trace_tokens=0
    )


def test_thinking_off_never_budgets_the_trace_on_a_users_own_reply() -> None:
    """The switch alone leaves the count to the tier, and that is the decision (ADR-0005).

    A user's reply renders its trace as the thinking status the overlay shows (ADR-0020), so a
    zero derived from the switch would blank a surface somebody is reading, on the one path in
    this repo where a bounded trace is a loss. Every deployment that wants one names it.
    """
    assert ReplyBoundsConfig(thinking=False).bounds() == GenerationBounds(
        max_tokens=None, thinking=False, trace_tokens=None
    )


def test_a_trace_budget_below_the_unset_sentinel_is_refused_at_the_edge() -> None:
    """Only the one negative that means "unset" is accepted; the port has no other."""
    with pytest.raises(ValueError, match="greater than or equal to -1"):
        ReplyBoundsConfig(trace_tokens=-2)
