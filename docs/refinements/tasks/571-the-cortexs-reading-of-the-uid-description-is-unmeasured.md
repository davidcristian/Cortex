# The cortex's reading of the uid description is unmeasured

**Status:** landed 2026-09-06
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)

Opened 2026-09-05 by the close of
[552](552-the-uid-parameter-of-read-email-carries-no-description.md), which gave `read_email`'s
`uid` a description and showed it reaching the brain's registry, and no further.

`UID_HELP` in `brain/packages/email/src/cortex_email/values.py` tells a model where a uid comes
from, that it names a message only in the folder it was listed in, and that a not-found answer is
final. `test_own_texts_bridge_live.py`'s wiring shows the sentence in the `ToolSpec` the cortex is
prompted with, and nothing shows what the cortex does with it: whether it copies the number off a
`search_emails` line digit for digit, whether it carries a uid from one folder into another, and
whether `message <uid> not found in <folder>` ends its attempts or starts a run of nearby numbers.
The search dialect's description was measured on the cortex in that shape
(`brain/packages/orchestrator/tests/test_unfenced_correction_live.py`, ADR-0013 unfenced-correction
addendum), and this one was written from the standard and from the shape of the listing line.

**What would close it.** A live pass in that harness's shape, on the GPU stack, driving the cortex
through a search and the read it prompts, over a folder holding mail and one holding none, and
counting the uids it writes that appear on the listing it read against those that do not, and the
calls it makes after a not-found answer. A count that shows a guessed or carried uid is the
trigger for rewording; a clean count records the description as one that works on this tier.

## Trail

- 2026-09-05: opened by the close of
  [552](552-the-uid-parameter-of-read-email-carries-no-description.md), which measured the
  reading through the registry and not on the model.
- 2026-09-06: measured and closed clean. `tests/test_uid_reading_live.py` drove the cortex
  tier through a search and the read it prompts, over a folder holding four messages and one
  holding none, twenty draws an arm. No draw in 140 wrote a uid the listing did not carry, none
  reached into the folder holding no mail, and the arm with the `uid` description stripped out
  matched the shipped arm in both rows, so the copying is not something the sentence produces on
  this tier. After a not-found answer every draw read again with a listed uid rather than a
  nearby one, and did so as often under a bare failure carrying no correction as under the
  sentence, so the answer ends the run of nearby numbers and the sentence is not what ends it.
  The counts and the readings behind them are in the ADR-0022 addendum of that date. What the
  sitting's own limits left is
  [584](584-the-uid-rows-are-measured-where-the-listing-answers-the-ask.md), and a stub found in
  the harness this one was shaped after is
  [583](583-the-correction-harnesss-folder-listing-step-carries-an-empty-answer.md).
