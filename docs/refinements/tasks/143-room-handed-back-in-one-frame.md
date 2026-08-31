# The room a section hands back in one frame

**Status:** landed 2026-08-08
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-03 with the budget above. A
section rolling shut is still in the tree until React removes it, which is what the share's own
`:has()` sees, so the other section holds its reduced share for the length of that roll and takes
the whole budget in the single frame the roll's end hands it over. Traced at 640x720 acking a full
reminder stack with the switcher open: the panel's own box never moves (one distinct height across
the trace, largest single-frame step of its top edge 0px) and the switcher steps 127.14 to 227 in
one frame, revealing two more rows. **The cost is a reveal and not a jump**, nothing outside the
list moving at all, which is what makes it a deferral. The fix is for the share to follow the
roll rather than the tree, which needs the rolling section's target height where the cascade can
read it, and that is the same publication the ride-along already makes to the panel.
- **LANDED 2026-08-08, measured before anything was touched, and it needed no JavaScript at all**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). Traced in headless Chromium against
  the demo bridge at 640x720 with the switcher's list seeded long enough to reach its cap, every
  painted frame sampled after the frame's rendering steps. The entry reproduces in shape and its
  numbers are this panel's rather than the ones printed above: the switcher steps **135.14 to 241
  in a single frame**, which is its entire travel, over a roll that runs 300ms, and the panel's own
  box holds one distinct height across the whole trace with its top edge travelling 0px. The
  printed 127.14 to 227 is the same step measured on a panel standing at a 436px ceiling instead of
  this one's 450px.
- **The publication the entry wanted is already in the DOM, and `:has()` can read it.** A roll sets
  `data-morphing` to the height it is going to (`overlay/morph.ts`), which is what the ride-along
  reads, and a closing roll sets it to exactly `0`. So the share asks whether the other section is
  GOING TO BE there rather than whether it is there: `:has(> .collapse.aside:not([data-morphing="0"]))`.
  No second publication, no JavaScript, and no arithmetic crossing the language boundary.
- **Reading the target alone moves the step rather than removing it,** which is the half the entry
  did not name: the whole 105.86px then lands in the FIRST frame of the roll instead of the frame
  after the last. So both caps ease to their new share over the roll's own duration and curve, and
  the wrapper's cap eases with the card's because the two are the same number less the card's air.
  After, the switcher covers the same 105.859px of travel over 19 distinct values with a largest
  single frame of **15.937px**, and the step at the roll's own boundary reads **0.000px** (241 on
  the last frame with the aside in the tree, 241 on the first frame without it). The history, which
  is what absorbs the handover, goes from a largest frame of 105.859px and 183.109px of total
  travel to 4.313px and 28.609px: it now moves only the 28.6px the exchange is actually worth
  instead of lurching a hundred pixels out and back. The panel is unmoved throughout, one distinct
  height and 0px of top-edge travel, before and after.
- **The gate on that ease is both sections being open, and NOT a roll running, which is the obvious
  rule and was measured wrong.** Gated on `[data-morphing]`, the closing direction eased and the
  opening direction did not move at all. The reason is an ordering nothing had written down: a
  section joins the tree one style recalc BEFORE it announces its roll, `Collapse` mounting the
  wrapper and then reading its natural height in a layout effect, and that read is the recalc that
  resolves the sibling's new share. The gate was not yet standing when the number moved. A share
  can only change while both sections are there to split it, so that is the condition, and it is
  true one recalc earlier.
- **Which fixed the mirror of this entry, found while measuring it.** Opening the switcher over a
  standing stack dropped the stack **187.75 to 99.84 in the first frame** of a roll with 300ms left
  to run, the same defect pointing the other way and never filed. It now covers that travel over 15
  distinct values with a largest single frame of 17.36px, the history's worst frame going 87.906px
  to 12.734px and its total travel 229.046px to 53.234px.
- **The arm was proved able to fail.** A live override in the same session restores the pre-change
  tree exactly, putting the share back on tree membership and taking the transition away: the
  closing step returns to 105.859px in one frame with 2 distinct values and a boundary step of
  135.141 to 241, and the opening step to 87.906px in one frame. Removing the override returns
  every number to the eased reading.
- **The two hazards an eased cap could carry were measured rather than argued.** A cap that lagged
  the panel could feed the panel's own watch on its box, and `--ceiling` is rewritten by every
  placement. It cannot: a share only binds when a section needs more than the column has, which is
  exactly when the panel is at its ceiling, so the history absorbs the change and the panel's box
  does not move. Over a console round trip and a viewport walked 720 to 900 and back with both
  sections open, the panel's top edge travels 0.062px with the ease against 1.625px without it, the
  switcher's own worst frame on the resize goes 65.14px to 11.94px, and the page raises no
  resize-loop error under either arm. Under `prefers-reduced-motion` the roll does not animate at
  all, so the cap moves on the sheet's own 0.12s floor for every transition rather than on the
  roll's 300ms, and the panel is still unmoved.

## Trail

- 2026-08-03: Opened with the section budget that landed above it.
- 2026-08-08: Landed, its shape reproducing first, and it needed no JavaScript at all, `:has()`
  being able to read the target the roll already publishes so that both caps ease to their new share
  on the roll's own clock. The switcher's largest single frame went 105.86px to 15.94px with a
  boundary step of 0.000px, and the close also took the unfiled mirror of the entry, an opening
  section taking the other's room in one frame. The area went nine to eight, one out and none in.
