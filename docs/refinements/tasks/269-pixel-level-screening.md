# Pixel-level screening in the body

**Status:** open, waiting for a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** A capture that has to go ahead with part of the screen removed rather than be refused,
over a window or a region Cortex does not own and so cannot exclude at the OS level.

The body is the only side holding the pixels before they cross the wire, so it is the only side
that could redact a region (a password field, a specific window) rather than refuse a whole
capture. Nothing in the design prevents it: the policy already lives in pure core, where a
screening pass would join it. One window is already excluded, by the OS rather than by Cortex: the
overlay sets `WDA_EXCLUDEFROMCAPTURE` on itself at setup, and the shell wires the refusing backend
if that call fails. That covers a window Cortex owns, which is why the trigger names one it does
not.

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-07-19: Recorded as one of three vision surfaces nothing reads, beside the content-addressed
  `AttachmentStore` and multi-monitor and DPI reporting.
- 2026-09-13: Checked against the code, and the trigger written for the first time. The body still
  holds the pixels alone, and the capture policy is still pure core, in `body_core`'s
  `screen_policy`, `screen_target` and `screen_image`. The overlay's own
  `WDA_EXCLUDEFROMCAPTURE` exclusion is the partial answer that already exists, and it covers
  windows Cortex owns and nothing else. `screen_policy.rs` is 289 lines against the 300-line cap,
  so a screening pass arrives as its own module.
- 2026-09-19: Checked again and unchanged. No commit since touched the capture path in `body/`, and
  nothing in the body crates or the shell masks, blurs or redacts pixels. The overlay's exclusion
  is still requested in the shell's `setup`, through `body_server::exclude_overlay`, which serves
  the refusing backend when `SetWindowDisplayAffinity` fails, and `screen_policy.rs` is still 289
  lines. The trigger has not occurred.
