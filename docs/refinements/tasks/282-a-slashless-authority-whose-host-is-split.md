# A slashless authority whose host is split

**Status:** open, fix when it bites
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)
**Trigger:** untrusted content, or a reply, spelling a link with both an absent solidus and a gap

The two widenings that sit closest together in this grammar do not compose, and the pass that
landed the second of them said so rather than letting it be found later. A special scheme reaches
its host with no solidus at all, which the eleventh addendum admitted behind a **host anchor**
asking for a dotted name; the twelfth addendum admits a host whose dot is a **gap**. A gap is not a
dotted name, so the anchor declines it and the two never meet. Measured against the shipped module:
`extract_urls("https:evil dot example/pay")` is empty, which is the severe shape this ADR has now
found seven times, both policies blind and the ledger holding nothing at all. It is reachable in
one refang, since a reader who closes the gap is left with `https:evil.example/pay`, which a real
parser resolves to `https://evil.example/pay` with no further help.

It is an entry rather than a row because the anchor is the eleventh addendum's whole
false-positive budget and a gap is what that budget was spent declining: `https:` followed by
anything with a space in it is the prose the eighth addendum deliberately protected
(`https:no slashes here`), and admitting a gap there hands the anchor back the space it was
narrowed to refuse. A fix has to say what distinguishes a gap that separates two labels from the
space between two words in a sentence, in a position where nothing else carries the anchor. The
number to beat is the one the closing addendum published: zero added spans across 707 files and
1,030,733 words.

## Trail

- 2026-08-16: Opened by the twelfth ADR-0015 addendum, which named the combination it was leaving
  out so it would not be found later as a surprise.
