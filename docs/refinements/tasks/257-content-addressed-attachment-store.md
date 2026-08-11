# A content-addressed `AttachmentStore`

**Status:** open, dead until a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** Accountability outweighing zero retention.

Today a
reopened chat shows no evidence of what the assistant saw, and the audit line records
dimensions, a byte count and a timestamp only, so a later dispute about what a capture
contained cannot be answered from the store. That is a deliberate cost, not an oversight. The
right shape if it ever needs paying is a content-addressed store with the message carrying a
reference, plus a garbage-collection answer and a `delete` cascade.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index recorded it as one of three vision surfaces nothing reads, beside
  multi-monitor and DPI reporting and pixel-level screening in the body. It added that this is also
  the expensive half of carrying a picture across a model swap, where the capability argument still
  says no, because no brain-tier candidate on the mount has a projector.
