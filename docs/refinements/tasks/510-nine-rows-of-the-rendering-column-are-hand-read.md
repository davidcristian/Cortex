# Nine rows of the rendering column are still hand readings

**Status:** done 2026-09-02
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

[ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)'s lineup section has a table of eleven chat
entries with a column reading "its template's answer to do not think", and the claim under it is
that the column predicts the constrained result on all eleven. Every one of those rows was read by
hand off a `POST /apply-template` response during one measurement on `b10644-d7a207411`, and the
rendering itself was never written down: what the table keeps is a three-word summary of each tail.
`just switch-tail` now publishes that comparison from a sample, and two rows have been through it,
Qwen3.5-0.8B and gemma-4-E4B on `b10680-d7bd3bfca`. The other nine have not.

So the record's strongest claim about this rule rests on a reading nobody can re-check without
repeating the whole measurement, and the machinery that would check it exists and is idle. Running
the lineup is eleven servers, five draws a cell, four cells each, with the larger picks needing the
card.

## History

- 2026-08-30: opened by the close of
  [R-499](499-the-rendering-predictor-is-asserted-nowhere.md), whose close (ADR-0050) published two
  rows of this column through the new reader and left nine read by hand.
- 2026-09-02: closed. Checked first: the nine rows stood exactly as described, three words a row
  read by hand on `b10644`, and the one thing the entry had wrong was where a sample is kept, since
  `measurements/` is gitignored by design and the place a row is recorded is the ADR itself. All
  nine picks were on the mount. Each was served alone on `b10680-d7bd3bfca` with neither reasoning
  flag, drawn five times a cell through the committed probe and published through `just switch-tail`:
  nine agreed at exit 0, every control on 5 of 5, every result the hand reading's. The lineup
  table's column now has the tail each result was read off, the E4B's constrained cell is written as
  a rate, 14 of 15 across three builds, and the two quant substitutions are recorded in the
  measurement's artifact column and in the samples' names. The three `-ngl 0` rows were read on the
  card after the CPU image decoded the E2B at under two tokens a second, which is recorded rather
  than hidden. Opened
  [R-528](528-a-switch-sample-names-the-model-the-operator-typed-and-no-engine-build.md) and
  [R-529](529-the-rendering-column-is-one-builds-measurement.md). Recorded
  as ADR-0050.
