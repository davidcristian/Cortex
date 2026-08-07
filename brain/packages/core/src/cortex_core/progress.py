"""ProgressSink: a side channel for ephemeral progress a suspended turn cannot yield (ADR-0010).

While a spawned subagent runs, the cortex turn's engine generator is suspended inside the tool
dispatch (``await dispatcher.dispatch(...)`` in ``tool_loop.py``), so it cannot yield a
``TurnEvent`` of its own. A subagent's progress (the batch's scale, each subagent's audited tool
steps) rides this sink instead, straight onto the ``Converse`` output queue, interleaved with the
turn's own events but never through the suspended generator. The real adapter is the
orchestrator's ``SeamProgressSink``, bound to one stream's queue; a caller with no stream (the
schedule ticker, a direct test) hands ``None`` and progress goes nowhere.

The sink is handed to a call on the dispatch ``TurnStamp`` (like the shared ``budget``), never
held as state on the ``SpawnSubagentsTool`` singleton, so one shared tool serves every stream
without a per-stream field to leak across turns: per-stream isolation is the stamp's, freshly
built per dispatch. Nothing is persisted and nothing survives the turn, so the one hard rule
holds by the sink carrying no state at all.

Only registry-authored (a ``ToolStep``'s spec fields) or brain-authored (a subtask count) text
ever rides it, exactly as the cortex's own ``ToolActivity`` is registry-authored (ADR-0009
addendum): nothing the model chose or untrusted content produced. So a tainted subagent's
progress carries no untrusted-derived text and needs no guardrail pass, the same argument the
activity chip already makes.
"""

from typing import Protocol

from cortex_core.events import StatusUpdate, ToolActivity

# The two ephemeral event kinds a sink carries: an audited tool step surfaced as activity, and a
# brain-authored progress line as status. Never a ``TextDelta`` (progress is not reply text) nor a
# ``TurnCompleted`` (a turn ends through its own generator, not this side channel).
#
# And deliberately never a ``ToolOutcome`` (ADR-0029 delegated-pairing addendum), which is why a
# delegated step is announced here and never settled. Three reasons, none of them cost: the one
# consumer of an outcome reads a single tool name (``capture_screen``) and that tool is a built-in
# the subagent dispatcher is never handed, so every forwarded outcome would be discarded by
# construction rather than by accident; a subagent's tools are the ungated subset, so no delegated
# step carries a consent decision for a surface to report; and ``emit`` below drops on a saturated
# buffer while the turn's own events block for a credit, so a pairing promised across this channel
# would still not be one. The widening is two lines and waits for a surface that renders how a
# delegated step ended.
type ProgressEvent = ToolActivity | StatusUpdate


class ProgressSink(Protocol):
    """Emit one ephemeral progress event onto the turn's stream from outside its generator.

    ``emit`` is non-blocking and best-effort: it returns having either queued the event or dropped
    it (a saturated consumer), never having suspended the caller on backpressure, so a slow
    overlay delays cosmetic progress rather than the real delegated work. Nothing is persisted.
    """

    async def emit(self, event: ProgressEvent) -> None: ...
