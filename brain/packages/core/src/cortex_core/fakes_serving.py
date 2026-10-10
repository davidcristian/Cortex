"""In-memory test double for the ``ServingProbe`` port."""

import asyncio


class ScriptedServingProbe:
    """A ``ServingProbe`` whose answer a test sets: ``None``, a fault, or no answer at all."""

    def __init__(self, part: str = "the scripted part", *, answer: str | None = None) -> None:
        self._part = part
        self.answer = answer
        self.silent = False
        self.calls = 0

    @property
    def part(self) -> str:
        """The part this probe asks about, as a person would name it."""
        return self._part

    async def fault(self) -> str | None:
        """Return the scripted answer, or wait forever while ``silent`` is set."""
        self.calls += 1
        if self.silent:
            await asyncio.Event().wait()
        return self.answer
