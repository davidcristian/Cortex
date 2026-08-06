"""The ``VisionProbe`` twin: a scripted answer sequence, and a count of who asked."""

from collections.abc import Sequence


class ScriptedVisionProbe:
    """A ``VisionProbe`` answering ``answers`` in order, the last one repeating forever."""

    def __init__(self, answers: Sequence[bool] = ()) -> None:
        self._answers = list(answers) or [True]
        self._next = 0
        self.asked = 0

    async def can_see(self) -> bool:
        """The next scripted answer, and one more on the tally."""
        self.asked += 1
        answer = self._answers[min(self._next, len(self._answers) - 1)]
        self._next += 1
        return answer

    def rescript(self, answers: Sequence[bool]) -> None:
        """Replace the script from here on, which is how a test changes the world mid-run.

        The tally is cumulative across rescripts on purpose: it counts questions asked, and the
        whole point of a rescript is to check that the next question really was asked.
        """
        self._answers = list(answers) or [True]
        self._next = 0
