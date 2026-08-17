# A fragment aimed anywhere but a backlog index

**Status:** landed 2026-08-17
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Opened 2026-08-16 by the close of [R-273](273-index-anchor-never-checked.md), which built the
anchor half of the backlog link check and drew its boundary at the target: a fragment is judged
when it aims at `docs/refinements/index.md` or `docs/host/index.md`, and ignored when it aims at
anything else. That was the right scope for that task, and it leaves this.

**The population is small and it is not clean.** The repo holds 260 fragments. 251 aim at one of
the two indexes and are now gated. The other nine were counted by hand while that gate was being
written: eight are `README.md` linking its own sections, all of them true, and the ninth was
`docs/host/index.md` pointing at `ADR-0030-brain-handoff.md#risks-flagged-for-user-review` while
that heading reads **Risks flagged for maintainer review**. One rot in nine, sitting in the tree,
found by a person running a one-off script rather than by any gate. It was corrected in the same
pass, so the count of known-bad fragments is zero and the count of gated ones is still 251.

**What would close it.** `backloganchors.py` already has every part except the input.
`anchors(text)` answers for any markdown document rather than only for an index, and `check`
already walks every markdown file under the root and resolves each pointer's path; what it does
today is look that resolved path up in a two-entry map and skip a miss. Widening it means reading
the headings of whatever document a pointer lands on, which is one extra read per distinct target
and a cache keyed by path.

**Why it was not done in the same pass**, beyond scope. The anchor set of a backlog index is known
exactly, because the gate renders it, while the anchor set of an arbitrary document is whatever a
renderer would make of the file on disk, so the check becomes an assertion about a file this repo
does not generate. That is fine for prose the repo writes and wrong for anything vendored or
generated, so the widening needs a rule for which targets it may judge, and nine pointers is a
thin case for writing one. What makes it worth keeping open is the ninth: the heading it aimed at
was renamed by the pass that took every person out of this repo's prose, which is exactly the kind
of sweeping edit that breaks anchors in bulk and would leave this gate silent.

**Closed 2026-08-17** ([ADR-0039 repo-wide-anchor addendum](../../adr/ADR-0039-backlog-per-task.md)).
The mechanism above was re-derived first and held: `anchors(text)` was already general, and `check`
already resolved every pointer's path, so the widening was the input and the rule and nothing else.
The counts moved with the tree and are corrected here rather than above, since what a task file
records is what somebody once measured. **389 markdown files now carry 262 fragments, 253 of them
aimed at a backlog index and nine elsewhere.** The nine are the same nine: eight `README.md`
self-links and the host index's one pointer into that decision record, corrected on the day this
file was written and still correct. All 262 are judged now, and none is wrong.

**The rule for which targets may be judged was the work**, and it is that a target is judged when
it is a document this same scan reads. `markdown_files` already decides which markdown is this
repo's own prose, and that one decision is now the rule for both halves of a link, so a vendored
or built tree is invisible in both directions instead of being excluded by one rule and judged by
another. Judging whatever git tracks was weighed and rejected: the heading set is read off the
working tree, so the permission to read it should come from there too, and gating on the index
would fail a document written but not yet added. Judging everything under the root is this rule
without the exclusion, which is the overreach the paragraph above warned about.

The scan fails closed, as the others here do. A markdown target it did not read is reported, the
three causes being a path that is missing, one outside the tree and one inside a vendored or built
tree; skipping what cannot be answered for is precisely how the stale anchor in this file's own
account survived every gate. One question is left unasked rather than failed open: a target whose
name is not markdown, since `body.proto#L42` is a line anchor and has no headings to be wrong
about.

**Proved able to fail before being trusted**, on the real tree in both new shapes. Renaming
`## Risks flagged for maintainer review` in `ADR-0030-brain-handoff.md`, which is the rot this
whole line of work started from, was reported at `docs/host/index.md:602`; pointing a `README.md`
fragment at a file that is not there was reported at `README.md:34`. Both were restored and the
gate returned to green over all 262 pointers. A problem now names the line it is written on, which
two documents did not need and 389 do.

## Trail

- 2026-08-16: written down as the residual of the backlog anchor check, which built the machinery
  and deliberately pointed it at two documents. The pass that opened it also found and fixed the
  one stale anchor of this kind in the tree.
- 2026-08-17: closed. The scan now judges every fragment in the repo against the document it aims
  at, under a rule that judges only what this scan itself reads, and reports rather than skips a
  markdown target outside that set. It opened [R-292](292-slug-rule-approximates-a-renderer.md),
  which is the one regex standing in for a renderer's slugger and the heading shapes where the two
  would disagree.
