# Three more documents write the legibility pair and only the compose comments are checked

**Status:** done 2026-08-23
**Area:** repo-checks
**Origin:** [ADR-0042](../../adr/ADR-0042-cross-tree-constant-registry.md)

The legibility pair is `1024` image tokens on the model host and a `2048` px capture edge on the
brain. [R-377](377-a-comment-restates-a-registered-value.md) registered the two compose comments
that name the other file's half of the pair. Several other files write the same numbers and were
not registered: [runbooks/vision.md](../../runbooks/vision.md) writes
`CORTEX_IMAGE_MAX_TOKENS=1024` three times, [runbooks/llamacpp-gpu.md](../../runbooks/llamacpp-gpu.md)
writes it in the copyable recipe and in two rows of the measured table, and
[modules/brain-model-manager.md](../../modules/brain-model-manager.md) writes
`CORTEX_BODY_CAPTURE_MAX_EDGE=2048` once.

They were left out because prose that explains a number is usually not registered: a search text
over a clause inside an explanation fixes the wording as much as the number, so rewording the
explanation would fail the check even though nothing moved. The two comments that were registered
state what the deployment does rather than explain it. The work left was to sort the rest by that
test and write the sorting down.

## History

- 2026-08-22: opened by the close of
  [R-377](377-a-comment-restates-a-registered-value.md), which settled that a comment is just
  another place a value appears, registered the two comments that state a deployment's own
  pairing, and left the prose around them unsorted.
- 2026-08-23: closed, and the survey found much more than this file predicted: the two numbers
  appear 49 times in 14 files outside the decision records and the backlog, not five times in
  three. After sorting, the token budget went from three registered places to ten and the capture
  edge from four to thirteen, and the edge gained a second declaring file in the other tree
  (`BRAIN_EDGE` in `body/crates/core/tests/capture_bytes.rs`, which measures byte-ceiling headroom
  at the edge the brain asks for). Registered: both environment table cells of the GPU runbook's
  row, the recipe block under it, the vision runbook's three claims about what ships, both
  declaring files' own prose, both compose overrides' comments about their own default, the three
  module contracts, and the capture check in `docs/host/`. Left out as records of a past
  measurement: every measured variant, cost and reservation row, each true of the value it was
  taken at. Two search-text shapes keep that sorting without fixing a sentence: the recipe is
  matched at the start of a line, because the measured table below it repeats the same text inside
  a cell, and a counted match treats a file's several claims about one shipped number as one set.
  Seventeen planted changes each made the check fail and four rewritten history sentences each
  left it passing. The reading of `docs/host/` that the companion entry called a judgement call is
  settled here: a host file is a live instruction and not a record, because a completed check's
  file shrinks to a heading, its status and a pointer. Recorded in ADR-0042, in
  [modules/repo-checks.md](../../modules/repo-checks.md) and in
  [modules/body-core.md](../../modules/body-core.md). Two narrower entries open in its place:
  [387](387-a-second-occurrence-shares-a-line-the-registry-covers.md) and
  [388](388-the-headroom-suite-writes-its-declared-edge-four-more-times.md).
