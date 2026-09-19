# The uid rows are measured where the listing answers the ask

**Status:** open, fix when it bites
**Area:** email
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-19
**Trigger:** `UID_HELP` or `NOT_FOUND` in `brain/packages/email/src/cortex_email/values.py` is
reworded, the shipped cortex pick changes (`DEFAULT_CORTEX_FILE` in
`brain/packages/model_manager/src/cortex_model_manager/config.py`, the tier whose argv the harness
starts), or a second sitting of `test_uid_reading_live.py` is run. Each is a moment the 2026-09-06
counts are read as evidence about what ships; the first two are read with `git log` on those two
files.

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
- 2026-09-13: the trigger has not fired and the two limits were checked against the harness
  rather than against the published counts. `test_uid_reading_live.py` under
  `brain/packages/orchestrator/tests/` carries one commit, the one that wrote it, and neither
  `UID_HELP` nor `NOT_FOUND` has changed since the sitting: the last commit touching either is
  the one that wrote it. In the harness, `_READ_ASK` asks for "her message about the electricity
  bill" against the listing subject "Electricity bill, final notice", `DRAWS` is 20, and the
  after-not-found row runs three arms over those twenty seeds, which is the sixty draws the body
  names.
- 2026-09-15: read again with the three email entries beside it and nothing has moved. `UID_HELP`
  and `NOT_FOUND` in `brain/packages/email/src/cortex_email/values.py` still carry the words the
  sitting measured, `test_uid_reading_live.py` still asks for "her message about the electricity
  bill" against the listing line "Electricity bill, final notice" over twenty seeds, and the
  trigger has not fired. What this sitting adds is where the entry belongs: closing it needs
  another run on the cortex tier, which is a GPU measurement rather than a mailbox one, so it
  will not be closed by a sitting that has the probe up.
- 2026-09-19: the claims held and the trigger was repaired. It named only a second sitting, which
  is the work that would close this entry, so a rewording or a new cortex pick that left the
  published counts describing words or a model that no longer ship would not have fired it. It
  now names those two directly, with the files they are read from. None has fired:
  `values.py` was last changed by the commit that put the correction into `NOT_FOUND`, which
  precedes the harness's one commit; `DEFAULT_CORTEX_FILE` is still the gemma-4-12B pick, as is
  the `CORTEX_MODEL_FILE_CORTEX` default in `docker/docker-compose.gpu.yml`; and neither sitting launched since, on 2026-09-17 or tonight, runs this
  harness. `_READ_ASK` and `DRAWS = 20` are unchanged, and the sixty draws are the three
  after-not-found arms of the ADR-0022 addendum of 2026-09-06, each `retried=20/20`.
