# A host that mixes a dot and a gap

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** untrusted content, or a reply, spelling a host with a plain dot and a gap at once

Opened by the pass that closed the whitespace-split host, and opened rather than chased for the
reason the slashless authority was: it is not fixable in the shape the close used, so it needs a
budget designed rather than a table extended. The close admits a gap only while every label so far
is **dotless**, because defanging replaces a host's dot and never adds one, and that one rule is
what buys the close its measured zero false positives over a million words of prose. A host that
does both at once falls outside it. Measured against the shipped module rather than read off the
regex: `extract_urls("http://www.evil dot com")` is `{"http://www.evil"}`, and
`extract_urls("hxxp://www[.]evil dot com")` is `{"http://www.evil"}`, so the ledger holds a **wrong
host** on the collection side and the reply side redacts a prefix while leaving ` dot com` beside
the marker, which is the third failure shape the closing addendum named. Two labels split and one
dotted is a spelling a person writes without thinking about it, since the `www.` is the part they
do not think of as the name.

What makes it an entry and not a row is that relaxing the dotless rule is exactly what reopens the
prose the rule protects: `visit http://example.com dot the file is there` reads as a host the
moment a label may carry a dot, which was measured during the close. A fix therefore needs a
different constraint carrying the same weight, and the candidates each cost something the repo does
not currently spend: a known-TLD tail (roughly 1,450 entries from IANA, and `dot com`, `dot net`
and `dot ai` are ordinary English besides), a requirement that the gap be one of at least two, or a
rule that a gap may follow a dotted prefix only when that prefix is a known subdomain label. None
is obviously right, which is why the number to beat is written down here: zero added spans across
707 files and 1,030,733 words.

## Trail

- 2026-08-16: Opened by the twelfth ADR-0015 addendum, which found it while widening the gap and
  left it standing on purpose, the tenth addendum's own precedent for a spelling whose fix needs
  its own false-positive budget.
