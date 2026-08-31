"""The boot check over two settings classes: a delegated dispatch inside the run that contains it.

The defect under test is not a bug in either bound. Both work, and nothing relates them. A
deployment that raises ``CORTEX_TOOLS_CALL_TIMEOUT_S`` past ``CORTEX_SUBAGENTS_RUN_TIMEOUT_S``
gets a wedged sidecar reported as a subagent that would not stop talking, because the run's own
deadline is what fires, and it loses the re-run a transport failure earns, a truncation never
being re-placed. That was measured on the shipped ``PlacedAttempt`` before this check existed:
with the pair ordered, a hanging sidecar costs one call and the subtask still answers; inverted,
the run ends ``TRUNCATED`` with no text at all.

**What has to fit is the dispatch and not the bound.** One delegated dispatch spends the bound
once per registry walk, so ordering the two numbers as typed leaves the same failure reachable
from a pair that reads as ordered: 700 s under 900 s costs a wedged sidecar 2100 s of a run
allowed 900. ``delegated_call_bounds`` counts the walks, the check compares the product, and the
last two cases here tie that arithmetic to the composition it describes rather than arguing from
it.

Proof these cases can fail, each mutation applied to production code alone and the whole
``brain/packages`` suite re-run (2836 cases, 80 integration cases deselected), so the counts are
measured rather than aimed at:

- comparing the two fields the other way round (``run_timeout_s < _dispatch_cost(tools)``) makes 5
  tests fail, which is what separates the ordering from the numbers it is over. The equal pair is
  deliberately not among them: reversed, that comparison still refuses equality, so the case below
  that pins strictness cannot tell a swapped comparison from the shipped one, and the two
  mutations need different cases for that reason;
- accepting equality (``<=`` rather than ``<``) makes 1 test fail,
  ``test_a_dispatch_allowed_the_whole_of_the_run_is_refused_too``, the one case that pins the
  strictness rather than the direction;
- comparing the bare call bound rather than the whole dispatch, which is the check as it was first
  written, makes 5 tests fail. That is the row this file exists for now: the version it restores
  shipped with a passing suite, and what it could not see is
  ``test_a_call_bound_the_bare_pair_admits_is_still_refused``;
- dropping the aggregate's routing walk from the multiple makes 3 tests fail and dropping the
  endpoint count makes 3 tests fail, each of them the two-sidecar cases plus the composition case
  that measures what the real stack spends; dropping the call itself makes 8 tests fail, every
  case that reads a multiple or a product;
- logging the misordering and returning instead of raising makes 4 tests fail, the three refusal
  cases here and the ``run_from_env`` case that drives the root;
- dropping the ``mcp`` half of the guard makes 1 test fail,
  ``test_a_deployment_with_no_tool_sidecars_has_no_pairing_to_check``, and dropping the
  ``llamacpp`` half makes 2 tests fail, this file's own tolerance case and a wiring case that runs
  a tool-enabled root without delegation, so each tolerance is pinned as deliberately as the
  refusal;
- naming the run bound where the message names the call bound (rendering one field twice) makes 2
  tests fail, the two cases that read the rendered values, which is the trap a test interpolating
  the config's own values into its expected string would not have caught: an object that names one
  number and spends another satisfies every assertion written that way;
- dropping the call from the composition root makes exactly 1 test fail, the ``run_from_env``
  case, which is the only reason that case exists beside the ones that drive the check directly.
  It is bounded by ``asyncio.wait_for`` because a root that never refuses goes on to ``serve``:
  without the bound the mutation hangs the suite instead of failing it, which shows nothing.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from mcp.types import CallToolResult, ListToolsResult, Tool
from redis.asyncio import Redis

import cortex_orchestrator.builders as builders_module
from cortex_core import (
    DEFAULT_SUBAGENT_RUN_TIMEOUT_S,
    DEFAULT_TOOL_CALL_TIMEOUT_S,
    PlainFormatter,
    ToolCall,
    ToolError,
    ToolNotFoundError,
    UngatedToolRegistry,
)
from cortex_orchestrator import (
    SubagentsConfig,
    ToolCallDeadlineError,
    ToolsConfig,
    build_tool_registry,
    check_tool_call_deadline,
    delegated_call_bounds,
    run_from_env,
)
from cortex_orchestrator.config_subagents import SubagentsBackendName
from cortex_orchestrator.config_tools import ToolsBackendName
from cortex_session import RedisSessionStore

_ENDPOINT = "http://tools:9000/mcp"
_EMAIL = "http://mcp-email:9100/mcp"
_CPU = "http://subagent-cpu:8082"
_GPU = "http://subagent-gpu:8083"

# The bound the composition case below wires, short enough that spending it several times costs
# the suite nothing, and the multiple of it a wedged sidecar answers after. Answering late rather
# than never is what makes deleting the bound a failing test rather than a hung suite, the shape
# `packages/core/tests/test_tool_deadline.py` uses and argues for.
_WEDGED_BOUND_S = 0.02
_WEDGED_ANSWER_S = _WEDGED_BOUND_S * 3


def _tools(
    *, backend: ToolsBackendName = "mcp", call_timeout_s: float = DEFAULT_TOOL_CALL_TIMEOUT_S
) -> ToolsConfig:
    """A tools config with one sidecar enabled, since a disabled one bounds no call.

    The unset bound is the shipped default **imported**, never retyped: a copy of the number here
    would go on satisfying the shipped-pair case below after a retune moved the real one, so the
    case that claims to compare the two defaults would quietly be comparing neither.
    """
    return ToolsConfig(backend=backend, endpoint=_ENDPOINT, call_timeout_s=call_timeout_s)


def _two_sidecars(*, call_timeout_s: float = DEFAULT_TOOL_CALL_TIMEOUT_S) -> ToolsConfig:
    """The same, with two endpoints, which is the shipped filesystem and email pair.

    A second sidecar is not a second copy of the same deployment: it puts an aggregate over the
    two, and the aggregate re-lists to route, so every walk costs more and there is one more walk.
    """
    return ToolsConfig(
        backend="mcp",
        endpoints={"files": _ENDPOINT, "email": _EMAIL},
        call_timeout_s=call_timeout_s,
    )


def _subagents(
    *,
    backend: SubagentsBackendName = "llamacpp",
    run_timeout_s: float = DEFAULT_SUBAGENT_RUN_TIMEOUT_S,
) -> SubagentsConfig:
    """A delegation config with both endpoints, since a disabled one runs nothing to contain it."""
    return SubagentsConfig(
        backend=backend, endpoint=_CPU, gpu_endpoint=_GPU, run_timeout_s=run_timeout_s
    )


def _only(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    """The single record the check emitted, so the shipped formatter can be run over it."""
    (record,) = caplog.records
    return record


def test_a_call_bounded_above_the_run_it_sits_inside_refuses_to_boot(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The misconfiguration is static while its failure is not, so the check rejects it at boot,
    where an operator typed it.

    The numbers are deliberately far apart and unequal, so a comparison reading one field twice,
    or a message rendering one field twice, cannot satisfy this by coincidence.
    """
    with caplog.at_level(logging.ERROR), pytest.raises(ToolCallDeadlineError) as excinfo:
        check_tool_call_deadline(_subagents(run_timeout_s=900.0), _tools(call_timeout_s=3000.0))
    # Each knob beside its own value, which is what an operator needs to know which one to move,
    # and the multiple between them, which is what says why 3000 and 900 are further apart than
    # they look. Spelled out rather than interpolated from the config the check was handed.
    assert "CORTEX_TOOLS_CALL_TIMEOUT_S is 3000.0 s" in str(excinfo.value)
    assert "spend it 3 times over across 1 configured sidecar(s), so 9000.0 s" in str(excinfo.value)
    assert "CORTEX_SUBAGENTS_RUN_TIMEOUT_S is 900.0 s" in str(excinfo.value)
    assert (
        "call_bounds_per_dispatch=3 call_timeout_s=3000.0 dispatch_timeout_s=9000.0 "
        "run_timeout_s=900.0" in PlainFormatter().format(_only(caplog))
    )


def test_a_dispatch_allowed_the_whole_of_the_run_is_refused_too() -> None:
    """An equal pair is a race between two bounds, and when the run's deadline fires first a
    wedged sidecar is reported as a subagent that would not stop.

    300 s is the equal pair here rather than 900: what has to fit inside the run is the whole
    dispatch, and at one sidecar a dispatch is three of these bounds.
    """
    with pytest.raises(ToolCallDeadlineError):
        check_tool_call_deadline(_subagents(run_timeout_s=900.0), _tools(call_timeout_s=300.0))


def test_a_call_bound_the_bare_pair_admits_is_still_refused() -> None:
    """A pair that passes a comparison of the two numbers alone still wedges a run, and is refused.

    700 s sits under 900 s, so a check that compared the bounds themselves shipped this. One
    delegated dispatch spends the bound twice before the call and once in it, so a wedged sidecar
    costs 2100 s of a run allowed 900, the run deadline fires first, and the truncation it reports
    is the exact outcome this check exists to prevent. It is the regression this case pins.
    """
    with pytest.raises(ToolCallDeadlineError, match=r"so 2100\.0 s"):
        check_tool_call_deadline(_subagents(run_timeout_s=900.0), _tools(call_timeout_s=700.0))


def test_the_shipped_pair_is_wired_and_says_so(caplog: pytest.LogCaptureFixture) -> None:
    """The two shipped defaults are compared as the running pair, since a check that refused them
    would refuse every stack.

    The numbers are attached to the record rather than written into the message, so they are read
    off the line the shipped formatter renders. ``caplog.text`` carries the message alone, and
    asserting them against that would pass only while they were printed twice.
    """
    subagents = _subagents()
    with caplog.at_level(logging.INFO):
        assert check_tool_call_deadline(subagents, _tools()) is subagents
    assert "outlasts one wedged tool dispatch" in caplog.text
    assert (
        "call_bounds_per_dispatch=3 call_timeout_s=60.0 dispatch_timeout_s=180.0 "
        "run_timeout_s=2400.0" in PlainFormatter().format(_only(caplog))
    )


def test_a_second_sidecar_costs_the_same_bound_more(caplog: pytest.LogCaptureFixture) -> None:
    """The headroom is a property of the whole deployment rather than of the two numbers alone.

    The same 60 s under the same 2400 s buys less with two sidecars configured, because the walks
    that spend it are wider and there is an extra one, so the multiple is on the record beside the
    bounds rather than left for a reader to work out.
    """
    subagents = _subagents()
    with caplog.at_level(logging.INFO):
        assert check_tool_call_deadline(subagents, _two_sidecars()) is subagents
    assert (
        "call_bounds_per_dispatch=7 call_timeout_s=60.0 dispatch_timeout_s=420.0 "
        "run_timeout_s=2400.0" in PlainFormatter().format(_only(caplog))
    )


@pytest.mark.parametrize(
    ("config", "bounds"),
    [(_tools(), 3), (_two_sidecars(), 7)],
    ids=["one sidecar", "two sidecars"],
)
def test_the_multiple_counts_every_walk_a_delegated_dispatch_makes(
    config: ToolsConfig, bounds: int
) -> None:
    """The expected counts are written as literals rather than derived from the expression under
    test.

    One sidecar: the run's advertisement, the gated strip on the dispatch, and the call. Two: each
    of those walks lists both endpoints, and a third walk appears, the aggregate's own routing
    pass, which a single endpoint does not have because it is composed as itself.
    """
    assert delegated_call_bounds(config) == bounds


def test_a_deployment_with_no_tool_sidecars_has_no_pairing_to_check(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Without ``mcp`` no ``BoundedToolRegistry`` is built, so the knob bounds nothing at all.

    The pair is inverted on purpose, so what makes the check accept this deployment is the backend
    setting and not the numbers.
    """
    subagents = _subagents(run_timeout_s=900.0)
    with caplog.at_level(logging.INFO):
        assert (
            check_tool_call_deadline(subagents, _tools(backend="none", call_timeout_s=3000.0))
            is subagents
        )
    assert caplog.records == []


def test_a_deployment_that_never_delegates_has_no_pairing_to_check(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cortex turn announces no deadline, so its own tool calls have nothing to be under."""
    subagents = _subagents(backend="none", run_timeout_s=900.0)
    with caplog.at_level(logging.INFO):
        assert check_tool_call_deadline(subagents, _tools(call_timeout_s=3000.0)) is subagents
    assert caplog.records == []


async def test_run_from_env_refuses_a_call_bounded_above_the_run_that_contains_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The composition root calls the check, which is what puts a correct check on the boot path.

    It is driven through ``run_from_env`` for that reason, and bounded because the failure it pins
    is a root that never asks: without the refusal the root goes on to ``serve``, which returns
    for nothing this test can arrange. Only the call bound is raised, so the run deadline keeps
    the default that clears its own stall ceiling and this stack is refused for one relation only.
    """
    monkeypatch.setenv("CORTEX_TOOLS_BACKEND", "mcp")
    monkeypatch.setenv("CORTEX_TOOLS_ENDPOINT", _ENDPOINT)
    monkeypatch.setenv("CORTEX_TOOLS_CALL_TIMEOUT_S", "3000")
    monkeypatch.setenv("CORTEX_SUBAGENTS_BACKEND", "llamacpp")
    monkeypatch.setenv("CORTEX_SUBAGENTS_ENDPOINT", _CPU)
    monkeypatch.setenv("CORTEX_SUBAGENTS_GPU_ENDPOINT", _GPU)
    server = FakeServer()

    def fake_from_url(url: str) -> Redis:
        del url
        return FakeAsyncRedis(server=server)

    monkeypatch.setattr(Redis, "from_url", fake_from_url)
    with pytest.raises(ToolCallDeadlineError, match=r"CORTEX_TOOLS_CALL_TIMEOUT_S is 3000\.0 s"):
        await asyncio.wait_for(
            run_from_env(
                store_factory=lambda _url: RedisSessionStore(FakeAsyncRedis(server=server))
            ),
            timeout=10,
        )


class _WedgedSession:
    """An MCP session that opens and then answers each verb three bounds late: a wedged sidecar.

    It answers rather than never returning so that a bound deleted from the stack fails a test
    instead of hanging the suite: every listing then succeeds, the tool is advertised, and the
    dispatch below hands back a result where a refusal was required. The argument is written out
    where the shape started, in ``packages/core/tests/test_tool_deadline.py``.
    """

    def __init__(self, spends: list[str], url: str) -> None:
        self._spends = spends
        self._url = url

    async def list_tools(self) -> ListToolsResult:
        self._spends.append(f"list {self._url}")
        await asyncio.sleep(_WEDGED_ANSWER_S)
        return ListToolsResult(tools=[Tool(name="read", description="", inputSchema={})])

    async def call_tool(
        self, name: str, arguments: dict[str, object] | None = None
    ) -> CallToolResult:
        del name, arguments
        self._spends.append(f"call {self._url}")
        await asyncio.sleep(_WEDGED_ANSWER_S)
        return CallToolResult(content=[])


async def _spends_of(config: ToolsConfig, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every bound one delegated run spends before its first dispatch answers, through the root.

    The real ``build_tool_registry`` composition, wrapped in the ``UngatedToolRegistry`` the
    subagent wiring puts over it, driven the way a delegated run drives it: advertise once, then
    dispatch. Each entry in the returned list is one verb reaching a wedged sidecar, which is one
    whole bound, so counting entries counts bound spends without reading a clock.
    """
    spends: list[str] = []

    @asynccontextmanager
    async def wedged(url: str) -> AsyncGenerator[_WedgedSession, None]:
        yield _WedgedSession(spends, url)

    monkeypatch.setattr(builders_module, "streamable_http_session", wedged)
    registry, close = build_tool_registry(config)
    assert registry is not None
    delegated = UngatedToolRegistry(registry)
    assert list(await asyncio.wait_for(delegated.describe_tools(), 10)) == []
    with pytest.raises((ToolError, ToolNotFoundError)):
        await asyncio.wait_for(delegated.invoke(ToolCall(id="c-1", name="read", arguments={})), 10)
    await close()
    return spends


@pytest.mark.parametrize(
    ("endpoints", "spends"),
    [({"files": _ENDPOINT}, 3), ({"files": _ENDPOINT, "email": _EMAIL}, 6)],
    ids=["one sidecar", "two sidecars"],
)
async def test_no_wedged_delegated_dispatch_outspends_the_multiple(
    endpoints: dict[str, str], spends: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The arithmetic above, tied to the composition it describes rather than argued from it.

    ``skip`` is the mode measured because it is the expensive one: ``fail`` aborts a walk at the
    first overrun, so it can only spend less, and the multiple is an upper bound over both.

    At one sidecar the observed count **is** the multiple, the call being reached. At two it is one
    short, and deliberately so: a skipped sidecar advertises nothing, so this fixture cannot route
    a call to one, while a sidecar that recovers between the routing walk and the invoke can, which
    is the live-walk race ``AggregateToolRegistry`` is built around. Counting that call is what
    makes the multiple a ceiling rather than a sample.
    """
    config = ToolsConfig(
        backend="mcp",
        endpoints=endpoints,
        on_unavailable="skip",
        call_timeout_s=_WEDGED_BOUND_S,
    )
    observed = await _spends_of(config, monkeypatch)
    assert len(observed) == spends
    assert len(observed) <= delegated_call_bounds(config)
