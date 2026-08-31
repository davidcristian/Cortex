"""Integration: whether a live cortex spreads independent subtasks across roster models (ADR-0018).

The spawn spec tells the cortex that subtasks on **distinct** roster models overlap while subtasks
sharing one model run one after another, wording that understates this deployment's two-way overlap
on purpose (ADR-0018 declined the rewrite), and points it at spreading a batch as the wall-clock
lever. Whether a live cortex takes that advice **unprompted** is what this suite observes, over the
real cortex `llama-server`, the real `spawn_subagents` tool, and a roster built from the
deployment's own `CORTEX_SUBAGENTS_*` values.

Three arms, because the question has two halves and needs a control:

- **armed** asserts the advertised spec really carries the `model` knob and the trade-off line, so
  a run that never delegates is not read as a spec that never offered the choice. No model call.
- **prose-only** puts an ask carrying independent subtasks and *nothing about delegation*.
- **invited** asks for the same work with delegation requested in ordinary user prose (no tool
  name, no model name, no parallelism language), so the only spontaneous decision left is the pick.

The two model arms assert what must hold whatever the model decides (the turn answered, every pick
names a roster entry, the batch fits `MAX_SPAWN_BATCH`) and **print** the choice, because the
choice is an observation and not a contract: sampling is stochastic, so one run is one data point.
Run each several times and read the spread (`-s` shows the report).

Integration-marked, so CI and the coverage gate never see it. Bring up base + gpu + subagents +
subagents-roster (docs/runbooks/subagents-cpu.md section 3c), then:

    cd brain && CORTEX_INFERENCE_ENDPOINT=http://127.0.0.1:8080 \\
      CORTEX_SUBAGENTS_BACKEND=llamacpp \\
      CORTEX_SUBAGENTS_ENDPOINT=http://127.0.0.1:8082 \\
      CORTEX_SUBAGENTS_GPU_ENDPOINT=http://127.0.0.1:8082 \\
      CORTEX_SUBAGENTS_ROSTER__qwen='{"endpoint": "http://127.0.0.1:8083"}' \\
      uv run pytest -m integration --no-cov -s packages/orchestrator/tests/test_spawn_nudge_live.py

Observed 2026-08-04 on gemma-4-12B at 16K beside the two CPU sidecars: over 20 prose-only turns of
four asks the cortex delegated in **none** of them, and over 16 invited turns it delegated in every
one and put the whole batch on a **single** roster entry in every one. The record is in the
ADR-0018 addendum of that date; the bring-up, and what a batch on the CPU tiers costs in wall
clock, are in the runbook section above.
"""

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

import httpx
import pytest

from cortex_core import (
    MAX_SPAWN_BATCH,
    InMemoryTaskStore,
    Message,
    PlacementRequest,
    PlacementTarget,
    ResourceBudgetScheduler,
    Role,
    SingleResidentModelManager,
    SpawnSubagentsTool,
    SubagentPlacer,
    SubagentProfile,
    SubagentResources,
    SubagentRoster,
    SubagentRunner,
    SubagentScheduler,
    SystemClock,
    TaintLedger,
    ToolSpec,
    TurnCapabilities,
    VramBudgetPlacer,
    new_nonce,
)
from cortex_core.loop_events import ReasoningDelta
from cortex_core.tool_loop import ToolLoopContext, stream_tool_loop
from cortex_core.turn_context import assemble_inference_messages
from cortex_inference import LlamaCppBackend
from cortex_orchestrator.builders import (
    LLAMACPP_CONNECT_TIMEOUT_S,
    build_builtin_tools,
    build_cortex_tools,
)
from cortex_orchestrator.config import BrainRuntimeConfig
from cortex_orchestrator.config_subagents import SubagentRosterEntry, SubagentsConfig

_INFERENCE = os.environ.get("CORTEX_INFERENCE_ENDPOINT")
# Read from the raw environment rather than from `SubagentsConfig`, so collecting this file
# cannot fail on a half-configured deployment the run would skip anyway.
_ALTERNATES = [name for name in os.environ if name.startswith("CORTEX_SUBAGENTS_ROSTER__")]

# A one-entry roster advertises no `model` knob at all (`build_spawn_spec`), so there would be
# nothing to spread across and the observation would be empty.
_needs_a_cortex_and_a_multi_entry_roster = pytest.mark.skipif(
    not (_INFERENCE and _ALTERNATES),
    reason="set CORTEX_INFERENCE_ENDPOINT and at least one CORTEX_SUBAGENTS_ROSTER__<name>",
)

# Independent subtasks, no delegation language of any kind: what a user would simply type.
_ASK_PROSE = (
    "I am putting together notes for a talk tomorrow and I need three short write-ups. One on "
    "what a hash table is, one on what a bloom filter is, and one on what a skip list is. Two or "
    "three sentences each, plain enough for someone new to the subject. None of them depends on "
    "the others."
)
# The same work with delegation invited in the user's own words. It names no tool, no model and
# no parallelism, so the model pick is the only thing left for the cortex to decide.
_ASK_INVITED = (
    "I need three separate things written and I would rather you farm them out than write them "
    "all yourself. One: two or three sentences on what a hash table is. Two: two or three "
    "sentences on what a bloom filter is. Three: two or three sentences on what a skip list is. "
    "Nothing in any of them depends on the others."
)


@dataclass(frozen=True, slots=True)
class _Observed:
    """One turn's record: what the cortex chose, and what it said."""

    picks: list[str] = field(default_factory=list[str])
    batches: list[int] = field(default_factory=list[int])
    reply: str = ""
    reasoning: str = ""


def _profile(
    name: str,
    entry: SubagentRosterEntry,
    client: httpx.AsyncClient,
    scheduler: SubagentScheduler,
    placer: SubagentPlacer,
) -> SubagentProfile:
    """Build one roster entry as the composition root does, with its own backend pair and ask."""
    return SubagentProfile(
        resources=SubagentResources(
            backends={
                PlacementTarget.GPU: LlamaCppBackend(
                    SingleResidentModelManager(name, entry.gpu_endpoint), client
                ),
                PlacementTarget.CPU: LlamaCppBackend(
                    SingleResidentModelManager(name, entry.endpoint), client
                ),
            },
            scheduler=scheduler,
            placer=placer,
            request=PlacementRequest(name, entry.vram_gb, entry.cpus, entry.memory_gb),
        ),
        description=entry.description,
    )


def _spawn_tool(
    config: SubagentsConfig, runtime: BrainRuntimeConfig, client: httpx.AsyncClient
) -> SpawnSubagentsTool:
    """Build the deployment's own spawn tool over every roster entry, with one budget and ledger.

    Numbers come from the settings classes the composition root reads, so the spec the cortex is
    shown here is the spec the shipped brain would show it. The task store is in-memory because
    what is observed is the cortex's choice, which is made before a task is ever stored.
    """
    scheduler = ResourceBudgetScheduler(config.cpu_budget, config.mem_budget_gb)
    placer = VramBudgetPlacer(
        soft_cap_gb=runtime.vram_soft_cap_gb,
        cortex_reservation_gb=runtime.cortex_reservation_gb,
    )
    roster = SubagentRoster(
        entries={
            name: _profile(name, entry, client, scheduler, placer)
            for name, entry in config.named_roster.items()
        },
        default=config.model,
    )
    store = InMemoryTaskStore()
    clock = SystemClock()
    runner = SubagentRunner(store, roster, clock, constrain_output=config.constrain_output)
    return SpawnSubagentsTool(runner, store, clock)


def _advertised_models(spec: ToolSpec) -> list[str]:
    """Return the `model` enum the spec publishes, read out of the JSON Schema it carries."""
    properties = cast("Mapping[str, object]", spec.parameters["properties"])
    instructions = cast("Mapping[str, object]", properties["instructions"])
    items = cast("Mapping[str, object]", instructions["items"])
    variants = cast("Sequence[Mapping[str, object]]", items["anyOf"])
    object_item = cast("Mapping[str, object]", variants[1]["properties"])
    knob = cast("Mapping[str, object]", object_item["model"])
    return list(cast("Sequence[str]", knob["enum"]))


async def _one_turn(ask: str) -> _Observed:
    """Run one real cortex turn with only `spawn_subagents` advertised, and record the choice."""
    config = SubagentsConfig()
    runtime = BrainRuntimeConfig()
    clock = SystemClock()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)
    ) as client:
        dispatcher = build_cortex_tools(
            None, build_builtin_tools(_spawn_tool(config, runtime, client), None), clock
        )
        assert dispatcher is not None
        backend = LlamaCppBackend(
            SingleResidentModelManager(runtime.cortex_model, _INFERENCE or ""), client
        )
        context = ToolLoopContext(
            dispatcher=dispatcher,
            clock=clock,
            turn_id="nudge-probe",
            taint=TaintLedger(),
            nonce=new_nonce(),
            session_id="nudge-probe",
        )
        user = Message(role=Role.USER, text=ask, at=clock.now(), turn_id=context.turn_id)
        caps = TurnCapabilities(tools=dispatcher)
        working = list(await assemble_inference_messages(ask, [user], caps, context, clock))
        reply: list[str] = []
        reasoning: list[str] = []
        async for event in stream_tool_loop(backend, runtime.cortex_model, working, context):
            if isinstance(event, ReasoningDelta):
                reasoning.append(event.text)
            elif isinstance(event, str):
                reply.append(event)
    observed = _Observed(reply="".join(reply), reasoning="".join(reasoning))
    for message in working:
        for call in message.tool_calls:
            # A malformed `instructions` is the tool's own `is_error` to answer, not this
            # observation's to crash on, so a call that carries no array simply records nothing.
            raw: object = call.arguments.get("instructions")
            if not isinstance(raw, list):
                continue
            items = cast("Sequence[object]", raw)
            observed.batches.append(len(items))
            observed.picks.extend(_pick_of(item, config.model) for item in items)
    return observed


def _pick_of(item: object, default: str) -> str:
    """Return the roster entry one instructions item asked for, or the default when it named
    none."""
    if isinstance(item, Mapping):
        chosen = cast("Mapping[str, object]", item).get("model", "")
        return cast("str", chosen) if chosen else default
    return default


def _report(label: str, observed: _Observed) -> None:
    """Print the observation, which is the output of the run rather than an assertion."""
    print(  # noqa: T201
        f"\n[{label}] batches={observed.batches} picks={observed.picks} "
        f"distinct_models={len(set(observed.picks))} reply_chars={len(observed.reply)} "
        f"reasoning_chars={len(observed.reasoning)}"
    )


def _assert_the_choice_is_well_formed(observed: _Observed, config: SubagentsConfig) -> None:
    """Assert what holds whatever the cortex decided, delegation or none."""
    assert observed.reply.strip(), "the turn produced no reply at all"
    for size in observed.batches:
        assert 0 < size <= MAX_SPAWN_BATCH, f"a batch of {size} is outside the advertised cap"
    for pick in observed.picks:
        assert pick in config.named_roster, f"the cortex named {pick!r}, which is not in the roster"


@pytest.mark.integration
@_needs_a_cortex_and_a_multi_entry_roster
async def test_the_spawn_tool_offers_the_knob_and_the_trade_off_it_is_meant_to_take() -> None:
    """The advertised spec carries the `model` knob and the trade-off line, so a run that never
    spreads is not a spec that never offered the choice.

    This arm is deterministic and makes no model call, so it is the evidence the two observation
    arms rest on.
    """
    config = SubagentsConfig()
    runtime = BrainRuntimeConfig()
    async with httpx.AsyncClient() as client:
        spec = _spawn_tool(config, runtime, client).spec
    # Asserted before the enum is read, because a one-entry roster publishes no `model` property
    # at all and digging for one would raise where a sentence should explain.
    assert len(config.named_roster) > 1, "a one-entry roster has nothing to spread across"
    assert sorted(_advertised_models(spec)) == sorted(config.named_roster)
    assert "spread independent subtasks across models" in spec.description
    print(f"\n[armed] models={sorted(_advertised_models(spec))}")  # noqa: T201
    print(f"[armed] description={spec.description}")  # noqa: T201


@pytest.mark.integration
@_needs_a_cortex_and_a_multi_entry_roster
async def test_a_prose_only_ask_carrying_independent_subtasks() -> None:
    """Observe whether the cortex reaches for delegation at all when the ask carries no
    delegation language."""
    config = SubagentsConfig()
    observed = await _one_turn(_ASK_PROSE)
    _report("prose-only", observed)
    _assert_the_choice_is_well_formed(observed, config)


@pytest.mark.integration
@_needs_a_cortex_and_a_multi_entry_roster
async def test_an_ask_that_invites_delegation_in_the_users_own_words() -> None:
    """Observe whether an invited cortex spreads the batch across entries or puts it all on
    one."""
    config = SubagentsConfig()
    observed = await _one_turn(_ASK_INVITED)
    _report("invited", observed)
    print(f"[invited] roster={json.dumps(sorted(config.named_roster))}")  # noqa: T201
    _assert_the_choice_is_well_formed(observed, config)
