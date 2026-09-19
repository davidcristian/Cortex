# A pointer's anchor is never checked

**Status:** done 2026-08-16
**Area:** repo-checks
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)

Opened 2026-08-11 by the split that created the one-file-per-task layout. `backlogcheck.py`
requires every relative link in a task file and in each index to resolve to a file on disk, which
is what made the migration safe. What nothing checked is the fragment. Those pointers were aimed at
anchors of the form `refinements/index.md#memory`, and an anchor is only as true as the heading the
index renders for that area. Rename an area, or close and move the last task out of one, and the
heading stops being rendered while the link still resolves, so the reader arrives at the top of a
long index with no idea which part was meant.

Closed 2026-08-16 ([ADR-0039 decision 9](../../adr/ADR-0039-backlog-per-task.md)). Two numbers in
this file did not survive being checked again and are corrected here: 355 was the count of links
the migration moved, not of anchors. The pointers aiming at a heading in one of the two indexes
number 251, and only 77 of them are written inside the backlog, while the other 174 live in
decision records, runbooks and module docs.

That split decided the scope. Checking only the backlog's own files would have left most of these
pointers unchecked, so the scan reads every markdown file under the root and judges a fragment only
when it aims at one of the two indexes. The anchor set is read off the index as it will be written,
the hand-written halves wrapped around the freshly rendered block, so no second list of headings
has to be kept in step with the renderer and the hand-written headings are covered too.
`backloganchors.py` holds all of it, together with the link parsing that moved out of `backlog.py`
under the line cap.

Proved able to fail before being trusted, on a copy of the real tree, in five ways: an area
renamed, an area emptied by moving its last tasks out, a rename whose pointers turned out to live
in two task files as well as two decision records, a renamed host entry, and a renamed hand-written
heading the host index links to from within itself. Each exits 1 naming the file, the pointer and
the index; the same tree exits 0 unchanged.

Out of scope is a fragment aimed at any document that is not a backlog index, which is
[R-276](276-repo-wide-anchor-check.md). Counting that population turned up the one stale anchor of
that kind in the tree: `docs/host/index.md` aimed at
`ADR-0030-brain-handoff.md#risks-flagged-for-user-review` against a heading that reads "Risks
flagged for maintainer review". It is fixed, and it is the best argument for doing the wider scan,
since the rename that broke it was the pass that took every named person out of this repo's prose.

## History

- 2026-08-11: Written down by the migration that created the layout, as the half of its own link
  check that the check does not reach.
- 2026-08-16: Closed. It became `backloganchors.py` and a fifth failure in the backlog check, and
  it opened [R-276](276-repo-wide-anchor-check.md).
