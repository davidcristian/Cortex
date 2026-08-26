# The trail's logger name is spelled in three places and held in none

**Status:** open, fix when it bites
**Area:** repo-gates
**Trigger:** the sink's logger is renamed, or a third document tells an operator to select the
trail by logger name
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

Opened 2026-08-27 by the close of
[R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), which tied the trail's message and
its widest field to the sink and deliberately left the logger alone.

`cortex.memory.recall` is written in `brain/packages/memory/src/cortex_memory/audit.py`, as the
argument of the `logging.getLogger` call, and restated in two documents:
[memory-pgvector.md](../../runbooks/memory-pgvector.md) says the trail is "one `cortex.memory.recall`
line per recall", and [local-dev-wsl.md](../../runbooks/local-dev-wsl.md) names it among the loggers
a deployment can raise or lower on its own. Rename it and both sentences instruct an operator about
a logger nothing writes through, with every gate green.

**Why it was left.** Two reasons, and the second is the real one. The registry compares a
declaration against the places restating it, and there is no declaration here: the name is a call
argument, so registering it means adding a module-private constant to the sink for the gate's
benefit, which is the shape this repo blesses reading and not creating. And the name is not one
value but the tail of another: it ends in the message the trail writes, and the needle that reached
it would either pin that resemblance, which nothing in the tree states, or pin the whole string
against a declaration that does not exist.

**What would close it.** Most likely a private `_LOGGER = "cortex.memory.recall"` in the sink, read
as a site by `logcouplings.py` with the two runbook sentences as mentions, which costs one line of
production code to buy a coupling three places wide. The alternative worth weighing first is that a
logger name is what `samplecheck.py` already resolves a documented sample's own logger against, and
the gap is only the sentences that name a logger without printing a line under it.

## Trail

- 2026-08-27: opened by the close of
  [R-454](454-the-readers-needles-are-not-tied-to-the-sink.md), whose needle for the message is
  written as the emitting call precisely so that it cannot be satisfied by this name.
