# A settled reasoning reply shrinks the panel by 4px

**Status:** landed 2026-07-20
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

This is [ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 13.
The deferral read: traced at 60Hz at a
900px viewport while verifying the floor, through the first send and the whole streamed reply the
panel only grows, from 546px to 582px, and then eases *down* to 577.6px over about 130ms at the
end. The cause is not the floor and not the geometry: it is the moment the turn completes, where
the live thinking chip is dropped and the accumulated trace reappears as the collapsed "Thoughts"
disclosure (ADR-0020 addendum), which is 4.5px shorter than the chip it replaces. The panel is
correctly following its content; the content is what changes size. It is invisible on the body's
own 720px window, where a chat that has streamed a reply is already against its ceiling. The fix
is a component one (give the settled disclosure the chip's resting height, or cross-fade the two
in place), not a motion one.

The first of the two named fixes is what shipped, and both the diagnosis and the size were right:
the chip is 24px and the disclosure was 20px, both single-line boxes of the same 12px text, so
the whole of the difference was 8px of chip padding plus 2px of border against 6px of summary
padding. Both rules now floor on `--trace-row`, and the summary centres its label in the taller
box so the text does not step up 5px at the same moment. A/B in one browser session, with the old
heights restored by an override, settled it: 4.73px of descent over 11 frames
became 0.19px over two, which is the sub-pixel snap where a predicted height and the natural one
disagree, and the panel ends the turn at its maximum rather than 4.4px under it. The one thing
the deferral did not say is that the pairing is a *contract* rather than a coincidence, so it now has a
structural test (`Message.test.tsx`, "settles the live thinking chip into the disclosure in
place, one row for one row"): matching heights only mean anything while the two are one row in
two states, and a second settled row or an empty slot would put the shrink straight back.

## Trail

- 2026-07-20: Traced at 60Hz at a 900px viewport while verifying the chat floor, and landed the same
  day as the first of the two fixes it named. An A/B in one browser session took 4.73px of descent
  over 11 frames to 0.19px over two, and the pairing is now a contract with a structural test rather
  than a coincidence.
