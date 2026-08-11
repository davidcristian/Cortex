# A pointer's anchor is never checked

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Trigger:** the first rename of an area or a sitting, or the first area whose last task moves out of it, either of which leaves every pointer aimed at a heading that is no longer rendered while the link itself still resolves.

Opened 2026-08-11 by the split that created this layout, as the half of its own link check that
the check does not reach. `backlogcheck.py` holds every relative link in a task file and in each
index to resolving to a file on disk, which is what made the migration safe: 355 pointers across
52 files changed depth at once, and a mistake in any of them would otherwise have been invisible.
What no gate reads is the **fragment**. Those same 355 pointers were retargeted onto anchors of
the form `refinements/index.md#memory`, and an anchor is only as true as the heading the roll call
renders for that area.

Today every one of them is true, and for a reason that is not a guarantee: the roll call emits one
`### <area>` heading per area, and no area is empty. Rename an area, or close and move the last
task out of one, and the heading stops being rendered while the link keeps resolving, so the
reader lands at the top of a long index with no idea which part was meant. That is the same class
of silent rot the link check exists for, caught one level short.

**What would close it.** The renderer already knows every heading it emits, so holding each
fragment that points into a backlog index against that set costs a set membership test and no new
parsing. What that would still not cover is a fragment pointing into any other document in the
repo, which is a wider scan over a wider input and a different piece of work; this task is only
the backlog's own anchors, which are the ones this layout created.
