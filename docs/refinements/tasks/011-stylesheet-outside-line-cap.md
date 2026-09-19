# The overlay stylesheet outside the line cap

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** a commit whose diff to `body/app/src/overlay.css` moves a rule to repair which rule
wins, or a second `.css` file under `body/app/src`.
**Verified:** 2026-09-17

Once the line cap covered the overlay's TypeScript
([R-010](010-line-cap-overlay-gap.md)), leaving the stylesheet out became a decision rather than
an oversight. `body/app/src/overlay.css` was 2420 lines when this opened on 2026-08-03 and is 2706
as of 2026-09-17, nine times the cap every other non-test source file is held to, and no check
measures it. The only longer hand-written source is a test, the 2818-line live injection suite
under `brain/packages/inference/tests/`, which the cap exempts as a test.

It is excluded because the cap's remedy is to split by responsibility, which assumes a module with
a public contract. A stylesheet is one cascade in which order decides which rule applies, so
splitting it trades a long file for `@import` ordering that nothing checks and that fails by
changing what is drawn rather than by reporting an error. That is a fair account of the remedy and
not of the problem: a file this long is exactly the reading load the cap exists to limit, and it
has grown with every overlay change.

What would close it: either a cap for `.css` at a width chosen for stylesheets rather than
modules, with the split done by layer (tokens, panel, console, motion) and imported in a fixed
order from one entry sheet, or the same split done for its own sake with the cap following.
Neither is a scanner change; the scanner needs one suffix added.

## History

- 2026-08-03: Opened once the cap reached the overlay's TypeScript, because leaving the stylesheet
  out became a decision. `body/app/src/overlay.css` stood at 2420 lines.
- 2026-08-08: Measured again at 2686 lines.
- 2026-08-09: 2700 lines. The trigger was checked the same day and had not fired, there being
  still exactly one stylesheet under `body/app/src`.
- 2026-09-11: `wc -l body/app/src/overlay.css` answers 2705. `find body/app/src -name '*.css'`
  still finds exactly that one file and `main.tsx` is its only importer, so the
  second-stylesheet half of the trigger has not fired. Neither has the other half: none of the
  four commits touching the stylesheet since 2026-08-09 moved a rule to repair its cascade
  position. `SOURCE_SUFFIXES` in `scripts/linecap.py` is still four suffixes without `.css`.
- 2026-09-17: Neither half has fired. `wc -l body/app/src/overlay.css` answers 2706, one more than
  the last reading, from the one commit to touch it since 2026-09-11, which repointed a comment
  and moved no rule. `find body/app -name '*.css'` outside `node_modules` still finds that one
  file, imported only by `main.tsx`, and `SOURCE_SUFFIXES` is unchanged. The stylesheet is no
  longer the longest hand-written source: the live injection test grew past it on 2026-09-13 and
  stands at 2818 lines.
