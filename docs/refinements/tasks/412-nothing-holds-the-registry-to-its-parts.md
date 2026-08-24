# The parts are held to the tuple and the tuple is held to nothing

**Status:** open, actionable
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
