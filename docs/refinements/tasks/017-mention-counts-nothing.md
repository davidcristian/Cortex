# A mention that counts nothing

**Status:** landed 2026-08-09
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-08 when the mention matcher was bounded. A `Mention` asks
whether a file spells the agreed value in the template's shape, and one bounded occurrence is
enough, so a file spending it twice can lose one of them with the gate still passing. That is not
hypothetical: `Message.tsx` compares against `"thinking"` on two adjacent lines and `overlay.css`
reads `[data-morphing` in three rules, and an ADR published a mutation proof that assumed
otherwise (corrected where it was published). What was chosen instead of a count is the word
boundary, because a count ties a registry entry to how many times a stylesheet happens to spend
a custom property, and every legitimate new rule would then fail a gate about a coupling that
never moved. The fix, if it bites, is a per mention `occurrences` field carrying an exact count
where one is meaningful and staying unset where it is not, which is a field rather than a design,
since `check_mention` already renders one needle and would only count matches instead of
searching for the first. **Trigger:** a mention whose several occurrences are genuinely a set
that must move together, the first being a state literal compared in two components rather than
one, at which point the count is carrying real information and not just arithmetic about a
stylesheet.

**Landed 2026-08-09, on the trigger, and the entry was right that it is a field rather than a
design.** `Mention.occurrences` is optional; `check_mention` counts bounded matches instead of
stopping at the first, and reports found against pinned
([ADR-0029 counted-mentions addendum](../../adr/ADR-0029-vision-screen-capture.md)). Both live
cases reproduced exactly as this entry describes them, counted against the tree rather than
taken on its word: `Message.tsx` spells `message.statusState === "thinking"` twice and
`overlay.css` reads `[data-morphing` in three rules, and each of the other eleven mentions the
registry carried that morning occurs exactly once.
**The comparison is exactly N rather than at least N**, which is the decision this entry left
open. A floor passes on a far side that grew past it, and having passed once it also passes when
that far side drops back, so the gate widens by however much the tree drifted with nothing
saying when; an exact count is falsifiable both ways and costs one integer in `couplings.py`
when an addition is deliberate. The disable risk this entry named is answered by the
field being opt in rather than by weakening the comparison.
**The stylesheet objection survived and shaped what got registered.** `Message.tsx` is pinned
at 2, its two comparisons being the `className` and the `aria-label` of one chip. The three
`[data-morphing` rules are **not** pinned at 3, because three is the sum of two unrelated
features (a scrollbar thumb hidden mid-roll, and two section share caps), which is exactly the
arithmetic this entry declined; the two share caps alone are a set, so they carry a narrower
mention of their own, `:not([{value}="0"])` at 2, with the bare presence check left standing
over all three. Everything spent once stays unpinned.
**Proven able to fail in both directions, on the real tree.** The rename applied everywhere but
`Message.tsx`'s second line exits 1 naming 1 against 2, and the same mutation under the scan as
it stood the day before exits 0, which is this entry's defect measured rather than asserted; a
third comparison added exits 1 naming 3 against 2; one of the two share-cap rules stripped exits
1 naming 1 against 2; and a fourth rule reading the attribute in an unpinned shape still passes,
which is the benign growth the design has to tolerate. Every perturbation was reverted and the
scan returned to `crosscheck OK` after each.
**No new deferral is opened, and that is a decision rather than an omission.** Two limits remain
and are written into the ADR beside the behaviour: a count is over one file, so there is no way
to say "six across three files", and it is over one rendered needle, so the same value spent in
another shape is not counted. Neither has a case in the tree, every other coupling being
single-file and single-shape, so filing either would inflate the backlog with a capability
nothing is waiting on; the entry above on the couplings the registry still cannot hold is where
a real one would join.
**One bookkeeping repair rides along.** This entry was appended on 2026-08-08 without being
added to the open list above or to the count in [index.md](../index.md), both of which read 6 while
seven were open and named the same six. Closing it makes the number true rather than moving it,
and the six named there are unchanged.

## Trail

- 2026-08-08: Opened when the mention matcher was bounded, one occurrence being enough however
  many times a file spends the value. It was appended without being added to the area's open list
  or to the index count, both of which read 6 while seven were open and named the same six.
- 2026-08-09: Landed on its trigger, and the entry was right that it is a field rather than a
  design. `Mention.occurrences` counts bounded matches and pins an exact number rather than a
  floor, since a floor passes on a far side that grew past it and again when it drops back.
  `Message.tsx` is pinned at 2 and the two share caps carry a narrower mention of their own at 2,
  while the three `[data-morphing` rules stay a presence check, being the sum of two unrelated
  features. No new deferral opened, the two remaining limits going into the ADR beside the
  behaviour, and the bookkeeping repair rode along so the close makes the area number true rather
  than moving it.
