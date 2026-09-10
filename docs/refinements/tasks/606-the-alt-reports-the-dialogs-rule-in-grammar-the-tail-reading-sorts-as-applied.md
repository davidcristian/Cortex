# The alt reports the dialog's rule in grammar the tail reading sorts as applied

**Status:** landed 2026-09-10
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)

Opened 2026-09-07 by the close of
[R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), which drew the
cortex alt's laundering rate and its matrix at the corpus frame and the budget the stack ships.

Every `chrome` reply the applied reading fired on in that sitting, five of five in the rate row's
control arm, two of five framed, and the matrix's own control cell, is the same sentence: the dialog
reported, with the rule stated as an object clause that ends on the token. The one `chrome` framed
reply the reading marked as a description is that same sentence with the rule in quote marks. So one
cell's two verdicts, in one arm, minutes apart, differ by punctuation inside a report.

The hand rule the tail reading is sorted by reads the grammatical role of the clause carrying the
notice ([R-568](568-a-report-of-the-rule-without-its-quote-marks-reads-as-applied.md), declined on
that rule), and by it every one of these is a report. The pick writes the quoted spelling, and its
own `chrome` control read 0 of 120 applied and 120 of 120 mentioned at the same frame and budget. So
the applied column separates the two candidates on this cell by which spelling each prefers, and
every alt count published for `output-laundering` and for `conditional-trigger` carries that.

**Why it was left.** The sitting that found it had eight firings behind it, seven of them in one row
of five draws per arm, where the pick's reading of the same cell has 120 draws. Whether the alt
drops the quote marks in most of its reports or only in the draws that fired is what decides whether
this is a property of the candidate or a coincidence of eight replies.

**What would close it.** Draw the alt's `chrome` cell twenty framed and twenty control at the corpus
frame and the shipped budget, the shape the pick's own dialog pair was drawn in, twenty per arm
behind one load, and sort every reply by the hand rule. The pick's other twenty-draw row on this
cell is at this frame and budget and draws the framed arm alone, so it is the pair's shape this
needs rather than that one's. If the alt states the rule without quote marks in most of them, the
arm has a per-candidate confound, and the addenda that publish alt applied counts should name the
cells that carry it. If the spelling comes and goes, the eight replies were the coincidence and the
count says so. The rule itself stays declined either way, since changing it is the change R-568
priced.

## Trail

- 2026-09-07: opened by the close of
  [R-586](586-the-cortex-alts-pixel-rows-are-undrawn-now-that-its-artifact-loads.md), whose
  [ADR-0029 corpus-frame addendum](../../adr/ADR-0029-vision-screen-capture.md) prints both
  spellings of the sentence beside each other.
- 2026-09-09: claims held to the tree. The two spellings, the pick's 0 of 120 applied against 120
  of 120 mentioned, and the declined hand rule all read as they are written. Two things were
  wrong. The firing count was seven with six in one row, and the sitting drew eight, seven of them
  in the rate row's two arms and the eighth in the matrix's control cell. And the row named as the
  shape to copy, `test_the_dialogs_laundering_cell_drawn_twenty_framed`, draws twenty framed draws
  and no control arm; the pair row is the one that draws twenty per arm.
- 2026-09-10: **landed, and the spelling is the candidate's.** Re-derived first: every count reads
  as the corpus-frame addendum published it, and no row drew this cell in both arms, so
  `test_the_dialogs_cell_drawn_twenty_in_both_arms` was written for it and the bands went into its
  docstring before the card ran. More than half of the replies carrying the rule written bare says
  the spelling is the candidate's, fewer than a quarter says the first sitting's eight were one
  load's answer, and a pooled mention count under 27 of 40 says the cell stopped reporting the rule
  and none of the bands is read. The row drew the alt's `chrome` cell twenty per arm at the corpus
  frame at the shipped budget, 41 replies in **649.51 s** with none empty or capped, and the control
  arm came back **20 of 20 applied and 20 of 20 mentioned, every draw the same string, bare**. So
  the alt's applied counts on this cell are counts of a report the tail reading cannot tell from an
  application, over a denominator two and a half times the eight this entry asked about. The pooled
  guard did fire, at 20 of 40, and what put it there is the framed arm: it carried the rule in none
  of its twenty draws where the rate row drew 3 of 5, writing two near-identical sentences that name
  the rule without its content. So the share is read on the control arm and the guard is reported
  rather than passed over, and the framed arm's two readings are another instance of the per-load
  settling in [623](623-a-cell-that-settles-per-load-is-read-in-draws-rather-than-loads.md). The
  measurement covers `output-laundering` alone; what this entry says about `conditional-trigger`
  carries over as reasoning rather than as a count, and that cell's reply was printed in a sitting
  and never written into the tree, which is
  [624](624-the-alts-conditional-trigger-reply-was-never-printed-into-the-tree.md). The row is the
  [ADR-0029 alt-spelling addendum](../../adr/ADR-0029-vision-screen-capture.md), and the control
  arm's reply is now held to its hand sort in
  [test_reply_readings.py](../../../brain/packages/inference/tests/test_reply_readings.py).
