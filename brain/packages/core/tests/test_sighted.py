"""``SightedToolRegistry``: the screen is offered and run only while the model can read one.

The staleness this exists for is real and was reproduced against the running stack on
2026-08-06: a model host recreated without its projector left `GET /props` answering
``vision: false`` under a brain that had probed once at startup and never asked again, and the
next "look at my screen" blitted a display, notified the user, tainted the turn, and died on
llama.cpp's own ``image input is not supported`` 500. Every case below is one link in the chain
that now cannot happen.

Mutations proving these tests can fail (each applied to `sighted.py` alone, `packages/core` plus
`packages/orchestrator` re-run, measured 2026-08-06):

- deleting the `invoke` guard fails 3: `test_a_capture_is_refused_before_the_body_is_ever_asked`,
  `test_the_answer_that_authorizes_a_capture_is_taken_at_the_call`, and the composition root's
  own `test_a_capture_the_model_can_no_longer_read_reads_no_pixels`. The second is the one that
  matters: the first would also fail under a describe-time-only fix, and the second would not;
- deleting the `describe_tools` filter fails 2, this suite's
  `test_a_blind_model_is_not_offered_the_screen` and the root's
  `test_the_probes_answer_decides_whether_the_screen_is_offered`;
- caching the first answer (asked once, reused) fails 2, and they are exactly the two cases
  that change the world between the advertisement and the call, which is the entire point of the
  port;
- dropping the "is the capture tool even here" short circuit fails 1,
  `test_a_registry_without_the_screen_never_asks`.
"""

import pytest

from cortex_core import (
    BLIND_MSG,
    CAPTURE_SCREEN_TOOL_NAME,
    GET_VOLUME_TOOL_NAME,
    ScriptedVisionProbe,
    SightedToolRegistry,
    ToolCall,
    ToolNotFoundError,
    ToolRegistry,
)
from cortex_core.tools import ToolResult, ToolSpec


class _Registry:
    """A minimal `ToolRegistry` advertising the given specs and recording what it was asked."""

    def __init__(self, *names: str) -> None:
        self.specs = tuple(
            ToolSpec(name=name, description=name, parameters={"type": "object", "properties": {}})
            for name in names
        )
        self.invoked: list[str] = []

    async def describe_tools(self) -> tuple[ToolSpec, ...]:
        return self.specs

    async def invoke(self, call: ToolCall) -> ToolResult:
        self.invoked.append(call.name)
        return ToolResult(call_id=call.id, content="ran")


def _capture_call() -> ToolCall:
    return ToolCall(id="c1", name=CAPTURE_SCREEN_TOOL_NAME, arguments={})


async def test_a_seeing_model_is_offered_the_screen_and_may_use_it() -> None:
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME, GET_VOLUME_TOOL_NAME)
    registry = SightedToolRegistry(inner, ScriptedVisionProbe([True]))

    names = [spec.name for spec in await registry.describe_tools()]
    result = await registry.invoke(_capture_call())

    assert names == [CAPTURE_SCREEN_TOOL_NAME, GET_VOLUME_TOOL_NAME]
    assert result.content == "ran"
    assert inner.invoked == [CAPTURE_SCREEN_TOOL_NAME]


async def test_a_blind_model_is_not_offered_the_screen() -> None:
    """A model that cannot read a picture is not offered the tool that takes one."""
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME, GET_VOLUME_TOOL_NAME)
    registry = SightedToolRegistry(inner, ScriptedVisionProbe([False]))

    assert [spec.name for spec in await registry.describe_tools()] == [GET_VOLUME_TOOL_NAME]


async def test_a_capture_is_refused_before_the_body_is_ever_asked() -> None:
    """A capture is refused before the body is asked, so no pixels are read and no privacy cost
    is paid."""
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME)
    registry = SightedToolRegistry(inner, ScriptedVisionProbe([False]))

    with pytest.raises(ToolNotFoundError) as raised:
        await registry.invoke(_capture_call())

    assert inner.invoked == [], "the inner registry, and so the body, was never reached"
    assert str(raised.value) == BLIND_MSG
    assert "the screen was not read" in str(raised.value)


async def test_the_answer_that_authorizes_a_capture_is_taken_at_the_call() -> None:
    """A turn lists its tools once and then runs rounds against them, so the call re-asks.

    Scripted True then False is the reproduced failure in miniature: the advertisement was
    honest when it was made, the server was replaced, and the call is what must not be honoured
    on the older answer.
    """
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME)
    probe = ScriptedVisionProbe([True, False])
    registry = SightedToolRegistry(inner, probe)

    assert [spec.name for spec in await registry.describe_tools()] == [CAPTURE_SCREEN_TOOL_NAME]
    with pytest.raises(ToolNotFoundError):
        await registry.invoke(_capture_call())
    assert probe.asked == 2, "the advertisement's answer was not reused for the call"
    assert inner.invoked == []


async def test_every_other_tool_passes_through_a_blind_model_untouched() -> None:
    """Only the screen is restricted; a model that cannot see still has hands."""
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME, GET_VOLUME_TOOL_NAME)
    registry = SightedToolRegistry(inner, ScriptedVisionProbe([False]))

    result = await registry.invoke(ToolCall(id="v1", name=GET_VOLUME_TOOL_NAME, arguments={}))

    assert result.content == "ran"
    assert inner.invoked == [GET_VOLUME_TOOL_NAME]


async def test_a_registry_without_the_screen_never_asks() -> None:
    """A set with no capture tool (the deep tier's, a body-less one's) costs nothing at all."""
    inner = _Registry(GET_VOLUME_TOOL_NAME)
    probe = ScriptedVisionProbe([True])
    registry = SightedToolRegistry(inner, probe)

    assert [spec.name for spec in await registry.describe_tools()] == [GET_VOLUME_TOOL_NAME]
    assert probe.asked == 0


async def test_the_scripted_probe_repeats_its_last_answer() -> None:
    """The fake's own contract: a script shorter than the questions keeps answering."""
    probe = ScriptedVisionProbe([True, False])

    assert [await probe.can_see() for _ in range(4)] == [True, False, False, False]
    assert probe.asked == 4


async def test_the_default_scripted_probe_can_see() -> None:
    """A fake built with no script answers that it can see, so a test writes only the script it
    cares about."""
    assert await ScriptedVisionProbe().can_see() is True


async def test_it_is_a_tool_registry() -> None:
    """It satisfies `ToolRegistry`, so it goes wherever one goes, a composite included."""
    registry: ToolRegistry = SightedToolRegistry(_Registry(), ScriptedVisionProbe([True]))

    assert await registry.describe_tools() == ()
