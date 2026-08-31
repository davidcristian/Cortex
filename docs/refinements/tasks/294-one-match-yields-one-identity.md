# One match yields one identity

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** a spelling whose span has two honest readings, where picking either one loses the
other, which is what a host mixing a plain dot and a gap already is

Opened by the pass that declined the mixed dot-and-gap host, and opened because that decline is a
symptom rather than the cause. `extract_urls` reduces each `URL_RE` match to exactly one identity
and the redactor scrubs with `URL_RE.sub`, which yields non-overlapping matches and asks one
question per match. Every widening so far has fitted inside that shape because each merged two
written forms into one reading. A host that mixes a plain dot and a gap does not: `www.evil dot com`
reads correctly as `http://www.evil` and correctly as `http://www.evil.com`, and the grammar has to
pick. Measured: picking the second destroys the first, extending 14 existing spans and changing 14
identities across 1,072 files and 1,410,285 words, which turns a redaction into a delivered link and
is why that form was declined rather than closed.

A defense that carried **both** readings would lose nothing: the ledger would hold the plain host
beside the joined one, and a reply spelling either would still match. The work is not in the
grammar, which already locates where the second reading ends; it is in the two places that assume
one answer. `extract_urls` returns a frozenset and could carry two identities for one span with no
caller change. The redactor cannot: it would have to ask its question of every reading of a span, or
merge overlapping spans before it substitutes, and the trailing-punctuation and streaming hold-back
logic both read a match's bounds today. What it owes its next reader is a design for that seam with
its false-positive cost measured the way every widening here has been, since a second reading is a
second chance to redact prose.

## Trail

- 2026-08-17: Opened by the ADR-0015 addendum that priced the mixed dot-and-gap host (281) and
  declined it, naming the one-identity assumption as what actually blocks it rather than leaving
  the decline to read as a dead end.
