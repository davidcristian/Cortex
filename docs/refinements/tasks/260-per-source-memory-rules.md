# Per-source memory rules for vision turns

**Status:** declined 2026-08-16
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Proposed: per-source memory rules, so a vision turn can be remembered deliberately. An opaque turn
is dropped from durable memory outright, which is the safe default and a blunt one, since "remember
that my invoice number is 4021" after a capture is lost. A per-source policy (this source may be
recorded, that one may not) is the general fix, and it belongs with the per-provenance rules under
[untrusted-content.md](../index.md#untrusted-content).

Declined, because a per-source rule has to name a source and this boundary deliberately sends no
name. `describe` deliberately includes no window title and no application name, both being
attacker-chosen strings, and a caption assembled from them would be the one part of an untrusted
screen arriving outside the picture
([screen_tool.py](../../../brain/packages/core/src/cortex_core/screen_tool.py)). The only
source-shaped value on the wire is `CaptureTarget`, a closed two-value enum of what was pointed at,
and the proto states that the reply gives the resolved target and not the rectangle
([body.proto](../../../proto/body.proto)). That is a resolution rule rather than an identity, and a
memory policy over it would say "remember whole-display captures but not focused-window ones",
which does not answer this entry's own example: either target can be showing a password manager.

It does not reach the write anyway. The `ScreenCapture` value that holds `target` is turned into
prose at the tool boundary and no field on `ToolResult` passes it on, so the record notes the same
`Provenance(TOOL, "capture_screen")` for both targets, and `record_exchange` sees only the opaque
bit, the taint bit, the query and the reply
([turn_output.py](../../../brain/packages/core/src/cortex_core/turn_output.py)). A per-source rule
would therefore need an identifier added to the capture boundary first, which is the decision the
origin already made in the other direction.

The loss this entry names is real and needs no source at all: the sentence that goes missing is the
user's own, and the user's own words are the one thing on a capture turn an attacker cannot write.
`render_exchange` renders both halves and the opaque check skips the whole write, so the user's
half is collateral. That is [286](286-user-half-of-an-opaque-turn.md), a smaller and better-aimed
change.

It reopens on one thing: a capture-boundary field that names a source on the operating system's
word rather than the screen's, at which point the question is a policy over an attested identity
and no longer this entry.

## History

- 2026-07-18: Recorded when the vision slice was finished, as one of four vision entries deferred
  until they cause a problem.
- 2026-08-09: A review of those entries against the code found that none had.
- 2026-08-16: Declined, on the findings above, and it opened
  [286](286-user-half-of-an-opaque-turn.md). Recorded at the origin decision.
