"""The bound one remote tool call runs under, and what an overrun is reported as.

The registry under test is a hand-written stand-in rather than `InMemoryToolRegistry`, because
what is being asserted is a registry that answers far too late, which no fake built to answer at
once can be scripted into. It records whether the call it was in the middle of was cancelled,
which is the half of the bound no error message can show: a caller that stopped waiting and left
the work running would satisfy every assertion about the raise.

**The slow stub answers late rather than never, and that is the point of it.** A stub that waits
on an event nothing sets makes the production bound the only way out of the case, so deleting the
bound leaves every overrun case hanging rather than red, and a suite that cannot report is a
suite that cannot fail. Answering after a fixed multiple of the bound turns both mutations into
verdicts instead: delete the bound and the call returns a result where a `ToolError` was
required, widen it past that multiple and the same thing happens. It ties the two expressions no
message can tie, since the sentence renders `self._timeout_s` while the wait is a separate
expression over the same field, and it ties them without a clock, both waits being scheduled off
the one event loop and popped in deadline order however loaded the box is. The never-answering
case still exists where it can only be measured, against the real MCP client in
`packages/tools/tests/test_registry_live.py`. `asyncio.wait_for` sits over each of these cases
as well, for the reason `packages/orchestrator/tests/test_bounds.py` puts one over its own: it
catches the mutation the stub cannot, a production path that stops returning at all.
"""

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

# Short enough that the suite spends no real time on it and long enough that a loaded machine
# still reaches the `await` before it fires. Nothing here races: the arms that must expire are
# awaiting a timer strictly later than the bound's, and the arms that must not are
# already-finished coroutines.
_BOUND_S = 0.02

# How much later than the bound the slow stub answers, which is the whole of the tie between the
# bound a message names and the bound the object spends. Both waits are timers on the one event
# loop, so the earlier deadline is popped first whatever the machine is doing, and a bound
# widened to this multiple stops firing and hands back a result instead: it is a bracket rather
# than a window, and it flakes in neither direction because no wall-clock reading is compared to
# anything. Three rather than two so a mutation has to more than double the bound before it slips
# through, and not thirty, which would be a window again in all but name.
_LATE_FACTOR = 3

# How long a case waits for the bound to do anything at all before reporting instead of hanging,
# the shape `test_bounds.py` uses for the same reason. It is generous because it is not measuring:
# the stub always answers, so nothing but a production path that stopped returning can reach it.
_GIVE_UP_S = 10.0

_SPEC = ToolSpec(name="read", description="", parameters={})
_CALL = ToolCall(id="c-1", name="read", arguments={"path": "/etc/hosts"})


class _StubRegistry:
    """A registry that answers at once, answers far too late, or raises what it was built with.

    ``slow`` is the whole point: both verbs wait ``_LATE_FACTOR`` times the bound, so a bound
    that fires cuts them and a bound that does not lets them through, and ``cancelled`` says
    which of the two happened to the work rather than to the caller.
    """

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
    # The whole rendered sentence, spelled out rather than interpolated from the constant it
    # came from: this text is what the model is handed and what the audit line carries as its
    # error, so a message that stopped naming the tool or the bound is a change of contract.
    inner = _StubRegistry(slow=True)
    started = time.monotonic()
    with pytest.raises(ToolError) as caught:
        await asyncio.wait_for(_bounded(inner).invoke(_CALL), _GIVE_UP_S)
    elapsed = time.monotonic() - started
    assert str(caught.value) == "tool 'read' did not answer within 0.02s"
    # And the bound named is the bound spent, from both sides. The stub answers three bounds
    # late, so a wider bound would have let it through with a result instead of this error;
    # `cancelled` below is that half. The clock is asked only for the floor, which no load can
    # push the wrong way.
    assert elapsed >= _BOUND_S
    assert inner.cancelled is True


async def test_a_call_that_outruns_the_bound_is_cancelled_rather_than_left_running() -> None:
    # The half of the bound the message cannot show: a caller that stopped waiting and left the
    # sidecar call running would raise exactly the same error while leaking a task per dispatch.
    inner = _StubRegistry(slow=True)
    with pytest.raises(ToolError):
        await asyncio.wait_for(_bounded(inner).invoke(_CALL), _GIVE_UP_S)
    assert inner.cancelled is True


async def test_a_listing_that_outruns_the_bound_raises_tool_error() -> None:
    # A listing that outruns the bound strands a turn before any call is made, and it is what the
    # skip policy above this catches, so it is bounded by the same number rather than left open.
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
    # A socket that gave up, or a tool that answers with a TimeoutError, is the sidecar failing
    # rather than this brain giving up on it. Reporting it as the bound would quote a number that
    # never fired and send the reader to the wrong side of the seam.
    bounded = _bounded(_StubRegistry(raises=TimeoutError("the socket gave up")))
    with pytest.raises(TimeoutError, match="the socket gave up"):
        await (bounded.describe_tools() if verb == "describe" else bounded.invoke(_CALL))


@pytest.mark.parametrize("timeout_s", [0.0, -1.0])
async def test_a_bound_that_is_not_a_duration_is_refused_at_construction(timeout_s: float) -> None:
    # Zero refuses every call before it starts and a negative one is not a duration; both are
    # silent holes in a tool set rather than visible failures, so neither reaches a turn.
    with pytest.raises(ValueError, match="positive bound"):
        BoundedToolRegistry(_StubRegistry(), timeout_s=timeout_s)
