# A tab inside a scheme word

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** a reply or an untrusted result spelling a scheme or its separator with a tab inside
it, which is the one position of the three where the shipped grammar anchors nothing

As opened, verbatim: a URL parser removes every ASCII tab from its input **before it parses
anything**, at every position, so `ht<TAB>tp://evil.example/pay` and `http:/<TAB>/evil.example/pay`
are the plain link to the browser the user pastes into, exactly as the body position that closed
is. Measured through a real `TaintLedger` and a real streaming filter: neither anchors anything at
all, so `extract_urls` returns nothing for either, the ledger holds nothing when untrusted content
spells its link that way, and **all three policies pass the reply through untouched**, which is the
severe shape this ADR has now found eight times.

It is an entry and not a row because it needs a different kind of change from every widening so
far. Each of those admitted a character to a **class**, which is one edit and no table; this one has
to admit a character **inside a word**, so the scheme alternation `_family` builds and the streaming
hold-back's literal prefix table (`_SCHEME_PREFIXES`, compared with `str.startswith`) both have to
be respelled, and the identity has to decide where the removal sits relative to the refanger, since
`hxx<TAB>p` refangs only if the removal ran first while a tabbed gap folds only if it ran last. The
body position never asks that question, which is why it closed without answering it. The number the
change has to beat is that pass's: zero spans added, lost or extended across 1,054 files and
1,348,844 words.

## Trail

- 2026-08-16: Opened rather than chased when the fifteenth ADR-0015 addendum closed the tab in a
  URL's body, and counted from the day it opened.
