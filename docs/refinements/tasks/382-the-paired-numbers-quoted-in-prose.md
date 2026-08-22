# The legibility pair is quoted in three more documents and only the compose halves are held

**Status:** landed 2026-08-23
**Area:** repo-gates
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-08-22 by the close of
[R-377](377-a-comment-restates-a-registered-value.md), which held the two compose comments that
name the other file's half of the measured legibility pair. The pair is `1024` image tokens on the
model host and a `2048` px capture on the brain, and it is written out in five more places than
the two that closed.

**Where it is still loose.** [runbooks/vision.md](../../runbooks/vision.md) writes
`CORTEX_IMAGE_MAX_TOKENS=1024` three times, once inside the capture edge's own env row, once in
the paragraph costing a picture and once in the legibility finding that names both numbers
together. [runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md) writes it in the recipe block
a reader copies and again in two rows of the measured table. [modules/brain-model-manager.md](../../modules/brain-model-manager.md)
writes `CORTEX_BODY_CAPTURE_MAX_EDGE=2048` in the sentence explaining why the budget is raised. A
mention is a presence check, so each of those files needs at most one needle per value, which
makes this three or four rows rather than eight.

**Why it was left.** The compose survey's rule is that prose arguing with a number is eligible and
mostly unregistered, because a needle over a clause inside an argument pins the argument's
phrasing as much as the number, and rewording an explanation would then redden a gate about a
coupling that never moved. The two comments that closed are statements of what the deployment does
rather than arguments about it, which is what earned them a row. Some of these five are the same
shape (the runbook's recipe block is a copyable statement) and some are plainly not (a table row
recording a measured arm is history, and history is never a far side).

**What would close it.** Read the five, sort each by the survey's own tense test, and register the
ones that state rather than argue, with a needle written to pin the number and not the sentence
around it. The ones that argue stay out, and the sorting is the deliverable either way: what this
task must not leave behind is another reading nobody wrote down.

## Trail

- 2026-08-22: opened by the close of
  [R-377](377-a-comment-restates-a-registered-value.md), which settled that a comment is a place a
  value appears and not a form or a spelling, registered the two that state a deployment's own
  pairing, and deliberately left the prose that argues for it unsorted.
- 2026-08-23: landed. The survey ran wider than this file: the two numbers are spelled 49 times in
  14 files outside the decision records and the backlog, not five times in three. Sorted by the
  tense test, the token budget went from three registered far sides to ten and the capture edge
  from four to thirteen, and the edge gained a second declaring site in the other tree
  (`BRAIN_EDGE` in `body/crates/core/tests/capture_bytes.rs`, which measures byte-ceiling headroom
  at the edge the brain asks for). Held: both env table cells of the GPU runbook's row, the recipe
  block under it, the vision runbook's three claims about what ships, both declaring files' own
  prose, both compose overrides' comments about their own default, the three module contracts, and
  the capture check in `docs/host/`. Left out as history: every measured arm, cost and reservation
  row, each true of the value it was taken at. Two needle shapes carry that sort without pinning a
  sentence: the recipe is pinned at a line start, since the measured table below it writes the same
  text inside a cell, and the counted mentions hold a file's several claims about one shipped
  number as one set. Seventeen planted drifts each reddened the gate and four rewritten history
  sentences each left it green. The reading of `docs/host/` that this entry's neighbour called a
  judgement call is settled here and shared with it: a host file is a live instruction and not a
  record, because a completed check's file shrinks to a heading, its status and a pointer. Recorded
  in the ADR-0029 legibility-prose addendum, in
  [modules/repo-gates.md](../../modules/repo-gates.md) and in
  [modules/body-core.md](../../modules/body-core.md). Two narrower entries open in its place:
  [387](387-a-second-spelling-shares-a-held-line.md) and
  [388](388-the-headroom-suite-spells-its-own-constant.md).
