# The room a section hands back in one frame

**Status:** done 2026-08-08
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

A section rolling shut is still in the tree until React removes it, which is what the share's
`:has()` sees, so the other section held its reduced share for the length of that roll and took
the whole budget in the single frame the roll's end handed it over. Nothing outside the list
moved, so this was a reveal rather than a jump.

**Shipped 2026-08-08, and it needed no JavaScript**
([ADR-0035](../../adr/ADR-0035-console-and-motion.md)). Traced in headless Chromium against the
demo bridge at 640x720 with the switcher's list seeded long enough to reach its cap, every painted
frame sampled after the frame's rendering steps. The entry reproduces in shape, with this panel's
own numbers: the switcher steps 135.14 to 241 in a single frame, which is its entire travel, over
a roll that runs 300 ms, and the panel's own box holds one distinct height with its top edge
travelling 0px. The 127.14 to 227 the entry printed is the same step measured on a panel at a
436px ceiling instead of this one's 450px.

The publication the entry wanted is already in the DOM, and `:has()` can read it. A roll sets
`data-morphing` to the height it is going to (`overlay/morph.ts`), and a closing roll sets it to
`0`. So the share asks whether the other section is going to be there rather than whether it is
there: `:has(> .collapse.aside:not([data-morphing="0"]))`.

Reading the target alone moves the step rather than removing it, which is the half the entry did
not name: the whole 105.86px then falls in the first frame of the roll instead of the frame after
the last. So both caps ease to their new share over the roll's own duration and curve, and the
wrapper's cap eases with the card's, the two being the same number less the card's air. After, the
switcher covers the same 105.859px over 19 distinct values with a largest single frame of
15.937px, and the step at the roll's boundary reads 0.000px (241 on the last frame with the aside
in the tree, 241 on the first frame without it). The history, which absorbs the handover, goes
from a largest frame of 105.859px and 183.109px of total travel to 4.313px and 28.609px.

The condition for that ease is both sections being open, and not a roll running, which was
measured wrong at first. Conditioned on `[data-morphing]`, the closing direction eased and the
opening direction did not move at all. A section joins the tree one style recalculation before it
announces its roll, because `Collapse` mounts the wrapper and then reads its natural height in a
layout effect, and that read is the recalculation that resolves the sibling's new share, so the
condition was not yet true when the number moved. A share can only change while both sections are
there to split it, so that is the condition, and it is true one recalculation earlier.

That also fixed the mirror of this entry, found while measuring it and never filed: opening the
switcher over an open stack dropped the stack 187.75 to 99.84 in the first frame of a roll with
300 ms left to run. It now covers that travel over 15 distinct values with a largest single frame
of 17.36px, the history's worst frame going 87.906px to 12.734px and its total travel 229.046px to
53.234px.

Proved able to fail: a live override in the same session restores the pre-change tree, putting the
share back on tree membership and taking the transition away, so the closing step returns to
105.859px in one frame with 2 distinct values and a boundary step of 135.141 to 241, and the
opening step to 87.906px in one frame. Removing the override returns every number to the eased
reading.

Two risks an eased cap could have were measured rather than argued. A cap that lagged the panel
could feed the panel's own watch on its box, and `--ceiling` is rewritten by every placement. It
cannot: a share only binds when a section needs more than the column has, which is exactly when
the panel is at its ceiling, so the history absorbs the change and the panel's box does not move.
Over a console round trip and a viewport walked 720 to 900 and back with both sections open, the
panel's top edge travels 0.062px with the ease against 1.625px without it, the switcher's worst
frame on the resize goes 65.14px to 11.94px, and the page raises no resize-loop error either way.
Under `prefers-reduced-motion` the roll does not animate at all, so the cap moves on the sheet's
own 0.12 s floor for every transition rather than on the roll's 300 ms, and the panel is still
unmoved.

## History

- 2026-08-03: Opened with the section budget of [R-141](141-sections-outrun-the-panel.md).
- 2026-08-08: Shipped, its shape reproducing first, and it took the unfiled mirror of the entry
  with it. The area went nine to eight, one out and none in.
