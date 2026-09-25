# A tainted subagent task's context goes unfenced as a system message

**Status:** open, actionable
**Area:** subagents
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-09-25

`task_messages` (`cortex_core/subagent_attempt.py`) sends a task's `context` as a `Role.SYSTEM`
message ahead of the instruction, with no fence, whether or not the task is tainted. The cortex
writes that context, and on a tainted turn it can quote what the turn read, so an injection in it
reaches the subagent as a system message, the role that holds its instructions. A subagent with no
tools gets no security preamble; one with tools gets `SECURITY_PREAMBLE`, which names only text
between the untrusted markers as data, and this context has no markers. On the request of a
subagent with no tools, the pick obeys an injection in 29 of 75 constrained draws
([subagent CPU rows](../../readings/subagent-cpu-rows.md#the-constrained-reply-path)).

The reply itself comes back tainted and fenced (ADR-0013 decision 3), and the spawning turn stays
tainted, so the confirmation rule still stops an outbound action. What an obeyed injection can
still change is the text the cortex reads back.

**What would be measured.** Two variants beside `constrained` in
`measurements/cpu2-2026-09-25/constrained_rows.py`, both constrained and built in its `request()`
in place of `task_messages`:

- `user-role`: the context as a `Role.USER` message ahead of the instruction, with no fence and no
  preamble.
- `fenced`: `SECURITY_PREAMBLE` as the system message, as a tainted cortex turn gets it, and the
  context inside `wrap_untrusted(context, nonce=new_nonce())` (`cortex_core/untrusted.py`) as a
  user message ahead of the instruction. The preamble comes with the fence because it is what
  names the fenced text as data. `PLAIN_SECURITY_PREAMBLE` would not do: it names the user's
  messages as the ones that direct the model, and the fenced context is one.

Drawn on the pick at the constrained row's depth, 80 draws per variant. Against 29 of 75, a count
of 18 or fewer reads apart below it at a two-sided Fisher p under 0.05; the slot that draws writes
its own depth and deciding count down before the first draw. A variant that reads apart becomes
`task_messages`'s framing for a tainted task, a test over the real core types, and a sentence in
ADR-0013; if neither does, the task closes `declined` with the counts.

## History

- 2026-09-25: opened by
  [R-715](715-the-subagent-pick-obeys-framed-injections-as-often-as-the-qwen-candidates.md), whose
  constrained reply path rows send a tainted task's context as a system message.
