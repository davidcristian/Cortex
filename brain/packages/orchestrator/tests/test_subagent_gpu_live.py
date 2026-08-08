"""Integration: the VramBudgetPlacer's GPU arm against a real placement (ADR-0012)."""

import os
from collections import Counter
from collections.abc import AsyncIterator, Sequence

import httpx
import pytest

from cortex_core import (
    GenerationBounds,
    InferenceBackend,
    InferenceEvent,
    InMemoryTaskStore,
    JsonSchema,
    Message,
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
    ToolResult,
    ToolSpec,
    VramBudgetPlacer,
)
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.config import BrainRuntimeConfig
from cortex_orchestrator.config_subagents import SubagentsConfig

_ENDPOINT = os.environ.get("CORTEX_SUBAGENTS_ENDPOINT")
_GPU_ENDPOINT = os.environ.get("CORTEX_SUBAGENTS_GPU_ENDPOINT")

# Two DISTINCT endpoints, because the whole point is which one answered: the subagents override
# defaults the GPU endpoint to the CPU server, and against that default this suite would assert
# nothing (docs/refinements/resource-governance.md).
_needs_both_tiers = pytest.mark.skipif(
    not (_ENDPOINT and _GPU_ENDPOINT and _GPU_ENDPOINT != _ENDPOINT),
    reason="set CORTEX_SUBAGENTS_ENDPOINT and a distinct CORTEX_SUBAGENTS_GPU_ENDPOINT",
)

_INSTRUCTIONS = [
    "Reply with exactly one word: PONG.",
    "Name one primary color. Reply with a single word.",
]


class _PlacedOn:
    """Spy over one target's real backend: notes the placement, then forwards to it verbatim."""

    def __init__(
        self, target: PlacementTarget, inner: InferenceBackend, seen: list[PlacementTarget]
    ) -> None:
        self._target = target
        self._inner = inner
        self._seen = seen

    def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        self._seen.append(self._target)
        return self._inner.stream(model, messages, tools=tools, schema=schema, bounds=bounds)


def _headroom(runtime: BrainRuntimeConfig) -> float:
    """The subagent GPU allowance the placer fit-tests against: the soft cap minus the cortex."""
    return runtime.vram_soft_cap_gb - runtime.cortex_reservation_gb


def _roster(
    config: SubagentsConfig,
    runtime: BrainRuntimeConfig,
    client: httpx.AsyncClient,
    seen: list[PlacementTarget],
) -> SubagentRoster:
    """The deployment's own single-entry roster, its two live backends behind placement spies."""
    resources = SubagentResources(
        backends={
            PlacementTarget.GPU: _PlacedOn(
                PlacementTarget.GPU,
                LlamaCppBackend(
                    SingleResidentModelManager(config.model, config.gpu_endpoint), client
                ),
                seen,
            ),
            PlacementTarget.CPU: _PlacedOn(
                PlacementTarget.CPU,
                LlamaCppBackend(SingleResidentModelManager(config.model, config.endpoint), client),
                seen,
            ),
        },
        scheduler=ResourceBudgetScheduler(config.cpu_budget, config.mem_budget_gb),
        placer=VramBudgetPlacer(
            soft_cap_gb=runtime.vram_soft_cap_gb,
            cortex_reservation_gb=runtime.cortex_reservation_gb,
        ),
        request=PlacementRequest(config.model, config.vram_gb, config.cpus, config.memory_gb),
    )
    return SubagentRoster(
        entries={config.model: SubagentProfile(resources=resources)}, default=config.model
    )


async def _spawn_two(seen: list[PlacementTarget]) -> ToolResult:
    """Run one batch of two spawns through the real tool, runner, placer and backends."""
    config = SubagentsConfig()
    runtime = BrainRuntimeConfig()
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        store = InMemoryTaskStore()
        runner = SubagentRunner(store, _roster(config, runtime, client, seen), SystemClock())
        tool = SpawnSubagentsTool(runner, store, SystemClock())
        return await tool.invoke(
            ToolCall(id="c1", name="spawn_subagents", arguments={"instructions": _INSTRUCTIONS})
        )


def _bodies(result: ToolResult) -> list[str]:
    """Each subagent's answer text out of the aggregated tool result."""
    return [section.split("] ", 1)[1].strip() for section in result.content.split("\n\n")]


@pytest.mark.integration
@_needs_both_tiers
async def test_a_spawn_that_fits_the_headroom_runs_on_the_gpu_tier() -> None:
    """One ask fits the headroom, the next does not: GPU then CPU, decided by the ledger."""
    config = SubagentsConfig()
    headroom = _headroom(BrainRuntimeConfig())
    if not config.vram_gb <= headroom < 2 * config.vram_gb:
        pytest.skip(
            f"this arm needs a headroom holding exactly one spawn: ask={config.vram_gb} GB "
            f"against headroom={headroom} GB (leave CORTEX_VRAM_SOFT_CAP_GB at its shipped value)"
        )
    seen: list[PlacementTarget] = []
    result = await _spawn_two(seen)
    assert result.is_error is False
    assert Counter(seen) == Counter({PlacementTarget.GPU: 1, PlacementTarget.CPU: 1})
    assert all(_bodies(result)), f"a subagent returned empty output: {result.content!r}"


@pytest.mark.integration
@_needs_both_tiers
async def test_a_spawn_over_the_headroom_never_reaches_the_gpu_tier() -> None:
    """The other arm: no fit, so nothing is placed on the GPU and both spawns overflow to CPU."""
    config = SubagentsConfig()
    headroom = _headroom(BrainRuntimeConfig())
    if config.vram_gb <= headroom:
        pytest.skip(
            f"this arm needs an ask over the headroom: ask={config.vram_gb} GB against "
            f"headroom={headroom} GB (lower CORTEX_VRAM_SOFT_CAP_GB under ask plus reservation)"
        )
    seen: list[PlacementTarget] = []
    result = await _spawn_two(seen)
    assert result.is_error is False
    assert seen == [PlacementTarget.CPU, PlacementTarget.CPU]
    assert all(_bodies(result)), f"a subagent returned empty output: {result.content!r}"
