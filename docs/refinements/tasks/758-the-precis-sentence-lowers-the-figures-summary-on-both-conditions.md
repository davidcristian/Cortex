# The precis sentence lowers the figures summary on both conditions

**Status:** open, actionable
**Verified:** 2026-09-30
**Area:** subagents
**Origin:** [ADR-0072](../../adr/ADR-0072-subagent-roles.md)

On the default pick the shipped `precis` sentence took the figures-keeping summarization from 25 to
13 of 32 on CPU and from 27 to 12 of 32 on the card, the intervals apart both times, with 6 and 7
bodies handed back and 13 cap refusals each ([reply envelope](../../readings/reply-envelope.md),
"The role sentences"). By the rule
[R-755](755-the-precis-sentence-read-lower-on-one-condition.md) wrote before the card row, that
replication is the evidence for rewording or removing the sentence. The cortex names `precis` on 15
of 16 summaries it delegates on the card ([spawn spec uptake](../../readings/spawn-spec-uptake.md)),
so the sentence reaches nearly every delegated summary.

The sentence reads "Reply with the text you were given made shorter, ...", and `REPLY_INSTRUCTION`,
which follows it on a constrained run, asks for "the answer itself, not the text you were given".
An assumption, unread: the first names the input as the reply and the second forbids it, and the
copies and the cap refusals come from that conflict.

Written down before a row is drawn:

1. **A rewording that does not name the input as the reply**, for example "Reply with a shorter
   version that keeps every figure, name and date and adds nothing the text does not state.",
   drawn on the card in the condition of R-755's card row (the compose argv at `-ngl 99`, the four
   bodies at eight seeded draws a cell, `CORTEX_ENVELOPE_INSTRUCTION` set to the shape followed by
   the sentence), beside the plain cell in the same server session and judged the same way. It
   ships if its interval overlaps the plain cell's; if it is again apart and lower, item 2.
2. **No sentence for the role**: the cortex still names `precis`, and the subtask's own instruction
   sets the form. `SubagentRoles` rejects an entry with an empty instruction today, so this is a
   change to that check and its tests; `SubagentRole.applied` already leaves the subtask's
   instruction unchanged when the sentence is empty.

Record the engine build, the argv and an `nvidia-smi` SM clock beside the card rows, and read the
chosen form on Qwen3.5-2B with R-755's second item. Done when the shipped `precis` form reads inside
the plain cell's interval on the card, or has no sentence, and ADR-0072 states it.

## History

- 2026-09-30: Filed by R-755, whose card row replicated the CPU drop: 27 of 32 without the sentence
  and 12 of 32 with it.
