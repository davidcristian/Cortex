# One match yields one identity

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** a second spelling whose span has two honest readings, or the mixed dot-and-gap host
reaching a real reply on this machine, either of which would make a two-reading defense buy more
than the one form that is already declined. The cheap recheck is whether the assumption is still
four call sites: `extract_urls` in `brain/packages/core/src/cortex_core/urls.py`, `URL_RE.sub` and
the trailing-punctuation trim in `brain/packages/core/src/cortex_core/guardrail.py`, and the
`last.start()` read in `brain/packages/core/src/cortex_core/url_holdback.py`. One
`grep -rn 'URL_RE\.\|rstrip(TRAILING_PUNCTUATION)\|last\.end()' brain/packages/core/src/cortex_core/`
reports all four in five lines. The body records what the relaxation cost when it was last measured.

Opened by the pass that declined the mixed dot-and-gap host, and opened because that decline is a
symptom rather than the cause. `extract_urls` reduces each `URL_RE` match to exactly one identity
and the redactor scrubs with `URL_RE.sub`, which yields non-overlapping matches and asks one
question per match. Every widening so far has fitted inside that shape because each merged two
written forms into one reading. A host that mixes a plain dot and a gap does not: `www.evil dot com`
reads correctly as `http://www.evil` and correctly as `http://www.evil.com`, and the grammar has to
pick. Picking the second destroys the first, which turns a redaction into a delivered link and is
why that form was declined rather than closed.

A defense that carried **both** readings would lose nothing: the ledger would hold the plain host
beside the joined one, and a reply spelling either would still match. The work is not in the
grammar, which already locates where the second reading ends; it is in the places that assume one
answer, and the interaction between them is the part a mutation table over a new matcher would not
reach. `extract_urls` returns a frozenset and could carry two identities for one span with no caller
change. The other three cannot. `_scrub` substitutes with `URL_RE.sub`, which visits non-overlapping
spans and calls `_redacted` once per span; `_redacted` then trims trailing prose punctuation off the
matched text and rebuilds the replacement around what it trimmed, so a span holding two readings
would have to decide whose punctuation that is; and `held_from` releases the buffer up to
`last.start()` on a match ending at `last.end() == len(buf)`, so a second reading ending later than
the first would be released before it could ever be recognized. Any two-reading design has to answer
all three together, since the escaping the trim performs and the ordering the hold-back imposes both
read a span's edges. What it owes its next reader is a design for that seam with its false-positive
cost measured the way every widening here has been, since a second reading is a second chance to
redact prose.

**Re-measured 2026-09-08, and the relaxation costs more than this entry recorded.** The number here
was 14 extended spans and 14 changed identities over 1,072 files and 1,410,285 words. Re-run against
`HEAD` with the same construction, a `SPLIT_LABEL` allowed to carry a plain dot and every rule above
it rebuilt on it, the corpus is 1,548 readable files and 2,304,319 words carrying 2,997 matched
spans, and the relaxation adds 0 spans, loses 0, and extends **22**, changing all 22 identities. The
published bar was zero added spans and the relaxation still passes it; the last column still decides
it, and the failure is the same one at a larger size, `http://example.com` followed by ` dot the`
becoming `http://example.com.the` and the guardrail delivering a link it catches today. The four
call sites are unchanged, so the decline stands on the reading it was made on.

## Trail

- 2026-09-08: **Not fired**, and the measurement in the body is repaired from a fresh run. No second
  two-reading spelling has appeared and the mixed host has not reached a reply here, the shipped
  policy being the collected-identity default. The relaxation was rebuilt from the current
  `url_spellings` tables rather than assumed and now extends 22 spans and 22 identities where this
  entry claimed 14 of each; the shape of the failure is unchanged. The trigger, which used to name a
  condition that was already true the day it was written, is replaced by one a reader can check.
  Recorded in the twenty-first ADR-0015 addendum beside
  [R-284](284-the-lookalike-policy-as-the-shipped-default.md).
- 2026-08-17: Opened by the ADR-0015 addendum that priced the mixed dot-and-gap host (281) and
  declined it, naming the one-identity assumption as what actually blocks it rather than leaving
  the decline to read as a dead end.
