"""Offer the screen only while the model that would read it can see (ADR-0029).

``capture_screen`` is worth advertising only when two things are true at once: a body can take
the picture, and the model serving this tier can read one. The first is settled at composition
(no body, no tool). The second is a property of a **process** that the brain does not own and
can restart under it, so it cannot be settled once: the model host recreates a
``llama-server`` child with whatever argv its own boot gave it, and a deployment that drops the
projector leaves a model that answers text and rejects pictures. Measured 2026-08-06: a
projector-less recreate of the sidecar flips ``GET /props`` from ``vision: true`` to
``vision: false`` under a brain that is never restarted and never asks again.

So the answer is re-read rather than remembered, and it is read at both places it can be wrong:

- ``describe_tools`` drops the spec, so a model that cannot see is not offered eyes;
- ``invoke`` refuses the call, which is the one that matters. A turn lists its tools once and
  then runs several rounds against them, so the advertisement is always a little older than the
  call it authorizes; refusing here is what makes it impossible to blit a screen, fire the
  host's receipt and taint the turn for an image that will come back as an HTTP 500.

The direction of failure is the whole design. Advertising a capability the model lacks spends
the **user's** privacy on nothing; withholding one it has costs a capability the next turn can
still ask for. So an unknown answer is no vision, at both points, and the port owes that: a
``VisionProbe`` answers ``False`` when it cannot find out, and never raises.

Nothing here is cached, which is what makes the guarantee a guarantee rather than a bound on
how stale it can be. The probe costs one ``GET /props`` on the loopback network (measured at
1.5 ms idle and 1.7 ms with a generation in flight, worst of 40 samples 2.5 ms), against a
capture that blits and encodes a whole display, so freshness is bought at a price that does not
register. It also keeps the one hard rule trivially: there is no state here to survive a swap.
"""

from collections.abc import Sequence
from typing import Protocol

from cortex_core.errors import ToolNotFoundError
from cortex_core.ports import ToolRegistry
from cortex_core.screen_tool import CAPTURE_SCREEN_TOOL_NAME
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

# What the model reads when it calls the screen and the model serving cannot read pictures. It
# names the reason rather than saying "unknown tool", because the tool is not unknown: it exists
# and is useless right now, and a model told that can answer from what it already has.
BLIND_MSG = (
    f"{CAPTURE_SCREEN_TOOL_NAME!r} is unavailable: the model now serving cannot read images, so "
    "the screen was not read"
)


class VisionProbe(Protocol):
    """Whether the model serving this tier right now can read a picture (ADR-0029).

    ``can_see`` is asked once per advertisement and once per call, so an implementation answers
    from the world rather than from a remembered verdict: the whole point of the port is that
    the process it describes can be replaced without telling anyone.

    It **never raises and never blocks unboundedly**. A server that cannot be reached, answers
    an error, or answers something this version does not understand is ``False``, because the
    cost of the two mistakes is not symmetric: a wrong ``True`` spends a screen read, a
    notification and a tainted turn on an image nothing can read, while a wrong ``False`` costs
    one turn's worth of a capability that comes back the moment the server does.
    """

    async def can_see(self) -> bool: ...


class SightedToolRegistry:
    """A ``ToolRegistry`` offering ``capture_screen`` only while the serving model can see.

    A port-preserving combinator like the ones in ``aggregate.py``, and the same "restrict, never
    add" shape: it can hide and refuse the one tool, and it touches nothing else. The probe is
    consulted only when the capture tool is actually in play, so a registry that never carried it
    (the deep tier's, a body-less deployment's) costs nothing at all.
    """

    def __init__(self, inner: ToolRegistry, probe: VisionProbe) -> None:
        self._inner = inner
        self._probe = probe

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools, minus the screen when the model cannot read one."""
        specs = await self._inner.describe_tools()
        if not any(spec.name == CAPTURE_SCREEN_TOOL_NAME for spec in specs):
            return specs
        if await self._probe.can_see():
            return specs
        return tuple(spec for spec in specs if spec.name != CAPTURE_SCREEN_TOOL_NAME)

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate every other call; refuse a capture the serving model could not read.

        Refused **before** the inner registry is reached, so the body is never asked and no
        pixels are read. The refusal crosses as ``ToolNotFoundError`` like every other
        registry-level refusal in the core, which the dispatcher audits and hands back as an
        error result the model can act on.
        """
        if call.name == CAPTURE_SCREEN_TOOL_NAME and not await self._probe.can_see():
            raise ToolNotFoundError(BLIND_MSG)
        return await self._inner.invoke(call)
