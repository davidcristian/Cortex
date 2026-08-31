# An outcome-driven capture indicator

**Status:** landed 2026-08-06
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The overlay's dot is lit by the `ToolActivity` chip,
which the brain emits just *before* the dispatch, so it means "the assistant asked to look at
your screen" and its label says exactly that. It cannot say the screen was read, because no
outcome crosses the seam: the host kill switch, a self-exclusion that failed closed, an
unreachable body, and a declined gated capture all produce the same event. A stronger surface
(the one consent surface that would then match the body's own OS receipt) needs a post-dispatch
signal on the `Converse` stream, which is a proto field plus a reducer arm plus a tool-loop
emission point, so it is a seam change rather than an increment.

**Closed 2026-08-06** ([ADR-0029 outcome
addendum](../../adr/ADR-0029-vision-screen-capture.md)). The entry was right about its own premise,
which this file's standing warning says is not the way to bet: driven through the real loop over
the real dispatcher and the real `CaptureScreenTool`, all four modes yield exactly
`ToolStep(tool_name="capture_screen", ...)` and nothing else, identical to a successful capture.
Two of the four are tighter than it knew and are **one code path**, since the shell wires
`DeniedScreenCapture` whether the switch is off or the exclusion failed, so a refused capture
and a failed self-exclusion are indistinguishable in the error text and no design can separate
them. The cost estimate was right too, plus a mapping arm per language and a line-cap split.

What landed is `ToolOutcome { tool_name, ok }` as a new `ServerEvent` arm rather than a field on
`ToolActivity`, whose chip is pre-dispatch and would have to be emitted twice, or a `StatusUpdate`,
whose reducer arm drives the live chip and feeds the reasoning trace. It carries a bit and not a
taxonomy: the indicator has two accurate rungs, "the user declined" cannot be told from "no
confirmer was configured" without misreporting one of them, and every non-success outcome has to
render identically anyway. The bit is `ToolInvocation.ok` off the same result the audit line was
written from, so the consent surface and the audit log cannot disagree.

**The direction of the risk is the design.** Over-reporting a screen read is safe and
under-reporting is not, and the brain genuinely cannot tell a capture that failed *after* the frame
was taken from one that never happened. Reading the body's own order back (blit, encode, timestamp,
receipt, answer) also found the one case where neither surface reports a frame that was read: an
encode that ends in `TooLarge` returns before the receipt fires. So `ok=false` means "this side
cannot say the screen was read" and changes nothing on screen. Enforced structurally on both sides:
the outcome is emitted after the dispatch and outside every branch inside it, under the identical
condition the step was, so the taint denial, a declined confirmation, a registry fault and the
tool's own failure all resolve into the one result it reads; and `state.capturing` became
`state.capture: "asked" | "read" | null`, a ladder whose every write is non-decreasing, with
`endTurn` the one reset. Proven by mutation six ways, the one that matters most being the happy-path
guard (`and not result.is_error`), which is the gate-that-cannot-fail shape this repo keeps meeting
and which makes six tests fail.

The ring only ever gains detail: `"asked"` is the open ring unchanged and `"read"` grows a 2.5px
pupil, measured in Chromium at devicePixelRatio 1 because 2px is a smudge and 3px closes the hole
into the connection dot's amber twin. Both themes driven live. It opened one entry in
[subagents.md](../index.md#subagents), and it fixed one defect found in passing: the reduced-motion
block clamped `*`, which does not match pseudo-elements, so five motions including two infinite ones
ran at full speed for a user who asked for none.

## Trail

- 2026-07-19: written down from the vision slice's audit, one of the three entries that took the
  area 15 to 18 that day, since the overlay's dot is lit by a pre-dispatch chip and can only
  accurately say the assistant asked to look. The index adds that this dot is one of the three
  consent surfaces that justify shipping capture ungated.
- 2026-08-06: closed, moving the area's count 14 to 13, and subagents went 2 to 3 the same day
  because the pairing this landing guarantees for a turn's own dispatches does not reach a delegated
  step, which is now its own line there.
- 2026-08-06: its name left the Open items line later the same day, carried off beside the
  live-probe refresh's, so the two files agree on the arithmetic and no count moved for it twice.
