# A third family that appends nothing either way still reads as open

**Status:** done 2026-09-02
**Area:** inference
**Origin:** [ADR-0050](../../adr/ADR-0050-live-probe-records.md)

`switchtail.py` refuses to read a switched tail that has no marker of either family it knows and
differs from the tail the same template renders with the key left alone. The second half of that
test is what makes the first half safe: the failing pick responds to the key by dropping a
`<|think|>` system turn at the front, so its tail is byte identical both ways, and refusing every
unmarked tail would refuse the one pick the module exists to read correctly.

The case the test cannot see is the other one. A template that renders one identical tail both ways
and closes its thought with an unlisted marker falls on the failing pick's side of the line and is
read as an open thought. It is not unprotected: a tail that closes the thought invites no
deliberation, so that tier's control, the same request with no switch, would fail to deliberate on
every draw and the run refuses one step later for that. The operator sees "this prompt invites no
thought here and the switch stopped nothing" where the true reading is "this reader does not know
your template", which is a failure in the wrong words rather than a result published off a guess.

## History

- 2026-08-30: opened by the close of
  [R-509](509-a-third-familys-closed-thought-reads-as-an-open-one.md), recorded as ADR-0050.
- 2026-09-02: closed, the cheap fix built and the thorough one found to have no pick to draw from.
  Checked first: the case reads exactly as described, and the wrong words stand in two places rather
  than one, since the probe's own control assertion says "invites no thought" before the reader is
  ever run. Every chat model file on the mount was read for its template's markers, 17 files across
  every ADR-0004 pick and the two Qwen3.8 entries outside the lineup, and all of them write one of
  the two listed pairs and leave the thought open with the key absent, so no third pair exists to
  add. The control refusal in `scripts/switchtail.py` is now worded off the unswitched tail, which
  was already computed and printed: a tail closed in a listed marker names the template, an open one
  names the prompt, and an unmarked one names both readings it cannot separate. The probe's
  assertion points at `just switch-tail` for the same reading. Opened
  [R-524](524-the-readers-thought-vocabulary-is-a-hand-list-held-to-nothing-the-model-files-say.md).
  Recorded as ADR-0050.
