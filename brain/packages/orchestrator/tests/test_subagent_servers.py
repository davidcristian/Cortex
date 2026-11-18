import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from functools import partial
from typing import cast

import pytest
from fakeredis import FakeAsyncRedis, FakeServer
from pydantic import ValidationError

from cortex_core import SystemClock, ToolCall, VramBudgetPlacer
from cortex_orchestrator.config_subagents import SubagentsConfig, endpoint_list
from cortex_orchestrator.subagent_builders import build_subagents
from cortex_session import RedisTaskStore

_REPLY = b'data: {"choices":[{"delta":{"content":"done"}}]}\n\ndata: [DONE]\n\n'
_TOGETHER = 2
_SERVING_S = 0.05
_DONE = -1


def _fake_task_store(url: str) -> RedisTaskStore:
    del url
    return RedisTaskStore(FakeAsyncRedis(server=FakeServer()))


@asynccontextmanager
async def _holding_servers(
    count: int, *, together: int = _TOGETHER, loading: frozenset[int] = frozenset()
) -> AsyncGenerator[tuple[list[str], list[int]]]:
    """Loopback servers that hold each completion until ``together`` have arrived."""
    released = asyncio.Event()
    arrivals: list[int] = []

    async def serve(index: int, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if (await reader.readline()).startswith(b"GET /health"):
            status = b"503 Service Unavailable" if index in loading else b"200 OK"
            writer.write(b"HTTP/1.1 " + status + b"\r\nContent-Length: 0\r\n\r\n")
            await writer.drain()
            writer.close()
            return
        arrivals.append(index)
        if len(arrivals) >= together:
            released.set()
        await released.wait()
        await asyncio.sleep(_SERVING_S)
        arrivals.append(_DONE)
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n" + _REPLY)
        await writer.drain()
        writer.close()

    servers = [
        await asyncio.start_server(partial(serve, index), "127.0.0.1", 0) for index in range(count)
    ]
    ports = [cast("int", server.sockets[0].getsockname()[1]) for server in servers]
    try:
        yield [f"http://127.0.0.1:{port}" for port in ports], arrivals
    finally:
        released.set()
        for server in servers:
            server.close()
            await server.wait_closed()


_TWO_TASKS = ("count to three", "name a colour")


async def _spawn_two(
    config: SubagentsConfig,
    *,
    soft_cap_gb: float = 14.0,
    instructions: tuple[str, ...] = _TWO_TASKS,
) -> None:
    spawn, _scheduler, close = await build_subagents(
        config,
        None,
        "redis://sub:6379/0",
        SystemClock(),
        placer=VramBudgetPlacer(soft_cap_gb=soft_cap_gb, cortex_reservation_gb=11.3),
        task_store_factory=_fake_task_store,
    )
    assert spawn is not None
    try:
        async with asyncio.timeout(5.0):
            await spawn.invoke(
                ToolCall(
                    id="c1",
                    name="spawn_subagents",
                    arguments={"instructions": list(instructions)},
                )
            )
    finally:
        await close()


async def test_two_spawns_of_one_model_run_together_on_two_servers_of_one_slot() -> None:
    async with _holding_servers(2) as (endpoints, arrivals):
        both = ", ".join(endpoints)
        await _spawn_two(
            SubagentsConfig(backend="llamacpp", endpoint=both, gpu_endpoint=both, parallel=1)
        )
    assert sorted(arrivals[:_TOGETHER]) == [0, 1]


async def test_two_spawns_of_one_model_run_together_on_one_server_of_two_slots() -> None:
    async with _holding_servers(1) as (endpoints, arrivals):
        only = endpoints[0]
        await _spawn_two(
            SubagentsConfig(backend="llamacpp", endpoint=only, gpu_endpoint=only, parallel=2)
        )
    assert arrivals[:_TOGETHER] == [0, 0]


async def test_two_targets_naming_one_server_of_one_slot_run_one_spawn_at_a_time() -> None:
    async with _holding_servers(1, together=1) as (endpoints, arrivals):
        only = endpoints[0]
        await _spawn_two(
            SubagentsConfig(backend="llamacpp", endpoint=only, gpu_endpoint=only, parallel=1),
            soft_cap_gb=16.0,
        )
    assert arrivals[:_TOGETHER] == [0, _DONE]


@pytest.mark.parametrize(
    ("soft_cap_gb", "server", "parallel", "gpu_parallel"), [(14.0, 0, 2, 1), (20.0, 1, 1, 2)]
)
async def test_each_target_leases_its_own_servers_at_its_own_slot_count(
    soft_cap_gb: float, server: int, parallel: int, gpu_parallel: int
) -> None:
    async with _holding_servers(2) as (endpoints, arrivals):
        cpu, gpu = endpoints
        config = SubagentsConfig(
            backend="llamacpp",
            endpoint=cpu,
            gpu_endpoint=gpu,
            parallel=parallel,
            gpu_parallel=gpu_parallel,
        )
        await _spawn_two(config, soft_cap_gb=soft_cap_gb)
    assert arrivals[:_TOGETHER] == [server, server]


@pytest.mark.parametrize(
    ("loading", "served_by"), [(frozenset({0}), 1), (frozenset({1}), 0), (frozenset({0, 1}), 2)]
)
async def test_a_lone_spawn_runs_on_a_gpu_server_that_serves_or_else_on_the_cpu(
    loading: frozenset[int], served_by: int
) -> None:
    async with _holding_servers(3, together=1, loading=loading) as (endpoints, arrivals):
        first, second, cpu = endpoints
        config = SubagentsConfig(backend="llamacpp", endpoint=cpu, gpu_endpoint=f"{first},{second}")
        await _spawn_two(config, soft_cap_gb=20.0, instructions=("count to three",))
    assert arrivals == [served_by, _DONE]


@pytest.mark.parametrize(
    ("value", "servers"),
    [
        ("http://a:8082", ("http://a:8082",)),
        ("http://a:8083,http://a:8084", ("http://a:8083", "http://a:8084")),
        (" http://a:8083 , http://a:8084, ", ("http://a:8083", "http://a:8084")),
        (" , ", ()),
    ],
)
def test_an_endpoint_setting_names_one_server_or_several(
    value: str, servers: tuple[str, ...]
) -> None:
    assert endpoint_list(value) == servers


def test_an_endpoint_setting_that_names_no_server_is_rejected() -> None:
    with pytest.raises(ValidationError, match="CORTEX_SUBAGENTS_GPU_ENDPOINT are required"):
        SubagentsConfig(backend="llamacpp", endpoint="http://a:8082", gpu_endpoint=" , ")


@pytest.mark.parametrize(
    ("endpoint", "gpu_endpoint", "repeated"),
    [
        ("http://a:8082", "http://a:8083,http://a:8083", "http://a:8083"),
        ("http://a:8082", "http://a:8083, http://a:8084 ,http://a:8084", "http://a:8084"),
        ("http://a:8082,http://a:8082", "http://a:8083", "http://a:8082"),
    ],
)
def test_an_endpoint_setting_that_names_one_server_twice_is_rejected(
    endpoint: str, gpu_endpoint: str, repeated: str
) -> None:
    with pytest.raises(ValidationError, match=f"'subagent' names {repeated} twice"):
        SubagentsConfig(backend="llamacpp", endpoint=endpoint, gpu_endpoint=gpu_endpoint)


def test_a_roster_entry_that_names_one_server_twice_is_rejected() -> None:
    twice = {"endpoint": "http://b:8085,http://b:8085"}
    with pytest.raises(ValidationError, match="'qwen' names http://b:8085 twice"):
        SubagentsConfig.model_validate(
            {
                "backend": "llamacpp",
                "endpoint": "http://a:8082",
                "gpu_endpoint": "http://a:8083",
                "roster": {"qwen": twice},
            }
        )


def test_two_targets_naming_the_same_server_once_each_are_accepted() -> None:
    config = SubagentsConfig(
        backend="llamacpp", endpoint="http://a:8082", gpu_endpoint="http://a:8082"
    )
    assert endpoint_list(config.gpu_endpoint) == endpoint_list(config.endpoint)
