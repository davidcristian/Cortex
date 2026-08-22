# The legibility pair is quoted in three more documents and only the compose halves are held

**Status:** open, actionable
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
