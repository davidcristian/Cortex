# The trail's logger name is spelled in three places and held in none

**Status:** landed 2026-08-28
**Area:** repo-gates
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
- 2026-08-28: **landed**, as the [ADR-0038 named-logger
  addendum](../../adr/ADR-0038-ranked-recall.md) and an entry in `scripts/trailcouplings.py`, a new
  registry part the split took: the logger brought `logcouplings.py` past the line cap, so the
  recall trail's three words moved into a part of their own, on the seam that file's docstring had
  drawn between one word across the brain and one line on one stream. The sink declares
  `_LOGGER_NAME` and the two runbooks and the module contract hold the mentions.
  **Both halves of this entry's account were stale.** The reopen trigger named a third document
  telling an operator to select the trail by logger name, and `docs/modules/brain-memory.md` had
  been that document since the trail landed, three weeks before the entry was written: the
  condition to revisit was met before the entry existed. And a rename was never green everywhere.
  Nine of the memory package's forty checks read a line back through `caplog` under this
  name, so the rename is loud in the tree that writes the trail and silent in the three documents
  that read it, which is what
  makes leaving the documents behind plausible: the suite goes green again the moment the tests
  move onto the new name. The `samplecheck.py` alternative the entry asked to weigh first was
  measured and declined, because finding a logger name in a document by its shape also finds
  `cortex.seam.v1` and `cortex.dump`, and reaching the module-path loggers two runbooks name would
  reach every module reference in every module contract. `scripts/logcalls.py` learned the third
  spelling of a logger claim in the same slice, so the trail does not drop out of the sample gate's
  answer the day it gains a declaration. Opened by this close:
  [R-486](486-the-tool-audits-logger-name-is-spelled-in-four-places-and-held-in-none.md).
