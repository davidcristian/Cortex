"""How long one call on a remote tool seam may take, and what an overrun is reported as.

The third bound a tool loop runs under, and the one neither of the other two is.
``tool_loop.py`` owns how many rounds a loop may take, ``tool_budget.py`` owns how much of the
outside world those rounds may touch, and both of them count. This one is time: how long a
*single* call may take before the turn stops waiting for it.

Until this, nothing in the brain said. A dispatch reached ``ToolRegistry.invoke`` and waited for
as long as the sidecar took, and the only bound anywhere on that path was whatever the MCP
client library happened to default its own transport to, which this repo neither sets nor states.
The MCP session's own wait for a response is unbounded by construction (``read_timeout_seconds``
defaults to ``None``, which is ``anyio.fail_after(None)``), so a sidecar that accepts a call and
never answers holds the turn open for as long as the process lives. A wedged sidecar is therefore
worse handled than a dead one, which is the wrong way round: a sidecar that is *down* has been
served around since the degraded-mode addendum, because ``SkipUnavailableToolRegistry`` catches a
``ToolError`` and a dial that fails raises one, while a sidecar that is merely *hung* raises
nothing at all and so defeats that whole design.

``BoundedToolRegistry`` is that missing bound, expressed the way every other property of a tool
set here is: a port-preserving combinator the composition root composes, rather than a policy
inside one adapter. Two things follow from it being a wrapper rather than an adapter feature.
The root can put it around the **remote** registries only, which matters because the built-ins
beside them are deliberately slow (a delegated batch runs for minutes under its own bound, and an
escalate card waits on a human), so a bound that covered them would cut exactly the calls that
are supposed to take a while. And a second remote adapter later inherits the bound by being
wrapped, without knowing it exists.

**An overrun is a ``ToolError``, which is the port's word for a call that did not happen.** The
dispatcher already turns one into an ``is_error`` result the model reads and audits it like any
other dispatch, so the turn continues with the model told what failed, and the durable record of
the overrun is the audit line that dispatch was always going to write. Nothing here logs: a
second line would say the same thing at a different place.

**The caller's own remaining time does not travel here, deliberately.** Three things dispatch
tools: a ``Converse`` turn, a subagent's run inside one, and the schedule ticker. The turn
announces no deadline at all (ADR-0024), so there is nothing for a call to inherit and reading one
would be the first half of enforcing a bound that seam deliberately does not have; the ticker has
none either. A subagent's run does hold one, and it already covers the dispatches its loop makes,
from outside and without this: ``PlacedAttempt`` wraps the whole run. So the bound here belongs to
the deployment, like the control seam's (``CORTEX_MODELHOST_TIMEOUT_S``) and the body seam's
(``CORTEX_BODY_CALL_TIMEOUT_S``) before it.
"""

import asyncio
from collections.abc import Sequence

from cortex_core.errors import ToolError
from cortex_core.ports import ToolRegistry
from cortex_core.tools import ToolCall, ToolResult, ToolSpec

# How long one call on a remote tool seam may take before the caller stops waiting, in seconds.
# Far past a healthy call and far short of forever: the shipped filesystem sidecar answers a
# fresh-session `invoke` in 154 ms and a listing in 146 ms (measured 2026-08-08, the table in
# docs/runbooks/tools-mcp.md), so this is some four hundred times the slowest call this
# deployment has ever timed, which leaves room for a mailbox search nobody here has measured.
# It bounds a *call* and not a turn, and the difference is worth stating because it is easy to
# read the other way. A loop lists its tools once before its rounds and dispatches inside them,
# and each of those reaches this bound separately, so a single wedged sidecar costs a cortex
# loop's first dispatch twice this number and a subagent's three times it, the extra walk being
# the live one `UngatedToolRegistry` makes to strip gated names. Two spends land exactly on the
# confirm card's own wait rather than under it, so this number is not a ceiling on what a wedge
# can cost a turn. What it buys is that the wedge ends in an error the model reads, instead of
# in a turn nobody can end.
DEFAULT_TOOL_CALL_TIMEOUT_S = 60.0

# What an overrun tells the model, which is the same sentence the audit line carries as its
# error. Each names the bound, because "the tool did not answer" without it reads as a tool that
# refused rather than as one this brain stopped waiting for.
LISTING_OVERRAN_MSG = "listing a tool sidecar's tools took longer than {timeout_s:g}s"
CALL_OVERRAN_MSG = "tool {name!r} did not answer within {timeout_s:g}s"


class BoundedToolRegistry:
    """A ``ToolRegistry`` whose every call gives up after ``timeout_s`` (ADR-0009 bound addendum).

    Both verbs are bounded by the one number, because both reach the same sidecar over the same
    session and a listing that hangs strands a turn before any call is made. A non-positive bound
    is refused at construction: zero would refuse every call before it started and a negative one
    is not a duration, and both are silent holes rather than visible failures, the shape
    ``FilteredToolRegistry`` and ``GatedToolRegistry`` already reject their own empty sets for.

    The bound is ``asyncio.timeout``, so an overrun **cancels** the inner call rather than
    abandoning it: the per-call MCP session is opened and closed inside the caller's own task
    (``streamable_http_session``), which is what makes the cancellation unwind cleanly instead of
    leaving a task holding a socket nobody will read.
    """

    def __init__(
        self, inner: ToolRegistry, *, timeout_s: float = DEFAULT_TOOL_CALL_TIMEOUT_S
    ) -> None:
        if timeout_s <= 0:
            msg = f"BoundedToolRegistry needs a positive bound, got {timeout_s}"
            raise ValueError(msg)
        self._inner = inner
        self._timeout_s = timeout_s

    async def describe_tools(self) -> Sequence[ToolSpec]:
        """The inner registry's tools; a listing that outruns the bound raises ``ToolError``."""
        bound = asyncio.timeout(self._timeout_s)
        try:
            async with bound:
                return await self._inner.describe_tools()
        except TimeoutError as err:
            if not bound.expired():
                raise
            msg = LISTING_OVERRAN_MSG.format(timeout_s=self._timeout_s)
            raise ToolError(msg) from err

    async def invoke(self, call: ToolCall) -> ToolResult:
        """Delegate one call; one that outruns the bound is cancelled and raises ``ToolError``.

        Only this object's own expiry is reported as this object's bound. A ``TimeoutError``
        raised anywhere beneath it (a socket giving up, a tool that answers with one) is the
        sidecar failing rather than the brain giving up on it, and relabelling it would name a
        bound that had not fired, the distinction ``PlacedAttempt`` draws for the same reason.
        """
        bound = asyncio.timeout(self._timeout_s)
        try:
            async with bound:
                return await self._inner.invoke(call)
        except TimeoutError as err:
            if not bound.expired():
                raise
            msg = CALL_OVERRAN_MSG.format(name=call.name, timeout_s=self._timeout_s)
            raise ToolError(msg) from err
