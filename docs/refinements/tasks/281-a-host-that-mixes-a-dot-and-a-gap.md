# A host that mixes a dot and a gap

**Status:** declined 2026-08-17
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

Opened by the pass that closed the whitespace-split host, and opened rather than chased because it
is not fixable in the shape the close used. The close admits a gap only while every label so far is
**dotless**, because defanging replaces a host's dot and never adds one, and that one rule is what
buys the close its measured zero false positives over a million words of prose. A host that does
both at once falls outside it. Measured against the shipped module rather than read off the regex:
`extract_urls("http://www.evil dot com")` is `{"http://www.evil"}`, so the ledger holds a **wrong
host** on the collection side and the reply side redacts a prefix while leaving ` dot com` beside
the marker, which is the third failure shape the closing addendum named. Two labels split and one
dotted is a form a person writes without thinking about it, since the `www.` is the part they do not
think of as the name.

## Trail

- 2026-08-16: Opened by the twelfth ADR-0015 addendum, which found it while widening the gap and
  left it standing on purpose, the tenth addendum's own precedent for a written form whose fix needs
  its own false-positive budget.
- 2026-08-17: Declined, on a measurement that says the obvious fix makes this guardrail worse rather
  than wider. Relaxing the dotless rule costs zero added spans over 1,072 files and 1,410,285 words,
  which clears the published bar, but it **extends 14 existing spans and changes 14 identities**,
  and that column is not a false positive: an ordinary link followed by ` dot the` stops normalizing
  to itself, so a link collected from untrusted content and reproduced in the reply is **delivered
  rather than redacted**, confirmed end to end through a real ledger and a real streaming filter. An
  attacker reaches that by asking the model for one extra word. Every narrowing considered is a data
  table this repo does not carry or does not reach the case at all, because nothing structural
  separates `http://www.evil dot com` from `http://example.com dot the`. The real fix is not in the
  grammar: a mixed host has two valid readings and the seam yields one identity per match, so
  closing this needs a defense that emits both, which is recorded as its own entry (294). Sibling
  entries closed the same day: the slashless authority whose host is split (282) and the tab inside
  a scheme word (285), neither of which touches the dotless rule.
