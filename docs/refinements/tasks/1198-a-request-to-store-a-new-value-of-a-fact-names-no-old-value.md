# A request to store a new value of a fact names no old value

**Status:** done 2026-11-15
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unrequested` refuses the forget tool on a bare statement such as `My alarm code is
5528.`, and `_replaced` (`memory_old_value.py`) then closes the reply with the old value note
when a stored row holds another value of that fact. `stores_fact` (`fact_request.py`) now refuses
the tool on English requests to store a fact too, but `_replaced` reads only a message that is
one `FACT_VALUE` statement from its start. Beside a stored `Remember that my alarm code is
4826.`, run with `hold_old_value` and `forget_unrequested` and no model:

| Message | Tool refused | Old value note |
| --- | --- | --- |
| `My alarm code is 5528.` | yes | `4826` |
| `Save this: my alarm code is 5528.` | yes | none |
| `Store my alarm code 5528.` | yes | none |
| `Record that my alarm code is 5528.` | yes | none |
| `Remember that my alarm code is 5528.` | yes | none |

The start build of 2026-11-14 kept the tool on the three store requests. The person now ends
up with both values stored and no word about the older one. `Remember that ...` had the same gap
before, and so do the French, German, Spanish and Romanian requests that `asks_kept_fact_other`
reads, such as `Retiens que mon nouveau numéro est 0721 555 019.`.

## What to do

1. Write tests first: each request form above beside the stored alarm code names `4826`; the same
   forms with a negation, `Don't save my alarm code 5528.`, name nothing.
2. Read the fact after the request opener in `_replaced`, from the same shapes `stores_fact` and
   `asks_kept` read, rather than a new word list. A note only shows, so a misread costs a note.
3. Decide whether the other four languages get the same reader, and file it if not.
4. Replay every string literal of the brain's memory tests and every backticked string of
   `docs/readings/` through both builds and count notes newly shown.

## History

- 2026-11-14: filed by the audit of the night's forget refusal changes.
- 2026-11-15: done. The table still held at HEAD after the day's changes to the store request
  readers. `_replaced` now reads the fact after a request that opens the message, from
  `fact_stored` and the request to remember `asks_kept` reads (`fact_asked`), unless
  `asks_not_kept` reads the message; a value with no `is` counts only after a word naming a value.
  Of 19,698 replayed strings 111 gain a note, each naming the row of the fact the request states,
  and none loses one
  ([readings](../../readings/forget-refused-statement-old-row.md#a-request-to-store-or-remember-before-the-statement-2026-11-15)).
  The other four languages are task 1236, since a bare statement in them gets no note either, and
  three loose readings of a value the bare statement already had are task 1237.
