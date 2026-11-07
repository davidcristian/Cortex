# An English keep idiom or a contrast before a request to remember withholds the turn

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-07

`asks_not_kept` (`memory_request.py`) reads any English negated keep verb at a clause start as a
request not to keep, whatever follows it, and `memory_withheld` then stores nothing of the turn.
Each of these returns true, so the fact the message states is lost:

- `Don't keep it to yourself, my sister is getting married on 12 May.`
- `Don't keep me waiting, my train leaves at 6.`
- `Don't note everything, but remember that my code is 4512.`

The French, German, Spanish and Romanian forms count only when the verb ends its clause after at
most an object naming the message, a phrase naming memory and a polite word. The English reader
does not have that rule, and its `_DONT_KEEP` match before a request to remember counts even when
the request names what to keep.

## What to do

1. Write the messages above as tests first, with near misses that must still withhold:
   `Don't keep this.`, `Don't save my card number.`, `Don't keep a record of this.`,
   `Don't note it down, please.`
2. Replay every recorded draw message and every test string through the old and new reader.
3. Compare the clause rule of the other four languages with a narrower rule for `keep` alone, the
   verb whose idioms the list above shows.

## History

- 2026-11-07: filed by the slot that narrowed the reader of a request not to keep in four more
  languages, which left the English reader as it was.
