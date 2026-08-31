# Per-source memory rules for vision turns

**Status:** declined 2026-08-16
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Per-source memory rules, so a vision turn can be remembered deliberately. An opaque turn is
dropped from durable memory outright, which is the safe default and a blunt one: "remember that
my invoice number is 4021" after a capture is lost. A per-source policy (this source may be
recorded, that one may not) is the general fix, and it belongs with the per-provenance rules
already recorded under [untrusted-content.md](../index.md#untrusted-content).

**Declined, because a per-source rule has to name a source and this seam refuses to carry a name,
on purpose.** `describe` is documented as deliberately carrying no window title and no application
name, both being attacker-chosen strings and a caption assembled from them being the one part of an
untrusted screen that would arrive outside the picture
([screen_tool.py](../../../brain/packages/core/src/cortex_core/screen_tool.py)); the origin says
the same in its own words. The only source-shaped value that crosses the wire is `CaptureTarget`,
a closed two-value enum of what was pointed at, and the proto is explicit that the reply carries
the resolved target and not the rectangle it resolved to
([body.proto](../../../proto/body.proto)). That is a resolution rule, not an identity, and a
memory policy written over it would say "remember whole-display captures but not focused-window
ones", which does not answer this entry's own example: either target can be showing a password
manager.

**And it does not reach the write anyway, which is a second obstacle behind the first.** The
`ScreenCapture` that holds `target` is consumed into prose at the tool boundary and no field on
`ToolResult` carries it forward, so the ledger notes the same `Provenance(TOOL, "capture_screen")`
for both targets, and `record_exchange` sees only the opaque bit, the taint bit, the query and the
reply ([turn_output.py](../../../brain/packages/core/src/cortex_core/turn_output.py)). Reaching a
per-source rule therefore means adding an identifier to the capture seam first, which is the
decision the origin already made in the other direction.

**The loss this entry names is real and it needs no source at all**, which is the real residue: the
sentence that goes missing is the user's own, and the user's own words are the one thing on a
capture turn that an attacker cannot write. `render_exchange` renders both halves and the opaque
check skips the whole write, so the user's half is collateral. That is filed as
[R-286](286-user-half-of-an-opaque-turn.md), and it is a smaller and better-aimed change than the
one declined here.
**The area's count moves by one.** This reopens on one thing: a capture-seam field that names a
source on the operating system's word rather than the screen's, at which point the question is a
policy over an attested identity and no longer this entry.

## Trail

- 2026-07-18: recorded in this area when the vision slice landed, one of four vision entries the
  index grouped in its fix-when-it-bites bucket with the trigger its own entry implies, and the one
  it read as riding the per-provenance eviction entry in untrusted content rather than standing
  alone. The index dates that grouping only as "the same day" beside a paragraph about entries that
  had no bucket line until 2026-07-19, so which of the two days it means is not settled there.
- 2026-08-09: covered by the trigger sweep that ran against the tree over the whole fix-when-it-bites
  bucket and fired nothing. The index recorded that sweep so the next reader would spend the pass
  elsewhere instead of re-deriving the same verdicts, and it read every entry in the bucket against
  the code rather than against the entry's own text.
- 2026-08-16: Declined, which closes the gap its unrecorded trigger left by settling the entry
  rather than by naming what would fire it. Recorded as the per-source addendum at the origin
  decision record, and it opened [R-286](286-user-half-of-an-opaque-turn.md).
