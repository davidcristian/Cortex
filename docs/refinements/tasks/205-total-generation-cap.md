# A total generation cap

**Status:** landed 2026-08-11
**Area:** resource-governance
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

This is a fix-when-it-bites entry closed before
it bit, which is established practice here when the fix is cheap and provable, and it is worth
saying plainly why it was cheap. What kept the entry closed was never the mechanism, both halves
of which the entry had already priced down to nothing; it was the guess about how long a
legitimate answer runs. That is not a guess on this machine, it is an afternoon: five subtask
shapes on the shipped CPU entry, from a one-word lookup to an open-ended essay, measured for
decoded tokens and wall clock, with the cap set at roughly five times the longest narrow reply and
the deadline at four times the longest whole subtask, the extra doubling covering a tool-using
run whose loop spends on several rounds what the measurement spent on one completion. The trigger asked for one observed runaway to size
the bound from; what the measurements give instead is the other end, the longest run that must
**not** be cut, which is the end a cap is actually sized against.
The entry read: "*Fix when it bites.* Opened
2026-08-09 by the close above, whose ceiling cannot see this: a stall detector fires on silence,
and a model in a repetition loop is never silent. Nothing in the shipped wiring bounds a
delegated generation's length (`n_predict: -1`, no `max_tokens` on the subagent path), so a
runaway subagent holds its admission and its entry's lease exactly as the wedged stream used to,
and at the CPU tier's 0.35 tok/s it can do so for a very long time while looking healthy the
whole way. **The trigger is the first delegated run observed running away**, which nothing has
seen yet; that it has not been seen is why this is recorded rather than built, since a cap set
without one measured runaway would be a guess about how long a legitimate answer is, and the
cost of guessing low is a truncated reply on every long subtask. Two shapes, and only one of
them is cheap: a **token** cap is expressible today, `GenerationBounds.max_tokens` already
riding the `InferenceBackend` port and already used by the recap fold, so it is a value threaded
from `SubagentsConfig` through the runner; a **wall-clock** cap is not, needing the same timeout
design as the bounded admission wait above, and it is the one that would
actually bound the pool's worst case, a token budget on a 0.35 tok/s tier still being minutes.
**That half got cheaper on 2026-08-09**, hours after this entry was written, when the wait it
points at landed: the design turned out to be `asyncio.timeout` around the wait rather than the
injected `Clock` this entry priced it at (a duration belongs on the loop's monotonic clock, and
the `Clock`/`Sleeper` pair exists for poll loops), so the wall-clock cap is the same wrapper
around the attempt's stream consumption and needs no port to carry a deadline. What did not get
cheaper is the number, which is still the guess about how long a legitimate answer runs that
keeps this entry closed.
Its origin decision is the [ADR-0005 stall-ceiling addendum](../../adr/ADR-0005-llamacpp-engine.md),
which declined it deliberately: converting an unbounded wait into a bounded reported failure is
a transport concern, while capping how much a model may say is a policy about answers, and
mixing the two would have shipped an unmeasured number inside a fix that needed none."
Every word of the defect held, and the reproduction is the reason the fix is not a description of
one: a backend yielding a text chunk forever, through the shipped runner, streamed **3,099,896
chunks in 5 s**, never returned, and persisted no result, holding its admission and its VRAM
placement throughout. One word of the *fix* did not hold, and it is the one an entry is most
likely to get wrong: "expressible today" was true of the port and false of the path. The
`InferenceBackend.stream` signature really does carry `GenerationBounds`, but `ToolLoopContext`
had no `bounds` field and `stream_tool_loop` passed none, so the only route a subagent reaches
that port by could not carry a cap. One field of loop vocabulary fixed it and the port is
untouched, which is this area's blanket "behind the unchanged port" coming out true for once,
though not for the reason the entry gave.
What landed is `AttemptBounds(max_tokens, timeout_s)` on the runner: the cap rides every
completion an attempt asks for, and the deadline is `asyncio.timeout` around the whole
consumption, so it covers the tool dispatches between completions as well, which is the unit that
actually holds an admission. Reaching the deadline is `AttemptFailure.TRUNCATED`, an `ok=False`
result naming the bound, and it is deliberately **not** re-placed on the CPU, for the reason a
malformed reply is not: a model still talking at its deadline was answering, and the slower tier
is the last place to send it. Two things the entry could not have known, both settled here rather
than left implicit: the deadline is armed **per attempt** rather than per task, since a re-run
handed the remains of a spent one would be refused before it began, and it must sit **above** the
pool's stall ceiling, which `SubagentsConfig` now refuses to start without, because a deadline
under the ceiling would report every wedged stream as a runaway and silently delete the CPU
re-run scheduled for exactly that failure.
Two residues are recorded rather than folded in: the finish reason a capped completion carries is
still not distinguishable through the port (below, in this file's open set), and the "200 to
300 s whole subtask" the admission wait's own derivation rests on is an underestimate by a factor
of two for a summarization, which these measurements are the first to say.

## Trail

- 2026-08-09: Opened by the stall ceiling's close, whose per-read ceiling cannot see a model in a
  repetition loop, and declined at the
  [ADR-0005 stall-ceiling addendum](../../adr/ADR-0005-llamacpp-engine.md), where converting an
  unbounded wait into a bounded reported failure was called a transport concern while capping how
  much a model may say is a policy about answers.
- 2026-08-09: Its wall-clock half got cheaper hours later, when the bounded admission wait landed on
  `asyncio.timeout` rather than on the injected `Clock` this entry had priced it at.
- 2026-08-11: Landed ahead of its trigger, recorded at the
  [ADR-0005 total-cap addendum](../../adr/ADR-0005-llamacpp-engine.md), which is also where its decline
  was recorded: `AttemptBounds(max_tokens, timeout_s)` on the runner, a cap of 1024 tokens at
  roughly five times the longest narrow reply and a deadline of 2400 s at four times the longest
  whole subtask, which also lands the deadline between the pool's stall ceiling and its admission
  wait, so a run can never hold its admission longer than a peer is willing to queue for it. Two
  entries opened in its place.
