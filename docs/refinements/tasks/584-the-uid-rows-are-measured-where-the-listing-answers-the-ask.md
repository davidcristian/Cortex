# The uid rows are measured where the listing answers the ask

**Status:** open, fix when it bites
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Trigger:** a second sitting of `test_uid_reading_live.py`, whether for another tier, another
model pick, or a reworded `UID_HELP` or `NOT_FOUND`.

Opened 2026-09-06 by the close of
[571](571-the-cortexs-reading-of-the-uid-description-is-unmeasured.md), which measured the
cortex's reading of the uid description and recorded three counts that read stronger than the
sitting that produced them.

Two limits on that sitting, both in the harness rather than in the finding. The user's ask names
the subject of one listing line almost word for word, "her message about the electricity bill"
against the line reading "Electricity bill, final notice", so a model that matches text has the
answer in front of it and never has to decide what a uid is. And every draw of every arm produced
the same tool call at every one of the twenty seeds, so the counts are rates over twenty draws of
a sampler that had one answer for this turn rather than twenty samples of a distribution. A
`listed=20/20` under both conditions is a weaker reading than the number looks.

The last row opens a third question, about the sentence rather than the harness. `NOT_FOUND`
tells the model to search the folder again, and all sixty draws did something else and cheaper:
they read again with a uid off the listing already in the turn. The sentence names the correction
that works when the listing is gone, and this tier's own recovery is the one for when it is not.
Whether it should name both is a wording question no measurement here answers, since the tier
recovered under an answer that said nothing at all.

**What would close it.** A sitting whose ask does not name a listing line, so a model that
composes a uid has an opening to; a reading that says what the draws are draws of, whether by
varying the ask across seeds or by reporting the identical-reply count beside each rate; and a
decision on whether the correction names the listing as well as the search.

## Trail

- 2026-09-06: opened by the close of
  [571](571-the-cortexs-reading-of-the-uid-description-is-unmeasured.md), which published the
  counts and recorded what they were measured over.
