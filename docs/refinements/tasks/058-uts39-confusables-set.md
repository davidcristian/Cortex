# Full UTS-39 confusables set

**Status:** declined 2026-08-16
**Area:** untrusted-content
**Origin:** [ADR-0015](../../adr/ADR-0015-output-guardrail.md)

It was recorded inside the model-independent output guardrail entry, in its list of what remains
behind the same seam (ADR-0015 deferred). The fragment, verbatim: the **full UTS-39 confusables set**
(needs a dependency).

**Declined on measurement, and the measurement says the dependency was never the blocker.** Against
`confusables.txt` v17.0.0, 745,683 bytes and 6,565 single-codepoint mappings: 1,438 of them aim at
an ASCII host character, **stdlib NFKC already folds 749 of those (52%)**, the curated table holds
29 of the remaining 689 and every one of its 29 is a real UTS-39 entry rather than an invention,
and the untabled residue that a host label can actually carry is 635 codepoints collapsing to **483
distinct characters** after NFKC. So the small curated widening the entry imagines does not exist:
Cyrillic alone is 23 more entries, Cyrillic with Greek and Latin is 116 entries covering 249 of the
635, which is 39%, and full coverage is a data file rather than a source file.

**The resolver question this ADR decides rows by is answered no here, which is the deeper reason.**
Every row it has closed was a respelling of one URL that something in the path undoes. A confusable
host is not: `http://ev<Cyrillic i>l.example/pay` resolves, in a real parser, to
`http://xn--evl-khd.example/pay`, a **different host**, and nothing turns one into the other. Pass 6
is therefore the one fold in the identity that is a judgement about what looks alike rather than a
resolver's reading, which is why "the full set" completes nothing.

**And the table is not where the boundary is, measured through both policies.** With a legitimate
link collected and the reply spelling a lookalike, a curated homoglyph is redacted by both
policies, and an untabled one (U+0406, say) **leaks under the default policy and is redacted under
strict**, because `URL_RE` matches a homoglyph host whatever the table holds. The attacker picks the
codepoint, so a fold carrying 29 of 6,565 mappings, or 483, is a defence against exactly the
characters an attacker would avoid. Three costs the fragment never named settle it: the data is not
deterministic across upgrades (this interpreter's database is UCD 15.0.0 against the file's 17.0.0,
and **41 of the 483 characters are codepoints it cannot even name**), UTS-39's mapping is
confusables rather than exact equivalents (`ш` to `w`, `б` to `6`), and a local-first assistant would carry
either a package or 745 KB of vendored table for it. **The area's count moves by one.** It reopens
only on a measurement naming a specific confusable a deployed model reproduces, and the answer then
is that one character in the curated table, not the set.

## Trail

- 2026-08-09: A trigger sweep of the fix-when-it-bites bucket ran against the tree and fired
  nothing. It named the guardrail tails as live-observation shaped, the trigger being a
  deployment doing something rather than a file saying something, so no reading of the code
  settles it.
- 2026-08-11: The index's fix-when-it-bites bucket counts four guardrail tails, this one among
  them, where five stood the day before and the fifth was the slashless authority URL.
- 2026-08-16: Declined as the thirteenth ADR-0015 addendum, which closes the gap its unrecorded
  trigger left by settling the row rather than by naming what would fire it. The pricing moved no
  code and opened [R-283](283-a-chosen-homoglyph-outlives-any-table.md), which is where the
  residue went: the boundary against a chosen homoglyph is the policy, never the table.
