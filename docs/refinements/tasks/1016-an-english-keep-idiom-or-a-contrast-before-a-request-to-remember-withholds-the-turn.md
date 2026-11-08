# An English keep idiom or a contrast before a request to remember withholds the turn

**Status:** done 2026-11-08
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)

`asks_not_kept` (`memory_request.py`) reads any English negated keep verb at a clause start as a
request not to keep, whatever follows it, and `memory_withheld` then stores nothing of the turn.
Each of these returns true, so the fact the message states is lost:

- `Don't keep it to yourself, my sister is getting married on 12 May.`
- `Don't keep me waiting, my train leaves at 6.`
- `Don't note everything, but remember that my code is 4512.`

The French, German, Spanish and Romanian forms count unless an idiom word such as `rancune` or
`für dich` follows the verb. The English reader does not have that rule, and its `_DONT_KEEP`
match before a request to remember counts even when the request names what to keep.

## What to do

1. Write the messages above as tests first, with near misses that must still withhold:
   `Don't keep this.`, `Don't save my card number.`, `Don't keep a record of this.`,
   `Don't note it down, please.`
2. Replay every recorded draw message and every test string through the old and new reader.
3. Do not use a clause end rule, which counts the verb only when it ends its clause. Checked on
   2026-11-07 against 22,179 distinct strings (the night's turn records, the brain's test files
   and the readings records), that rule applied to every English keep verb, or to `keep` alone,
   released the two idioms above and also stopped withholding `Also, don't keep my locker code 7319.`,
   `Remember my PIN 5521, but don't keep it after today.` and `Don't keep a record of this.`
   (and, for every verb, `Don't remember my locker code 7319 anymore.`). Read the idiom's own
   complement instead (`to yourself`, a person and a gerund), and replay the same strings.

## History

- 2026-11-07: filed by the slot that narrowed the reader of a request not to keep in four more
  languages, which left the English reader as it was.
- 2026-11-08: done. A negated `keep` before `to yourself` or a person and a gerund, and a negated keep
  verb before `everything, but remember`, no longer withhold; the four near misses above, `Don't record
  me talking.` and `Don't keep everything, my PIN is 5521.` still do. Of 13,259 replayed strings, 7
  stopped being requests not to keep, each one of these forms
  ([readings](../../readings/claim-reader-replays.md#a-forget-in-four-more-languages-and-an-english-keep-idiom-2026-11-08)).
