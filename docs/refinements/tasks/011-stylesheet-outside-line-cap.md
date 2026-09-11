# The overlay stylesheet outside the line cap

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** An edit landing in the wrong cascade position, or a second stylesheet appearing.
**Verified:** 2026-09-11

Opened 2026-08-03 behind the entry above, because turning the cap on made the exclusion a decision
rather than an oversight. `body/app/src/overlay.css` was **2420 lines** the day this opened, **2686**
when it was re-measured on 2026-08-08, **2700** on 2026-08-09, and is **2705** as of 2026-09-11, the
longest hand-written source file in the repo (the next longest, a test file, is 2488 lines), and
no gate measures it. It is excluded on the argument that the cap's remedy is
"split by responsibility", which presumes a module with a public contract, while a stylesheet is
one cascade in which order decides which rule applies: splitting it trades a long file for
`@import` ordering that nothing checks and that fails by changing what is drawn rather than by
reporting an error. That argument is honest about the
remedy and evasive about the problem, since a file this long is exactly the cognitive load the cap
exists to bound, and it has grown with every overlay slice, by 285 lines since the entry was
filed. That growth is also why the number above is now measured rather than quoted: an entry that
states a file's size has to re-read the file, the way every other claim about the code here does. **What would close it:** either
a cap for `.css` at a width chosen for stylesheets rather than modules, with the split done by
layer (tokens, panel, console, motion) and imported in a fixed order from one entry sheet, or the
same split done for its own sake with the cap following. Neither is a scanner change; the scanner
needs one suffix added. **Trigger:** the first time an edit lands in the wrong cascade position
because the file is too long to hold in view, or a second stylesheet appearing, at which point the
ordering question has to be answered anyway. Until then the cap covers every executable module in
the repo and this is the one measured hole in it.

## Trail

- 2026-08-03: Opened behind the cap reaching the overlay's TypeScript, taking the area from three
  entries to four, because turning the cap on made the exclusion a decision rather than an
  oversight. `body/app/src/overlay.css` stood at 2420 lines.
- 2026-08-08: Re-measured at 2686 lines.
- 2026-08-09: 2700 lines, by a wide margin the longest hand-written file in the repo. The bucket
  sweep checked the trigger the same day and found it quiet, there being still exactly one
  stylesheet under `body/app/src`.
- 2026-09-11: `wc -l body/app/src/overlay.css` answers 2705, five more than the last reading.
  `find body/app/src -name '*.css'` still finds exactly that one file and `main.tsx` is its one
  importer, so the second-stylesheet half of the trigger has not fired. The other half has not
  either: none of the four commits touching the stylesheet since 2026-08-09 moved a rule to repair
  its cascade position. `SOURCE_SUFFIXES` in `scripts/linecap.py` is still the four suffixes without
  `.css`. The nearest source file is a 2488-line test, so the wide margin the body used to claim has
  narrowed to 217 lines and the sentence now says what it measured.
