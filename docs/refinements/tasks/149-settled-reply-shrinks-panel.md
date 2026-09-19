# A settled reasoning reply shrinks the panel by 4px

**Status:** done 2026-07-20
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md), the chat's floor under the empty state ([overlay-ux.md §3](../../design/overlay-ux.md))

Traced at 60Hz at a 900px viewport while checking the chat floor, the panel only grows through
the first send and the whole streamed reply, from 546px to 582px, and then eases down to 577.6px
over about 130 ms at the end. The cause is the moment the turn completes: the live thinking chip
is dropped and the accumulated trace reappears as the collapsed Thoughts disclosure (ADR-0020
decision 9), which was 4.5px shorter than the chip it replaces. The panel was correctly following
its content.

**Shipped the same day as the first of the two fixes the entry named**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md) decision 13). Both the diagnosis and the
size were right: the chip is 24px and the disclosure was 20px, both single-line boxes of the same
12px text, so the whole difference was 8px of chip padding plus 2px of border against 6px of
summary padding. Both rules now floor on `--trace-row`, and the summary centres its label in the
taller box so the text does not step up 5px at the same moment.

An A/B in one browser session, with the old heights restored by an override, settled it: 4.73px of
descent over 11 frames became 0.19px over two, which is the sub-pixel snap where a predicted
height and the natural one disagree, and the panel ends the turn at its maximum rather than 4.4px
under it.

The pairing is a contract rather than a coincidence, which the entry did not say, so it has a
structural test (`Message.test.tsx`, "settles the live thinking chip into the disclosure in place,
one row for one row"). Matching heights only mean anything while the two are one row in two
states, and a second settled row or an empty slot would put the shrink straight back.

## History

- 2026-07-20: Traced at 60Hz at a 900px viewport while checking the chat floor, and shipped the
  same day.
