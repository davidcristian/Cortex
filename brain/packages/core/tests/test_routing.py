"""Behavior tests for cortex_core.routing: every branch and precedence interaction."""

import dataclasses

import pytest

from cortex_core import RoutingHints, Tier, route_turn


def test_default_hints_route_to_cortex() -> None:
    assert route_turn(RoutingHints()) is Tier.CORTEX


def test_deep_reasoning_routes_to_brain() -> None:
    assert route_turn(RoutingHints(needs_deep_reasoning=True)) is Tier.BRAIN


def test_narrow_delegable_routes_to_subagent() -> None:
    assert route_turn(RoutingHints(is_narrow_delegable=True)) is Tier.SUBAGENT


def test_deep_reasoning_takes_precedence_over_narrow_delegable() -> None:
    hints = RoutingHints(needs_deep_reasoning=True, is_narrow_delegable=True)
    assert route_turn(hints) is Tier.BRAIN


@pytest.mark.parametrize("tier", list(Tier))
def test_explicit_tier_is_honored(tier: Tier) -> None:
    assert route_turn(RoutingHints(explicit_tier=tier)) is tier


def test_explicit_cortex_overrides_deep_reasoning() -> None:
    hints = RoutingHints(explicit_tier=Tier.CORTEX, needs_deep_reasoning=True)
    assert route_turn(hints) is Tier.CORTEX


def test_explicit_subagent_overrides_every_other_hint() -> None:
    hints = RoutingHints(
        explicit_tier=Tier.SUBAGENT,
        needs_deep_reasoning=True,
        is_narrow_delegable=True,
    )
    assert route_turn(hints) is Tier.SUBAGENT


@pytest.mark.parametrize(
    ("tier", "value"),
    [(Tier.CORTEX, "cortex"), (Tier.SUBAGENT, "subagent"), (Tier.BRAIN, "brain")],
)
def test_tier_values_are_stable_strings(tier: Tier, value: str) -> None:
    assert tier.value == value


def test_hints_are_immutable() -> None:
    hints = RoutingHints()
    with pytest.raises(dataclasses.FrozenInstanceError):
        hints.needs_deep_reasoning = True  # pyright: ignore[reportAttributeAccessIssue]
