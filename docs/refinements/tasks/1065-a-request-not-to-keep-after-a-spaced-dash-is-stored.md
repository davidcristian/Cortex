# A request not to keep after a spaced dash is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-08

`asks_not_kept` in `memory_request.py` opens a clause only at the start of a sentence, after `,`,
`;` or `:`, or after a conjunction. A request written after a spaced hyphen, an en dash or inside
brackets opens none of them, so `My PIN is 4412 - don't keep it.`, the same with an en dash, and
`My PIN is 4412 (don't keep it).` all read as no request. On 2026-11-08 the live turn
`My PIN is 4412 - I mean don't keep it.` (chat `s18-28800`, stack brain from `0d6efa10e`) stored
its exchange as a row while the reply said `I will not save or remember your PIN.` The next chat
recalled it ([the readings](../../readings/not-kept-requests-on-the-stack.md)). The safe direction
of this reader is to withhold when unsure.

## What to do

1. Write near-miss tests first: a dash or a bracket before a statement with the same verb
   (`My bike - I don't store it outside`, `(I never record calls)`), then the three forms above.
2. Read a spaced dash and an opening bracket as clause openers. `dashcheck.py` reads test strings,
   so write the dash as an escape in the test source.
3. Replay every recorded draw message through the old and new reader.

## History

- 2026-11-08: filed by the audit of tonight's reader changes, from one live turn and three unit
  probes; the same audit shipped "what I mean is", "I meant to say" and "put it nowhere".
