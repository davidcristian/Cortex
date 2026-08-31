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
    """A minimal ``ToolRegistry`` that advertises the given specs and records what it was asked."""

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
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME, GET_VOLUME_TOOL_NAME)
    registry = SightedToolRegistry(inner, ScriptedVisionProbe([False]))

    assert [spec.name for spec in await registry.describe_tools()] == [GET_VOLUME_TOOL_NAME]


async def test_a_capture_is_refused_before_the_body_is_ever_asked() -> None:
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME)
    registry = SightedToolRegistry(inner, ScriptedVisionProbe([False]))

    with pytest.raises(ToolNotFoundError) as raised:
        await registry.invoke(_capture_call())

    assert inner.invoked == [], "the inner registry, and so the body, was never reached"
    assert str(raised.value) == BLIND_MSG
    assert "the screen was not read" in str(raised.value)


async def test_the_answer_that_authorizes_a_capture_is_taken_at_the_call() -> None:
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME)
    probe = ScriptedVisionProbe([True, False])
    registry = SightedToolRegistry(inner, probe)

    assert [spec.name for spec in await registry.describe_tools()] == [CAPTURE_SCREEN_TOOL_NAME]
    with pytest.raises(ToolNotFoundError):
        await registry.invoke(_capture_call())
    assert probe.asked == 2, "the advertisement's answer was not reused for the call"
    assert inner.invoked == []


async def test_every_other_tool_passes_through_a_blind_model_untouched() -> None:
    inner = _Registry(CAPTURE_SCREEN_TOOL_NAME, GET_VOLUME_TOOL_NAME)
    registry = SightedToolRegistry(inner, ScriptedVisionProbe([False]))

    result = await registry.invoke(ToolCall(id="v1", name=GET_VOLUME_TOOL_NAME, arguments={}))

    assert result.content == "ran"
    assert inner.invoked == [GET_VOLUME_TOOL_NAME]


async def test_a_registry_without_the_screen_never_asks() -> None:
    inner = _Registry(GET_VOLUME_TOOL_NAME)
    probe = ScriptedVisionProbe([True])
    registry = SightedToolRegistry(inner, probe)

    assert [spec.name for spec in await registry.describe_tools()] == [GET_VOLUME_TOOL_NAME]
    assert probe.asked == 0


async def test_the_scripted_probe_repeats_its_last_answer() -> None:
    probe = ScriptedVisionProbe([True, False])

    assert [await probe.can_see() for _ in range(4)] == [True, False, False, False]
    assert probe.asked == 4


async def test_the_default_scripted_probe_can_see() -> None:
    assert await ScriptedVisionProbe().can_see() is True


async def test_it_is_a_tool_registry() -> None:
    registry: ToolRegistry = SightedToolRegistry(_Registry(), ScriptedVisionProbe([True]))

    assert await registry.describe_tools() == ()
