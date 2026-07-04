"""Integration: real CPU llama-server subagent delegation (host-only, ADR-0010).

Exercises the delegation machinery end to end against a live subagent ``llama-server``, covering the
`LlamaCppBackend` (CPU), the `SubagentRunner`, the concurrency budget, and the `spawn_subagents`
tool's concurrent batch + aggregation, all WITHOUT the GPU cortex (the tool is invoked directly, as
the cortex would). Integration-marked: excluded from CI and the coverage gate by the workspace
addopts (`-m "not integration"`); run manually with a subagent server up (subagents-cpu.md):

    CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \
      uv run pytest -m integration --no-cov packages/orchestrator/tests/test_subagent_live.py

Skips unless CORTEX_SUBAGENTS_ENDPOINT is set (the `--no-cov` matters, since the 100% gate would
otherwise fail the run). The subagent server must have reasoning disabled, and
`docker-compose.subagents.yml` bakes in `--chat-template-kwargs '{"enable_thinking": false}'`; a
reasoning model without it crawls (see docs/runbooks/subagents-cpu.md).
"""

import os

import httpx
import pytest

from cortex_core import (
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


@pytest.mark.integration
@pytest.mark.skipif(not _ENDPOINT, reason="set CORTEX_SUBAGENTS_ENDPOINT to a live subagent server")
async def test_spawn_subagents_runs_two_subagents_on_a_real_cpu_model() -> None:
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=None)) as client:
        store = InMemoryTaskStore()
        manager = SingleResidentModelManager(_MODEL, _ENDPOINT or "")
        backend = LlamaCppBackend(manager, client)
        # This host smoke test drives one CPU server; a zero-headroom placer (cap == reservation)
        # keeps both spawns on the CPU path (ADR-0012). The two-server GPU-first path is the user's
        # separate host-half validation.
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
    # The batch ran (no dispatch error), both subagents reported, and the real model produced
    # non-empty text for each. This is a live smoke test, so assert structure not exact wording.
    assert result.is_error is False
    assert "[subagent 1]" in result.content
    assert "[subagent 2]" in result.content
    bodies = [section.split("] ", 1)[1].strip() for section in result.content.split("\n\n")]
    assert all(bodies), f"a subagent returned empty output: {result.content!r}"
