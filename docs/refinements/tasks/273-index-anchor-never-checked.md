# A pointer's anchor is never checked

**Status:** landed 2026-08-16
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Opened 2026-08-11 by the split that created this layout, as the half of its own link check that
the check does not reach. `backlogcheck.py` holds every relative link in a task file and in each
index to resolving to a file on disk, which is what made the migration safe: 355 pointers across
52 files changed depth at once, and a mistake in any of them would otherwise have been invisible.
What no gate reads is the **fragment**. Those same 355 pointers were retargeted onto anchors of
the form `refinements/index.md#memory`, and an anchor is only as true as the heading the roll call
renders for that area.

Today every one of them is true, and for a reason that is not a guarantee: the roll call emits one
`### <area>` heading per area, and no area is empty. Rename an area, or close and move the last task
out of one, and the heading stops being rendered while the link keeps resolving, so the reader lands
at the top of a long index with no idea which part was meant. That is the same class of silent
breakage the link check exists for, caught one level short.

**What would close it.** The renderer already holds every heading it emits, so holding each fragment
that points into a backlog index against that set costs a set membership test and no new parsing.
What that would still not cover is a fragment pointing into any other document in the repo, which is
a wider scan over a wider input and a different piece of work; this task is only the backlog's own
anchors, which are the ones this layout created.

**Closed 2026-08-16** ([ADR-0039 anchor addendum](../../adr/ADR-0039-backlog-per-task.md)). The
mechanism above was re-derived from the tree first and held exactly: `local_links` split each
target on `#` and returned the path, so a fragment could neither break resolution nor be read, and
the roll call's only per-area heading was the `### <group>` line the reader is aimed at. Two
numbers in this file did not survive the re-derivation and are corrected here rather than above,
since what a task file records is what somebody once measured. **355 was the count of links the
migration moved, not of anchors.** The pointers aiming at a heading in one of the two indexes
number 251, and the split matters more than the total: only 77 of them are written inside the
backlog, and the other 174 live in decision records, runbooks and module docs.

That split decided the scope. Holding only the backlog's own files would have left the majority of
these pointers unguarded while the gate passed, so the scan reads every markdown file under the root
and judges a fragment only when it aims at one of the two indexes. The anchor set is read off the
**spliced** index, the hand-written halves wrapped around the freshly rendered block, which is the
document `just backlog` is about to require on disk, so no second list of headings has to be kept in
step with the renderer and the hand-written half's own headings are covered for free.
`backloganchors.py` holds all of it, together with the link parsing that moved out of `backlog.py`
under the line cap.

**Proved able to fail before being trusted**, on a copy of the real tree, in the five ways this
gate is meant to catch: an area renamed, an area emptied by moving its last tasks out, a rename
whose pointers turned out to live in two task files as well as in two decision records, a renamed
host sitting, and a renamed hand-written heading the host index links to from within itself. Every
one of them exits 1 naming the file, the pointer and the index; the same tree exits 0 unchanged.

What stays out of scope is the sentence this file already wrote: a fragment aimed at any document
that is not a backlog index. That is [R-276](276-repo-wide-anchor-check.md), and counting its
population turned up the one stale anchor of that kind in the tree, `docs/host/index.md` aiming at
`ADR-0030-brain-handoff.md#risks-flagged-for-user-review` against a heading that reads **Risks
flagged for maintainer review**. It is fixed, and it is the best argument the residual has: the
rename that broke it was the pass that took every person out of this repo's prose, which is the
shape of edit that breaks anchors in bulk.

## Trail

- 2026-08-11: written down by the migration that created the layout, as the half of its own link
  check the check does not reach.
- 2026-08-16: closed. It became `backloganchors.py` and a fifth failure in the backlog gate,
  scanning every markdown file in the repo for fragments aimed at either index and judging them
  against the headings that index renders. It opened
  [R-276](276-repo-wide-anchor-check.md), which is the wider scan this file
  deliberately excluded and now has the machinery for.
