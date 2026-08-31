# The module contract names the registry's parts twice, and nothing holds either list

**Status:** landed 2026-08-26
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-24 by the close of
[R-408](408-the-registry-shape-counts-places-not-parts.md), which held `registry.py`'s own list of
parts to the files on disk and left the two copies in the module contract as they were.

[modules/repo-gates.md](../../modules/repo-gates.md) names the nine `*couplings.py` files twice:
once in the no-CLI-module listing near the top and once in the `crosscheck.py` bullet, the second
of which also gives each part's subject in a parallel prose list. Both are hand-maintained. A
tenth part lands, `registry.py`'s docstring fails the suite until it names it, and this document
goes on describing nine with nothing reporting it. The two copies are already in different orders, the top listing not being
in read order, which is fine and is also the evidence that nobody is comparing them to anything.

**Why it was left.** The close held a module's own docstring to its own directory, which is a
tight loop. Reaching into a document in `docs/` is a different rule and it has a standing decision
in front of it: the registry-shape close declined to gate this document against the registry,
because a document describing the gate is not a far side of the gate and a tally in it goes stale
on the next row.

**What would close it.** Decide whether that standing decision covers a list of **names** or only
a list of **numbers**. The argument that it does not is that a name list goes stale exactly when a
part is added, which is when it should fail, where a tally goes stale on any edit anywhere. The
argument that it does is that this document restates what `registry.py` already declares and now
has held, so its copy is a convenience and a stale convenience is a documentation lag rather than
a lost answer. If the answer is to hold it, the cheapest shape is the one the close already used,
reading the backticked module names out of the document and requiring them to be the files on
disk, and the question is whether both copies are held or only the one that also states each
part's subject.

## Trail

- 2026-08-24: filed by the close of
  [R-408](408-the-registry-shape-counts-places-not-parts.md), which held `registry.py`'s own list
  of parts to the files on disk and left the two copies in the module contract as they were.
- 2026-08-26: landed as the
  [ADR-0029 roster-membership addendum](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-26-the-standing-decision-covers-numbers-and-not-names-so-both-lists-are-held),
  on the same mechanism that closed
  [R-442](442-nothing-holds-the-live-check-roster-to-the-suite.md), `scripts/rostercheck.py`.
  **The standing decision was answered rather than worked around**: it covers a list of numbers
  and not a list of names, on the entry's own argument, that a tally goes stale on any edit
  anywhere while a name list goes stale on exactly the edit that should make it fail. **Both copies
  are held, and the first one wider than this entry asked.** Re-derivation found the parts list is
  a run inside a bigger roster: that paragraph names every module in `scripts/`, not only the ten
  `*couplings.py` files, and the promise it makes is that a future agent can work here without
  reading the tree, which breaks the day any module lands unnamed. So the registered roster is the
  paragraph against the directory, and it reported the four modules this change itself added as
  four failures before the document was updated. The second copy, the tuple names in the
  `crosscheck.py` bullet, is held on its own against the names the `<subject>couplings.py`
  convention gives, so no third place spells them. Both copies were **current** on the day this was
  picked up, ten parts in each, the log part having been absorbed by hand, and both were still in
  different orders, which is the entry's own evidence that nobody was comparing them. What is
  deliberately still unheld is the number of modules with no CLI and which half of the paragraph a
  module is named in, filed as
  [R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), and a third copy of the same
  list, the `scripts/` entry of the repo map, which is unheld for a different reason and filed as
  [R-449](449-the-repo-map-names-every-gate-module-unheld.md).
