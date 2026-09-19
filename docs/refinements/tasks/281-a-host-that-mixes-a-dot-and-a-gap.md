# A host that mixes a dot and a gap

**Status:** declined 2026-08-17
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

Opened by the pass that closed the whitespace-split host, and opened rather than fixed because it
cannot be fixed in the shape that close used. The close accepts a gap only while every label so far
has no dot, because defanging replaces a host's dot and never adds one, and that one rule is what
buys it a measured zero false positives over a million words of prose. A host that does both at
once falls outside it. Measured against the shipped module rather than read off the regex:
`extract_urls("http://www.evil dot com")` is `{"http://www.evil"}`, so the record holds a wrong
host on the collection side, and the reply side redacts a prefix while leaving ` dot com` beside
the marker. Two labels split and one dotted is a form a person writes without thinking, since the
`www.` is the part they do not think of as the name.

## History

- 2026-08-16: Opened by the split-host pass, which found it while widening the gap and left it
  alone deliberately, following the backslash pass's precedent for a written form whose fix needs
  its own false-positive budget.
- 2026-08-17: Declined, on a measurement showing the obvious fix makes this defence worse rather
  than wider. Relaxing the no-dot rule costs zero added spans over 1,072 files and 1,410,285 words,
  which clears the published bar, but it extends 14 existing spans and changes 14 identities, and
  that is not a false positive: an ordinary link followed by ` dot the` stops normalizing to
  itself, so a link collected from untrusted content and reproduced in the reply is delivered
  rather than redacted, confirmed end to end through a real record and a real streaming filter. An
  attacker reaches that by asking the model for one extra word. Every narrowing considered needs a
  data table this repo does not have, or does not reach the case at all, because nothing structural
  separates `http://www.evil dot com` from `http://example.com dot the`. The real fix is not in the
  grammar: a mixed host has two valid readings and the matcher returns one identity per match, so
  closing this needs a defence that returns both, recorded as
  [294](294-one-match-yields-one-identity.md). Two sibling entries closed the same day,
  [282](282-a-slashless-authority-whose-host-is-split.md) and
  [285](285-a-tab-inside-a-scheme-word.md), neither of which touches the no-dot rule.
