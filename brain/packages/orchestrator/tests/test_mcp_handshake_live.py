"""Integration: what the MCP per-call session costs a turn, in handshakes and in seconds.

The registry opens a fresh MCP session per call (ADR-0009 boot-tolerance addendum), and the
refinement deferred behind that trade never had a number on it. This file measures one, in the
same unit the recall work uses: milliseconds on the path to the first token.

Two separable things are measured. **How many** session opens a turn pays is deterministic and is
asserted exactly, against the production registry stack, by counting opens through a wrapping
opener. **What one costs** is a property of the sidecar on the other end, so it is measured rather
than asserted absolutely, and what the run asserts is that the seconds track the count. A timing
harness that reported the same number whatever the system did would measure nothing.

The control arm is a **pre-warmed** session: the same `McpToolRegistry` calls with the open
already paid. Fresh minus warm is the open, and the run fails if that difference collapses.

Integration-marked, so CI and the coverage gate never see it. Bring up the filesystem sidecar
(docs/runbooks/tools-mcp.md), then:

    cd brain && CORTEX_TOOLS_ENDPOINT=http://127.0.0.1:9000/mcp \\
      uv run pytest -m integration --no-cov -s \\
      packages/orchestrator/tests/test_mcp_handshake_live.py

Measured 2026-08-08 against the shipped filesystem sidecar: an open costs about 134 ms, a
fresh-session `describe_tools` about 146 ms, a fresh-session `invoke` about 154 ms, and the same
two calls on a warm session about 5 ms and 4 ms. Nearly all of the open is that sidecar spawning
its stdio child; against the FastMCP transport `cortex_email` serves, the same open is 17.8 ms.
"""

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
    FilteredToolRegistry,
    GatedToolRegistry,
    ToolCall,
    ToolRegistry,
    UngatedToolRegistry,
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

# The composition root's gated set (ADR-0022); named here so the stack under measurement is the
# shipped one, GatedToolRegistry included, rather than a simplified stand-in.
_GATED = ("send_email", "escalate_to_brain")

pytestmark = pytest.mark.skipif(
    not _TOOLS, reason="needs CORTEX_TOOLS_ENDPOINT (host-only, a live MCP sidecar)"
)


class CountingOpener:
    """A session opener that counts opens. One open is one handshake, which is the unit."""

    def __init__(self, url: str) -> None:
        self._url = url
        self.opens = 0

    @asynccontextmanager
    async def __call__(self) -> AsyncGenerator[McpSession, None]:
        self.opens += 1
        async with streamable_http_session(self._url) as session:
            yield session


def _endpoint(counter: CountingOpener, allow: Sequence[str]) -> ToolRegistry:
    """One configured endpoint as `build_tool_registry` assembles it: the allow-list filter over
    the reconnecting registry."""
    return FilteredToolRegistry(ReconnectingMcpToolRegistry(counter), allow=allow)


def _roots(counters: Sequence[CountingOpener], allows: Sequence[Sequence[str]]) -> ToolRegistry:
    """The shared registry root for N endpoints, aggregated (when N > 1) and gated."""
    registries = [_endpoint(c, a) for c, a in zip(counters, allows, strict=True)]
    root = registries[0] if len(registries) == 1 else AggregateToolRegistry(registries)
    return GatedToolRegistry(root, gated=_GATED)


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
    """The handshake count per turn shape, asserted exactly against the production stack.

    With N endpoints and the called tool owned by the k-th (config order), advertising the tool
    set costs N opens and one cortex dispatch costs k + 1: `AggregateToolRegistry.invoke` routes
    by re-listing each registry until one claims the name, deliberately (a live walk, so a tool a
    sidecar dropped or re-flagged fails closed rather than routing stale). A **subagent** pays
    N more on top, because `UngatedToolRegistry.invoke` re-lists to recompute the gated set
    before delegating. Both walks are deliberate. What was recorded nowhere is that together they
    make a delegated dispatch cost twice what a cortex dispatch costs.
    """
    assert _TOOLS is not None
    call = ToolCall(id="hs-1", name=_READ_TOOL, arguments={"path": _READ_PATH})

    # N = 1: the single-endpoint root is the endpoint itself, no aggregate in the way.
    solo = [CountingOpener(_TOOLS)]
    root = _roots(solo, [(_READ_TOOL, _LIST_TOOL)])
    cortex = CompositeToolRegistry([], remote=root)
    assert await _opens(solo, cortex.describe_tools) == 1
    assert await _opens(solo, partial(cortex.invoke, call)) == 1
    assert await _opens(solo, partial(UngatedToolRegistry(root).invoke, call)) == 2

    # N = 2, with the called tool owned by the SECOND endpoint: the allowlists split the one
    # live sidecar into two that advertise different names, which is what makes k observable.
    pair = [CountingOpener(_TOOLS), CountingOpener(_TOOLS)]
    root = _roots(pair, [(_LIST_TOOL,), (_READ_TOOL,)])
    cortex = CompositeToolRegistry([], remote=root)
    assert await _opens(pair, cortex.describe_tools) == 2
    assert await _opens(pair, partial(cortex.invoke, call)) == 3
    assert await _opens(pair, partial(UngatedToolRegistry(root).invoke, call)) == 5


@pytest.mark.integration
async def test_the_open_is_what_a_fresh_session_costs_over_a_warm_one() -> None:
    """Measure what one session open costs, and check that the harness is reading the open rather
    than the sidecar's own work.

    Three arms over the same live server: a bare open with no tool traffic, the registry's own
    per-call opens, and the control, the identical calls on a session already open. The assertions
    are all relative, since the absolute numbers belong to whatever sidecar answers: a fresh call
    has to exceed its warm twin by most of a bare open, and a two-open dispatch (the subagent
    stack) has to exceed a one-open dispatch by the same margin. If either difference collapses,
    the harness is measuring something other than the open, and the run fails.
    """
    assert _TOOLS is not None
    url = _TOOLS  # A local, so the None narrowing reaches into the closure below.
    call = ToolCall(id="hs-2", name=_READ_TOOL, arguments={"path": _READ_PATH})
    fresh = ReconnectingMcpToolRegistry(partial(streamable_http_session, url))
    counter = CountingOpener(url)
    subagent = UngatedToolRegistry(_roots([counter], [(_READ_TOOL, _LIST_TOOL)]))

    async def bare_open() -> None:
        async with streamable_http_session(url):
            pass

    await bare_open()  # Pay whatever the first connection costs once (DNS, the sidecar's boot).
    handshake, hs_lo, hs_hi = await _median_ms(bare_open)
    fresh_list, fl_lo, fl_hi = await _median_ms(fresh.describe_tools)
    fresh_call, fc_lo, fc_hi = await _median_ms(partial(fresh.invoke, call))
    two_open_call, tc_lo, tc_hi = await _median_ms(partial(subagent.invoke, call))

    # The control arm. Held open for the whole block, so these calls pay no open at all; the
    # `async with` is also what releases it, whatever the assertions below do.
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

    # Half an open is the margin throughout: enough to catch a harness that stopped separating
    # the arms, loose enough that a jittery localhost round trip does not fail a green run.
    margin = handshake / 2
    assert fresh_list - warm_list > margin, (fresh_list, warm_list, handshake)
    assert fresh_call - warm_call > margin, (fresh_call, warm_call, handshake)
    assert two_open_call - fresh_call > margin, (two_open_call, fresh_call, handshake)
