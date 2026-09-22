# The module contract names the registry's parts twice, and nothing checks either list

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

[modules/repo-checks.md](../../modules/repo-checks.md) names the nine `*couplings.py` files twice:
once in the listing of modules with no CLI near the top, and once in the `crosscheck.py` bullet,
which also gives each part's subject in a parallel list. Both are maintained by hand. A tenth part
arrives, `registry.py`'s docstring fails the suite until it names it, and this document goes on
describing nine with nothing reporting it. The two copies are already in different orders, which is
fine and is also the evidence that nobody compares them.

The open question is whether the earlier decision, that nothing may compare this document with the
registry, covers a list of names or only a list of numbers. A name list goes stale exactly when a
part is added, which is when it should fail; a tally goes stale on any edit anywhere.

## History

- 2026-08-24: filed by the close of
  [R-408](408-the-registry-shape-counts-places-not-parts.md), which compared `registry.py`'s own
  list of parts with the files on disk and left the two copies in the module contract as they were.
- 2026-08-26: closed as the roster membership rule of
  [ADR-0044](../../adr/ADR-0044-document-rosters.md), on the same mechanism that closed
  [R-442](442-nothing-holds-the-live-check-roster-to-the-suite.md), `scripts/rostercheck.py`. The
  earlier decision was answered rather than worked around: it covers a list of numbers and not a
  list of names, on this entry's own argument. Both copies are now checked, and the first one more
  widely than this entry asked. Reading it again found the parts list is part of a bigger roster:
  that paragraph names every module in `scripts/`, not only the ten `*couplings.py` files, and the
  promise it makes is that a future agent can work here without reading the tree, which breaks the
  day any module arrives unnamed. So the registered roster is the paragraph against the directory,
  and it reported the four modules this change itself added as four failures before the document
  was updated. The second copy, the tuple names in the `crosscheck.py` bullet, is checked on its
  own against the names the `<subject>couplings.py` convention gives, so no third place writes
  them. Both copies were current on the day this was picked up, ten parts in each, and both were
  still in different orders. What is deliberately still unchecked is the number of modules with no
  CLI and which half of the paragraph a module is named in, filed as
  [R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md), and a third copy of the same
  list, the `scripts/` entry of the repo map, unchecked for a different reason and filed as
  [R-449](449-the-repo-map-names-every-check-module-in-an-unseen-block.md).
