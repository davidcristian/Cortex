# A request to store a new value of a fact names no old value

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)
**Verified:** 2026-11-14

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
