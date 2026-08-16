# A fragment aimed anywhere but a backlog index

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0039](../../adr/ADR-0039-backlog-per-task.md)
**Trigger:** the second stale anchor of this kind, or any pass that renames headings across the decision records, either of which makes a scan cheaper than a reread.

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

## Trail

- 2026-08-16: written down as the residual of the backlog anchor check, which built the machinery
  and deliberately pointed it at two documents. The pass that opened it also found and fixed the
  one stale anchor of this kind in the tree.
