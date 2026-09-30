import json
import os
from collections.abc import Mapping, Sequence
from contextlib import aclosing
from dataclasses import dataclass, field, replace
from typing import cast

import httpx
import pytest

from cortex_core import (
    MAX_SPAWN_BATCH,
    NO_ROLES,
    SHIPPED_ROLES,
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
    SubagentRoles,
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
from cortex_core.loop_events import ReasoningDelta, ToolStep
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
_ALTERNATES = [name for name in os.environ if name.startswith("CORTEX_SUBAGENTS_ROSTER__")]

_needs_a_cortex_and_a_multi_entry_roster = pytest.mark.skipif(
    not (_INFERENCE and _ALTERNATES),
    reason="set CORTEX_INFERENCE_ENDPOINT and at least one CORTEX_SUBAGENTS_ROSTER__<name>",
)

_ASK_PROSE = (
    "I am putting together notes for a talk tomorrow and I need three short write-ups. One on "
    "what a hash table is, one on what a bloom filter is, and one on what a skip list is. Two or "
    "three sentences each, plain enough for someone new to the subject. None of them depends on "
    "the others."
)
_ASK_INVITED = (
    "I need three separate things written and I would rather you farm them out than write them "
    "all yourself. One: two or three sentences on what a hash table is. Two: two or three "
    "sentences on what a bloom filter is. Three: two or three sentences on what a skip list is. "
    "Nothing in any of them depends on the others."
)

_needs_a_cortex_and_a_roster = pytest.mark.skipif(
    not (_INFERENCE and os.environ.get("CORTEX_SUBAGENTS_BACKEND") == "llamacpp"),
    reason="set CORTEX_INFERENCE_ENDPOINT and CORTEX_SUBAGENTS_BACKEND=llamacpp with its endpoints",
)
_ROLE_DRAWS = int(os.environ.get("CORTEX_ROLE_UPTAKE_DRAWS", "1"))
_EXCERPT_DESCRIPTION = os.environ.get("CORTEX_ROLE_UPTAKE_EXCERPT", "")


def _roles() -> SubagentRoles:
    """``SHIPPED_ROLES``, with the `excerpt` description a row sets drawn in its place."""
    if not _EXCERPT_DESCRIPTION:
        return SHIPPED_ROLES
    excerpt = replace(SHIPPED_ROLES.entries["excerpt"], description=_EXCERPT_DESCRIPTION)
    return SubagentRoles(entries={**SHIPPED_ROLES.entries, "excerpt": excerpt})


_INVITE = "I would rather you hand this to a subagent than do it yourself."
_ROLE_ASKS = {
    "precis": (
        "precis",
        "Summarize the note below in two sentences, keeping its figures, names and dates.",
    ),
    "excerpt": ("excerpt", "List every date the note below mentions."),
    "numbers": ("excerpt", "Extract every number from the note below."),
    "answer": ("answer", "What total cost does the note below state?"),
}
_NOTES = (
    "Minutes, 14 March 2025. Priya Nair reported that the roof repair at the Leeds depot finished "
    "on 2 March, eleven days late, at a total cost of 48,200 pounds against a budget of 41,000. "
    "Tom Hale will ask the contractor, Brightwell Roofing, for the delay penalty by 30 April.",
    "Field note, 9 June 2024. The survey team under Ana Costa sampled 312 wells in the Tejo valley "
    "between 20 May and 6 June. Nitrate exceeded 50 mg per litre in 47 of them. Fuel, lab fees and "
    "wages came to 26,750 euros in total. Results go to the regional water board on 1 July.",
    "Release memo, 3 October 2023. Version 4.2 of the billing service shipped on 28 September "
    "after two postponements. Kenji Mori's team closed 83 of the 91 open defects. Cloud spend for "
    "the release cycle was 12,400 dollars in total. Dana Ruiz reviews it on 17 October.",
    "Club newsletter, 21 January 2026. The Harbourside Rowing Club bought two new eights on 8 "
    "January for a total of 61,500 dollars, paid from the 2025 appeal. Coach Mei Lin expects them "
    "on the water by 15 February. Membership rose from 164 to 203 over the year.",
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
    """Build the deployment's own spawn tool over every roster entry, with one budget and ledger."""
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
    runner = SubagentRunner(
        store,
        roster,
        clock,
        constrain_output=config.constrain_output,
        roles=_roles() if config.roles else NO_ROLES,
    )
    return SpawnSubagentsTool(runner, store, clock)


def _advertised(spec: ToolSpec, key: str) -> list[str]:
    """Return the enum the spec publishes for one object-item property, or none if it is absent."""
    properties = cast("Mapping[str, object]", spec.parameters["properties"])
    instructions = cast("Mapping[str, object]", properties["instructions"])
    items = cast("Mapping[str, object]", instructions["items"])
    variants = cast("Sequence[Mapping[str, object]]", items["anyOf"])
    object_item = cast("Mapping[str, object]", variants[1]["properties"])
    if key not in object_item:
        return []
    chosen = cast("Mapping[str, object]", object_item[key])
    return list(cast("Sequence[str]", chosen["enum"]))


async def _started(
    ask: str, client: httpx.AsyncClient
) -> tuple[LlamaCppBackend, list[Message], ToolLoopContext]:
    """Build one real cortex turn with only `spawn_subagents` advertised, ready to stream."""
    config = SubagentsConfig()
    runtime = BrainRuntimeConfig()
    clock = SystemClock()
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
    return backend, working, context


def _spawn_items(working: Sequence[Message]) -> list[list[object]]:
    """Return the instructions items of every spawn call in ``working``, one list per call."""
    batches: list[list[object]] = []
    for message in working:
        for call in message.tool_calls:
            raw: object = call.arguments.get("instructions")
            if isinstance(raw, list):
                batches.append(list(cast("Sequence[object]", raw)))
    return batches


async def _one_turn(ask: str) -> _Observed:
    """Run one real cortex turn with only `spawn_subagents` advertised, and record the choice."""
    config = SubagentsConfig()
    runtime = BrainRuntimeConfig()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)
    ) as client:
        backend, working, context = await _started(ask, client)
        reply: list[str] = []
        reasoning: list[str] = []
        async for event in stream_tool_loop(backend, runtime.cortex_model, working, context):
            if isinstance(event, ReasoningDelta):
                reasoning.append(event.text)
            elif isinstance(event, str):
                reply.append(event)
    observed = _Observed(reply="".join(reply), reasoning="".join(reasoning))
    for items in _spawn_items(working):
        observed.batches.append(len(items))
        observed.picks.extend(_pick_of(item, config.model) for item in items)
    return observed


def _pick_of(item: object, default: str) -> str:
    """Return the roster entry an instructions item asked for, or the default when it named none."""
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
async def test_the_spawn_tool_offers_the_model_choice_and_the_trade_off_it_is_meant_to_take() -> (
    None
):
    config = SubagentsConfig()
    runtime = BrainRuntimeConfig()
    async with httpx.AsyncClient() as client:
        spec = _spawn_tool(config, runtime, client).spec
    assert len(config.named_roster) > 1, "a one-entry roster has nothing to spread across"
    assert sorted(_advertised(spec, "model")) == sorted(config.named_roster)
    assert "spread independent subtasks across models" in spec.description
    print(f"\n[armed] models={sorted(_advertised(spec, 'model'))}")  # noqa: T201
    print(f"[armed] description={spec.description}")  # noqa: T201


@pytest.mark.integration
@_needs_a_cortex_and_a_multi_entry_roster
async def test_a_prose_only_ask_with_independent_subtasks() -> None:
    config = SubagentsConfig()
    observed = await _one_turn(_ASK_PROSE)
    _report("prose-only", observed)
    _assert_the_choice_is_well_formed(observed, config)


@pytest.mark.integration
@_needs_a_cortex_and_a_multi_entry_roster
async def test_an_ask_that_invites_delegation_in_the_users_own_words() -> None:
    config = SubagentsConfig()
    observed = await _one_turn(_ASK_INVITED)
    _report("invited", observed)
    print(f"[invited] roster={json.dumps(sorted(config.named_roster))}")  # noqa: T201
    _assert_the_choice_is_well_formed(observed, config)


async def _first_spawn(ask: str) -> list[list[object]]:
    """Run one cortex turn up to its first dispatch, and return the spawn items it wrote."""
    runtime = BrainRuntimeConfig()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(LLAMACPP_CONNECT_TIMEOUT_S, read=None)
    ) as client:
        backend, working, context = await _started(ask, client)
        events = stream_tool_loop(backend, runtime.cortex_model, working, context)
        async with aclosing(events):
            async for event in events:
                if isinstance(event, ToolStep):
                    break
    return _spawn_items(working)


def _as_object(item: object) -> Mapping[str, object]:
    """Return an instructions item as an object, a bare string being its instruction alone."""
    if isinstance(item, str):
        try:
            decoded: object = json.loads(item)
        except ValueError:
            decoded = None
        if isinstance(decoded, Mapping):
            return cast("Mapping[str, object]", decoded)
        return {"instruction": item}
    return cast("Mapping[str, object]", item) if isinstance(item, Mapping) else {}


def _role_of(item: object) -> str:
    """Return the role an instructions item names, or the repr of a role that is not a string."""
    role = _as_object(item).get("role", "")
    return role if isinstance(role, str) else repr(role)


@pytest.mark.integration
@_needs_a_cortex_and_a_roster
@pytest.mark.parametrize("draw", range(_ROLE_DRAWS))
@pytest.mark.parametrize("note", range(len(_NOTES)))
@pytest.mark.parametrize("ask", sorted(_ROLE_ASKS))
async def test_the_cortex_names_the_role_of_the_subtask_it_delegates(
    ask: str, note: int, draw: int
) -> None:
    expected, wording = _ROLE_ASKS[ask]
    batches = await _first_spawn(f"{_INVITE} {wording}\n\n{_NOTES[note]}")
    named = [_role_of(item) for items in batches for item in items]
    async with httpx.AsyncClient() as client:
        spec = _spawn_tool(SubagentsConfig(), BrainRuntimeConfig(), client).spec
    offered = _advertised(spec, "role")
    print(  # noqa: T201
        f"\n[role-uptake] ask={ask} expected={expected} note={note} draw={draw} offered={offered} "
        f"batches={[len(items) for items in batches]} named={named} "
        f"excerpt_description={_roles().entries['excerpt'].description!r}"
    )
    for items in batches:
        for item in items:
            print(f"[role-uptake] wrote={json.dumps(_as_object(item))}")  # noqa: T201
    for items in batches:
        assert 0 < len(items) <= MAX_SPAWN_BATCH, f"a batch of {len(items)} is outside the cap"
