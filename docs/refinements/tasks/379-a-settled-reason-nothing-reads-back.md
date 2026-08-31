# A settled handoff's reason is written twice and read back by nothing

**Status:** open, fix when it bites
**Area:** inference-model-manager
**Origin:** [ADR-0030](../../adr/ADR-0030-brain-handoff.md)
**Trigger:** a failed handoff whose reason nobody found in time, or any surface that starts
carrying handoff history.

Opened 2026-08-22 by the close of
[R-350](350-a-failed-swap-in-says-nothing-brain-side.md), which gave a failed handoff a reason and
put it in the two places that outlive different things: one `WARNING` in the brain's log, and the
`failure` field on the record in Redis.

Neither is a surface anybody is looking at. The log line is found by an operator who is already
tailing the brain, or who knows the sentence to grep for; the record is found by somebody who
knows the key layout and asks Redis inside the diagnosis hour the adapter's TTL keeps a terminal
record for. Nothing in the tree reads `failure` back: the seam's residency report does not carry
it, the overlay never sees it, boot recovery does not read it, and no code path branches on it.
It is written for a human who has to know it is there.

That is defensible, and it is also the same gap the spill note closed for a related problem. A
handoff that decoded below its floor used to say so only in the brain's log, and the spill-note
addendum decided that was not a surface, so the verdict now travels on the residency report for an
hour and reaches an operator who is not tailing a container. A failed handoff's reason is the same
kind of fact one step further along: something about the last handoff, true for a bounded while,
that an operator would want without being told where to look.

**What is not the same, and is the argument against.** The user has already been told, in the
reply, what is true of their machine, and a failure they were told about does not obviously owe a
second telling on a health surface. A spill is the opposite case: nobody was told anything,
because the answer arrived and only its rate was wrong. So this may be right as it stands.

**What would close it.** Decide, rather than leaving it implied by the close that created it:
either put the last failed handoff's reason on a surface that reaches somebody (the residency
report is the precedent, with the same standing-and-lapsing rule), or record that the log line
plus the runbook's Redis recipe is deliberately the whole of it, and say why the spill note's
argument does not carry across. One paragraph either way; the field and its two writes stay.

## Trail

- 2026-08-22: opened by the close of
  [R-350](350-a-failed-swap-in-says-nothing-brain-side.md), which wrote the reason down in two
  places and found nothing that reads either of them.
