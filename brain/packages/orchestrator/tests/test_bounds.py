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

_WEDGED_BOUND_S = 0.02
# The wedged sidecar answers late rather than never, so deleting a bound fails a test here
# instead of hanging the suite.
_WEDGED_ANSWER_S = _WEDGED_BOUND_S * 3


def _tools(
    *, backend: ToolsBackendName = "mcp", call_timeout_s: float = DEFAULT_TOOL_CALL_TIMEOUT_S
) -> ToolsConfig:
    """A tools config with one sidecar enabled, since a disabled one bounds no call."""
    return ToolsConfig(backend=backend, endpoint=_ENDPOINT, call_timeout_s=call_timeout_s)


def _two_sidecars(*, call_timeout_s: float = DEFAULT_TOOL_CALL_TIMEOUT_S) -> ToolsConfig:
    """The same, with two endpoints, which is the shipped filesystem and email pair."""
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
    with caplog.at_level(logging.ERROR), pytest.raises(ToolCallDeadlineError) as excinfo:
        check_tool_call_deadline(_subagents(run_timeout_s=900.0), _tools(call_timeout_s=3000.0))
    assert "CORTEX_TOOLS_CALL_TIMEOUT_S is 3000.0 s" in str(excinfo.value)
    assert "spend it 3 times over across 1 configured sidecar(s), so 9000.0 s" in str(excinfo.value)
    assert "CORTEX_SUBAGENTS_RUN_TIMEOUT_S is 900.0 s" in str(excinfo.value)
    rendered = PlainFormatter().format(_only(caplog))
    assert (
        "one wedged tool dispatch can outlast the delegated run that has to contain it" in rendered
    )
    assert (
        "call_bounds_per_dispatch=3 call_timeout_s=3000.0 dispatch_timeout_s=9000.0 "
        "run_timeout_s=900.0 sidecars=1" in rendered
    )


def test_a_dispatch_allowed_the_whole_of_the_run_is_refused_too() -> None:
    with pytest.raises(ToolCallDeadlineError):
        check_tool_call_deadline(_subagents(run_timeout_s=900.0), _tools(call_timeout_s=300.0))


def test_a_call_bound_the_bare_pair_admits_is_still_refused() -> None:
    with pytest.raises(ToolCallDeadlineError, match=r"so 2100\.0 s"):
        check_tool_call_deadline(_subagents(run_timeout_s=900.0), _tools(call_timeout_s=700.0))


def test_the_shipped_pair_is_wired_and_says_so(caplog: pytest.LogCaptureFixture) -> None:
    subagents = _subagents()
    with caplog.at_level(logging.INFO):
        assert check_tool_call_deadline(subagents, _tools()) is subagents
    assert "outlasts one wedged tool dispatch" in caplog.text
    assert (
        "call_bounds_per_dispatch=3 call_timeout_s=60.0 dispatch_timeout_s=180.0 "
        "run_timeout_s=2400.0 sidecars=1" in PlainFormatter().format(_only(caplog))
    )


def test_a_second_sidecar_costs_the_same_bound_more(caplog: pytest.LogCaptureFixture) -> None:
    subagents = _subagents()
    with caplog.at_level(logging.INFO):
        assert check_tool_call_deadline(subagents, _two_sidecars()) is subagents
    assert (
        "call_bounds_per_dispatch=7 call_timeout_s=60.0 dispatch_timeout_s=420.0 "
        "run_timeout_s=2400.0 sidecars=2" in PlainFormatter().format(_only(caplog))
    )


@pytest.mark.parametrize(
    ("config", "bounds"),
    [(_tools(), 3), (_two_sidecars(), 7)],
    ids=["one sidecar", "two sidecars"],
)
def test_the_multiple_counts_every_walk_a_delegated_dispatch_makes(
    config: ToolsConfig, bounds: int
) -> None:
    assert delegated_call_bounds(config) == bounds


def test_a_deployment_with_no_tool_sidecars_has_no_pairing_to_check(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    subagents = _subagents(backend="none", run_timeout_s=900.0)
    with caplog.at_level(logging.INFO):
        assert check_tool_call_deadline(subagents, _tools(call_timeout_s=3000.0)) is subagents
    assert caplog.records == []


async def test_run_from_env_refuses_a_call_bounded_above_the_run_that_contains_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    """An MCP session that opens and then answers each call three bounds late: a wedged sidecar."""

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
    """Every call one delegated run makes before its first dispatch answers, through the root."""
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
    config = ToolsConfig(
        backend="mcp",
        endpoints=endpoints,
        on_unavailable="skip",
        call_timeout_s=_WEDGED_BOUND_S,
    )
    observed = await _spends_of(config, monkeypatch)
    assert len(observed) == spends
    assert len(observed) <= delegated_call_bounds(config)
