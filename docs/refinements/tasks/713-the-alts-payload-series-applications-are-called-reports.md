# ADR-0041 calls the alt's payload-series applications reports, and hand counts find some

**Status:** open, actionable
**Area:** vision
**Origin:** [ADR-0041](../../adr/ADR-0041-injection-image-variant.md)
**Verified:** 2026-09-23

ADR-0041's consequence on the alternative candidate says "its applied counts on the dialog's
laundering cell and in its payload series are reports". The hand counts in
[injection over pixels](../../readings/injection-over-pixels.md#the-alt-candidate) do not all agree:

- the payload series at the doubled frame on the engine budget (2026-09-19) applied the rule in 22
  of 90 draws structurally and 11 by hand;
- the two series redrawn at the engine's sampler on 2026-09-23 applied it by hand in 3 of 45 framed
  and 12 of 45 control draws at the corpus frame, and 9 of 45 framed and 6 of 44 control at the
  third frame
  ([R-695](695-an-alt-mail-control-voids-in-every-draw-at-the-engine-budget.md)).

The shipped-budget series of 2026-09-13 applied it in 3 of 90 framed draws, and the readings do not
say whether those were read by hand. So the sentence may describe only that run, or only the
structural counts the alt's bare report inflates.

**What would close it.** Read which series the sentence rests on, and edit the consequence in place
to state what the hand counts show for each series, or keep it and name the series it covers. No
redraw is needed: the replies are in the logs under `measurements/`.

## History

- 2026-09-23: opened by the write-up of the unattended run that closed
  [R-695](695-an-alt-mail-control-voids-in-every-draw-at-the-engine-budget.md), whose hand counts
  found applications in both of the alt's payload series.
