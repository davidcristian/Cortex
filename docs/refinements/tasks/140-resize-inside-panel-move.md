# A resize inside the panel's own move waits for it

**Status:** landed 2026-08-06
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-03 with the panel's watch on its own box
([ADR-0035](../../adr/ADR-0035-console-and-motion.md), the 2026-08-03 addendum). The watch refuses a
reading while the panel's own ease is running, because answering one would cancel that ease to
measure the natural box and start another, once per frame, which is the mid-stream retarget the
entry below is about arriving sixty times a second instead of once per token. So a keystroke that
grows the pill while the panel is already moving is not eased until the move it landed inside has
landed. **The cost is latency and not a jump**, which is what makes it a deferral rather than a
defect: traced at 900x1000 with 200px injected into the log and 40px more injected 100ms into the
resulting ease, the first move runs the top edge 368 to 168 over about 316ms with the second
growth invisible throughout (the running height animation overrides the box it would have
changed), the frame that hands the element back reads 168, the frame after reads 165.83, and the
residue eases 40px to 128 over about 120ms, monotonic, with no step anywhere. The wait is bounded
by the 380ms move ceiling ([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 7) and is
usually far shorter, and during a stream the panel's own renders cover most of it, a token landing
about every 55ms. The fix is not a second observer but whatever answers the mid-stream retarget
below, since both want a move that can be redirected from where it is without being restarted;
taken separately, this one would simply reintroduce that harm.
- **LANDED 2026-08-06 with the entry below, as the pair it said it was**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The entry reproduced at HEAD
  almost to the frame: re-traced at 900x1000 on an empty chat, 150px appended straight into the
  log and 40px more 100ms into the resulting 255ms ease, the second growth was invisible from
  t=160 to t=333, the frame that handed the element back read 514, the frame after read 516.31,
  and the residue eased to 556 over 120ms, settled at t=465. What the entry did not say is that
  the cost is not only the wait: the growth is answered from a standstill afterwards, so the
  reader waits 188ms and then watches a second movement that could have been part of the first.
  **The mechanism is the one the entry ruled out for the wrong reason.** It reads "the fix is not
  a second observer", and it is not, but neither is it a change to `place`: what the watch needed
  was to stop asking the box. A running height animation overrides the used height, so content
  growing inside the panel changes nothing the box can show, and no observer on that box could
  have seen it. An `!important` inline declaration outranks the animation origin in the cascade,
  so handing the height back to layout for the length of one read (`panelMemory.naturalHeightOf`)
  asks the question the animation is hiding: measured at 900x1400 with 60px appended and 40px more
  two frames into the ease, the box read 567.906 for both frames while the probe read 616.75 and
  then 667.75. Nothing paints in between and no notification comes of it. The growth is now
  answered one frame after it lands, by a retarget opening at 449.016, and the panel is settled at
  t=339 rather than t=465. **The alternative the entry's own doc argued against was measured
  instead of argued**: letting every notification place runs 24 animations for one growth rather
  than 2, the ease restarting its curve every frame, so the panel crawled 33px in the first 233ms
  and dumped 40.83px in a single frame at the end, against a largest single frame of 26.25px with
  the probe. One thing had to be added that neither entry named: the watch measures against the
  height the panel was PLACED for rather than the height it last looked at, because a placement
  resizes the element the watch is on, and measuring against a remembered reading placed a second
  time one frame later, doubling every move (6 animations for 3 growths over one reply, each pair
  3ms and 0.015px apart).

## Trail

- 2026-08-03: Opened with the panel's watch on its own box, as the one reading that watch
  deliberately refuses, and priced as latency rather than a jump.
- 2026-08-06: Landed with the mid-stream retarget as the pair it said it was. It reproduced at HEAD
  almost to the frame, and the mechanism was the one it ruled out for the wrong reason: the watch
  had to stop asking the box, since a running height animation overrides the used height, so an
  `!important` inline declaration hands the height back to layout for the length of one read. The
  panel settles at t=339 rather than t=465.
