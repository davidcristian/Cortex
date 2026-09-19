# A fragment aimed anywhere but a backlog index

**Status:** done 2026-08-17
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Opened 2026-08-16 by the close of [R-273](273-index-anchor-never-checked.md), which built the
anchor half of the backlog link check and judged a fragment only when it aims at
`docs/refinements/index.md` or `docs/host/index.md`.

The population was small and not clean. The repo held 260 fragments: 251 aimed at one of the two
indexes and were checked, and the other nine were counted by hand. Eight are `README.md` linking
its own sections, all true, and the ninth was `docs/host/index.md` pointing at
`ADR-0030-brain-handoff.md#risks-flagged-for-user-review` while that heading reads "Risks flagged
for maintainer review". One broken pointer in nine, found by a person running a one-off script
rather than by any check, and corrected in the same pass.

Closed 2026-08-17 ([ADR-0039 decision 9](../../adr/ADR-0039-backlog-per-task.md)). `anchors(text)`
was already general and `check` already resolved every pointer's path, so the widening was the
input and the rule and nothing else. The counts moved with the tree and are corrected here: 389
markdown files now contain 262 fragments, 253 of them aimed at a backlog index and nine elsewhere.
The nine are the same nine. All 262 are judged now, and none is wrong.

The rule for which targets may be judged was the work: a target is judged when it is a document
this same scan reads. `markdown_files` already decides which markdown is this repo's own prose, and
that one decision is now the rule for both halves of a link, so a vendored or built tree is
invisible in both directions rather than excluded by one rule and judged by another. Judging
whatever git tracks was weighed and rejected, because the heading set is read off the working tree,
so the permission to read it should come from there too, and that rule would fail a document
written but not yet added.

The scan fails when it cannot answer. A markdown target it did not read is reported, the three
causes being a path that is missing, one outside the tree and one inside a vendored or built tree;
skipping what cannot be answered for is how the stale anchor above survived every check. One
question is left unasked rather than failed: a target whose name is not markdown, since
`body.proto#L42` is a line anchor with no headings to be wrong about.

Proved able to fail before being trusted, on the real tree in both new shapes. Renaming `## Risks
flagged for maintainer review` in `ADR-0030-brain-handoff.md` was reported at
`docs/host/index.md:602`; pointing a `README.md` fragment at a file that is not there was reported
at `README.md:34`. Both were restored and the check passed again over all 262 pointers. A problem
now names the line it is written on, which two documents did not need and 389 do.

## History

- 2026-08-16: Written down as what was left over from the backlog anchor check, which built the
  machinery and deliberately pointed it at two documents. The pass that opened it also found and
  fixed the one stale anchor of this kind in the tree.
- 2026-08-17: Closed. The scan now judges every fragment in the repo against the document it aims
  at, under a rule that judges only what this scan itself reads. It opened
  [R-292](292-slug-rule-approximates-a-renderer.md), where one regex substitutes for a renderer's
  slug rule.
