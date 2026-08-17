# A tab inside a scheme word

**Status:** landed 2026-08-17
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

As opened, verbatim: a URL parser removes every ASCII tab from its input **before it parses
anything**, at every position, so `ht<TAB>tp://evil.example/pay` and `http:/<TAB>/evil.example/pay`
are the plain link to the browser the user pastes into, exactly as the body position that closed
is. Measured through a real `TaintLedger` and a real streaming filter: neither anchors anything at
all, so `extract_urls` returns nothing for either, the ledger holds nothing when untrusted content
spells its link that way, and **all three policies pass the reply through untouched**, which is the
severe shape this ADR has now found eight times.

It was an entry and not a row because it needs a different kind of change from every widening
before it. Each of those admitted a character to a **class**, which is one edit and no table; this
one admits a character **inside a word**, so the scheme alternation, the streaming hold-back's
literal prefix table and the refanger's own literals all had to be respelled.

## Trail

- 2026-08-16: Opened rather than chased when the fifteenth ADR-0015 addendum closed the tab in a
  URL's body, and counted from the day it opened.
- 2026-08-17: Landed as one rule rather than three patches: a removal may stand between any two
  characters of any literal this grammar spells, generated per character by `permeable` in
  `url_removals.py`, plus a run at the junctions a literal cannot see. Two premises in the entry
  were wrong and are recorded rather than repeated. `hxx<TAB>p` **already** refanged, the anchor
  reading only the first three characters, so the live position was one character left
  (`h<TAB>xxp`); and the ordering question dissolved rather than being answered, since making the
  refanger's literals permeable leaves the removal exactly where the gap fold needs it. One live
  bug was found in passing and closed here: a tab inside a bracketed defang token
  (`http://evil[d<TAB>ot]example`) failed the chunk, fell back to the body, stopped at the closing
  bracket and put the **wrong host** `http://evil[dot` in the ledger. An HTML character reference
  is deliberately left impermeable, on the same rendering-pass line that admitted it. Measured over
  the repo's own prose (1,072 files, 1,407,583 words, 2,851 spans): zero added, lost, extended or
  changed, the last checked by normalizing every match under both the previous passes and these.
  Eleven behaviour tests, eight mutation-proven breaks, two of which hold the decline rather than
  the close. Sibling entry: the host that mixes a dot and a gap (281) is untouched here.
