# Two instant motions in the switcher's list

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Two motions in the list happened in a single frame. Deleting the last chat animated its row out over
300ms and then put "no other chats yet" up in the next frame, taking the card from 14 to 53. And a
regrouping of the list moved every row it touched in one frame.

Both are fixed, and the first not by the fix this entry proposed. The line's two directions need no
flag between them, because the direction that must be instant is a plain unmount and only the other
is an animation. The line is now asked of `sessions` instead of of the rendered rows, so it appears
in the frame the last row starts leaving and grows from nothing over that row's own animation, and
it is unmounted in the frame a chat arrives. The card never returns to 14: it eases 64 to 53 over
283.9ms with a largest single frame of 1.66px, and the panel, which used to walk 108 to 119 and
correct itself afterwards, holds 108 and 518 on every frame. `Collapse` gained an `enter` prop read
once at mount, which also means a switcher opened on an empty list shows the line at full height
with nothing animating. The filling direction stays instant, an 11px step where the line's 39px is
replaced by a row's 50px.

The second shipped as `overlay/useTravel.ts`, a hook over a ref and a selector, using the pattern
usually called FLIP: every row's position is read before the commit and played back after it. A chat
moved to the top travels 270 to 170 over 300.3ms (largest frame 15.04px) where it used to move in
one, the two rows it displaces 50px each, and a leaving row is on the same clock because the hook
watches it too.

Two things the entry did not have. A travel is a transform, so it cannot disturb the panel: layout
is final before it starts, the card holds 164 on every frame, and not even a scrollbar flickers. And
FLIP's "before" cannot be read at the previous commit, which would have made this a regression: an
opening or closing section moves rows by layout with no commit in it, so the release at the end of a
300ms exit would read the 50px its neighbour had already travelled as a jump and send the row back
down. The recorded positions are refreshed every frame while an animation is in flight and played
from only on a commit. Interrupted travels use `composite: "add"` rather than being cancelled, so
two regroupings 90ms apart compose into one continuous move.

The demo bridge can make a chat arrive now, `converse` remembering the chat it was called for under
`deriveTitle`; before, the demo's list could only shrink, which left the filling direction
impossible to see by hand.

## History

- 2026-08-03: Opened with the switcher's per-row exit, which left both motions deliberately.
- 2026-08-03: Both closed the same day, the first not by the fix the entry proposed. Every number it
  published measured true again, the reading of the panel included.
