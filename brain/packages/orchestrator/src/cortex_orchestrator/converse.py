"""The Converse use-case: ClientEvents in, turn-engine runs, ServerEvents out."""

from collections.abc import AsyncGenerator, AsyncIterator

from cortex_core import Sleeper, new_turn_id
from cortex_orchestrator.converse_stream import (
    DEFAULT_CONFIRM_TIMEOUT_S,
    DEFAULT_MAX_BUFFERED_EVENTS,
    ERROR_CODE_INFERENCE_FAILED,
    ERROR_CODE_INTERNAL,
    ERROR_CODE_SESSION_STORE_UNAVAILABLE,
    ConverseStream,
    EngineFactory,
    TurnIdFactory,
)
from cortex_seam import ClientEvent, ServerEvent

__all__ = [
    "DEFAULT_CONFIRM_TIMEOUT_S",
    "DEFAULT_MAX_BUFFERED_EVENTS",
    "ERROR_CODE_INFERENCE_FAILED",
    "ERROR_CODE_INTERNAL",
    "ERROR_CODE_SESSION_STORE_UNAVAILABLE",
    "EngineFactory",
    "TurnIdFactory",
    "converse",
]


def converse(
    make_engine: EngineFactory,
    client_events: AsyncIterator[ClientEvent],
    *,
    max_buffered_events: int = DEFAULT_MAX_BUFFERED_EVENTS,
    confirm_timeout_s: float = DEFAULT_CONFIRM_TIMEOUT_S,
    turn_id_factory: TurnIdFactory = new_turn_id,
    sleeper: Sleeper | None = None,
) -> AsyncGenerator[ServerEvent, None]:
    """The Converse conversation loop as a server-event stream (see module docstring)."""
    stream = ConverseStream(
        make_engine,
        max_buffered_events=max_buffered_events,
        confirm_timeout_s=confirm_timeout_s,
        turn_id_factory=turn_id_factory,
        sleeper=sleeper,
    )
    return stream.events(client_events)
