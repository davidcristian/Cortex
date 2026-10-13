# A reply that repeats one line runs to the length limit

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0048](../../adr/ADR-0048-generation-bounds.md)
**Verified:** 2026-10-13

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
sentence as an assistant prefill, loops in 4 of 10 baseline draws, and a second rig primes the
loop with the reply's first 25 lines: both in [reply loop](../../readings/reply-loop.md).

## What to do

Draw the second rig's baseline and, if it reproduces, the two candidates under
[the pass rule](../../readings/reply-loop.md#the-pass-rule): a DRY setting on the cortex tier
(`--dry-multiplier 0.8`), and a check on the streamed reply that ends it at the third arrival of
one line, with a note saying so. Ship whichever the rule names, behind the turn's existing note path for a check, or the model
host's tier argv for a flag.

## History

- 2026-10-13: filed from the probe row of R-851, whose reply looped to the length limit.
- 2026-10-13: premise checked against the tree and the stack's cortex server: nothing ends a
  repeating reply before the context window. Wrote a replay rig's rows and pass rule into
  [reply loop](../../readings/reply-loop.md); its baseline looped 4 of 10, under the rule's 7, so
  neither candidate was judged, and a second rig with a longer prefill and its rule followed.
