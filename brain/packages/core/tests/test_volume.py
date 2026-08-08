"""Behavior tests for the volume built-in tools and the InMemoryBodyGateway fake (ADR-0023)."""

import pytest

from cortex_core import (
    GET_VOLUME_TOOL_NAME,
    SET_VOLUME_TOOL_NAME,
    BodyFailure,
    BodyGatewayError,
    GetVolumeTool,
    InMemoryBodyGateway,
    SetVolumeTool,
    ToolCall,
    Trust,
    VolumeState,
)


def _call(name: str, arguments: dict[str, object]) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


# --- InMemoryBodyGateway (the fake, the gRPC adapter's contract twin) --------------------


async def test_in_memory_gateway_reports_its_state() -> None:
    gateway = InMemoryBodyGateway(level=0.4, muted=True)
    assert await gateway.get_volume() == VolumeState(level=0.4, muted=True)


async def test_in_memory_gateway_applies_and_clamps_a_change() -> None:
    gateway = InMemoryBodyGateway(level=0.5, muted=False)
    # Level over 1.0 clamps to 1.0; mute left untouched (None).
    assert await gateway.set_volume(level=1.5) == VolumeState(level=1.0, muted=False)
    # Level under 0.0 clamps to 0.0; mute toggled.
    assert await gateway.set_volume(level=-0.2, mute=True) == VolumeState(level=0.0, muted=True)
    # Neither field set leaves the last state intact.
    assert await gateway.set_volume() == VolumeState(level=0.0, muted=True)


async def test_in_memory_gateway_raises_the_scripted_failure() -> None:
    boom = BodyGatewayError("body down")
    gateway = InMemoryBodyGateway(fail=boom)
    with pytest.raises(BodyGatewayError):
        await gateway.get_volume()
    with pytest.raises(BodyGatewayError):
        await gateway.set_volume(mute=True)


# --- GetVolumeTool -----------------------------------------------------------------------


async def test_get_volume_tool_spec_is_read_only_and_ungated() -> None:
    tool = GetVolumeTool(InMemoryBodyGateway())
    spec = tool.spec
    assert spec.name == GET_VOLUME_TOOL_NAME
    assert spec.gated is False
    assert spec.parameters["properties"] == {}


async def test_get_volume_tool_reports_state_trusted() -> None:
    tool = GetVolumeTool(InMemoryBodyGateway(level=0.3, muted=False))
    result = await tool.invoke(_call(GET_VOLUME_TOOL_NAME, {}))
    assert result.is_error is False
    assert result.trust is Trust.TRUSTED
    assert result.content == "volume is at 30%"


async def test_get_volume_tool_reports_muted() -> None:
    tool = GetVolumeTool(InMemoryBodyGateway(level=0.8, muted=True))
    result = await tool.invoke(_call(GET_VOLUME_TOOL_NAME, {}))
    assert result.content == "volume is at 80%, muted"


async def test_get_volume_tool_unreachable_body_is_a_trusted_error() -> None:
    fail = BodyGatewayError("no route", kind=BodyFailure.UNREACHABLE)
    tool = GetVolumeTool(InMemoryBodyGateway(fail=fail))
    result = await tool.invoke(_call(GET_VOLUME_TOOL_NAME, {}))
    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert result.content == "could not reach the body to control volume: no route"


async def test_get_volume_tool_says_the_host_is_unready_when_it_has_no_endpoint() -> None:
    """The volume half of the prefix defect. A host with no default audio device is not a
    body nobody could reach, and the two used to be the same sentence behind the same status
    code, so the cortex could not tell a dead body from an unplugged speaker."""
    fail = BodyGatewayError(
        "body get_volume failed: no audio endpoint: no device", kind=BodyFailure.UNREADY
    )
    result = await GetVolumeTool(InMemoryBodyGateway(fail=fail)).invoke(
        _call(GET_VOLUME_TOOL_NAME, {})
    )
    assert result.content == (
        "the host is not in a state to control volume: body get_volume failed: "
        "no audio endpoint: no device"
    )
    assert "could not reach the body" not in result.content


# --- SetVolumeTool -----------------------------------------------------------------------


async def test_set_volume_tool_spec_is_ungated() -> None:
    tool = SetVolumeTool(InMemoryBodyGateway())
    spec = tool.spec
    assert spec.name == SET_VOLUME_TOOL_NAME
    assert spec.gated is False
    assert set(spec.parameters["properties"]) == {"level", "mute"}


async def test_set_volume_tool_sets_level_and_mute() -> None:
    gateway = InMemoryBodyGateway(level=0.1, muted=False)
    tool = SetVolumeTool(gateway)
    result = await tool.invoke(_call(SET_VOLUME_TOOL_NAME, {"level": 0.25, "mute": True}))
    assert result.is_error is False
    assert result.trust is Trust.TRUSTED
    assert result.content == "volume is at 25%, muted"


async def test_set_volume_tool_accepts_an_integer_level() -> None:
    # JSON often carries 1 rather than 1.0; an int in range is a valid level.
    tool = SetVolumeTool(InMemoryBodyGateway(level=0.2, muted=False))
    result = await tool.invoke(_call(SET_VOLUME_TOOL_NAME, {"level": 1}))
    assert result.content == "volume is at 100%"


async def test_set_volume_tool_mute_only_leaves_level() -> None:
    tool = SetVolumeTool(InMemoryBodyGateway(level=0.6, muted=False))
    result = await tool.invoke(_call(SET_VOLUME_TOOL_NAME, {"mute": True}))
    assert result.content == "volume is at 60%, muted"


@pytest.mark.parametrize(
    ("arguments", "fragment"),
    [
        ({}, "requires"),
        ({"level": "loud"}, "'level' must be a number"),
        ({"level": True}, "'level' must be a number"),
        ({"level": 1.5}, "'level' must be a number"),
        ({"level": -0.1}, "'level' must be a number"),
        # An oversized JSON integer overflows float(): must be a recoverable message, not a raise.
        ({"level": 10**400}, "'level' must be a number"),
        ({"level": -(10**400)}, "'level' must be a number"),
        ({"mute": "yes"}, "'mute' must be true or false"),
    ],
)
async def test_set_volume_tool_rejects_bad_arguments(
    arguments: dict[str, object], fragment: str
) -> None:
    tool = SetVolumeTool(InMemoryBodyGateway())
    result = await tool.invoke(_call(SET_VOLUME_TOOL_NAME, arguments))
    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert fragment in result.content


async def test_set_volume_tool_unreachable_body_is_a_trusted_error() -> None:
    fail = BodyGatewayError("no route", kind=BodyFailure.UNREACHABLE)
    tool = SetVolumeTool(InMemoryBodyGateway(fail=fail))
    result = await tool.invoke(_call(SET_VOLUME_TOOL_NAME, {"mute": False}))
    assert result.is_error is True
    assert result.trust is Trust.TRUSTED
    assert result.content == "could not reach the body to control volume: no route"


async def test_set_volume_tool_says_the_body_refused_when_the_body_refused() -> None:
    """A standing refusal (a rejected seam token) is not a body that could not be reached,
    and retrying it changes nothing, which is what the wording now lets the cortex know."""
    fail = BodyGatewayError(
        "body set_volume failed: invalid or missing seam token", kind=BodyFailure.REFUSED
    )
    result = await SetVolumeTool(InMemoryBodyGateway(fail=fail)).invoke(
        _call(SET_VOLUME_TOOL_NAME, {"mute": False})
    )
    assert result.content == (
        "the body refused to control volume: body set_volume failed: invalid or missing seam token"
    )
