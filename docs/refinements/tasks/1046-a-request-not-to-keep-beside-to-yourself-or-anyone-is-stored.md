# A request not to keep beside to yourself or anyone is stored

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-08

`_IDIOM` in `memory_request.py` releases "keep it to yourself" from `_KEEP`, so `asks_not_kept`
reads no request not to keep in "Don't keep it to yourself". The lookahead ends at `yourself`, so
it also releases a message where the phrase goes on to name more people than the assistant, which
asks for the value not to be kept or passed on. Unit level, `asks_not_kept` is `False` for:

- `Don't keep this to yourself or anyone, it's my PIN 4412`

The turn is then not withheld and memory stores the number. A do-not-keep reader withholds when
unsure, and this message is at best ambiguous, so it is on the unsafe side. `Don't keep me in your
notes, my PIN is 4412` is read correctly (`True`).

## What to do

1. Write near misses first: "Don't keep it to yourself, tell my sister" stays released, and
   "don't keep this to yourself or anyone" and "don't keep it to yourself and don't save it" are
   read as requests not to keep.
2. Release the idiom only when `to yourself` ends its clause or is followed by an instruction to
   share, not by `or` or `nor` and another person.

## History

- 2026-11-08: filed by the night's audit slot, from a unit probe of the English keep idioms.
