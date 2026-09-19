# Pixel-level screening in the body

**Status:** open, dead until a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** A capture that has to proceed with part of the screen removed rather than be
refused, over a window or a region Cortex does not own and so cannot exclude at the OS level.

The body is the only side holding the pixels before they cross the seam, so it is the only side that
could redact a region (a password field, a specific window) rather than refuse a whole capture.
Nothing in the design precludes it: the policy already lives in pure core, where a screening pass
would join it. One window is already screened, and by the OS rather than by Cortex: the overlay
sets `WDA_EXCLUDEFROMCAPTURE` on itself at setup, and the shell wires the refusing backend if that
call fails. That covers a window Cortex owns, which is why the trigger names one it does not.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index recorded it as one of three vision surfaces nothing reads, beside the
  content-addressed `AttachmentStore` and multi-monitor and DPI reporting, with nothing yet asking
  it to.
- 2026-09-13: held against the code, and the trigger this file never had recorded. The premise is
  unchanged: the body still holds the pixels alone, and the capture policy is still pure core, in
  `body_core`'s `screen_policy`, `screen_target` and `screen_image`, where a screening pass would
  sit beside it. What the pass found is the partial answer that already exists, the overlay's own
  `WDA_EXCLUDEFROMCAPTURE` exclusion, which is what a trigger has to be written around: the
  affordance covers windows Cortex owns and nothing else. It also found a cost. `screen_policy.rs`
  is 289 lines against the 300 cap, so a screening pass arrives as its own module rather than
  inside the one it extends.
- 2026-09-19: re-derived and unchanged. No commit since the last pass touched the capture path in
  `body/`: the three since then changed the turn's idle gap, one bridge comment and one stylesheet
  line. Nothing in the body crates or the shell masks, blurs or redacts pixels. The overlay's
  exclusion is still requested in the shell's `setup`, through `body_server::exclude_overlay`,
  which serves the refusing backend when `SetWindowDisplayAffinity` fails, and `screen_policy.rs`
  is still 289 lines. The trigger names an arrival a reader can observe, and it has not fired.
