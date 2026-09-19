# Session-history summarization in turn assembly

**Status:** done 2026-08-06
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)

Compressing old turns instead of dropping them changes content, needing a model pass inside turn
assembly, so it was deferred when bounded windowing shipped. It is a different feature from memory
summarization, which is cross-session recall rather than in-context history.

An audit on 2026-07-16 priced the two costs the entry named and found both milder than written.
The `async` widening of `HistoryWindow.select` is contained: it had one production caller, already
an `async` method, so widening it adds one `await` and no caller above it changes, and the only
implementer was `CharBudgetHistoryWindow`. The GPU lease hazard is navigable:
`SingleResidentModelManager` guards a non-reentrant `asyncio.Lock` held for the whole stream
generator's lifetime, but selection runs before `handle_turn` opens the reply stream, so at
selection time the turn does not hold the lease. Verified against the real manager: a drained
acquire followed by a second acquire succeeds, while a summarizer stream held open across the
reply's acquire deadlocks. So the requirement is that the summarizer drains its own call, which
is what the title generator already does.

One stated blocker was false and was struck on 2026-07-19. It read that a summarizing window
cannot be validated on the 8 GB dev GPU because the cortex tier does not fit. It does fit:
[ADR-0029](../../adr/ADR-0029-vision-screen-capture.md) ran it there beside its vision projector
at `-ngl 99 --ctx-size 4096 --parallel 1`, and
[ADR-0030](../../adr/ADR-0030-brain-handoff.md) records the model alone using 7715 of that card's
8188 MiB.

The remaining design question, whether a summary is cached or recomputed per turn, was settled on
2026-08-06 as cache, because history is append-only. A summary lives in Redis behind
`SessionStore`, beside the messages and the title it derives from, never in `MemoryStore`, since a
summary is one conversation's working context and pgvector would make it recallable into other
conversations. It is keyed by the boundary it covers, and because `SessionStore` has `append`,
`history`, `set_title` and a whole-session delete and no verb that edits or removes a message, a
summary of a prefix can only become incomplete, never wrong: each new summary folds the previous
one together with the newly dropped turns, and a deleted session takes its summary with it.
Recompute would have cost one full cortex generation on every turn, serialized ahead of the reply
and so straight onto time to first token, against once per boundary move. The lease sequencing
became `drain_text` (`drain.py`), which leaves the adapter's acquire block in a `finally`, and
`generate_title` moved onto it in the same change.

Closed the same day. What shipped: the `SessionStore` recap verbs (`set_recap` and `recap`, a
`HistoryRecap(text, covers)` behind the port, in the fake, in the Redis adapter, under the same
shared contract suite, and removed by the whole-session delete in the same transaction), a
`SummarizingHistoryWindow` in the core, the `async` widening of `HistoryWindow.select` alongside
it, and `CORTEX_HISTORY_SUMMARY`, default off. Four things the design had not said: `select`
needed the `session_id` as well as the `async`; the value is a `Recap` rather than a `Summary`,
because `SessionSummary` already means a chat-list row; the pair belongs to `SessionStore` because
a recap is as private as the transcript and "forget this chat" must take it in the same write; and
the fallback is structural, the window being able only to prepend to the shipped window's
selection, so losing a word the user wrote is not reachable from any state of the summarizer. The
lease test had to be fixed before it meant anything: asserting the reply's acquire succeeds did
not fail when the drain was removed, because generator finalization closed the abandoned stream
first, so it now asserts the acquire block was left with no `await` in between.

Measured on the real cortex through the gpu stack, over a 23-message conversation whose opening
facts had dropped out of the window: the shipped window sent 295 characters and could not answer
"remind me of my booking reference" at all, while the recap sent 831 and answered it correctly, at
11.0 s for the pass that moved the boundary and 0.000 s for every turn after it. Time to first
token did not get worse. The default stays off, because those 11 s fall on the turn that triggers
the pass and because the corpus is one hand-built case.

## History

- 2026-07-03: Deferred when session-history windowing shipped, as a lossy model pass needing
  inference in turn assembly.
- 2026-07-16: Audited against the code and kept deferred. The `async` `select` widening is
  contained and the GPU lease hazard is navigable by the title generator's drain discipline, so
  neither was the binding blocker.
- 2026-07-19: The hardware blocker, that a model pass cannot be validated on the 8 GB dev GPU
  because the cortex tier does not fit, was struck. That card holds the cortex and a model pass
  can be judged there at 4K.
- 2026-07-19: The host page settled the same false clause per entry rather than recording it as
  stale. Its finding was that this pass was never hardware-blocked, and that the host's hardware
  would buy the same judgement at 16K with more than one slot.
- 2026-08-06: The cache question closed as cache rather than recompute, and the lease sequencing
  as the `drain_text` helper the title generator also moved onto. One claim did not hold: the
  window's caller is `assemble_inference_messages` in `turn_context.py`, not `_inference_messages`
  in `engine.py`, which no longer exists.
- 2026-08-06: Closed the same day and shipped with `CORTEX_HISTORY_SUMMARY` default off.
  `HistoryWindow.select` widened twice in the end, once for the `async` and the session id and
  once for a progress sink; splitting them was still right, because the sink had no consumer until
  a fold was slow enough to need narrating.
- 2026-08-06: It had stayed on the list of work needing the host's hardware, and left that list
  the same day by being built and measured against the real cortex in Docker.
