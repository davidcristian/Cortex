# One match yields one identity

**Status:** open, waiting for its trigger
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)
**Trigger:** a second written form whose span has two valid readings, or the mixed dot-and-gap host
reaching a real reply on this machine, either of which would make a two-reading defence buy more
than the one form already declined. The cheap recheck is whether the assumption is still four call
sites: `extract_urls` in `brain/packages/core/src/cortex_core/urls.py`, `URL_RE.sub` and the
trailing-punctuation trim in `brain/packages/core/src/cortex_core/guardrail.py`, and the
`last.start()` read in `brain/packages/core/src/cortex_core/url_holdback.py`. One
`grep -rn 'URL_RE\.\|rstrip(TRAILING_PUNCTUATION)\|last\.end()' brain/packages/core/src/cortex_core/`
prints six lines, five of them the four sites; the sixth is the trim `normalize_url` performs
inside the identity reduction in `url_identity.py`, which reads one matched string and assumes
nothing about how many readings its span has. The second condition cannot be decided from the tree,
since a reply lives in the session store. The first is read off `url_separators.py`.
**Verified:** 2026-09-24

Opened by the pass that declined the mixed dot-and-gap host, because that decline is a symptom
rather than the cause. `extract_urls` reduces each `URL_RE` match to exactly one identity and the
redactor scrubs with `URL_RE.sub`, which returns non-overlapping matches and asks one question per
match. Every widening so far fitted inside that shape because each merged two written forms into
one reading. A host that mixes a plain dot and a gap does not: `www.evil dot com` reads correctly as
`http://www.evil` and correctly as `http://www.evil.com`, and the grammar has to pick. Picking the
second destroys the first, which turns a redaction into a delivered link.

A defence that kept both readings would lose nothing: the record would hold the plain host beside
the joined one, and a reply writing either would still match. The work is not in the grammar, which
already locates where the second reading ends; it is in the places that assume one answer.
`extract_urls` returns a frozenset and could hold two identities for one span with no caller
change. The other three cannot. `_scrub` substitutes with `URL_RE.sub`, which visits
non-overlapping spans and calls `_redacted` once per span; `_redacted` then trims trailing prose
punctuation off the matched text and rebuilds the replacement around what it trimmed, so a span
with two readings would have to decide whose punctuation that is; and `held_from` releases the
buffer up to `last.start()` on a match ending at `last.end() == len(buf)`, so a second reading
ending later than the first would be released before it could be recognized. Any two-reading design
has to answer all three together, with its false-positive cost measured the way every widening here
has been, since a second reading is a second chance to redact prose.

## History

- 2026-08-17: Opened by the pass that costed the mixed dot-and-gap host
  ([281](281-a-host-that-mixes-a-dot-and-a-gap.md)) and declined it, naming the one-identity
  assumption as what actually blocks it.
- 2026-09-08: Not triggered, and the measurement repaired from a fresh run. No second two-reading
  form has appeared and the mixed host has not reached a reply here. The relaxation was rebuilt
  from the current `url_separators` tables rather than assumed: over 1,548 readable files, 2,304,319
  words and 2,997 matched spans it adds 0 spans, loses 0, and extends 22, changing all 22
  identities, where this entry claimed 14 of each. The failure is the same at the larger size,
  `http://example.com` followed by ` dot the` becoming `http://example.com.the`. The trigger used
  to name a condition already true the day it was written and now names one a reader can check. The
  readings are in [docs/readings/output-guardrail.md](../../readings/output-guardrail.md).
- 2026-09-11: Not triggered. The grep prints six lines rather than the five recorded here:
  `guardrail.py` twice, `urls.py` once and `url_holdback.py` twice are the four sites, and the
  sixth is `url_identity.py`'s `rstrip(TRAILING_PUNCTUATION)` inside `normalize_url`. The same grep
  over the earlier tree printed six as well, so the count was wrong the day it was written and the
  trigger is corrected. None of the four files has changed since 2026-09-07.
- 2026-09-17: Not triggered, and the relaxation was rebuilt and rerun rather than quoted. The grep
  prints the same six lines at `urls.py:226`, `guardrail.py:220` and `:226`, `url_identity.py:271`
  and `url_holdback.py:134` and `:136`, and none of those four files nor `url_separators.py` has
  changed since 2026-08-31. The rebuild composed the relaxed `SPLIT_LABEL` into the gap, the split
  host and the host anchor through the module's own `_family` and `_authority_sep`, after checking
  that the same composition over the shipped label reproduces `URL_RE.pattern` exactly. Over
  today's 3,018 spans it adds 0, loses 0, and extends 22, changing all 22 identities. The three
  `extract_urls` callers (`untrusted.py:179` and `:191`, `output_channels.py:64`) all take the
  result as a set.
- 2026-09-24: not triggered. The grep prints the same six lines, now at `urls.py:92`,
  `guardrail.py:158` and `:166`, `url_identity.py:119` and `url_holdback.py:72` and `:74`. The one
  change to `url_separators.py` and `url_holdback.py` since renamed the separator tables to
  `COLON_FORMS`, `SOLIDUS_FORMS` and `DOT_FORMS` and added no written form.
