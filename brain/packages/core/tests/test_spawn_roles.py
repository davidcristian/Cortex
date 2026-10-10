from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Any, cast

from cortex_core import (
    NO_ROLES,
    SHIPPED_ROLES,
    EchoInferenceBackend,
    GenerationBounds,
    InferenceBackend,
    InferenceError,
    InferenceEvent,
    InMemoryTaskStore,
    InMemoryToolRegistry,
    JsonSchema,
    Message,
    PlacementRequest,
    PlacementTarget,
    RecordingAuditSink,
    ResourceBudgetScheduler,
    SpawnSubagentsTool,
    SubagentProfile,
    SubagentResources,
    SubagentRole,
    SubagentRoles,
    SubagentRoster,
    SubagentRunner,
    SubagentTask,
    ToolCall,
    ToolDispatcher,
    ToolSpec,
    TurnStamp,
    VramBudgetPlacer,
)

_AT = datetime(2026, 9, 28, 5, 0, tzinfo=UTC)
_BRIEF = SubagentRole(description="a one-line reply", instruction="Reply in one line.")
_ROLES = SubagentRoles(entries={"brief": _BRIEF})


class FixedClock:
    def now(self) -> datetime:
        return _AT


class RefusingBackend:
    """Fails every request, so a subtask it answers is visible as a failure."""

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        del model, messages, tools, schema, bounds
        msg = "the weak entry was reached"
        raise InferenceError(msg)
        yield  # pragma: no cover - makes this an async generator; the raise ends it first


def _profile(backend: InferenceBackend, model: str) -> SubagentProfile:
    return SubagentProfile(
        resources=SubagentResources(
            backends={PlacementTarget.GPU: backend, PlacementTarget.CPU: backend},
            scheduler=ResourceBudgetScheduler(8.0, 8.0),
            placer=VramBudgetPlacer(soft_cap_gb=14.0, cortex_reservation_gb=11.0),
            request=PlacementRequest(model, vram_gb=2.0, cpus=2.0, memory_gb=2.0),
        )
    )


def _runner(
    store: InMemoryTaskStore,
    roles: SubagentRoles,
    *,
    tools: ToolDispatcher | None = None,
) -> SubagentRunner:
    roster = SubagentRoster(
        entries={
            "subagent": _profile(EchoInferenceBackend(), "subagent"),
            "weak": _profile(RefusingBackend(), "weak"),
        },
        default="subagent",
    )
    return SubagentRunner(store, roster, FixedClock(), tools=tools, roles=roles)


def _tool(store: InMemoryTaskStore, roles: SubagentRoles = _ROLES) -> SpawnSubagentsTool:
    ids = iter(f"st-{n}" for n in range(1, 100))
    return SpawnSubagentsTool(
        _runner(store, roles), store, FixedClock(), task_id_factory=lambda: next(ids)
    )


def _call(item: object, *, tainted: bool = False) -> ToolCall:
    return ToolCall(
        id="c1",
        name="spawn_subagents",
        arguments={"instructions": [item]},
        stamp=TurnStamp(tainted=tainted),
    )


def _role_property(spec: ToolSpec) -> dict[str, Any] | None:
    items = cast("dict[str, Any]", spec.parameters["properties"]["instructions"]["items"])
    item_object = cast("dict[str, Any]", items["anyOf"][1])
    return cast("dict[str, Any] | None", item_object["properties"].get("role"))


async def test_a_role_named_in_a_spawn_reaches_the_subagent_after_its_instruction() -> None:
    store = InMemoryTaskStore()
    item = {"instruction": "name a color", "role": "brief", "context": "The sky is blue."}
    result = await _tool(store).invoke(_call(item))
    assert result.is_error is False
    assert result.content == "[subagent 1] reply 1: name a color Reply in one line."
    task = await store.get_task("st-1")
    assert task is not None
    assert (task.instruction, task.role) == ("name a color", "brief")


async def test_a_role_on_a_spawn_with_no_context_leaves_the_instruction_as_written() -> None:
    store = InMemoryTaskStore()
    item = {"instruction": "name a color", "role": "answer"}
    result = await _tool(store, SHIPPED_ROLES).invoke(_call(item))
    assert result.content == "[subagent 1] reply 1: name a color"


async def test_a_role_never_moves_a_tainted_spawn_off_the_default_model() -> None:
    store = InMemoryTaskStore()
    item = {"instruction": "name a color", "role": "brief", "model": "weak", "context": "Blue."}
    result = await _tool(store).invoke(_call(item, tainted=True))
    assert result.content.startswith("[subagent 1] reply 1: <untrusted-tool-output")
    assert result.content.endswith("\n\nname a color Reply in one line.")


async def test_a_clean_spawn_with_a_role_still_runs_the_model_it_picked() -> None:
    store = InMemoryTaskStore()
    item = {"instruction": "name a color", "role": "brief", "model": "weak"}
    result = await _tool(store).invoke(_call(item))
    assert "the weak entry was reached" in result.content


async def test_an_unknown_role_is_an_error_the_cortex_can_correct() -> None:
    store = InMemoryTaskStore()
    result = await _tool(store).invoke(_call({"instruction": "go", "role": "ghost"}))
    assert result.is_error is True
    assert result.content == "unknown subagent role 'ghost'; options: brief"
    assert await store.get_task("st-1") is None


async def test_a_role_that_is_not_a_string_is_an_error() -> None:
    store = InMemoryTaskStore()
    result = await _tool(store).invoke(_call({"instruction": "go", "role": 3}))
    assert (result.is_error, result.content) == (True, "the 'role' of a subtask must be a string")


async def test_a_role_named_when_the_wiring_has_none_says_there_are_none() -> None:
    store = InMemoryTaskStore()
    result = await _tool(store, NO_ROLES).invoke(_call({"instruction": "go", "role": "brief"}))
    assert (result.is_error, result.content) == (
        True,
        "unknown subagent role 'brief'; options: none",
    )


async def test_a_stored_task_naming_an_unknown_role_fails_closed_and_keeps_its_taint() -> None:
    store = InMemoryTaskStore()
    task = SubagentTask(id="t1", instruction="go", context="", at=_AT, tainted=True, role="ghost")
    await store.put_task(task)
    result = await _runner(store, _ROLES).run("t1")
    assert (result.ok, result.detail, result.tainted) == (
        False,
        "unknown subagent role 'ghost'",
        True,
    )
    assert await store.get_result("t1") == result


async def test_the_spec_lists_every_role_with_what_it_returns() -> None:
    spec = _tool(InMemoryTaskStore(), SHIPPED_ROLES).spec
    role = _role_property(spec)
    assert role is not None
    assert role["enum"] == sorted(SHIPPED_ROLES.entries)
    for name, entry in SHIPPED_ROLES.entries.items():
        assert f"{name!r} ({entry.description})" in role["description"]
    assert "omit for a free instruction" in role["description"]
    assert '"role": "<role name>"' in spec.description


async def test_the_spec_offers_roles_to_a_wiring_whose_subagents_hold_tools() -> None:
    store = InMemoryTaskStore()
    dispatcher = ToolDispatcher(InMemoryToolRegistry({}), RecordingAuditSink(), FixedClock())
    runner = _runner(store, _ROLES, tools=dispatcher)
    spec = SpawnSubagentsTool(runner, store, FixedClock()).spec
    role = _role_property(spec)
    assert role is not None
    assert role["enum"] == ["brief"]


async def test_the_spec_names_no_role_when_the_wiring_has_none() -> None:
    spec = _tool(InMemoryTaskStore(), NO_ROLES).spec
    assert _role_property(spec) is None
    assert "'role'" not in spec.description
