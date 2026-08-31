"""The `ToolRegistry` contract, run over every implementation (AGENTS.md: ports before adapters).

Six checks over the two verbs the port has. They are the description the core is written against:
the tool loop advertises whatever `describe_tools` answers and feeds the model whatever `invoke`
returns, and the routing combinators in `aggregate.py` re-walk the listing on every call rather
than remembering one.

Each fixture supplies the two conditions no method of the port can create. `serve` replaces the
tool set, which is how a check changes the set the port has to re-read and how it arranges a tool
that runs and fails. `break_backend` makes the whole registry unreachable, which is what a dead
sidecar looks like from here.
"""

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
    """One tool a fixture publishes: what the model is told, and what calling it does.

    `failed` marks the tool that runs and reports an error, which is the case the port's
    ``is_error`` flag exists for and one the result text alone cannot express.
    """

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
    """Name, purpose and JSON Schema all reach the advertisement, in the order they were served.

    The schema is the only thing the model has to build a call from, so a registry that dropped or
    rewrote it would produce calls the tool rejects, with nothing in the failure naming the cause.
    Order is part of the answer because the routing combinators dedupe first-wins over it.
    """
    under_test.serve([_tool("read", description="read a file"), _tool("list")])
    specs = await under_test.registry.describe_tools()
    advertised = [(spec.name, spec.description) for spec in specs]
    assert advertised == [("read", "read a file"), ("list", "")]
    assert [dict(spec.parameters) for spec in specs] == [dict(_SCHEMA), dict(_SCHEMA)]


async def the_advertised_set_is_read_again_on_every_walk(under_test: RegistryUnderTest) -> None:
    """Each walk reads the tool set again, so an earlier listing is never reused.

    The routing combinators depend on that. `AggregateToolRegistry` picks the registry that
    advertises a name at call time, and `UngatedToolRegistry` rejects a name that is gated at call
    time, both reading the listing then rather than at startup. An implementation answering from a
    set it cached would route a call to a server that has dropped the tool, and would hand a
    subagent a gated tool that was ungated when the process started.
    """
    under_test.serve([_tool("read")])
    assert [spec.name for spec in await under_test.registry.describe_tools()] == ["read"]
    under_test.serve([_tool("list"), _tool("read")])
    assert [spec.name for spec in await under_test.registry.describe_tools()] == ["list", "read"]


async def a_call_comes_back_stamped_with_its_own_id_and_the_tools_text(
    under_test: RegistryUnderTest,
) -> None:
    """The result carries the call's id, the tool's output, and no error flag.

    The id is how the tool loop pairs a result with the call the model made, so a registry that
    invented one would strand the answer; the arguments have to survive the trip intact, which is
    what the echoing reply proves.
    """
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

    That is the distinction the port draws with ``is_error``: the call reached the tool, and the
    tool reported an error. The dispatcher hands that text back as untrusted content and the loop
    continues, while a raised failure becomes the dispatcher's own trusted sentence instead. An
    implementation that raised here would relabel a hostile file's error message as the
    dispatcher's own words.
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
    """An unknown name comes back as an error, either raised or flagged, and never as a success.

    The implementations differ here and the port allows both: a registry that holds its own set
    raises ``ToolNotFoundError``, while a remote one can only relay what its server says, and an
    MCP server answers an unknown tool with an error result. Either is safe. A result with
    ``is_error`` unset is not, since the loop would feed the model a success it never had.
    """
    under_test.serve([_tool("read")])
    call = ToolCall(id="c-3", name="ghost", arguments={"path": "/x"})
    try:
        result = await under_test.registry.invoke(call)
    except ToolError:
        return
    assert result.is_error is True


async def a_backend_that_cannot_answer_raises_tool_error(under_test: RegistryUnderTest) -> None:
    """Both verbs raise the port's one error type when the registry is unreachable.

    `SkipUnavailableToolRegistry` is built on that: it catches ``ToolError`` from a walk and
    reports a dead sidecar while the healthy ones keep serving. An implementation that answered an
    empty listing instead would make a dead sidecar look like one that serves no tools, and the
    turn would run on quietly without them.
    """
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
