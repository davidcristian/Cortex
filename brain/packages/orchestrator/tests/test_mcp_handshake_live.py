import os
import statistics
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from functools import partial

import pytest

from cortex_core import (
    AggregateToolRegistry,
    CompositeToolRegistry,
    ConfirmFreeToolRegistry,
    ConfirmRequiredToolRegistry,
    FilteredToolRegistry,
    ToolCall,
    ToolRegistry,
)
from cortex_tools import (
    McpSession,
    McpToolRegistry,
    ReconnectingMcpToolRegistry,
    streamable_http_session,
)

_TOOLS = os.environ.get("CORTEX_TOOLS_ENDPOINT")
_READ_TOOL = os.environ.get("CORTEX_TOOLS_READ_TOOL", "read_text_file")
_READ_PATH = os.environ.get("CORTEX_TOOLS_READ_PATH", "/projects/hello.txt")
_LIST_TOOL = os.environ.get("CORTEX_TOOLS_LIST_TOOL", "list_directory")
_SAMPLES = int(os.environ.get("CORTEX_TOOLS_HANDSHAKE_SAMPLES", "20"))

_CONFIRM_NAMES = ("send_email", "escalate_to_brain")

pytestmark = pytest.mark.skipif(
    not _TOOLS, reason="needs CORTEX_TOOLS_ENDPOINT (host-only, a live MCP sidecar)"
)


class CountingOpener:
    """A session opener that counts opens."""

    def __init__(self, url: str) -> None:
        self._url = url
        self.opens = 0

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[McpSession, None]:
        self.opens += 1
        async with streamable_http_session(self._url) as session:
            yield session


def _endpoint(counter: CountingOpener, allow: Sequence[str]) -> ToolRegistry:
    """One configured endpoint as `build_tool_registry` assembles it: the allow-list filter over the
    reconnecting registry.
    """
    return FilteredToolRegistry(ReconnectingMcpToolRegistry(counter), allow=allow)


def _roots(counters: Sequence[CountingOpener], allows: Sequence[Sequence[str]]) -> ToolRegistry:
    """The shared registry root for N endpoints, aggregated when N > 1, behind the approval wrap."""
    registries = [_endpoint(c, a) for c, a in zip(counters, allows, strict=True)]
    root = registries[0] if len(registries) == 1 else AggregateToolRegistry(registries)
    return ConfirmRequiredToolRegistry(root, names=_CONFIRM_NAMES)


async def _opens(counters: Sequence[CountingOpener], work: Callable[[], Awaitable[object]]) -> int:
    """Return how many sessions ``work`` opened."""
    before = sum(c.opens for c in counters)
    await work()
    return sum(c.opens for c in counters) - before


async def _median_ms(work: Callable[[], Awaitable[object]]) -> tuple[float, float, float]:
    """Median, min and max wall time of ``work`` over ``_SAMPLES`` runs, in milliseconds."""
    samples: list[float] = []
    for _ in range(_SAMPLES):
        start = time.perf_counter()
        await work()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples), min(samples), max(samples)


@pytest.mark.integration
async def test_a_turn_pays_one_session_open_per_advertisement_and_per_dispatch() -> None:
    assert _TOOLS is not None
    call = ToolCall(id="hs-1", name=_READ_TOOL, arguments={"path": _READ_PATH})

    solo = [CountingOpener(_TOOLS)]
    root = _roots(solo, [(_READ_TOOL, _LIST_TOOL)])
    cortex = CompositeToolRegistry([], remote=root)
    assert await _opens(solo, cortex.describe_tools) == 1
    assert await _opens(solo, partial(cortex.invoke, call)) == 1
    assert await _opens(solo, partial(ConfirmFreeToolRegistry(root).invoke, call)) == 2

    pair = [CountingOpener(_TOOLS), CountingOpener(_TOOLS)]
    root = _roots(pair, [(_LIST_TOOL,), (_READ_TOOL,)])
    cortex = CompositeToolRegistry([], remote=root)
    assert await _opens(pair, cortex.describe_tools) == 2
    assert await _opens(pair, partial(cortex.invoke, call)) == 3
    assert await _opens(pair, partial(ConfirmFreeToolRegistry(root).invoke, call)) == 5


@pytest.mark.integration
async def test_the_open_is_what_a_fresh_session_costs_over_a_warm_one() -> None:
    assert _TOOLS is not None
    url = _TOOLS
    call = ToolCall(id="hs-2", name=_READ_TOOL, arguments={"path": _READ_PATH})
    fresh = ReconnectingMcpToolRegistry(partial(streamable_http_session, url))
    counter = CountingOpener(url)
    subagent = ConfirmFreeToolRegistry(_roots([counter], [(_READ_TOOL, _LIST_TOOL)]))

    async def bare_open() -> None:
        async with streamable_http_session(url):
            pass

    await bare_open()
    handshake, hs_lo, hs_hi = await _median_ms(bare_open)
    fresh_list, fl_lo, fl_hi = await _median_ms(fresh.describe_tools)
    fresh_call, fc_lo, fc_hi = await _median_ms(partial(fresh.invoke, call))
    two_open_call, tc_lo, tc_hi = await _median_ms(partial(subagent.invoke, call))

    async with streamable_http_session(url) as session:
        warm = McpToolRegistry(session)
        warm_list, wl_lo, wl_hi = await _median_ms(warm.describe_tools)
        warm_call, wc_lo, wc_hi = await _median_ms(partial(warm.invoke, call))

    print(  # noqa: T201 -- the measurement IS this test's output
        f"\nn={_SAMPLES} per arm, median (min..max) ms, endpoint {_TOOLS}"
    )
    for label, med, lo, hi in (
        ("open only", handshake, hs_lo, hs_hi),
        ("describe_tools, fresh session", fresh_list, fl_lo, fl_hi),
        ("describe_tools, warm session", warm_list, wl_lo, wl_hi),
        ("invoke, fresh session", fresh_call, fc_lo, fc_hi),
        ("invoke, warm session", warm_call, wc_lo, wc_hi),
        ("invoke, subagent stack (two opens)", two_open_call, tc_lo, tc_hi),
    ):
        print(  # noqa: T201 -- the measurement IS this test's output
            f"  {label:36s} {med:8.2f}  ({lo:.2f}..{hi:.2f})"
        )

    # Half an open: wide enough to catch a harness that stopped separating the cases, loose
    # enough that a jittery localhost round trip does not fail a good run.
    margin = handshake / 2
    assert fresh_list - warm_list > margin, (fresh_list, warm_list, handshake)
    assert fresh_call - warm_call > margin, (fresh_call, warm_call, handshake)
    assert two_open_call - fresh_call > margin, (two_open_call, fresh_call, handshake)
