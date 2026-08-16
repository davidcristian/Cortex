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
