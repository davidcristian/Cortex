# Multi-monitor and DPI reporting

**Status:** open, dead until a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** anything that enumerates monitors, which nothing does yet, and it arrives with a body that honours the field rather than ahead of one.

v1 is the primary display only, in physical pixels.
Nothing enumerates monitors yet, which is why no field names one.
**Corrected 2026-08-10:** this entry used to say `CaptureScreenRequest` *reserves field 2* for a
display index. It does not any more. Field 2 was held by a comment rather than by a protobuf
`reserved` statement, and the capture target spent it, on the argument that a target subsumes
the ask the number was being kept for. A display index needs the next free number when it
arrives, and it arrives with a body that honours it, which is the rule that put the target and
its Z-order walk in one commit. The focus target also gives this entry a first observable
consequence: a focused window on a second monitor resolves to a rectangle with nothing on the
captured display, so it answers `NoTarget` rather than a wrong picture.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index recorded it as one of three vision surfaces nothing reads, beside the
  content-addressed `AttachmentStore` and pixel-level screening in the body, and named its consumer
  as the one region capture was already waiting for.
- 2026-08-10: corrected. The clause naming `CaptureScreenRequest`'s unassigned field 2 as the
  evidence was wrong, since the capture target spent that number, a target subsuming the ask the
  comment was holding it for, so a display index takes the next free one and arrives with a body
  that honours it. `display_index` is counted here rather than on the region and window capture
  entry, which stopped naming it the same day.
