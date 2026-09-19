# The parts are compared with the tuple and the tuple is compared with nothing

**Status:** done 2026-08-24
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

`test_every_registry_part_on_disk_is_read` asserts `set(entries) <= read` for each part: every
coupling a data file contains must reach `CONSTANTS`. Nothing asserts the other direction. A
`Constant` written inline in `registry.py`, or left in a module not named `*couplings.py`, would be
checked by the scan exactly like the rest and would sit under none of the nine names the docstring
lists. Measured on the day this was filed, the two sets are equal, 62 entries either way, so this
is a hole rather than a defect.

The remedy is to turn the subset into an equality: accumulate the union of the parts and assert it
is `set(CONSTANTS)`, so an entry outside every part fails with a message naming it. Two decisions
go with it: whether the count has to match too, which catches the same entry appearing in two
parts, and whether the naming convention the test walks (`*couplings.py` holding `<PART>_COUPLINGS`)
should be asserted rather than assumed, since a part exporting its tuple under another name
currently fails with an `AttributeError` rather than a sentence.

## History

- 2026-08-24: filed by the close of
  [R-408](408-the-registry-shape-counts-places-not-parts.md), which made the list of parts in
  `registry.py`'s docstring the answer to what the registry is written in and left the tuple
  compared only one way.
- 2026-08-24: closed, with both questions answered yes. Checked again first and the numbers had
  moved: ten parts holding 67 entries rather than nine holding 62, the tenth being `logcouplings`.
  The claim survived the move, the union of the parts being exactly `set(CONSTANTS)` and the sum of
  the part lengths being 67 too, so this stayed a hole rather than a defect. The subset is now an
  equality, renamed `test_the_parts_on_disk_are_exactly_what_the_registry_reads`, with the per-part
  message kept and a stray entry reported by label. The count has to match, enforced as no label
  appearing twice in `CONSTANTS`: an entry in two parts leaves the result alone, the scan asking
  one question twice, and the check printed `68 cross-tree constant(s)` over 67 distinct couplings,
  so what a duplicate breaks is `shape.entries`, the number every mutation table in this repo opens
  by stating. Labels are the key because the earlier decline rests on them being distinct and
  nothing asserted that, and because a copy repeats its label whether or not it stayed identical.
  The convention is asserted, decided on a planted part:
  `AttributeError: module 'probecouplings' has no attribute 'PROBE_COUPLINGS'` names the attribute
  and neither the rule nor which half of it is wrong, and it arrives twice with neither failure
  being about the convention. The assertion sits in the helper every caller goes through, and
  `registry.py`'s docstring now states the convention and that `CONSTANTS` holds nothing of its
  own. Four planted mutations over the scripts suite, recorded in ADR-0042. One residue filed: the
  count is enforced by labels, so a copy that is also relabelled is two entries checking one thing
  ([R-418](418-a-relabelled-copy-of-a-coupling-is-invisible.md)).
