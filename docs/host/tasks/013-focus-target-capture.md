# The focus-target capture and its Z-order walk

**Status:** never attempted
**Sitting:** windows-capture
**Capability:** W
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

The focus target was added on 2026-08-10, and it has its own check.

The body can now be pointed at **the window the user is looking at** rather than the whole
display ([ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)'s 2026-08-10 addendum). The
resolution is a walk down the desktop's Z-order in `body/crates/os_windows/src/focus.rs`, it is
authored and clippy-linted for the Windows target from Linux, and **no walk in it has ever seen a
real desktop**. Every predicate below is a documentation-derived claim about Win32 until this
runs.

**How to drive it, now that the brain asks.** As of 2026-08-10 the brain half has landed too, so
an ordinary question about a window is enough: `capture_screen` takes a required `target` and the
tool description steers the model to `focus` whenever the user is asking about one thing in front
of them. Ask something like "what does this error in the window in front of me say?" rather than
"what's on my screen?", which steers the other way on purpose. If the model picks `display`
anyway, that is worth recording as its own observation, and
`BodyService.CaptureScreen` can still be driven by hand with `target: CAPTURE_TARGET_FOCUS`
(field 2 = 1) to reach the walk regardless. The rest of the bring-up is the same as the display
check's, kill switch included.

## Do this check first, for the same reason as the other one

**Do.** With the overlay open and a browser behind it, ask for a targeted capture.

**Pass.** The picture is the **browser**, and the overlay is not in it and is not what was
resolved.

**Fail.** The picture is the overlay, or is black, or is the taskbar. Black means the walk landed
on a window that excludes itself from capture and the two guards that should have skipped it (this
process's id, and the display affinity) both missed. The overlay means the self-injection loop is
live through a second door, so treat it exactly like the first check's failure: `CORTEX_HOST_CAPTURE=0`,
stop, record.

## The other six observations

| Observation | Pass looks like | Failure looks like |
| --- | --- | --- |
| It picks what the user is looking at | The frontmost ordinary window, whichever app it is | A window behind it, or one the user forgot was open |
| The taskbar is never the answer | Never resolved, even with everything else minimized | A picture of the taskbar, which means the `WS_EX_TOOLWINDOW` filter did not hold |
| A bare desktop is refused | The reply says **the host is not in a state to capture the screen**; no picture, no receipt | A picture of the wallpaper, which means the walk resolved the shell window or the wallpaper host and the refusal was silently widened into a screen capture |
| The crop's edges are the window's | The picture stops at the window, with no strip of whatever is behind it along the edges | A few pixels of desktop on all four sides, which means `DWMWA_EXTENDED_FRAME_BOUNDS` was unavailable and `GetWindowRect`'s invisible resize border was used |
| A window dragged half off the screen | The half that is on the display, cropped, no error | An error, or a stretched picture, or a panic |
| A window on a second monitor | The same refusal sentence as a bare desktop, since v1 captures the primary display only | A picture of the primary display's pixels at that window's coordinates, which is the wrong part of the wrong screen |

**And the receipt, which is the seventh thing to look at and is counted with the display check's
receipt row rather than twice.** A targeted capture must say "A picture of one window was sent to the
assistant." A window maximised to fill the display says "your screen" instead, deliberately: the
sentence describes what was sent.

**The reply and the receipt must agree, which is now checkable from the assistant's side.** The
reply carries what the body resolved, picked by the same predicate as the receipt, and the model
is told "screen capture of one window, cropped out of the WxH primary display". So the assistant
describing a window while the toast says "your screen" (or the reverse) is a failure of that
shared predicate rather than of either surface, and it is worth reading the two together on the
maximised-window case in particular, where both must say screen.

## Record it

A dated addendum to [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md), extending its
"Still host-only" section with what was seen (especially the two self-exclusion results, the
window the walk actually resolved, and the latency number), and a note in
[runbooks/vision.md](../../runbooks/vision.md).
