# Slashless authority URL

**Status:** done 2026-08-11
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

Found on 2026-08-10 while running the resolver over the leftover list
([R-063](063-leftover-encoding-table-priced.md)): a special scheme whose authority has fewer than
two slashes. `new URL("https:evil.example/pay")` is `https://evil.example/pay`, and so is the
one-slash form, because the same special-authority states that skip a backslash also tolerate a
missing slash. Measured against the shipped module rather than read off the regex: `extract_urls`
returns nothing for it and a real streaming filter passes the reply through untouched under both
policies.

It could not be fixed in the usual shape. Every widening so far constrains the way a separator
that is present is written, and this one must admit a separator that is absent, so the anchor
needs a host-shaped lookahead it has never needed: `https:` followed by any non-space run is the
prose the fullwidth pass deliberately protected. The only precedent was `_DATA_ANCHOR`, a single
scheme's MIME shape rather than a host grammar. Its cost was therefore a false-positive budget to
design.

Closed 2026-08-11 in exactly that shape. The anchor gained its first lookahead at what follows a
separator, and the rule it enforces is one sentence: a host is a dotted name or a bracketed
literal containing a colon, and nothing else counts. The dotted name covers every registrable
domain, every IPv4 literal and every IDN, with the dot counting in each reading the resolver has,
so the same `LABEL_SEPARATORS` table the identity folds by now also defines the grammar's dot,
imported into the new `url_separators.py` so the two cannot disagree, joined by the HTML references
one rendering pass resolves and by the single percent escape a parser decodes inside a host. That
percent reading is the only one in this grammar and it is there on a measurement:
`https:evil%2eexample/pay` resolves to the plain link while the stacked `%252e` is a parse error,
so exactly one level is a reading, and the separator positions still decline the family because a
parser throws on `https%3A//evil.example`. The bracketed literal requires the colon, so an IPv6
address is admitted and `[1]` or `[abc]`, which a parser rejects, are not.

The budget is the single label, and it is spent on prose. `https:scheme` really is
`https://scheme/` to a parser, and it is also how a sentence names a scheme, so every one-label
host is declined: `http:foo`, `https:localhost:8080/x` and this repo's own way of writing about a
scheme all stay prose, as does anything containing a space. The decline costs no exfiltration
route, a bare label being registrable under no public suffix.

Two things came with the fix that the entry did not foresee. The separator is composed out of the
existing family rather than a new one, so a defanged bare colon reaches this position too
(`http[:]evil.example`, which a reader refangs and follows), which would otherwise have been the
bracket-shape asymmetry a second time. And the identity's authority-slash run went from `+` to
`*`, one character, without which the grammar would anchor the form and the default policy would
still hold no identity for it. The streaming hold-back needed a branch of its own, since a buffer
ending at `https:evil.` is neither a match nor a prefix of any separator, checked at every two-way
split point of nine probes under both policies (702 splits) and one character at a time. Thirteen
tests, each reverted with `__pycache__` cleared and each reversion verified applied.

`urls.py` could not hold a host grammar under the line cap, so the separator vocabulary moved to
`url_separators.py` in the same commit.

## History

- 2026-08-10: Opened rather than chased when running the resolver over the leftover list turned up
  a live form on none of its rows.
- 2026-08-11: Closed in the shape it predicted (ADR-0058 decision 7). It is the only one of these
  guardrail remainders to have both opened and closed inside the order it was written into.
