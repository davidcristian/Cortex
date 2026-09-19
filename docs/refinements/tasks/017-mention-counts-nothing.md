# A mention that counts nothing

**Status:** done 2026-08-09
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

A `Mention` asks whether a file contains the agreed value in the template's form, and one bounded
occurrence was enough, so a file using it twice could lose one of them with the scan still
passing. Two real cases: `Message.tsx` compares against `"thinking"` on two adjacent lines, and
`overlay.css` reads `[data-morphing` in three rules. An ADR had published a mutation proof that
assumed otherwise, corrected where it was published.

A count was not taken at first because it ties a registry entry to how many times a stylesheet
happens to use a custom property, so every legitimate new rule would fail a check about a coupling
that never moved. The word boundary was used instead.

Closed 2026-08-09. `Mention.occurrences` is optional, and `check_mention` counts bounded matches
instead of stopping at the first, reporting found against expected. Both live cases reproduced
exactly, counted against the tree: `Message.tsx` writes `message.statusState === "thinking"`
twice, `overlay.css` reads `[data-morphing` in three rules, and each of the other eleven mentions
occurs exactly once.

The comparison is exactly N rather than at least N. A floor passes on a far side that grew past
it, and having passed once it passes again when that far side drops back, so the check widens by
however much the tree moved with nothing reporting it. An exact count is falsifiable both ways and
costs one integer in `couplings.py` when an addition is deliberate. The risk of someone disabling
it is answered by the field being optional rather than by weakening the comparison.

The stylesheet objection shaped what got registered. `Message.tsx` is set to 2, its two
comparisons being the `className` and the `aria-label` of one chip. The three `[data-morphing`
rules are not set to 3, because three is the sum of two unrelated features (a scrollbar thumb
hidden mid-roll, and two section share caps); the two share caps alone are a set, so they have a
narrower mention of their own, `:not([{value}="0"])` at 2, with the bare presence check left over
all three. Everything used once stays uncounted.

Shown able to fail in both directions on the real tree. The rename applied everywhere but
`Message.tsx`'s second line exits 1 reporting 1 against 2, and the same change under the previous
day's scan exits 0. A third comparison added exits 1 reporting 3 against 2; one of the two
share-cap rules removed exits 1 reporting 1 against 2; and a fourth rule reading the attribute in
an unregistered form still passes, which is the harmless growth the design must tolerate. Every
change was reverted and the scan returned to `crosscheck OK`.

Two limits stay, written into the ADR beside the behaviour: a count is over one file, so there is
no way to require six across three files, and it is over one rendered search text, so the same
value used in another form is not counted. Neither has a case in the tree.

## History

- 2026-08-08: Opened when the mention matcher was bounded, one occurrence being enough however
  many times a file uses the value. It was added without being listed in the area's open entries
  or in the index count, both of which read 6 while seven were open.
- 2026-08-09: Closed, and it was a field rather than a design. `Mention.occurrences` counts
  bounded matches and requires an exact number rather than a floor, since a floor passes on a far
  side that grew past it and again when it drops back. `Message.tsx` is set to 2 and the two share
  caps have a narrower mention of their own at 2, while the three `[data-morphing` rules stay a
  presence check. No new entry opened, the two remaining limits going into the ADR, and the count
  in the index was corrected.
