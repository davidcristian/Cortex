import asyncio
import time
from collections.abc import Sequence

import pytest

from cortex_core import (
    BoundedToolRegistry,
    ToolCall,
    ToolError,
    ToolResult,
    ToolSpec,
)

# Short enough that the suite spends no real time on it, long enough that a loaded machine still
# reaches the await before it fires.
_BOUND_S = 0.02

# How much later than the bound the slow stub answers. Both waits are timers on one event loop,
# so the earlier one always fires first; three rather than two so a change has to more than
# double the bound to slip through.
_LATE_FACTOR = 3

# How long a case waits for the bound to do anything before failing instead of hanging. It is
# generous because it measures nothing: the stub always answers.
_GIVE_UP_S = 10.0

_SPEC = ToolSpec(name="read", description="", parameters={})
_CALL = ToolCall(id="c-1", name="read", arguments={"path": "/etc/hosts"})


class _StubRegistry:
    """A registry that answers at once, answers far too late, or raises the error it was given."""

    def __init__(self, *, slow: bool = False, raises: BaseException | None = None) -> None:
        self._slow = slow
        self._raises = raises
        self.cancelled = False

    async def describe_tools(self) -> Sequence[ToolSpec]:
        await self._answer()
        return (_SPEC,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        await self._answer()
        return ToolResult(call_id=call.id, content="read /etc/hosts")

    async def _answer(self) -> None:
        if self._raises is not None:
            raise self._raises
        if not self._slow:
            return
        try:
            await asyncio.sleep(_BOUND_S * _LATE_FACTOR)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


def _bounded(inner: _StubRegistry) -> BoundedToolRegistry:
    return BoundedToolRegistry(inner, timeout_s=_BOUND_S)


async def test_a_call_that_answers_in_time_is_handed_back_untouched() -> None:
    bounded = _bounded(_StubRegistry())
    assert [spec.name for spec in await bounded.describe_tools()] == ["read"]
    result = await bounded.invoke(_CALL)
    assert (result.call_id, result.content, result.is_error) == ("c-1", "read /etc/hosts", False)


async def test_a_call_that_outruns_the_bound_raises_tool_error_naming_the_tool() -> None:
    inner = _StubRegistry(slow=True)
    started = time.monotonic()
    with pytest.raises(ToolError) as caught:
        await asyncio.wait_for(_bounded(inner).invoke(_CALL), _GIVE_UP_S)
    elapsed = time.monotonic() - started
    assert str(caught.value) == "tool 'read' did not answer within 0.02s"
    assert elapsed >= _BOUND_S
    assert inner.cancelled is True


async def test_a_call_that_outruns_the_bound_is_cancelled_rather_than_left_running() -> None:
    inner = _StubRegistry(slow=True)
    with pytest.raises(ToolError):
        await asyncio.wait_for(_bounded(inner).invoke(_CALL), _GIVE_UP_S)
    assert inner.cancelled is True


async def test_a_listing_that_outruns_the_bound_raises_tool_error() -> None:
    inner = _StubRegistry(slow=True)
    started = time.monotonic()
    with pytest.raises(ToolError) as caught:
        await asyncio.wait_for(_bounded(inner).describe_tools(), _GIVE_UP_S)
    elapsed = time.monotonic() - started
    assert str(caught.value) == "listing a tool sidecar's tools took longer than 0.02s"
    assert elapsed >= _BOUND_S
    assert inner.cancelled is True


@pytest.mark.parametrize("verb", ["describe", "invoke"])
async def test_a_timeout_from_beneath_is_not_relabelled_as_our_bound(verb: str) -> None:
    bounded = _bounded(_StubRegistry(raises=TimeoutError("the socket gave up")))
    with pytest.raises(TimeoutError, match="the socket gave up"):
        await (bounded.describe_tools() if verb == "describe" else bounded.invoke(_CALL))


@pytest.mark.parametrize("timeout_s", [0.0, -1.0])
async def test_a_bound_that_is_not_a_duration_is_refused_at_construction(timeout_s: float) -> None:
    with pytest.raises(ValueError, match="positive bound"):
        BoundedToolRegistry(_StubRegistry(), timeout_s=timeout_s)
