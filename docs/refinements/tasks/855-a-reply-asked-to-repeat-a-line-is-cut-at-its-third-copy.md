# A reply asked to repeat a line is cut at its third copy

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)
**Verified:** 2026-10-14

The repeated line check (decision 17) cannot tell a loop from a repetition the person asked for.
On the test stack on 2026-10-14 the message "Without using any tool, write the sentence 'Remember
to bring your sheet music to practice.' five times, one per line, and nothing else." got three
copies and `REPEATED_LINE_NOTE`. A song whose chorus comes back three times, or a list whose
entries share one line, ends the same way.

## Reproduce

Send that message in a new chat on the GPU stack with the current brain. The twelve-month format
control of [reply loop](../../readings/reply-loop.md#the-rig) still passes, because its lines
differ.

## What to do

Read off the fourth rule's 22 looping baseline draws, a check that needs more arrivals costs little:
it stops all 22 at 213 to 512 words after the prefill at 3 arrivals, 243 to 552 at 8, and stops
none of the other 18 at either. Two candidates, alone or together: a higher arrival count, and
leaving out a line the person's own message contains, which `stream_turn_events` would need the
query for. Write a rule into the readings first: the 40 baseline rig draws read again, plus live
turns that ask for a line 5 and 10 times and for a song with a three times chorus, drawn before the
candidate is built. Ship only on a pass.

## History

- 2026-10-14: filed when the repeated line check shipped; a live turn asking for five copies of one
  line was cut at the third.
