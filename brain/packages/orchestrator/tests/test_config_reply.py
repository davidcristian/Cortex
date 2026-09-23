import pytest

from cortex_core import GenerationBounds
from cortex_orchestrator.config_reply import ReplyBoundsConfig


def test_an_unset_deployment_asks_for_no_bounds_at_all() -> None:
    assert ReplyBoundsConfig().bounds() is None


def test_a_cap_alone_is_carried_with_thinking_left_where_the_template_put_it() -> None:
    assert ReplyBoundsConfig(max_tokens=2048).bounds() == GenerationBounds(
        max_tokens=2048, thinking=True
    )


def test_thinking_off_alone_carries_no_cap() -> None:
    assert ReplyBoundsConfig(thinking=False).bounds() == GenerationBounds(
        max_tokens=None, thinking=False
    )


def test_both_settings_travel_together_as_one_value() -> None:
    assert ReplyBoundsConfig(max_tokens=512, thinking=False).bounds() == GenerationBounds(
        max_tokens=512, thinking=False
    )


def test_a_negative_cap_is_refused_at_the_edge_rather_than_at_the_server() -> None:
    with pytest.raises(ValueError, match="greater than or equal to 0"):
        ReplyBoundsConfig(max_tokens=-1)


def test_a_trace_budget_alone_is_carried_with_the_other_two_left_alone() -> None:
    assert ReplyBoundsConfig(trace_tokens=128).bounds() == GenerationBounds(
        max_tokens=None, thinking=True, trace_tokens=128
    )


def test_a_trace_budget_of_zero_is_a_setting_and_not_an_absence() -> None:
    assert ReplyBoundsConfig(trace_tokens=0).bounds() == GenerationBounds(
        max_tokens=None, thinking=True, trace_tokens=0
    )


def test_thinking_off_never_budgets_the_trace_on_a_users_own_reply() -> None:
    assert ReplyBoundsConfig(thinking=False).bounds() == GenerationBounds(
        max_tokens=None, thinking=False, trace_tokens=None
    )


def test_a_trace_budget_below_the_unset_sentinel_is_refused_at_the_edge() -> None:
    with pytest.raises(ValueError, match="greater than or equal to -1"):
        ReplyBoundsConfig(trace_tokens=-2)
