# The cortex's reading of the uid description is unmeasured

**Status:** done 2026-09-06
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

`UID_HELP` in `brain/packages/email/src/cortex_email/values.py` tells a model where a uid comes
from, that it names a message only in the folder it was listed in, and that a not-found answer is
final. The wiring in `test_own_texts_bridge_live.py` shows the sentence in the `ToolSpec` the cortex
is prompted with, and nothing shows what the cortex does with it: whether it copies the number off a
`search_emails` line digit for digit, whether it takes a uid from one folder into another, and
whether `message <uid> not found in <folder>` ends its attempts or starts a run of nearby numbers.
The search dialect's description was measured on the cortex that way
(`brain/packages/orchestrator/tests/test_unfenced_correction_live.py`, readings in
`docs/readings/untrusted-framing.md`), and this one was written from the standard and from the shape
of the listing line.

## History

- 2026-09-05: opened by the close of
  [552](552-the-uid-parameter-of-read-email-carries-no-description.md), which measured the
  description through the registry and not on the model.
- 2026-09-06: measured and closed clean. `tests/test_uid_reading_live.py` drove the cortex tier
  through a search and the read it prompts, over a folder holding four messages and one holding
  none, twenty draws per condition. No draw in 140 wrote a uid the listing did not contain, none
  reached into the folder with no mail, and the condition with the `uid` description removed matched
  the shipped one in both rows, so the copying is not something the sentence produces on this tier.
  After a not-found answer every draw read again with a listed uid rather than a nearby one, and did
  so as often under a bare failure with no correction as under the sentence, so the answer ends the
  run of nearby numbers and the sentence is not what ends it. The counts are in
  [docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md). What the session's
  own limits left is [584](584-the-uid-rows-are-measured-where-the-listing-answers-the-ask.md), and
  a stub found in the harness this one was modelled on is
  [583](583-the-correction-harnesss-folder-listing-step-carries-an-empty-answer.md).
