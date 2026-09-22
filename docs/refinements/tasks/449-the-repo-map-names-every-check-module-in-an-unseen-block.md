# The repo map names every check module in a block no reader here could see

**Status:** done 2026-08-26
**Area:** repo-checks
**Origin:** [ADR-0044](../../adr/ADR-0044-document-rosters.md)

The `scripts/` entry of the repo map in [AGENTS.md](../../../AGENTS.md) names all forty eight
modules in the tree, each with what it does, and it names the ten registry parts among them with a
tally in front. Measured on the day this was filed, it is complete and correct. It is also checked
by nothing, and four of its names were added by the same hand that added the four modules under it.

The reader that checks the other copies takes a name from a code span, and the repo map has none:
it is a fenced block of plain text laid out in columns, where every module name is a bare word.
Making the name reader take bare words needs a third way of writing a name down, and that way is
only safe inside a bounded passage, since a bare `linecap.py` in ordinary prose would otherwise
read as a list entry wherever it appeared.

## History

- 2026-08-26: opened by the close of
  [R-413](413-the-module-contracts-part-list-is-held-by-nobody.md), which checked one copy of this
  set and left this one alone for want of a third way of writing a list down.
- 2026-08-26: closed as the module listing rule of
  [ADR-0044](../../adr/ADR-0044-document-rosters.md), which added the bare form the entry asked
  for, every whole word in a bounded passage matching the list's pattern, guarded on both edges so
  a name inside a longer word is not one. Checking again left the answer intact and corrected the
  reason. The map was complete on the day this was picked up, naming all forty eight modules and
  nothing else, each exactly once. What moved is the diagnosis: the entry says the names sit in a
  fenced block no reader here can see, and the fence turns out not to be the obstacle, since the
  passage the boundary phrases cut out has no fence marker and this reader strips none. The code
  spans were the obstacle, which the mutation run measured rather than assumed, a fence-skipping
  mutant changing nothing until it was rewritten to strip fences from the whole document first. The
  entry's own instruction to check what the shape costs the other trees was followed and answered
  by deferral: the same map names every Rust crate and every brain package in the same shape, and
  whether a repo map is checked tree by tree is a decision about that document rather than about
  this mechanism, filed as [R-450](450-the-repo-map-holds-two-more-listings-unheld.md). The tally
  in front of the registry parts stays a hand count. The same commit closed
  [R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md).
