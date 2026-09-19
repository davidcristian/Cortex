# A content-addressed `AttachmentStore`

**Status:** open, waiting for a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** Something has to read a picture after its turn ends: a reopened chat showing what the
assistant saw, a question about a capture answered from the audit trail, or the deep tier in R-266.

A reopened chat shows no evidence of what the assistant saw, and the audit line has no picture
either: for a capture that succeeded it records the tool name, the call's arguments, the trust
level, a timestamp, the identities of the call, and `result_chars`, the length of the sentence the
model was given rather than the sentence itself. Written to a file (`CORTEX_TOOLS_AUDIT_FILE`),
those fields become durable and the picture is still not among them, so a later dispute about what
a capture contained cannot be settled from the store. That is a deliberate cost. If it ever needs
paying, the shape is a content-addressed store with the message holding a reference, plus an answer
for garbage collection and a `delete` cascade.

## History

- 2026-07-18: Recorded when the vision slice was finished.
- 2026-07-19: Recorded as one of three vision surfaces nothing reads, beside multi-monitor and DPI
  reporting and pixel-level screening in the body. It is also the expensive half of sending a
  picture across a model swap, where the capability argument still says no, because no brain-tier
  candidate on the mount has a projector.
- 2026-09-13: Corrected. The entry said the audit line records dimensions, a byte count and a
  timestamp, and it records none of the first two. `LoggingAuditSink.record` writes the tool name,
  `ok`, the call's arguments, the trust level, an ISO timestamp, whichever of the call, session,
  turn, task and item identities are set, then `result_chars` on success and `error` on failure.
  The dimensions and the capture time are in the summary sentence the tool returns, which goes to
  the model and is counted rather than kept, so the gap is one field wider than the entry said.
  Zero retention is unchanged and asserted at three layers. The trigger has not occurred: nothing
  in the tree asks a capture to be reconstructible.
- 2026-09-19: Checked again, with the trigger restated. The audit record can now also be kept in a
  file: `invocation_fields` in `cortex_tools/audit.py` builds the one field set that both
  `LoggingAuditSink` and the new `JsonLinesAuditSink` write, so an operator who sets
  `CORTEX_TOOLS_AUDIT_FILE` can say durably when a capture ran, which target it asked for and how
  long its sentence was, and still not what the picture held. That file is not a consumer, since it
  keeps exactly what the log line prints. Zero retention holds at the three layers: `Message`
  refuses images on any role but `TOOL`, both session stores refuse them through `refuse_images`,
  and `EscalationSlot.snapshot` raises on one in a handoff tail. The trigger used to read
  "accountability outweighing zero retention", which names nothing a reader could observe, so it
  now names the three readers that would have to see a picture after its turn.
