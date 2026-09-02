# Nine rows of the rendering column are still hand readings

**Status:** landed 2026-09-02
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)

Opened 2026-08-30 by the close of
[R-499](499-the-rendering-predictor-is-asserted-nowhere.md), which built the reader that publishes
a row and then ran it over two of the eleven.

[ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)'s lineup section carries a table of eleven chat
entries with a column reading "its template's answer to do not think", and the claim under it is
that the column predicts the constrained verdict on **all eleven**. Every one of those rows was
read by hand off a `POST /apply-template` response during one sweep on `b10644-d7a207411`, and the
rendering itself was never written down: what the table keeps is a three word summary of each tail.
`just switch-tail` now publishes that comparison from a sample, and two rows have been through it,
Qwen3.5-0.8B and gemma-4-E4B on `b10680-d7bd3bfca`. The other nine have not.

So the record's strongest claim about this rule rests on a reading nobody can re-check without
re-running the sweep, and the machinery that would check it exists and is idle.

**Why it was left.** The reader landed with the entry that built it, and running the lineup is a
sweep rather than a task: eleven servers, five draws a cell, four cells each, with the larger picks
needing the card. The two picks measured were chosen because they sit on opposite sides of the
column that splits, which is what a new instrument needs and is not what a record needs.

**What would close it.** The remaining nine entries run through the committed probe at five draws a
cell with neither reasoning flag, each published through `just switch-tail`, and the lineup table
gaining the tail each row's verdict was really read off rather than a summary of it. Two smaller
things belong in the same pass. The rows measured at a quant this ADR does not name should be
recorded as such where the sample is kept, since the substitution is already noted in the table and
would otherwise be lost. And the split cell should be watched rather than averaged: the E4B's
constrained arm has now measured 4 of 5, 5 of 5 and 5 of 5 across three builds, which is one cell
with a rate rather than a constant, and the reader deliberately treats any deliberating draw as the
open tail's prediction coming true.

## Trail

- 2026-08-30: opened by the close of
  [R-499](499-the-rendering-predictor-is-asserted-nowhere.md), whose ADR-0005 rendered-tail
  addendum published two rows of this column through the new reader and left nine hand read.

- 2026-09-02: landed. Re-derived first: the nine rows stood exactly as described, three words a row
  read by hand on `b10644`, and the one thing the entry had wrong was where a sample is kept, since
  `measurements/` is gitignored by design and the place a row is recorded is the ADR itself. All
  nine picks were on the mount. Each was served alone on `b10680-d7bd3bfca` with neither reasoning
  flag, drawn five times a cell through the committed probe and published through
  `just switch-tail`: nine agreed at exit 0, every control on 5 of 5, every verdict the hand
  reading's. The lineup table's column now carries the tail each verdict was read off, the E4B's
  constrained arm is written as a rate, 14 of 15 across three builds, and the two quant
  substitutions are recorded in the addendum's artifact column and in the samples' names. The three
  `-ngl 0` rows were read on the card after the CPU image decoded the E2B at under two tokens a
  second on the night, which is recorded rather than hidden. Opened
  [R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md), the
  sample naming no build, and
  [R-529](529-the-rendering-column-is-one-builds-sweep-and-an-engine-bump-reopens-it.md), the
  engine bump that reopens every row and the loop that is a scratch file. Recorded as the ADR-0005
  lineup-tails addendum.
