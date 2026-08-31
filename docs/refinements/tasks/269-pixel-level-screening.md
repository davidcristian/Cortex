# Pixel-level screening in the body

**Status:** open, dead until a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** unrecorded

The body is the only side holding the pixels before they cross the seam, so it is the only side that
could redact a region (a password field, a specific window) rather than refuse a whole capture.
Nothing in the design precludes it: the policy already lives in pure core, where a screening pass
would join it.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index recorded it as one of three vision surfaces nothing reads, beside the
  content-addressed `AttachmentStore` and multi-monitor and DPI reporting, with nothing yet asking
  it to.
