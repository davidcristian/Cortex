"""Integration: the VramBudgetPlacer's GPU arm against a real placement (ADR-0012).

The CPU suite beside this one (`test_subagent_live.py`) runs every spawn through a zero-headroom
placer, so the placer's GPU arm never fires there. This one fires it: two live `llama-server`
tiers, the CPU overflow server (`-ngl 0`, docker-compose.subagents.yml) and the model-host
sidecar's GPU-placed subagent tier (`-ngl 99` on :8083, opt-in behind
CORTEX_MODEL_FILE_SUBAGENT_GPU), with the budget read from the deployment's own three env values
through the very settings classes the brain reads them with. What it proves is the route: a GPU
verdict reaches an `-ngl 99` process, and the ledger that granted it refuses the next spawn the
headroom no longer holds.

Both arms are asserted, because a GPU arm that could not also NOT fire proves nothing. Each test
skips unless the budget in the environment selects its arm, so the two run as two commands
against one stack (docs/runbooks/subagents-cpu.md, section 2c, "The GPU-placed tier"):

    # the GPU arm: a soft cap sized to the real card, so the ask fits the headroom once
    CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
      CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:9083 \
      CORTEX_VRAM_SOFT_CAP_GB=20 \
      uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_gpu_live.py

    # the CPU arm: the shipped soft cap, whose headroom the shipped ask exceeds
    CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
      CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:9083 \
      uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_gpu_live.py

Integration-marked: excluded from CI and the coverage gate by the workspace addopts. The GPU
endpoint is the loopback publish of docker-compose.modelhost-loopback.yml (:9083 to the
container's :8083), since the sidecar's tiers are deliberately unpublished otherwise.
"""

import os
from collections import Counter
from collections.abc import AsyncIterator, Sequence

import httpx
import pytest

from cortex_core import (
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
    """Spy over one target's real backend: notes the placement, then forwards to it verbatim.

    The placement verdict is otherwise invisible from outside the runner (the placer's ledger is
    private and nothing logs the target), and inferring it from which server was slower would be
    a guess. This records it exactly, while the request itself still goes to the real
    `llama-server` at that target's endpoint.
    """

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
    ) -> AsyncIterator[InferenceEvent]:
        self._seen.append(self._target)
        return self._inner.stream(model, messages, tools=tools, schema=schema)


def _headroom(runtime: BrainRuntimeConfig) -> float:
    """The subagent GPU allowance the placer fit-tests against: the soft cap minus the cortex."""
    return runtime.vram_soft_cap_gb - runtime.cortex_reservation_gb


def _roster(
    config: SubagentsConfig,
    runtime: BrainRuntimeConfig,
    client: httpx.AsyncClient,
    seen: list[PlacementTarget],
) -> SubagentRoster:
    """The deployment's own single-entry roster, its two live backends behind placement spies.

    Everything numeric comes from the settings classes the composition root reads (ADR-0012's
    three env values: CORTEX_VRAM_SOFT_CAP_GB, CORTEX_VRAM_CORTEX_GB, CORTEX_SUBAGENTS_VRAM_GB),
    so the arm this run takes is the deployment's arithmetic and not the test's.
    """
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
    """One ask fits the headroom, the next does not: GPU then CPU, decided by the ledger.

    Two concurrent spawns of one entry against a headroom that holds exactly one of them. Which
    of the two wins the race is not asserted (both are admitted, and `place` is synchronous, so
    whichever reaches it first takes the GPU); what is asserted is that exactly one did, which is
    the ledger doing its job, and that the winner's request reached the GPU tier's process.
    """
    config = SubagentsConfig()
    headroom = _headroom(BrainRuntimeConfig())
    if not config.vram_gb <= headroom < 2 * config.vram_gb:
        pytest.skip(
            f"this arm needs a headroom holding exactly one spawn: ask={config.vram_gb} GB "
            f"against headroom={headroom} GB (raise CORTEX_VRAM_SOFT_CAP_GB for the real card)"
        )
    seen: list[PlacementTarget] = []
    result = await _spawn_two(seen)
    assert result.is_error is False
    assert Counter(seen) == Counter({PlacementTarget.GPU: 1, PlacementTarget.CPU: 1})
    assert all(_bodies(result)), f"a subagent returned empty output: {result.content!r}"


@pytest.mark.integration
@_needs_both_tiers
async def test_a_spawn_over_the_headroom_never_reaches_the_gpu_tier() -> None:
    """The other arm, which the shipped budget selects: no fit, so nothing is placed on the GPU.

    A GPU arm that cannot be made to stay silent proves nothing about the one that fired, and
    this is also the shipped deployment's own behaviour (ADR-0012's ask sits deliberately above
    the placeholder headroom), so the run doubles as evidence that opting in takes the three
    settings the gpu override's checklist names.
    """
    config = SubagentsConfig()
    headroom = _headroom(BrainRuntimeConfig())
    if config.vram_gb <= headroom:
        pytest.skip(
            f"this arm needs an ask over the headroom: ask={config.vram_gb} GB against "
            f"headroom={headroom} GB (leave CORTEX_VRAM_SOFT_CAP_GB at its shipped value)"
        )
    seen: list[PlacementTarget] = []
    result = await _spawn_two(seen)
    assert result.is_error is False
    assert seen == [PlacementTarget.CPU, PlacementTarget.CPU]
    assert all(_bodies(result)), f"a subagent returned empty output: {result.content!r}"
