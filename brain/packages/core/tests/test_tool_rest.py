import asyncio
from collections.abc import Awaitable, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from cortex_core import (
    BoundedToolRegistry,
    SkipUnavailableToolRegistry,
    ToolCall,
    ToolError,
    ToolResult,
    ToolSpec,
)

_BOUND_S = 0.02
_RETRY_S = 120.0
_GIVE_UP_S = 10.0

_SPEC = ToolSpec(name="read", description="", parameters={})
_READ = ToolCall(id="c-1", name="read", arguments={"path": "/a"})
_LIST = ToolCall(id="c-2", name="list", arguments={"path": "/"})


class _Clock:
    def __init__(self) -> None:
        self.at = datetime(2026, 10, 26, 3, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at


class _Sidecar:
    """A sidecar that answers at once until frozen, then never answers."""

    def __init__(self) -> None:
        self.frozen = False
        self.reached: list[str] = []

    async def describe_tools(self) -> Sequence[ToolSpec]:
        await self._answer("describe")
        return (_SPEC,)

    async def invoke(self, call: ToolCall) -> ToolResult:
        await self._answer(call.name)
        return ToolResult(call_id=call.id, content="done")

    async def _answer(self, what: str) -> None:
        self.reached.append(what)
        if self.frozen:
            await asyncio.Event().wait()


def _bounded(
    sidecar: _Sidecar, clock: _Clock, *, list_timeout_s: float = _BOUND_S
) -> BoundedToolRegistry:
    return BoundedToolRegistry(
        sidecar,
        server="files",
        clock=clock,
        timeout_s=_BOUND_S,
        list_timeout_s=list_timeout_s,
        retry_after_s=_RETRY_S,
    )


async def _error(operation: Awaitable[object]) -> str:
    with pytest.raises(ToolError) as caught:
        await asyncio.wait_for(operation, _GIVE_UP_S)
    return str(caught.value)


async def test_a_call_after_an_overrun_fails_at_once_without_reaching_the_sidecar() -> None:
    sidecar, clock = _Sidecar(), _Clock()
    bounded = _bounded(sidecar, clock)
    sidecar.frozen = True
    await _error(bounded.invoke(_READ))
    clock.at += timedelta(seconds=30)
    text = await _error(bounded.invoke(_LIST))
    assert text == (
        "the files tool server did not answer in time earlier, so 'list' was not sent; "
        "its tools fail at once for another 90s, so answer without them"
    )
    assert sidecar.reached == ["read"]


async def test_a_listing_after_an_overrun_fails_at_once_without_reaching_the_sidecar() -> None:
    sidecar, clock = _Sidecar(), _Clock()
    bounded = _bounded(sidecar, clock)
    sidecar.frozen = True
    await _error(bounded.describe_tools())
    clock.at += timedelta(seconds=100)
    text = await _error(bounded.describe_tools())
    assert text == (
        "the files tool server did not answer in time earlier, "
        "so its tools are not listed for another 20s"
    )
    await _error(bounded.invoke(_READ))
    assert sidecar.reached == ["describe"]


async def test_the_server_is_called_again_once_the_rest_has_passed() -> None:
    sidecar, clock = _Sidecar(), _Clock()
    bounded = _bounded(sidecar, clock)
    sidecar.frozen = True
    await _error(bounded.invoke(_READ))
    sidecar.frozen = False
    clock.at += timedelta(seconds=_RETRY_S)
    assert [spec.name for spec in await bounded.describe_tools()] == ["read"]
    assert (await bounded.invoke(_LIST)).content == "done"
    assert sidecar.reached == ["read", "describe", "list"]


async def test_a_clock_set_back_ends_the_rest_rather_than_lengthening_it() -> None:
    sidecar, clock = _Sidecar(), _Clock()
    bounded = _bounded(sidecar, clock)
    sidecar.frozen = True
    await _error(bounded.invoke(_READ))
    sidecar.frozen = False
    clock.at -= timedelta(hours=1)
    assert (await bounded.invoke(_LIST)).content == "done"


async def test_a_listing_has_its_own_bound_below_the_call_bound() -> None:
    sidecar, clock = _Sidecar(), _Clock()
    bounded = BoundedToolRegistry(
        sidecar, server="files", clock=clock, timeout_s=_GIVE_UP_S, list_timeout_s=_BOUND_S
    )
    sidecar.frozen = True
    text = await _error(bounded.describe_tools())
    assert text.startswith("the files tool server did not list its tools within 0.02s")


async def test_a_listing_bound_above_the_call_bound_is_lowered_to_it() -> None:
    sidecar, clock = _Sidecar(), _Clock()
    bounded = BoundedToolRegistry(
        sidecar, server="files", clock=clock, timeout_s=_BOUND_S, list_timeout_s=_GIVE_UP_S
    )
    sidecar.frozen = True
    text = await _error(bounded.describe_tools())
    assert text.startswith("the files tool server did not list its tools within 0.02s")


async def test_a_skipping_registry_lists_a_resting_server_as_empty_and_reports_it() -> None:
    sidecar, clock = _Sidecar(), _Clock()
    reports: list[str] = []
    skipping = SkipUnavailableToolRegistry(
        _bounded(sidecar, clock), name="files", report=lambda name, _err: reports.append(name)
    )
    sidecar.frozen = True
    assert list(await asyncio.wait_for(skipping.describe_tools(), _GIVE_UP_S)) == []
    assert list(await asyncio.wait_for(skipping.describe_tools(), _BOUND_S * 2)) == []
    assert reports == ["files", "files"]
    assert sidecar.reached == ["describe"]
