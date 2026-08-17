"""The ``InferenceBackend`` twin that reports a decode cadence, and how it is scripted."""

from collections.abc import AsyncIterator, Sequence

from cortex_core.conversation import Message
from cortex_core.errors import InferenceError
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.tools import ToolSpec


class ScriptedInferenceBackend:
    """An ``InferenceBackend`` streaming the events it was scripted with, per call."""

    def __init__(
        self,
        rounds: Sequence[Sequence[InferenceEvent]] = (),
        *,
        serves: Sequence[str] | None = None,
    ) -> None:
        self._rounds = [list(events) for events in rounds] or [[]]
        self._failure: InferenceError | None = None
        self._served = None if serves is None else frozenset(serves)
        self.calls: list[str] = []

    async def stream(
        self,
        model: str,
        messages: Sequence[Message],
        *,
        tools: Sequence[ToolSpec] = (),
        schema: JsonSchema | None = None,
        bounds: GenerationBounds | None = None,
    ) -> AsyncIterator[InferenceEvent]:
        """Yield the next scripted round; the script does not read the request."""
        del messages, tools, schema, bounds
        index = min(len(self.calls), len(self._rounds) - 1)
        self.calls.append(model)
        if self._served is not None and model not in self._served:
            msg = f"this backend does not serve model {model!r} (serves: {sorted(self._served)})"
            raise InferenceError(msg)
        if self._failure is not None:
            raise self._failure
        for event in self._rounds[index]:
            yield event

    def fail_with(self, error: InferenceError) -> None:
        """Make every later completion fail with ``error`` instead of streaming its round."""
        self._failure = error
