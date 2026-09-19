# A resize inside the panel's own move waits for it

**Status:** done 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

The panel's watch takes no reading while the panel's own ease is running
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 32), because taking one would
cancel that ease to measure the natural box and start another, once per frame. So a keystroke that
grew the pill while the panel was already moving was not eased until the move it began inside had
finished.

That cost latency rather than a jump: traced at 900x1000 with 200px injected into the log and 40px
more injected 100 ms into the resulting ease, the first move ran the top edge 368 to 168 over
about 316 ms with the second growth invisible throughout, the frame that handed the element back
read 168, the frame after read 165.83, and the residue eased 40px to 128 over about 120 ms,
monotonic, with no step. The wait is bounded by the 380 ms move ceiling (decision 7), and during a
stream the panel's own renders cover most of it, a token arriving about every 55 ms.

**Shipped 2026-08-06 with the mid-stream retarget, as the pair this entry said it was.** It
reproduced at HEAD almost to the frame: re-traced at 900x1000 on an empty chat, 150px appended
into the log and 40px more 100 ms into the resulting 255 ms ease, the second growth was invisible
from t=160 to t=333, the frame that handed the element back read 514, the frame after read 516.31,
and the residue eased to 556 over 120 ms, settled at t=465. What the entry did not say is that the
growth is then handled from a standstill, so the reader waits 188 ms and then watches a second
movement that could have been part of the first.

The mechanism is not a change to `place`: what the watch needed was to stop asking the box. A
running height animation overrides the used height, so content growing inside the panel changes
nothing the box can show, and no observer on that box could have seen it. An `!important` inline
declaration outranks the animation origin in the cascade, so handing the height back to layout for
the length of one read (`panelMemory.naturalHeightOf`) asks the question the animation is hiding.
Measured at 900x1400 with 60px appended and 40px more two frames into the ease, the box read
567.906 for both frames while the probe read 616.75 and then 667.75. Nothing paints in between and
no notification comes of it. The growth is now handled one frame after it happens, by a retarget
opening at 449.016, and the panel settles at t=339 rather than t=465.

The alternative was measured rather than argued: letting every notification place runs 24
animations for one growth rather than 2, the ease restarting its curve every frame, so the panel
crawled 33px in the first 233 ms and dumped 40.83px in a single frame at the end, against a
largest single frame of 26.25px with the probe.

One thing had to be added that neither entry named: the watch measures against the height the
panel was placed for rather than the height it last looked at, because a placement resizes the
element the watch is on, and measuring against a remembered reading placed a second time one frame
later, doubling every move (6 animations for 3 growths over one reply, each pair 3 ms and 0.015px
apart).

## History

- 2026-08-03: Opened with the panel's watch on its own box, as the one reading that watch
  deliberately refuses, and priced as latency rather than a jump.
- 2026-08-06: Shipped with the mid-stream retarget as the pair it said it was, by the mechanism it
  had ruled out for the wrong reason.
