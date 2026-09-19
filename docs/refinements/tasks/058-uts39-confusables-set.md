# Full UTS-39 confusables set

**Status:** declined 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0058](../../adr/ADR-0058-url-recognition-and-identity.md)

Left behind by [R-056](056-output-guardrail.md), noted as needing a dependency.

Declined on measurement, and the measurement says the dependency was never the obstacle. Against
`confusables.txt` v17.0.0, 745,683 bytes and 6,565 single-codepoint mappings: 1,438 of them aim at
an ASCII host character, stdlib NFKC already folds 749 of those (52%), the curated table holds 29
of the remaining 689 and every one of its 29 is a real UTS-39 entry rather than an invention, and
the untabled remainder a host label can contain is 635 codepoints collapsing to 483 distinct
characters after NFKC. So the small curated widening the entry imagined does not exist: Cyrillic
alone is 23 more entries, Cyrillic with Greek and Latin is 116 entries covering 249 of the 635,
which is 39%, and full coverage is a data file rather than a source file.

The deeper reason is the question this ADR decides by. Every case it has closed was one URL
written differently, which something in the path turns back into the original. A confusable host
is not: `http://ev<Cyrillic i>l.example/pay` resolves, in a real parser, to
`http://xn--evl-khd.example/pay`, a different host, and nothing turns one into the other. The
confusable fold is the one pass in the identity that is a judgement about what looks alike rather
than a reading of what a resolver does, which is why the full set completes nothing.

The table is also not where the boundary is, measured through both policies. With a legitimate
link collected and the reply writing a lookalike, a curated homoglyph is removed by both policies,
and an untabled one (U+0406, say) leaks under the default policy and is removed under strict,
because `URL_RE` matches a homoglyph host whatever the table holds. The attacker picks the
codepoint, so a fold with 29 of 6,565 mappings, or 483, defends against exactly the characters
an attacker would avoid. Three costs the note never named settle it: the data is not the same
across upgrades (this interpreter's database is UCD 15.0.0 against the file's 17.0.0, and 41 of
the 483 characters are codepoints it cannot even name), UTS-39's mapping is of confusables rather
than exact equivalents (`ш` to `w`, `б` to `6`), and a local-first assistant would have to ship
either a package or 745 KB of vendored table for it.

It reopens only on a measurement naming a specific confusable a deployed model reproduces, and the
answer then is that one character in the curated table, not the set.

## History

- 2026-08-09: A review of deferred triggers ran against the tree and none fired.
- 2026-08-11: The index counted four guardrail remainders, this one among them.
- 2026-08-16: Declined (ADR-0058 decision 16). The pricing moved no code and opened
  [R-283](283-a-chosen-homoglyph-outlives-any-table.md), which is where the residue went: the
  boundary against a chosen homoglyph is the policy, never the table.
