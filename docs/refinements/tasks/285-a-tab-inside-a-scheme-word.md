# A tab inside a scheme word

**Status:** done 2026-08-17
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

A URL parser removes every ASCII tab from its input before it parses anything, at every position,
so `ht<TAB>tp://evil.example/pay` and `http:/<TAB>/evil.example/pay` are the plain link to the
browser the user pastes into. Measured through a real `TaintLedger` and a real streaming filter:
neither matched anything, so `extract_urls` returned nothing for either, the record held nothing
when untrusted content wrote its link that way, and all three policies passed the reply through
untouched.

It was an entry rather than a one-line fix because it needs a different kind of change from every
widening before it. Each of those admitted a character to a class, which is one edit and no table;
this one admits a character inside a word, so the scheme alternation, the streaming hold-back's
literal prefix table and the refanger's own literals all had to be rewritten.

## History

- 2026-08-16: Opened when the tab was admitted in a URL's body.
- 2026-08-17: Done as one rule rather than three patches: a removal may stand between any two
  characters of any literal this grammar writes, generated per character by `permeable` in
  `url_removals.py`, plus a run at the junctions a literal cannot see. Two premises in the entry
  were wrong and are recorded rather than repeated. `hxx<TAB>p` already refanged, the anchor
  reading only the first three characters, so the live case was one character left
  (`h<TAB>xxp`); and the ordering question disappeared rather than being answered, since making the
  refanger's literals permeable leaves the removal exactly where the gap fold needs it. One live
  bug was found in passing and fixed here: a tab inside a bracketed defang token
  (`http://evil[d<TAB>ot]example`) failed the chunk, fell back to the body, stopped at the closing
  bracket and put the wrong host `http://evil[dot` in the record. An HTML character reference is
  deliberately left impermeable, on the same rendering-pass reasoning that admitted it. Measured
  over the repo's own prose (1,072 files, 1,407,583 words, 2,851 spans): zero added, lost, extended
  or changed, the last checked by normalizing every match under both the previous passes and these.
  Eleven behaviour tests, eight breaks proven by mutation, two of which cover the decline rather
  than the fix.
