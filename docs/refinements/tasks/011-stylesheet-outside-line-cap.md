# The overlay stylesheet outside the line cap

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0011](../../adr/ADR-0011-body-v1.md)
**Trigger:** `find body/app/src -name '*.css'` lists a second file, or
`git log --since='<Verified date> 00:00' --oneline -- body/app/src/overlay.css` lists a commit
whose diff moves a rule to change which rule applies. A commit that edits only comments does not.
**Verified:** 2026-09-22

Once the line cap covered the overlay's TypeScript
([R-010](010-line-cap-overlay-gap.md)), leaving the stylesheet out became a decision rather than
an oversight. `body/app/src/overlay.css` is 2039 lines as of 2026-09-22, almost seven times the
cap every other non-test source file is held to, and no check measures it. It is the longest
hand-written source file in the tree. The one longer file is the Rust stub generated from
[proto/body.proto](../../../proto/body.proto), which is exempt as generated code, and the next
longest, `brain/packages/core/tests/test_engine.py` at 1891 lines, is a test.

It is excluded because the cap's remedy is to split by responsibility, which assumes a module with
a public contract. A stylesheet is one cascade in which order decides which rule applies, so
splitting it trades a long file for `@import` ordering that nothing checks and that fails by
changing what is drawn rather than by reporting an error. That is a fair account of the remedy and
not of the problem: a file this long is exactly the reading load the cap exists to limit.

What would close it: either a cap for `.css` at a width chosen for stylesheets rather than
modules, with the split done by layer (tokens, panel, console, motion) and imported in a fixed
order from one entry sheet, or the same split done for its own sake with the cap following.
The work is the split, not the scanner. A cap at the source width needs only `.css` added to
`SOURCE_SUFFIXES` in `scripts/linecap.py`; a stylesheet width needs a third limit beside the
source and markdown ones. Either way the line in AGENTS.md naming the stylesheet as outside the
limit is removed.

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
- 2026-09-22: Neither half has fired. `wc -l body/app/src/overlay.css` answers 2039, and
  `find body/app -name '*.css'` outside `node_modules` finds that file and a build output under the
  ignored `dist/`. `main.tsx` is still its only importer. The one commit to touch it since
  2026-09-17 renamed a file a comment cites, and with comments removed the file before and after
  that commit is the same. The last commit to change a rule was the 2026-08-09 one defining the roll
  duration in one place. `SOURCE_SUFFIXES` is unchanged at `scripts/linecap.py:15`. The stylesheet
  is the longest hand-written source, with the live injection suite at 1837 lines. The trigger now
  names the two commands that answer it.
