"""The ``InferenceBackend`` twin that reports a decode cadence, and how it is scripted.

Its own module rather than a corner of ``fakes.py``, which sits near the line cap, following the
``fakes_body`` / ``fakes_model_host`` / ``fakes_vision`` precedent.

``EchoInferenceBackend`` cannot serve this role for the **cadence** and deliberately is not taught
to. It is shipped wiring, not a test stub: a GPU-less deployment really runs it, and a fabricated
rate coming out of it would be a made-up number in a real log, on the one path whose whole purpose
is telling a real number from a plausible one. An echo has no server, so it has no timings, and
that is the honest answer for it to give.

That argument stops at the **stop reason**, and the echo reports one (ADR-0005 finish-reason
addendum). The difference is who knows the fact: a rate is a measurement only a real server has
taken, while why a completion ended is something the echo itself decided, and its script ending is
a model ending its own turn. So it says ``FINISHED`` truthfully and can say nothing else, honouring
no ``bounds``; what it still cannot do is vary its answer, which is what this twin is for.

What this twin owes the ``InferenceBackend`` contract is the world-condition no verb can create:
whether the engine behind a backend reports how fast it decoded, and what it says about why the
completion ended. ``ScriptedInferenceBackend``
takes that condition as its script, the same stance ``ScriptedModelHost`` takes toward readiness
and a dying process. Its checks therefore pin that the twin honours what it was handed, while the
same checks over ``LlamaCppBackend`` are driven by a real llama-server transcript, which is where
the parsing is genuinely derived.
"""

from collections.abc import AsyncIterator, Sequence

from cortex_core.conversation import Message
from cortex_core.inference import GenerationBounds, InferenceEvent, JsonSchema
from cortex_core.tools import ToolSpec


class ScriptedInferenceBackend:
    """An ``InferenceBackend`` streaming the events it was scripted with, per call.

    ``rounds`` is one event list per ``stream`` call, so a tool loop's successive completions can
    each carry their own cadence (or none); the last list repeats forever, which is what makes a
    loop of unknown length scriptable. ``calls`` records every request the loop made, so a check
    can assert how many completions a phase actually ran.
    """

    def __init__(self, rounds: Sequence[Sequence[InferenceEvent]] = ()) -> None:
        self._rounds = [list(events) for events in rounds] or [[]]
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
        for event in self._rounds[index]:
            yield event
