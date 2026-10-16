"""A turn's wait for its model's server to finish loading, announced to the overlay."""

import logging
from collections.abc import AsyncGenerator, AsyncIterator, Generator, Sequence
from contextlib import AsyncExitStack, contextmanager
from datetime import datetime, timedelta

from cortex_core.conversation import Message
from cortex_core.errors import ModelLoadingError
from cortex_core.events import TurnEvent
from cortex_core.images import ImagePart
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.ports import Clock, InferenceBackend, Sleeper, TurnRunner
from cortex_core.progress import ProgressSink, hold_wait
from cortex_core.tools import ToolSpec
from cortex_core.waits import SWAPPING, Wait

MODEL_LOADING_DETAIL = "waiting for the model to finish loading"
MODEL_LOADING = Wait(SWAPPING, MODEL_LOADING_DETAIL)

# llama-server refuses a request with a 503 at once while it loads, so asking again each second
# costs one refused request and ends the wait within a second of the load.
LOAD_POLL_INTERVAL_S = 1.0

_logger = logging.getLogger(__name__)


class _Bound:
    """A wait bound that starts at the first loading answer it is asked about."""

    def __init__(self, clock: Clock, wait_s: float) -> None:
        self._clock = clock
        self._wait_s = wait_s
        self._at: datetime | None = None

    def passed(self) -> bool:
        """Whether the bound has passed, starting it on the first ask."""
        now = self._clock.now()
        if self._at is None:
            self._at = now + timedelta(seconds=self._wait_s)
        return now >= self._at


class LoadWaitBackend:
    """An ``InferenceBackend`` that asks again while the server is still loading, up to a bound.

    Calls inside one ``turn()`` share one bound; any other call gets its own. Any other failure,
    and a loading answer after the bound or after the first event, is raised.
    """

    def __init__(
        self,
        inner: InferenceBackend,
        progress: ProgressSink | None,
        *,
        clock: Clock,
        sleeper: Sleeper,
        wait_s: float,
        poll_s: float = LOAD_POLL_INTERVAL_S,
    ) -> None:
        self._inner = inner
        self._progress = progress
        self._clock = clock
        self._sleeper = sleeper
        self._wait_s = wait_s
        self._poll_s = poll_s
        self._turn: _Bound | None = None

    @contextmanager
    def turn(self) -> Generator[None]:
        """Share one bound among the calls made inside, forgotten when the turn ends."""
        self._turn = _Bound(self._clock, self._wait_s)
        try:
            yield
        finally:
            self._turn = None

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Stream from the wrapped backend, holding a wait while its server is still loading."""
        bound = self._turn or _Bound(self._clock, self._wait_s)
        held = False
        async with AsyncExitStack() as waiting:
            while True:
                events = self._inner.stream(
                    model, messages, tools=tools, schema=schema, bounds=bounds
                )
                started = False
                try:
                    async for event in events:
                        if not started:
                            started = True
                            await waiting.aclose()
                        yield event
                except ModelLoadingError:
                    if started or bound.passed():
                        _logger.warning(
                            "the model was still loading when the turn stopped waiting",
                            extra={"model": model, "wait_s": self._wait_s},
                        )
                        raise
                else:
                    return
                finally:
                    if isinstance(events, AsyncGenerator):
                        await events.aclose()
                if not held:
                    held = True
                    await waiting.enter_async_context(hold_wait(self._progress, MODEL_LOADING))
                    _logger.info(
                        "the model is still loading; the turn waits for it",
                        extra={"model": model, "wait_s": self._wait_s},
                    )
                await self._sleeper.sleep(self._poll_s)


class LoadWaitTurns:
    """A ``TurnRunner`` whose turns each wait at most one bound in all for a loading model."""

    def __init__(self, inner: TurnRunner, backend: LoadWaitBackend) -> None:
        self._inner = inner
        self._backend = backend

    @property
    def inner(self) -> TurnRunner:
        """The runner each turn runs through."""
        return self._inner

    async def handle_turn(
        self, session_id: str, text: str, *, turn_id: str, images: tuple[ImagePart, ...] = ()
    ) -> AsyncGenerator[TurnEvent, None]:
        """Run ``inner``'s turn inside one ``turn()`` of the waiting backend."""
        with self._backend.turn():
            events = self._inner.handle_turn(session_id, text, turn_id=turn_id, images=images)
            try:
                async for event in events:
                    yield event
            finally:
                await events.aclose()
