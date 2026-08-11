# Whether the reply says a window was resampled

**Status:** open, a seam or port change comes first
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** The next change that opens `CaptureScreenReply`, or a measured caption effect.

Opened 2026-08-10 by the measurement above
and the steer correction that followed it
([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s fourth addendum of that date).
`CaptureScreenReply` carries `resolved_target` and nothing else about the picture's provenance,
so a `focus` capture of a window wider than the capture edge goes through the same box filter
the whole display does, lands at the same 2048x1152, and arrives indistinguishable from a crop
that was never touched. The model asked for the target that keeps detail, got a picture exactly
as lossy as a screenshot, and has no way to find out. The body knows: the identity arm of
`downscale` either fired or it did not, and `Capture` holds the crop and the bound side by side,
so the value is one `bool` on the reply, symmetric with `resolved_target`, and `describe()` would
finally be able to say which of the two pictures arrived.

**Why it was not built, in descending weight.** Its only consumer is a sentence in the stand-in
text, and that is the one intervention this area has measured twice and found inert: with
`describe()`'s source size in front of it, saying in so many words that the picture is a shrunk
view, and "unreadable" offered as an allowed answer, the cortex declined on 3 of 47 and invented
the other 38, and the crop arm found the same thing from the other side, that a crop converts
declines into readings rather than inventions into truths. The cheaper half of the value landed
instead, in the tool description, which now tells the model **before** the pick that `focus` is
not a guarantee of detail, which is the half it can act on. And the cost is a slice rather than a
follow-up: a fourth proto regeneration on this path in one day, reaching `screen_policy.rs` (286
of 300 at HEAD, so a field plus its accessor forces a split by responsibility), `gateway.py` (263
of 300), the seam facade, both fakes, six test files and six docs. Per this backlog's own
standing warning, everything in that sentence except the two line counts is a hypothesis; the
line counts were read at HEAD.

What is **not** a reason is honesty. The silence is a real gap in what `describe()` can say, and
it is why that function already refuses to guess. The claim is that the gap is not currently
reachable by any behaviour this repo can measure, not that it is not a gap.

**Trigger.** It lands with the next change that opens `CaptureScreenReply` at all, a
`display_index` or the overlay-drawn region picker the rectangle decline waits on, or the day a
caption is measured to change what this cortex does with a picture it cannot read, whichever
comes first.

## Trail

- 2026-08-10: opened by the window measurement and by the steer correction that followed it,
  moving the area's count 10 to 11. This is the area's first arrival since the swap entry's halves
  and the first reading here to move a vision count up. The shipped tool description had promised
  the model that a focused window is cut out "at full detail", unconditionally, while the mechanism
  is being unresampled rather than being cropped, so a window wider than the capture edge gets the
  same box filter and the same 2048x1152 the screen does and is indistinguishable from an untouched
  crop on arrival. The description now names small text in one thing as the case the window wins,
  says what it costs (everything outside that window) and promises no detail it cannot keep, and
  both copies of the steer are held to that by a test proved able to fail three ways. One
  restatement went with it: refusing a call that names no target had leaned on the whole screen
  being the less legible picture as well as the more exposing one, which the measurement narrows to
  the smallest type alone, and the refusal never needed that leg. It is a whole new entry rather
  than the closed one reopening, since what closed was a question about the world and what opens is
  a piece of work with its own trigger.
