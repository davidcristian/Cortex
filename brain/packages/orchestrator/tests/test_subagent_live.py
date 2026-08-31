import os

import httpx
import pytest

from cortex_core import (
    InferenceBackend,
    InMemoryTaskStore,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    SingleResidentModelManager,
    SpawnSubagentsTool,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SystemClock,
    ToolCall,
    VramBudgetPlacer,
)
from cortex_inference import LlamaCppBackend

_ENDPOINT = os.environ.get("CORTEX_SUBAGENTS_ENDPOINT")
_MODEL = os.environ.get("CORTEX_SUBAGENTS_MODEL", "subagent")
_QWEN_ENDPOINT = os.environ.get("CORTEX_SUBAGENTS_QWEN_ENDPOINT")


@pytest.mark.integration
@pytest.mark.skipif(not _ENDPOINT, reason="set CORTEX_SUBAGENTS_ENDPOINT to a live subagent server")
async def test_spawn_subagents_runs_two_subagents_on_a_real_cpu_model() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        store = InMemoryTaskStore()
        manager = SingleResidentModelManager(_MODEL, _ENDPOINT or "")
        backend = LlamaCppBackend(manager, client)
        resources = SubagentResources(
            backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
            scheduler=ResourceBudgetScheduler(8.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=11.0, cortex_reservation_gb=11.0),
            request=PlacementRequest(_MODEL, vram_gb=2.0, cpus=2.0, memory_gb=2.0),
        )
        roster = SubagentRoster(
            entries={_MODEL: SubagentProfile(resources=resources)}, default=_MODEL
        )
        runner = SubagentRunner(store, roster, SystemClock())
        tool = SpawnSubagentsTool(runner, store, SystemClock())
        call = ToolCall(
            id="c1",
            name="spawn_subagents",
            arguments={
                "instructions": [
                    "Reply with exactly one word: PONG.",
                    "Name one primary color. Reply with a single word.",
                ]
            },
        )
        result = await tool.invoke(call)
    assert result.is_error is False
    assert "[subagent 1]" in result.content
    assert "[subagent 2]" in result.content
    bodies = [section.split("] ", 1)[1].strip() for section in result.content.split("\n\n")]
    assert all(bodies), f"a subagent returned empty output: {result.content!r}"


def _cpu_only_profile(backend: InferenceBackend, model: str) -> SubagentProfile:
    return SubagentProfile(
        resources=SubagentResources(
            backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
            scheduler=ResourceBudgetScheduler(8.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=11.0, cortex_reservation_gb=11.0),
            request=PlacementRequest(model, vram_gb=2.0, cpus=2.0, memory_gb=2.0),
        )
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not (_ENDPOINT and _QWEN_ENDPOINT),
    reason="set CORTEX_SUBAGENTS_ENDPOINT and CORTEX_SUBAGENTS_QWEN_ENDPOINT to live servers",
)
async def test_spawn_subagents_routes_each_pick_to_its_roster_model() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        store = InMemoryTaskStore()
        default = LlamaCppBackend(SingleResidentModelManager(_MODEL, _ENDPOINT or ""), client)
        qwen = LlamaCppBackend(SingleResidentModelManager("qwen", _QWEN_ENDPOINT or ""), client)
        roster = SubagentRoster(
            entries={
                _MODEL: _cpu_only_profile(default, _MODEL),
                "qwen": _cpu_only_profile(qwen, "qwen"),
            },
            default=_MODEL,
        )
        runner = SubagentRunner(store, roster, SystemClock())
        tool = SpawnSubagentsTool(runner, store, SystemClock())
        call = ToolCall(
            id="c1",
            name="spawn_subagents",
            arguments={
                "instructions": [
                    "Reply with exactly one word: PONG.",
                    {
                        "instruction": "Name one primary color. Reply with a single word.",
                        "model": "qwen",
                    },
                ]
            },
        )
        result = await tool.invoke(call)
    assert result.is_error is False
    assert "[subagent 1]" in result.content
    assert "[subagent 2]" in result.content
    bodies = [section.split("] ", 1)[1].strip() for section in result.content.split("\n\n")]
    assert all(bodies), f"a subagent returned empty output: {result.content!r}"
