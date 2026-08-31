"""The ``VisionProbe`` twin: a scripted answer sequence, plus a count of the calls made.

Its own module rather than a corner of ``fakes.py``, which sits near the line cap, following the
``fakes_body`` / ``fakes_model_host`` precedent.

A sequence rather than one boolean, because the condition this port exists for is one that changes
between two calls: the tool set is advertised, the server is replaced, the model calls the screen.
Scripting ``[True, False]`` reproduces that in a test, and the count is how a test proves an
implementation asked again instead of reusing an earlier answer.
"""

from collections.abc import Sequence


class ScriptedVisionProbe:
    """A ``VisionProbe`` answering ``answers`` in order, the last one repeating forever."""

    def __init__(self, answers: Sequence[bool] = ()) -> None:
        self._answers = list(answers) or [True]
        self._next = 0
        self.asked = 0

    async def can_see(self) -> bool:
        """The next scripted answer; each call adds one to the tally."""
        self.asked += 1
        answer = self._answers[min(self._next, len(self._answers) - 1)]
        self._next += 1
        return answer

    def rescript(self, answers: Sequence[bool]) -> None:
        """Replace the script from here on, which is how a test changes the answer mid-run.

        The tally is cumulative across rescripts on purpose: it counts calls made, and a rescript
        is used to check that the next call really was made.
        """
        self._answers = list(answers) or [True]
        self._next = 0
