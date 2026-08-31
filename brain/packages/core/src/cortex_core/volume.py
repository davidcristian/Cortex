"""The ``get_volume`` / ``set_volume`` built-in tools: the first host OS action (ADR-0023).

The cortex calls these like any tool. Each runs through the audited ``ToolDispatcher`` and
calls the ``BodyGateway`` port, which reaches the host body over ``BodyService`` (the first
brain→body seam direction). Both are internal built-ins rather than MCP tools, so they are
cortex-only by construction, since a subagent never gets one (ADR-0010/0013).

Volume is reversible and low-harm, so both tools are ungated (``gated=False``): a spoken
"set volume to 30%" should not demand an approval card. The gate is still inherited by later
irreversible OS actions (``gated=True``), and a user can opt volume in by adding
``set_volume`` to ``CORTEX_TOOLS_GATED`` (the dispatcher's authoritative backstop, ADR-0022).
Every result is ``Trust.TRUSTED`` since host state is system-generated, never third-party content,
so a volume call never taints the turn. Bad arguments and a failed body call both become an
``is_error`` result the cortex can correct or report. It is never an exception, and a body
failure is worded from its ``BodyFailure`` kind, so a host with no audio endpoint reads as a
host that is not in a state to do it rather than as a body nobody could reach.
"""

from collections.abc import Mapping
from typing import Any

from cortex_core.body import VolumeState
from cortex_core.body_failure import body_failure_message
from cortex_core.errors import BodyGatewayError
from cortex_core.ports import BodyGateway
from cortex_core.tools import ToolCall, ToolResult, ToolSpec, Trust

GET_VOLUME_TOOL_NAME = "get_volume"
SET_VOLUME_TOOL_NAME = "set_volume"

# The infinitive the shared per-kind lead completes (ADR-0023's 2026-08-08 addendum), so a
# host with no audio endpoint is not announced as a body nobody could reach.
_ACTION = "control volume"
_SET_REQUIRES_ARG = "set_volume requires 'level' (0.0-1.0) and/or 'mute' (true/false)"
_BAD_LEVEL = "'level' must be a number between 0.0 and 1.0"
_BAD_MUTE = "'mute' must be true or false"


def _format_state(state: VolumeState) -> str:
    """A one-line, human-readable summary of the host volume state for the cortex."""
    muted = ", muted" if state.muted else ""
    return f"volume is at {round(state.level * 100)}%{muted}"


def _parse_set_args(arguments: Mapping[str, Any]) -> tuple[float | None, bool | None] | str:
    """Validate ``set_volume`` arguments; return ``(level, mute)`` or an error message string.

    At least one of ``level``/``mute`` must be present. ``level`` must be a real number in
    [0.0, 1.0] (a JSON bool is rejected because ``bool`` subclasses ``int`` but is not a level);
    ``mute`` must be a bool. An out-of-range or wrong-typed value returns a message the cortex
    can correct, never raising.
    """
    level = arguments.get("level")
    mute = arguments.get("mute")
    if level is None and mute is None:
        return _SET_REQUIRES_ARG
    parsed_level: float | None = None
    if level is not None:
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            return _BAD_LEVEL
        try:
            numeric = float(level)
        except OverflowError:
            # An out-of-double-range int (e.g. a huge JSON integer) is not a valid level;
            # fail as a recoverable message, never a raise (the tool's contract).
            return _BAD_LEVEL
        if not 0.0 <= numeric <= 1.0:
            return _BAD_LEVEL
        parsed_level = numeric
    parsed_mute: bool | None = None
    if mute is not None:
        if not isinstance(mute, bool):
            return _BAD_MUTE
        parsed_mute = mute
    return parsed_level, parsed_mute


class GetVolumeTool:
    """Built-in ``get_volume`` tool over a ``BodyGateway`` (ADR-0023): read the host volume."""

    def __init__(self, body: BodyGateway) -> None:
        self._body = body

    @property
    def spec(self) -> ToolSpec:
        """The read-only, ungated spec advertised to the cortex."""
        return ToolSpec(
            name=GET_VOLUME_TOOL_NAME,
            description="Read the host system's current audio volume level and mute state.",
            parameters={"type": "object", "properties": {}},
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Read the host volume; a failed body call becomes a trusted, kind-worded error result."""
        try:
            state = await self._body.get_volume()
        except BodyGatewayError as err:
            return ToolResult(
                call_id=call.id,
                content=body_failure_message(err, action=_ACTION),
                is_error=True,
                trust=Trust.TRUSTED,
            )
        return ToolResult(call_id=call.id, content=_format_state(state), trust=Trust.TRUSTED)


class SetVolumeTool:
    """Built-in ``set_volume`` tool over a ``BodyGateway`` (ADR-0023): change the host volume.

    Ungated (reversible); a user can opt into confirmation via ``CORTEX_TOOLS_GATED``.
    """

    def __init__(self, body: BodyGateway) -> None:
        self._body = body

    @property
    def spec(self) -> ToolSpec:
        """The ungated spec: ``level`` (0.0-1.0) and/or ``mute``, at least one required."""
        return ToolSpec(
            name=SET_VOLUME_TOOL_NAME,
            description=(
                "Set the host system's audio volume and/or mute state. Provide 'level' as a "
                "fraction from 0.0 (silent) to 1.0 (max), 'mute' as true/false, or both."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Target volume as a fraction from 0.0 to 1.0.",
                    },
                    "mute": {"type": "boolean", "description": "Whether to mute the output."},
                },
            },
        )

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Validate the arguments, apply the change, and report the resulting state.

        Bad arguments and a failed body call are both trusted ``is_error`` results; a
        successful change reports the state the body read back after applying it.
        """
        parsed = _parse_set_args(call.arguments)
        if isinstance(parsed, str):
            return ToolResult(call_id=call.id, content=parsed, is_error=True, trust=Trust.TRUSTED)
        level, mute = parsed
        try:
            state = await self._body.set_volume(level=level, mute=mute)
        except BodyGatewayError as err:
            return ToolResult(
                call_id=call.id,
                content=body_failure_message(err, action=_ACTION),
                is_error=True,
                trust=Trust.TRUSTED,
            )
        return ToolResult(call_id=call.id, content=_format_state(state), trust=Trust.TRUSTED)
