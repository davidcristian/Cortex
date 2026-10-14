# A reply that repeats one line runs to the length limit

**Status:** done 2026-10-14
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)

Nothing stops a reply that repeats itself before the length limit. In a probe row of the cut off
tool call rows ([readings](../../readings/tool-call-cut-off.md#results)), gemma 12B as the cortex
wrote "Actually, I'll try `read_text_file` again." and "Actually, I'll try `read_file`." in turn
until the reply, 3,764 words, stopped at the length limit 169 s into the turn, with the person
watching it stream and `REPLY_CAPPED_NOTE` at the end. Any loop the model falls into costs the
whole limit this way, whatever starts it; R-851 is one cause.

Nothing in the tree or the engine reads repeated text. The brain sends no sampling field and,
with `CORTEX_REPLY_MAX_TOKENS` at 0, no `max_tokens`, so the context window is the limit, about
11,000 tokens of reply on this prompt; the cortex server runs with `repeat_penalty` 1.0 and
`dry_multiplier` 0.0, both off. The loop is in the reply text, not in `reasoning_content`: the
model wrote its plan as reply text, then repeated two lines of it.

## Reproduce

The probe row above, on the current tree under `CORTEX_TOOLS_ON_UNAVAILABLE=skip`, is 1 of the 7
cut off reads drawn on 2026-10-13. A replay of its state at the engine, with its first reply
sentence as an assistant prefill, loops in 4 of 10 baseline draws, and a second rig with the
reply's first 25 lines loops in 10 of 30: both in [reply loop](../../readings/reply-loop.md).

## What to do

Write a fourth rule into [reply loop](../../readings/reply-loop.md) before drawing anything,
sized from the 14 of 40 rig draws that looped and comparing within one night: 40 baseline draws
of the second rig and 40 with `"dry_multiplier": 0.8`, plus that candidate's 20 control draws.
For example, the DRY setting ships when its loops are at most a quarter of the baseline's and its
controls pass, and the repeated line check ships when, off the 40 baseline draws, it stops every
loop but one before the token limit and stops nothing else. Ship whichever the rule names: a
check through the turn's existing note path, or a flag on the model host's cortex tier argv.

## History

- 2026-10-13: filed from the probe row of R-851, whose reply looped to the length limit.
- 2026-10-13: premise checked against the tree and the stack's cortex server: nothing ends a
  repeating reply before the context window. Wrote a replay rig's rows and pass rule into
  [reply loop](../../readings/reply-loop.md); its baseline looped 4 of 10, under the rule's 7, so
  neither candidate was judged. A second rig with a longer prefill looped 5 of 10, also under 7,
  and a third rule sized for that rate was written before its baseline, which looped 5 of 20,
  under its 6. Neither candidate is judged; the next step is a fourth rule sized from 14 of 40.
- 2026-10-14: premise checked again on a fresh test stack: the same server build, both repetition
  samplers off, and no sampling field from the brain. Wrote the fourth rule into
  [reply loop](../../readings/reply-loop.md#the-fourth-rule) before drawing its rows.
- 2026-10-14: done. The fourth rule's baseline looped 22 of 40, so the defect reproduces. DRY
  sampling at 0.8 failed: 12 loops, and no format control reply at all. The repeated line check
  passed, stopping all 22 loops and nothing else. A fifth rule then chose its shape against
  requests to repeat a line, a song and a list: a reply now ends when one block of up to four
  lines comes three times back to back with a line the person's message does not hold, with
  `REPEATED_LINE_NOTE` ([ADR-0048](../../adr/ADR-0048-generation-bounds.md) decision 17).
