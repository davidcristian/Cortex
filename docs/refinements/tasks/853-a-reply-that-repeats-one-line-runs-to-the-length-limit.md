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

## Reproduce

The probe row in the readings above, on the current tree under `CORTEX_TOOLS_ON_UNAVAILABLE=skip`.
How often a row loops is not measured yet.

## What to do

Measure first: draw the cut off call rows of R-851 and count the replies that loop. Then decide
between a repeated-line check on the streamed reply that ends it early with a note saying so, and
a repeat penalty in the cortex's sampling settings. Either changes what the person reads, so it
ships on rows and a pass rule written in the readings first.

## History

- 2026-10-13: filed from the probe row of R-851, whose reply looped to the length limit.
