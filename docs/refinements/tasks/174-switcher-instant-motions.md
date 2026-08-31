# Two instant motions in the switcher's list

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened
2026-08-03 with the switcher's per-row exit ([ADR-0035
addendum](../../adr/ADR-0035-console-and-motion.md)), which left them on purpose. The first is the
empty line: deleting the last chat rolls its row out over 300ms and then puts "no other chats
yet" up in the frame after, taking the card 14 to 53 (traced at 900x900; the panel does not snap
with it, easing its top 119 to 108 over the following 117ms). Rolling that line through its own
`Collapse` is three lines and is worse in the other direction, because the same flag runs
backwards when a first chat arrives into an empty list: the new row's 50px lands instantly and
the 39px line then rolls away underneath it, an overshoot bigger than the snap it removes.
Settling it means giving the two directions different treatments, which is a decision about what
an empty list is rather than a parameter. The second is the reorder itself: a pin regrouping the
list moves every row it touches in one frame, as it always has, and the exit only made a leaving
row travel with them instead of being left behind. Animating that is a different mechanism (every
row's position read before the commit and played back after it, the pattern usually called FLIP,
which this overlay has nowhere else) and would want the leaving row on the same clock as the
survivors. Trigger for either: the maintainer catching the frame, or a second list in the overlay
wanting reordered rows to travel.
- **LANDED 2026-08-03, both of them, and the first one is not the fix this entry proposed**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). Every number above measured true
  again at 900x900, the panel reading included: the card went 14 to 53 in one frame after a
  300ms roll whose own largest frame was 7.47px, and the panel eased 118.41 to 108 over the 117ms
  after it rather than snapping with it, the 108 a probe reads in the landing frame being the
  known `requestAnimationFrame` artefact this ADR already documents. **What was wrong is that this
  is one flag at all.** The line's two directions do not need a flag between them, because the
  direction that must be instant is a plain unmount and only the other one is an animation: the
  line is now asked of `sessions` instead of of the rendered rows, so it goes up in the frame the
  last row STARTS leaving and grows from nothing over that row's own roll, and it is unmounted in
  the frame a chat arrives. So the card never returns to 14 at all. It eases 64 to 53 over 283.9ms
  with a largest single frame of 1.66px, and the panel, which used to walk 108 to 119 over the
  roll and correct itself afterwards, holds 108 and 518 on every frame of it (86 and 450 at
  640x720, where it is on its ceiling). Rolling the line in "as well" would have been the entry's
  own worse answer arriving after the roll rather than during it. The mount is where the roll
  belongs, so `Collapse` gained an `enter` prop read once at mount, which also keeps a switcher
  opened on an empty list showing the line at full height with nothing animating. What the entry
  got right and this kept: the filling direction stays instant, an 11px step where the line's 39px
  is replaced by a row's 50, three and a half times smaller than the frame it removes and in the
  direction the eye is already looking. **The second motion landed as the entry described it**, as
  `overlay/useTravel.ts`, a hook over a ref and a selector so the next list to want it wires it in
  one line. The pinned chat travels 270 to 170 over 300.3ms (largest frame 15.04px) where it used
  to move in one, the two rows it displaces 50px each (largest frame 7.52px), and the leaving row
  is on that same clock because it is one of the rows the hook watches, traced with a pin 120ms
  into a delete. Two things the entry did not have. **A travel is a transform, so it cannot disturb the
  panel**: layout is final before it starts, the card holds 164 on every frame and its
  `scrollHeight` holds 162 against a 162 client box, so not even a scrollbar flickers. **And
  FLIP's "before" cannot be read at the previous commit**, which is the hazard that would have
  turned this into a regression: a roll moves rows by layout with no commit anywhere in it, so
  the release at the end of a 300ms exit reads the 50px its neighbour had already travelled as a
  jump to answer, and answers it by sending the row back down. The record is refreshed every frame
  while a roll is in flight and played from only on a commit, which fixes that and puts a mid-roll
  regrouping on honest numbers as well. Interrupted travels are `composite: "add"` rather than
  cancelled, so two pins 90ms apart compose into one continuous move and nothing is stranded.
  **And the demo bridge can make a chat arrive**, `converse` remembering the chat it was called
  for under `deriveTitle`, the brain's own rule: the demo's list could only ever shrink, which
  left the filling direction unmeasurable by hand, exactly as the delete was before the row exit
  landed.

## Trail

- 2026-08-03: Opened with the switcher's per-row exit, which left both motions on purpose.
- 2026-08-03: Both landed the same day, taking the area 15 to 14, and the first one not by the fix
  the entry proposed. Every number it published measured true again, its reading of the panel
  included, which is worth recording because this file's usual finding is the opposite. The reorder
  landed as the FLIP the entry named, and what it did not have is the hazard that would have made
  FLIP a regression.
