# The parts are held to the tuple and the tuple is held to nothing

**Status:** landed 2026-08-24
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-408](408-the-registry-shape-counts-places-not-parts.md), which declined a part count and made
the list of parts in `registry.py`'s docstring the answer instead, which is only an answer if
every entry lives in a part.

`test_every_registry_part_on_disk_is_read` asserts `set(entries) <= read` for each part: every
coupling a data file holds must reach `CONSTANTS`. Nothing asserts the other direction. A
`Constant` written inline in `registry.py`, or left in a module that is not named `*couplings.py`,
would be checked by the scan exactly like the rest and would sit under none of the nine names the
docstring lists. Measured on the day this was filed, the two sets are equal, 62 entries either
way, so this is a hole rather than a defect.

**Why it was left.** The close was about whether to count the parts, and it decided not to. Adding
a second assertion to the same test would have been a change nobody asked for landing inside a
decline, and the direction that was already gated is the one with a real history behind it: the
registry has been split five times and an import forgotten is the failure that actually happens.

**What would close it.** Turn the subset into an equality: accumulate the union of the parts and
assert it is `set(CONSTANTS)`, so an entry outside every part fails with a message naming it.
Decide two things while doing it. Whether the count has to match too, which catches the same entry
appearing in two parts, and whether that is a defect at all given the scan would simply check it
twice and the shape would count it twice. And whether the naming convention the test walks
(`*couplings.py` holding `<PART>_COUPLINGS`) should be asserted rather than assumed, since a part
that exported its tuple under another name currently fails with an `AttributeError` rather than a
sentence.

## Trail

- 2026-08-24: filed by the close of
  [R-408](408-the-registry-shape-counts-places-not-parts.md), which made the list of parts in
  `registry.py`'s docstring the answer to what the registry is written in and left the tuple held
  only one way.
- 2026-08-24: landed, with both questions answered yes. **Re-derived first and the numbers had
  moved**: ten parts holding 67 entries rather than nine holding 62, the tenth being
  `logcouplings`. The claim survived the move, the union of the parts being exactly
  `set(CONSTANTS)` and the sum of the part lengths being 67 too, so this stayed a hole rather than
  a defect. **The subset is now an equality**, renamed
  `test_the_parts_on_disk_are_exactly_what_the_registry_reads`, with the per-part message kept and
  a stray entry reported by label. **The count has to match**, held as no label appearing twice in
  `CONSTANTS`: an entry in two parts leaves the verdict alone, the scan asking one question twice,
  and the gate printed `68 cross-tree constant(s)` over 67 distinct couplings, so what a duplicate
  breaks is `shape.entries`, the number every mutation table in this repo opens by stating. Labels
  carry it because the earlier decline rests on them being distinct and nothing asserted that, and
  because a copy repeats its label whether or not it stayed identical. **The convention is
  asserted**, decided on a planted part: `AttributeError: module 'probecouplings' has no attribute
  'PROBE_COUPLINGS'` names the attribute and neither the rule nor which half of it is wrong, and it
  arrives twice with neither failure being about the convention. The assertion sits in the helper
  every caller goes through, and `registry.py`'s docstring now states the convention and that
  `CONSTANTS` holds nothing of its own. Four planted mutations over the scripts suite, tabled in
  the ADR-0029 registry-equality addendum. One residue filed: the count is held by labels, so a
  copy that is also relabelled is two entries checking one thing
  ([R-418](418-a-relabelled-copy-of-a-coupling-is-invisible.md)).
