# A capture indicator driven by the outcome

**Status:** done 2026-08-06
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The overlay's dot was lit by the `ToolActivity` chip, which the brain emits just before the
dispatch, so it meant "the assistant asked to look at your screen" and its label said so. It could
not say the screen was read, because no outcome crossed the wire: the host kill switch, a
self-exclusion that failed closed, an unreachable body and a capture the user declined all produced
the same event.

Closed 2026-08-06 ([ADR-0029 decision 18](../../adr/ADR-0029-vision-screen-capture.md)). The entry
was right about its premise: driven through the real loop over the real dispatcher and the real
`CaptureScreenTool`, all four cases yield exactly `ToolStep(tool_name="capture_screen", ...)` and
nothing else, identical to a successful capture. Two of the four are one code path, since the shell
wires `DeniedScreenCapture` whether the switch is off or the exclusion failed, so a refused capture
and a failed self-exclusion cannot be told apart in the error text.

What was built is `ToolOutcome { tool_name, ok }` as a new `ServerEvent` variant, rather than a
field on `ToolActivity`, whose chip is pre-dispatch and would have to be emitted twice, or a
`StatusUpdate`, whose reducer drives the live chip and feeds the reasoning trace. It sends a bit
and not a taxonomy: the indicator has two accurate steps, "the user declined" cannot be told from
"no confirmer was configured" without misreporting one of them, and every non-success outcome
renders identically anyway. The bit is `ToolInvocation.ok` off the same result the audit line was
written from, so the consent surface and the audit log cannot disagree.

The direction of the risk is the design. Over-reporting a screen read is safe and under-reporting
is not, and the brain cannot tell a capture that failed after the frame was taken from one that
never happened. Reading the body's own order back (blit, encode, timestamp, receipt, answer) also
found the one case where neither surface reports a frame that was read: an encode that ends in
`TooLarge` returns before the receipt fires. So `ok=false` means "this side cannot say the screen
was read" and changes nothing on screen. Both sides enforce it structurally: the outcome is emitted
after the dispatch and outside every branch inside it, under the same condition the step was, so
the taint denial, a declined confirmation, a registry fault and the tool's own failure all resolve
into the one result it reads; and `state.capturing` became `state.capture: "asked" | "read" |
null`, whose every write is non-decreasing, with `endTurn` the one reset. Proven by mutation six
ways, the one that matters most being the happy-path condition (`and not result.is_error`), a check
that could not fail until it was written this way, and which makes six tests fail.

The ring only gains detail: `"asked"` is the open ring unchanged and `"read"` grows a 2.5px pupil,
measured in Chromium at devicePixelRatio 1, because 2px is a smudge and 3px closes the hole into
the connection dot's amber twin. Both themes driven live. It opened one entry in
[subagents.md](../index.md#subagents), and it fixed one defect found in passing: the
reduced-motion block applied to `*`, which does not match pseudo-elements, so five motions
including two infinite ones ran at full speed for a user who asked for none.

## History

- 2026-07-19: Written down from the vision slice's audit, since the overlay's dot is lit by a
  pre-dispatch chip and can only accurately say the assistant asked to look. This dot is one of the
  three consent surfaces that justify shipping capture without a confirmation card.
- 2026-08-06: Closed. Subagents gained an entry the same day, because the pairing this guarantees
  for a turn's own dispatches does not reach a delegated step.
