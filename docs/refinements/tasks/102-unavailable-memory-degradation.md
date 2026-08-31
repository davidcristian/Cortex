# A dead embedder or store kills the turn

**Status:** landed 2026-08-11
**Area:** memory
**Origin:** [ADR-0008](../../adr/ADR-0008-memory-v1.md)

The port documents one
failure channel, `EmbedderError`, and the pgvector adapter documents `MemoryStoreError` beside
it, and writing the shared checks turned up the fact that **nothing in the brain catches
either**. `recall_memory_context` (`turn_context.py`) awaits `caps.memory.recall(...)` bare,
`MemoryRecaller.recall` awaits `embed` bare, and the engine's only handler is for
`InferenceError`, so an embedding server that is down or a Postgres that is unreachable does not
cost a turn its recalled notes, it fails the turn. That is the opposite bias from every other
optional capability here: a dead tool sidecar is served around and reported
(`SkipUnavailableToolRegistry`), a body that will not answer becomes a recoverable tool result,
a subagent that cannot be admitted degrades to an `ok=False` result. Memory is the one that
takes the whole turn down with it, and it is the capability a turn most obviously has an answer
without.
**What it is not is a hole in the checks.** The shared list holds both implementations to
raising `EmbedderError` rather than their own backend's exception, which is what makes a single
catch possible at all; what is missing is the catch. The fix is a decision rather than a line:
where it belongs (`recall_memory_context`, which already answers `None` for memory being
switched off, so a failure reading as "no memories this turn" needs no new shape), whether the
user is told (a turn that forgets without saying so is its own kind of wrong, and the
degraded-mode precedent reports rather than hides), and whether a write failing is the same call as a read
failing (`remember` losing an exchange is a durability question, not a context one).
**Trigger:** the first live turn taken against a stopped embedding server or a stopped Postgres,
which the memory runbook's own teardown step makes easy to hit by accident, or the degraded-mode
question being answered for any other optional capability.
**Closed 2026-08-11**, hours after it opened and **ahead of its trigger, neither arm of which
fired**: no live turn had been taken against a stopped server, and no other optional capability
had had its degraded-mode question reopened. It was taken because the entry's only blocker was
the decision it named, and the decision was available. The defect was re-derived by running
rather than by reading, as this file's own standing warning demands: a `TurnEngine` over the
in-memory session store with a `HashEmbedder` told to `fail_with` answered `TURN FAILED with
EmbedderError` where the same turn with a live embedder answered in four events, so the entry's
account was still exact. Two of its own guesses were tested against the tree and both held, the
method name being `_recalled_context` rather than `recall_memory_context`. What landed is in the
[ADR-0008](../../adr/ADR-0008-memory-v1.md) unavailable-memory addendum: `EmbedderError` and
`MemoryStoreError` degrade on both halves and nothing else does, the read in `_recalled_context`
and the write in `record_exchange`, which are also the two functions `BrainPhase` shares with
`TurnEngine`, so the deep model's phase degrades identically with no second copy. The entry's
hardest question, whether a failed write is the same call as a failed read, resolved to **both
degrade for opposite reasons**: the read because the turn genuinely has an answer without its
notes, the write because **raising cannot save it**, the reply having streamed and the assistant
message being persisted before `record_exchange` runs, so an exception there loses the memory
just the same and takes a turn the user has read with it. The exchange is not the thing lost
either, staying in the conversation the user can scroll to; what is lost is a derived index
entry, which is why the write logs an `error` and the read a `warning`. On being told, the entry
guessed right that the precedent reports rather than hides, and the report is unconditional on
the module logger rather than a line on the opt-in recall trail, since an outage visible only where
`CORTEX_MEMORY_RECALL_AUDIT` is on would be the same silence rather than a cure. The trail gains an
omission instead: no line is written for a recall that never happened, so `pool == available`
goes on meaning the pool was the whole readable store rather than acquiring a `0 == 0` reading
for a store nobody could reach. The user is told once, about the read only, by one app-authored
`StatusUpdate(state="forgoing")` on the channel a fold already narrates itself on, which earns
its chip where a recap lost without a signal does not because a recap compresses history the user can
still scroll to while a recalled memory is knowledge from other conversations they cannot see
and cannot supply. **Two opened in its place**, both residue of this close rather than found
beside it, and they are the next two entries here.

## Trail

- 2026-08-11: Opened by the `Embedder` port's shared check list, which established that both
  implementations raise `EmbedderError` and nothing else and then that nothing in the brain catches
  it or the store's error either. It was filed rather than taken because the remedy was a decision,
  and it was filed fix when it bites. Filing it took the area to 8, and it moved the index cell and
  not the area header, which went on reading 7 for the hours the entry was open.
- 2026-08-11: Closed the same day, hours after it opened and ahead of a trigger neither arm of which
  fired, taking the area back to 7 and then to 9 on the two entries it opened in its place, both
  residue of the close rather than anything found beside it. The defect was re-derived by running
  rather than by reading: a `TurnEngine` over the in-memory session store with a `HashEmbedder` told
  to `fail_with` answered `TURN FAILED with EmbedderError` where the same turn with a live embedder
  answered in four events.
- 2026-08-11: The index states the boundary the close drew and the placement it refused: what
  degrades is the adapters' own wrapping and nothing else, so a policy's `ValueError` still fails
  the turn, and the catch went into the two core functions rather than into an adapter that also
  serves the delete cascade.
