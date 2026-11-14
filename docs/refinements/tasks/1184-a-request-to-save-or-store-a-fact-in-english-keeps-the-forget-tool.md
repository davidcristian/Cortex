# A request to save or store a fact in English keeps the forget tool

**Status:** done 2026-11-14
**Area:** memory
**Origin:** [ADR-0075](../../adr/ADR-0075-forget-chosen-memories.md)

`forget_unrequested` (`forget_unrequested.py`) refuses the forget tool on an English request to
remember only when `asks_kept` reads it, and `asks_kept` (`memory_request.py`) reads `remember`,
`note that` and `keep in mind`. `Save my phone number 0721 555 019.`,
`Store this: my phone is 0721 555 019.`, `Keep my phone number 0721 555 019.`,
`Write down my phone number 0721 555 019.` and `Memorize my phone number 0721 555 019.` are not
read, so each keeps the tool at HEAD `c0e02329e`. An unasked call on a plain statement withheld the
stated fact in 4 of 8 draws ([readings](../../readings/forget-refusal-english-statement.md)), and
these messages are the same store turn. Keeping the tool is the safe direction, so the cost is a
round and a withheld fact, never a lost row the person did not see on a card.

## What to do

1. Write tests first: each message above refuses the tool; `Save me a seat.`, `Store the old one
   somewhere else.` and `Don't save my PIN.` keep it.
2. Read the opening imperative and its fact in `forget_unrequested` alone, by the statement's
   shape (`fact_statement.py`), and leave `asks_kept` unchanged, since it also decides what is
   stored.
3. Replay every recorded message and test string through the start build and the new reader, in
   Italian, Portuguese, Dutch and Polish too, and name every string whose result changes.

## History

- 2026-11-13: filed by the first audit of the night.
- 2026-11-14: done. `stores_fact` (`fact_request.py`) reads an opening `save`, `store`, `keep`,
  `record`, `memorize` or `write down` only before one sentence stating a fact, and
  `forget_unrequested` refuses the tool on it; `asks_kept` is unchanged. The near misses keep the
  tool, and a replay of 19934 recorded strings changed 13 to refused. No forget call came in 8
  store turns on either build, so the draws decide nothing about the refusal; the turns that
  stored no row called a file tool, filed as
  [task 1196](1196-a-request-to-save-a-fact-in-english-keeps-the-file-tools.md)
  ([readings](../../readings/forget-refusal-stated-fact.md)).
