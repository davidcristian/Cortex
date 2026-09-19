# A content-addressed `AttachmentStore`

**Status:** open, dead until a consumer
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Verified:** 2026-09-19
**Trigger:** Something has to read a picture after its turn ends: a reopened chat showing what the
assistant saw, a question about a capture answered from the audit trail, or R-266's deep tier.

Today a reopened chat shows no evidence of what the assistant saw, and the audit line carries no
picture either: for a capture that succeeded it records the tool name, the call's arguments, the
trust level, a timestamp, the identities of the call, and `result_chars`, which is the length of
the sentence the model was given rather than the sentence. Kept in a file
(`CORTEX_TOOLS_AUDIT_FILE`), those fields become durable, and the picture is still not among them.
So a later dispute about what a capture contained cannot be answered from the store. That is a
deliberate cost. The right shape if it ever needs paying is a content-addressed store with the
message carrying a reference, plus a garbage-collection answer and a `delete` cascade.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed.
- 2026-07-19: the index recorded it as one of three vision surfaces nothing reads, beside
  multi-monitor and DPI reporting and pixel-level screening in the body. It added that this is also
  the expensive half of carrying a picture across a model swap, where the capability argument still
  says no, because no brain-tier candidate on the mount has a projector.
- 2026-09-13: corrected. The entry said the audit line records dimensions, a byte count and a
  timestamp, and it records none of the first two. `LoggingAuditSink.record` writes the tool name,
  `ok`, the call's arguments, the trust level, an ISO timestamp and whichever of the call,
  session, turn, task and item identities are set, then `result_chars` on success and `error` on
  failure. The dimensions and the capture time the entry was thinking of are in the summary
  sentence the tool returns, which goes to the model and is counted rather than kept, so the
  retention gap this entry describes is one field wider than it said. Zero retention itself is
  unchanged and asserted at three layers, which the user-attached image entry re-derived the same
  day. The trigger has not fired: nothing in the tree asks a capture to be reconstructible.
- 2026-09-19: re-derived, with the trigger restated. Since the last pass the audit record can also
  be kept in a file: `invocation_fields` in `cortex_tools/audit.py` now builds the one field set
  that both `LoggingAuditSink` and the new `JsonLinesAuditSink` write, so an operator who sets
  `CORTEX_TOOLS_AUDIT_FILE` can say durably when a capture ran, which target it asked for and how
  long its sentence was, and still not what the picture held. That file is not a consumer, since it
  keeps exactly what the log line prints. Zero retention holds at the three layers: `Message`
  refuses images on any role but `TOOL`, both session stores refuse them through `refuse_images`,
  and `EscalationSlot.snapshot` raises on one in a handoff tail. The trigger read "accountability
  outweighing zero retention", which names nothing a reader could observe happening. It now names
  the three readers that would have to see a picture after its turn. One of them is the swap
  entry's expensive half, whose own trigger used to wait on this store, so each entry waited on the
  other; that entry now names a demand instead.
