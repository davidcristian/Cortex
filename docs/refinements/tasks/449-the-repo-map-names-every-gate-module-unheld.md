# The repo map names every gate module in a block no reader here can see

**Status:** landed 2026-08-26
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-26 by the close of
[R-413](413-the-module-contracts-part-list-is-held-by-nobody.md), which registered the Public
contract paragraph of [modules/repo-gates.md](../../modules/repo-gates.md) as a roster over every
module in `scripts/` and left a third copy of that same set alone.

The `scripts/` entry of the repo map in [AGENTS.md](../../../AGENTS.md) names all forty eight
modules in the tree, each with what it holds, and it names the ten registry parts among them with
a tally in front of them. Measured on the day this was filed, it is complete and correct. It is
also held by nothing, and four of its names were added by the same hand that added the four
modules under it.

**Why it was left.** The reader that holds the other copies takes a name from a **code span**, and
the repo map has none: it is a fenced block of plain text laid out in columns, where every module
name is a bare word. Making the name reader take bare words needs a third way of writing a name down,
and that way is only safe inside a bounded passage, since a bare `linecap.py` in ordinary prose
would otherwise read as a roster entry wherever it appeared. That is a real design decision rather
than a line of code, and it was not the decision either closing entry was about.

**What would close it.** A third way of writing a roster down, bare names matching a pattern
inside a passage, plus one registry entry bounding the repo map's `scripts/` entry against the
lines above and below it. Check what that costs the other trees first: the same repo map names
every Rust crate and every brain package in the same shape, so the shape that lands here decides
whether those become rosters too or stay prose. The tally in front of the parts stays a hand count
either way, under the standing decision that a document's numbers are its own business.

## Trail

- 2026-08-26: opened by the close of
  [R-413](413-the-module-contracts-part-list-is-held-by-nobody.md), which held one copy of this set
  and left this one alone for want of a third way of writing a roster down.
- 2026-08-26: landed as the
  [ADR-0029 addendum on holding that listing in halves](../../adr/ADR-0029-vision-screen-capture.md#addendum-2026-08-26-the-module-listing-is-held-in-halves-and-the-repo-maps-copy-is-held-too),
  which added the bare spelling the entry asked for, every whole word in a bounded passage matching
  the roster's pattern, guarded on both edges so a name inside a longer word is not one.
  **Re-derivation left the answer standing and corrected the reason.** The map was complete on
  the day this was picked up, naming all forty eight modules and nothing else, each exactly once.
  What
  moved is the diagnosis: the entry says the names sit in a fenced block no reader here can see,
  and the fence turns out not to be the obstacle at all, since the passage the boundary phrases cut
  out carries no fence marker and this reader strips none. The code spans were the obstacle, which
  the mutation run measured rather than assumed, a fence-skipping mutant changing nothing until it
  was rewritten to strip fences from the whole document first. The entry's own instruction to check
  what the shape costs the other trees was followed and answered by deferral: the same map names
  every Rust crate and every brain package in the same shape, and whether a repo map is held tree by
  tree is a decision about that document rather than about this mechanism, filed as
  [R-450](450-the-repo-map-holds-two-more-listings-unheld.md). The tally in front of the registry
  parts stays a hand count either way, as this entry asked. The same commit closed
  [R-448](448-the-module-listing-is-held-whole-and-not-in-halves.md).
