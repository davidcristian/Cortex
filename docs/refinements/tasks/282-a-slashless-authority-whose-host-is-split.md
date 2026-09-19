# A slashless authority whose host is split

**Status:** done 2026-08-17
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

The two widenings that sit closest together in this grammar did not combine, and the pass that
added the second said so rather than letting it be found later. A special scheme reaches its host
with no slash at all, which the slashless pass allowed behind a host anchor asking for a dotted
name; the split-host pass allows a host whose dot is a gap. A gap is not a dotted name, so the
anchor refused it and the two never met. Measured against the shipped module:
`extract_urls("https:evil dot example/pay")` is empty, so both policies match nothing and the
record holds nothing at all. It is reachable in one refang, since a reader who closes the gap is
left with `https:evil.example/pay`, which a real parser resolves to `https://evil.example/pay`.

It was an entry rather than a one-line fix because the anchor is the slashless pass's whole
false-positive budget, and a gap looked like what that budget was spent refusing: `https:` followed
by anything with a space in it is the prose the fullwidth pass deliberately protected
(`https:no slashes here`). Read against the code, that was too strong, and the correction is the
close: the anchor was never narrowed against a space, it was narrowed against a run with no dot in
it, and a gap is whitespace around a dot token, which no English sentence puts between two words.

## History

- 2026-08-16: Opened by the split-host pass, which named the combination it was leaving out so it
  would not be a surprise later.
- 2026-08-17: Done. The host anchor reads a split host as a third host shape, and the grammar now
  writes that anchor twice, once finished and once still arriving, since a half-typed split host
  satisfies no finished anchor and the streaming hold-back would otherwise release the opening
  delta early; the separator alternation takes the anchor as a parameter so the two cannot
  diverge. Measured over the repo's own prose at `HEAD` (1,071 files, 1,404,408 words, 2,812
  spans): zero lost, zero extended, zero identities changed, three added, all three of them this
  repo writing the attack form down. Every prose protection the slashless pass bought is intact,
  `https:no slashes here` included. Eleven behaviour tests, three breaks proven by mutation, a
  fourth tried and reported as a no-op rather than claimed. The streaming hold-back moved to
  `url_holdback.py` at the line cap in the same commit.
