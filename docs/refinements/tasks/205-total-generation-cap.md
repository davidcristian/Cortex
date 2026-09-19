# A total generation cap

**Status:** done 2026-08-11
**Area:** resource-governance
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

The stall ceiling cannot see this: a stall detector fires on silence, and a model in a repetition
loop is never silent. Nothing in the shipped wiring bounded a delegated generation's length
(`n_predict: -1`, no `max_tokens` on the subagent path), so a runaway subagent held its admission and
its roster entry's lease exactly as the wedged stream used to, and at the CPU tier's 0.35 tok/s it
could do so for a very long time while looking healthy. Reproduced through the shipped runner: a
backend yielding a text chunk forever streamed 3,099,896 chunks in 5 s, never returned, and stored no
result, holding its admission and its VRAM placement throughout.

What blocked the fix was never the mechanism but the guess about how long a legitimate answer runs.
That became a measurement: five subtask shapes on the shipped CPU entry, from a one-word lookup to an
open-ended essay, measured for decoded tokens and wall clock. The cap is 1024 tokens, roughly five
times the longest narrow reply, and the deadline is 2400 s, four times the longest whole subtask,
the extra doubling covering a tool-using run whose loop spends on several rounds what the measurement
spent on one completion. The entry's trigger asked for one observed runaway to size the bound from;
the measurements give the other end instead, the longest run that must not be cut, which is the end a
cap is actually sized against.

One word of the proposed fix did not hold: "expressible today" was true of the port and false of the
path. `InferenceBackend.stream` does take `GenerationBounds`, but `ToolLoopContext` had no `bounds`
field and `stream_tool_loop` passed none, so the only route a subagent reaches that port by could not
pass a cap through. One field fixed it and the port is untouched.

What shipped is `AttemptBounds(max_tokens, timeout_s)` on the runner: the cap applies to every
completion an attempt asks for, and the deadline is `asyncio.timeout` around the whole consumption,
so it covers the tool dispatches between completions as well, which is the unit that actually holds
an admission. Reaching the deadline is `AttemptFailure.TRUNCATED`, an `ok=False` result naming the
bound, and it is deliberately not re-run on the CPU, for the reason a malformed reply is not: a model
still talking at its deadline was answering.

Two things the entry could not have known, settled here rather than left implicit. The deadline is
set per attempt rather than per task, since a re-run handed the remains of a spent one would be
refused before it began. And it must sit above the pool's stall ceiling, which `SubagentsConfig` now
refuses to start without, because a deadline under the ceiling would report every wedged stream as a
runaway and silently remove the CPU re-run scheduled for exactly that failure.

Two residues are recorded rather than folded in: the finish reason a capped completion has is still
not distinguishable through the port, and the "200 to 300 s whole subtask" the admission wait's
derivation rests on is an underestimate by a factor of two for a summarization.

## History

- 2026-08-09: Opened by the stall ceiling's close and declined at
  [ADR-0005 decision 7](../../adr/ADR-0005-llamacpp-engine.md), where converting an unbounded wait
  into a bounded reported failure was called a transport concern while capping how much a model may
  say is a policy about answers.
- 2026-08-09: The wall-clock half got cheaper hours later, when the bounded admission wait shipped on
  `asyncio.timeout` rather than on the injected `Clock` this entry had priced it at.
- 2026-08-11: Closed ahead of its trigger, recorded at
  [ADR-0048](../../adr/ADR-0048-generation-bounds.md). The deadline sits between the pool's stall
  ceiling and its admission wait, so a run can never hold its admission longer than a peer is willing
  to queue for it. Two entries opened in its place.
