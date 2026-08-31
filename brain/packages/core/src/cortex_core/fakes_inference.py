"""The ``InferenceBackend`` twin that reports a decode cadence, and how it is scripted.

Its own module rather than a corner of ``fakes.py``, which sits near the line cap, following the
``fakes_body`` / ``fakes_model_host`` / ``fakes_vision`` precedent.

``EchoInferenceBackend`` cannot serve this role for the cadence and deliberately is not taught to.
It is shipped wiring rather than a test stub: a GPU-less deployment really runs it, and a
fabricated rate coming out of it would be a made-up number in a real log, on the one path whose
whole purpose is telling a real number from a plausible one. An echo has no server, so it has no
timings, and reporting none is the truthful answer for it.

That argument stops at the stop reason, which the echo does report (ADR-0005 finish-reason
addendum). The difference is where the fact comes from: a rate is a measurement only a real server
has taken, while why a completion ended is settled by the echo's own script, and a script ending
is a model ending its own turn. So it reports ``FINISHED`` truthfully and can report nothing else,
honouring no ``bounds``; what it cannot do is vary its answer, which is what this twin is for.

What this twin owes the ``InferenceBackend`` contract is the condition no method call can create:
whether the engine behind a backend reports how fast it decoded, and what it says about why the
completion ended. ``ScriptedInferenceBackend``
takes that condition as its script, the same stance ``ScriptedModelHost`` takes toward readiness
and a dying process. Its checks therefore pin that the twin honours what it was handed, while the
same checks over ``LlamaCppBackend`` are driven by a real llama-server transcript, which is where
the parsing is genuinely derived.
"""

from collections.abc import AsyncIterator, Sequence

from cortex_core.conversation import Message
from cortex_core.errors import InferenceError
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.tools import ToolSpec


class ScriptedInferenceBackend:
    """An ``InferenceBackend`` streaming the events it was scripted with, per call.

    ``rounds`` is one event list per ``stream`` call, so a tool loop's successive completions can
    each carry their own cadence (or none); the last list repeats forever, which is what makes a
    loop of unknown length scriptable. ``calls`` records every request the loop made, so a check
    can assert how many completions a phase actually ran.

    ``fail_with`` is the one thing here a script cannot say, and it is the port's only failure
    channel: a server that stops answering is a condition of the world rather than an event in a
    stream, so a twin without it cannot stand in for the adapter on the single path where the two
    have anything to disagree about. It is the same knob ``HashEmbedder`` and
    ``InMemoryBodyGateway`` carry. The attempt is still recorded before it fails, a backend that
    cannot answer having taken the request all the same.

    ``serves`` names the model ids this twin stands for, and it is the wiring rather than the
    script: with it set, an id outside it fails with ``InferenceError`` exactly as
    ``LlamaCppBackend`` does when its ``ModelManager`` will not lease one, which is what stops the
    fake being more permissive than the adapter it stands in for. ``None``, the default, is a twin
    that has been told nothing about a deployment and so answers for any id, which suits a script
    written about the events rather than about the wiring; the shared streaming list is
    driven over a twin that has been told, since a check about which ids a backend serves needs a
    backend that serves some. The refusal follows the recorded call for ``fail_with``'s reason.
    """

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
        """Yield the next scripted round; the script does not read the request.

        The one part of the request it does read is ``model``, and only against ``serves``: a twin
        told which deployment it stands for refuses an id that deployment could not have leased.
        """
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
