"""The `ToolRegistry` contract checks, run over every implementation of the port."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from cortex_core import ToolCall, ToolError, ToolRegistry, ToolSpec

_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {"path": {"type": "string"}},
    "required": ["path"],
}


def _echo(arguments: Mapping[str, Any]) -> str:
    """Return the reply a served tool gives: the arguments it was handed, rendered as text."""
    return f"read {arguments.get('path', '')}"


@dataclass(frozen=True, slots=True)
class ServedTool:
    """One tool a fixture publishes: what the model is told, and what calling it does."""

    spec: ToolSpec
    reply: Callable[[Mapping[str, Any]], str] = _echo
    failed: bool = False


@dataclass(frozen=True, slots=True)
class RegistryUnderTest:
    """One implementation plus the two ways a check may change the world behind it."""

    registry: ToolRegistry
    serve: Callable[[Sequence[ServedTool]], None]
    break_backend: Callable[[], None]


type Check = Callable[[RegistryUnderTest], Awaitable[None]]


def _tool(name: str, *, description: str = "", failed: bool = False) -> ServedTool:
    return ServedTool(
        spec=ToolSpec(name=name, description=description, parameters=_SCHEMA), failed=failed
    )


async def every_served_tool_is_advertised_as_the_model_will_see_it(
    under_test: RegistryUnderTest,
) -> None:
    """Name, purpose and JSON Schema all reach the advertisement, in the order they were served."""
    under_test.serve([_tool("read", description="read a file"), _tool("list")])
    specs = await under_test.registry.describe_tools()
    advertised = [(spec.name, spec.description) for spec in specs]
    assert advertised == [("read", "read a file"), ("list", "")]
    assert [dict(spec.parameters) for spec in specs] == [dict(_SCHEMA), dict(_SCHEMA)]


async def the_advertised_set_is_read_again_on_every_walk(under_test: RegistryUnderTest) -> None:
    """Each walk reads the tool set again, so an earlier listing is never reused."""
    under_test.serve([_tool("read")])
    assert [spec.name for spec in await under_test.registry.describe_tools()] == ["read"]
    under_test.serve([_tool("list"), _tool("read")])
    assert [spec.name for spec in await under_test.registry.describe_tools()] == ["list", "read"]


async def a_call_comes_back_stamped_with_its_own_id_and_the_tools_text(
    under_test: RegistryUnderTest,
) -> None:
    """The result has the call's id, the tool's output, and no error flag."""
    under_test.serve([_tool("read")])
    result = await under_test.registry.invoke(
        ToolCall(id="c-1", name="read", arguments={"path": "/etc/hosts"})
    )
    assert (result.call_id, result.content, result.is_error) == ("c-1", "read /etc/hosts", False)


async def a_tool_that_ran_and_failed_is_a_result_rather_than_an_exception(
    under_test: RegistryUnderTest,
) -> None:
    """A tool that ran and reported a failure comes back as a result with ``is_error`` set, rather
    than as a raised exception.
    """
    under_test.serve([_tool("read", failed=True)])
    result = await under_test.registry.invoke(
        ToolCall(id="c-2", name="read", arguments={"path": "/nope"})
    )
    assert (result.call_id, result.is_error) == ("c-2", True)
    assert result.content == "read /nope"


async def a_name_that_is_not_served_never_comes_back_as_success(
    under_test: RegistryUnderTest,
) -> None:
    """An unknown name comes back as an error, either raised or flagged, and never as a success."""
    under_test.serve([_tool("read")])
    call = ToolCall(id="c-3", name="ghost", arguments={"path": "/x"})
    try:
        result = await under_test.registry.invoke(call)
    except ToolError:
        return
    assert result.is_error is True


async def a_backend_that_cannot_answer_raises_tool_error(under_test: RegistryUnderTest) -> None:
    """Both verbs raise the port's one error type when the registry is unreachable."""
    under_test.serve([_tool("read")])
    under_test.break_backend()
    call = ToolCall(id="c-4", name="read", arguments={"path": "/x"})
    attempts: Sequence[Callable[[], Awaitable[object]]] = (
        under_test.registry.describe_tools,
        lambda: under_test.registry.invoke(call),
    )
    for attempt in attempts:
        try:
            await attempt()
        except ToolError:
            continue
        msg = "an unreachable registry answered anyway"
        raise AssertionError(msg)


ALL_CHECKS: Sequence[Check] = (
    every_served_tool_is_advertised_as_the_model_will_see_it,
    the_advertised_set_is_read_again_on_every_walk,
    a_call_comes_back_stamped_with_its_own_id_and_the_tools_text,
    a_tool_that_ran_and_failed_is_a_result_rather_than_an_exception,
    a_name_that_is_not_served_never_comes_back_as_success,
    a_backend_that_cannot_answer_raises_tool_error,
)
