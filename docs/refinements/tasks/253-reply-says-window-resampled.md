# Whether the reply says a window was resampled

**Status:** done 2026-09-24
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

`CaptureScreenReply` contains `resolved_target` and nothing else about where the picture came from,
so a `focus` capture of a window wider than the capture edge goes through the same box filter the
whole display does, arrives at the same 2048x1152, and looks exactly like a crop that was never
resampled. The model asked for the target that keeps detail, got a picture as lossy as a
screenshot, and cannot tell. The body can tell, since either `downscale` resampled or it did not,
and `Capture` holds the crop and the bound side by side, so the value is one `bool` on the reply,
matching `resolved_target`, and `describe()` could then say which of the two arrived.

It was not built for three reasons. Its only consumer is a sentence in the placeholder text, and
that kind of wording has been measured twice and found to change nothing: with `describe()`'s
source size in front of it, told the picture is a shrunk view, and with "unreadable" offered as an
allowed answer, the cortex declined on 3 of 47 and invented the other 38. The cheaper half of the
value was done instead, in the tool description, which now tells the model before it picks that
`focus` is not a guarantee of detail. And the cost is a slice rather than a follow-up: a proto
regeneration reaching `screen_policy.rs` (289 of 300 lines, so a field plus its accessor forces a
split), the body client's `gateway.py` (285 of 300), the gRPC facade, both fakes, six test files
and six docs. Everything in that sentence except the two line counts is a hypothesis; the line
counts were read at HEAD.

Accuracy is not a reason against it. The missing field is a real gap in what `describe()` can say,
and it is why that function already refuses to guess; the claim is only that no behaviour this repo
can measure currently reaches the gap.

It should be done with the next change that opens `CaptureScreenRequest` or `CaptureScreenReply` at
all, such as a `display_index` or the overlay-drawn region picker, or the day a caption is measured
to change what the cortex does with a picture it cannot read. Either message counts, because what
such a change pays for is the regeneration and the files it reaches, and a request field reaches
most of the same ones.

## History

- 2026-08-10: Opened by the window measurement and by the correction to the tool description that
  followed it. That description had promised the model that a focused window is cut out "at full
  detail", unconditionally, while the real mechanism is not being resampled rather than being
  cropped, so a window wider than the capture edge gets the same box filter as the screen. The
  description now names small text as the case a window wins, says what it costs (everything
  outside that window) and promises no detail it cannot keep, with a test proved able to fail three
  ways. Refusing a call that names no target had partly relied on the whole screen being the less
  legible picture, which the measurement narrows to the smallest type alone; the refusal never
  needed that argument.
- 2026-09-13: Checked and left open, with both line citations refreshed. The trigger has not
  occurred. `CaptureScreenReply` still has `image` and `resolved_target` and nothing else, and the
  one change to `proto/body.proto` since edited the delete-session comment. `Capture::from_bgra`
  still crops before the halving ladder and a region already inside the edge passes through
  unresampled, while `describe()` in `screen_tool.py` still says nothing about which arrived. Both
  cost citations had moved under the same 300-line cap, `screen_policy.rs` from 286 to 289 and
  `gateway.py` from 263 to 285.
- 2026-09-19: Checked and left open, with the trigger restated. `proto/body.proto` is unchanged and
  no caption measurement has run. The brain still asks for a 2048 edge
  (`DEFAULT_CAPTURE_MAX_EDGE` in the orchestrator's `config_body.py`), so 2048x1152 is still what a
  16:9 display arrives at, and both line counts are unchanged at 289 and 285. The trigger named the
  next change opening `CaptureScreenReply` while the text below counted a `display_index` among
  such changes, and that is a request field, so both now name either capture message.
- 2026-09-24: Done, before its trigger, because the cost that held it back was gone: the two files
  it cited were 197 and 206 lines, not 289 and 285, so a field forced no split. The reply has
  `target_width` and `target_height`, the size of the part of the display the picture shows before
  the downscale, rather than the one `bool` proposed above: a proto3 `bool` reads a body older than
  the field as "not resampled", while a zero size reads as "not said", and the size lets
  `describe()` say what a window was shrunk from, as it already does for the display. A window's
  sentence now ends "downscaled from the window's WxH" or "at the window's own size", and says
  neither for an older body. A paired draw on the resampled spreadsheet window found that the
  sentence changes nothing the cortex reads: 59 of 108 strings read with it against 64 of 108
  without, sign test p = 0.45 ([vision capture](../../readings/vision-capture.md#legibility)).
