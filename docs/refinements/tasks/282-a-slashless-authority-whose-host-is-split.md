# A slashless authority whose host is split

**Status:** landed 2026-08-17
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

The two widenings that sit closest together in this grammar do not compose, and the pass that landed
the second of them said so rather than letting it be found later. A special scheme reaches its host
with no solidus at all, which the eleventh addendum admitted behind a **host anchor** asking for a
dotted name; the twelfth addendum admits a host whose dot is a **gap**. A gap is not a dotted name,
so the anchor declines it and the two never meet. Measured against the shipped module:
`extract_urls("https:evil dot example/pay")` is empty, which is the severe shape this ADR has now
found seven times, both policies matching nothing and the ledger holding nothing at all. It is
reachable in one refang, since a reader who closes the gap is left with `https:evil.example/pay`,
which a real parser resolves to `https://evil.example/pay` with no further help.

It was an entry rather than a row because the anchor is the eleventh addendum's whole
false-positive budget and a gap looked like what that budget was spent declining: `https:` followed
by anything with a space in it is the prose the eighth addendum deliberately protected
(`https:no slashes here`). Re-derived from the code, that reading was too strong, and the finding
is the close: **the anchor was never narrowed against a space, it was narrowed against a run with
no dot in it**, and a gap is whitespace wrapped around a **dot token**, which no English sentence
puts between two words. So the split host joins the dotted name and the bracketed literal as a
third host shape, and the budget is unspent.

## Trail

- 2026-08-16: Opened by the twelfth ADR-0015 addendum, which named the combination it was leaving
  out so it would not be found later as a surprise.
- 2026-08-17: Landed. The host anchor reads a split host as a third host shape, and the grammar now
  spells that anchor twice, once finished and once **arriving**, since a half-typed split host
  satisfies no finished anchor and the streaming hold-back would otherwise release the opening one
  delta early; the separator alternation takes the anchor as a parameter so the two cannot drift.
  Measured over the repo's own prose at `HEAD` (1,071 files, 1,404,408 words, 2,812 spans): zero
  lost, zero extended, zero identities changed, three added, all three of them this repo writing the
  attack form down. Every prose protection the eleventh addendum bought is intact, `https:no slashes
  here` included. Eleven behaviour tests, three mutation-proven breaks, a fourth tried and reported
  as a no-op rather than claimed. The streaming hold-back moved to `url_holdback.py` at the line cap
  in the same commit, per the split-as-you-go rule. Sibling entries: the tab inside a scheme word
  (285) is separate and untouched here; the host that mixes a dot and a gap (281) needs the
  **dotless rule** relaxed, which this pass deliberately does not do.
