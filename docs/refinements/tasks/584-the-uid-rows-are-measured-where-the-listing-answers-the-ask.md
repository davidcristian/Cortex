# The uid rows are measured where the listing already answers the request

**Status:** open, waiting for its trigger
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)
**Verified:** 2026-09-19
**Trigger:** `UID_HELP` or `NOT_FOUND` in `brain/packages/email/src/cortex_email/values.py` is
reworded, the shipped cortex pick changes (`DEFAULT_CORTEX_FILE` in
`brain/packages/model_manager/src/cortex_model_manager/config.py`), or a second run of
`test_uid_reading_live.py` happens. Each is a moment the 2026-09-06 counts are read as evidence
about what ships; the first two are read with `git log` on those two files.

Two limits on the 2026-09-06 session, both in the harness rather than in the finding. The user's
request names the subject of one listing line almost word for word, "her message about the
electricity bill" against the line reading "Electricity bill, final notice", so a model that matches
text has the answer in front of it and never has to decide what a uid is. And every draw produced
the same tool call at every one of the twenty seeds, so the counts are rates over twenty draws of a
sampler that had one answer for this turn rather than twenty samples of a distribution. A
`listed=20/20` under both conditions is weaker than the number looks.

The last row opens a third question, about the sentence rather than the harness. `NOT_FOUND` tells
the model to search the folder again, and all sixty draws did something cheaper: they read again
with a uid off the listing already in the turn. The sentence names the correction that works when
the listing is gone, and this tier's own recovery is the one for when it is not.

Closing it means a session whose request does not name a listing line, a reading that says what the
draws are draws of, and a decision on whether the correction names the listing as well as the
search.

## History

- 2026-09-06: opened by the close of
  [571](571-the-cortexs-reading-of-the-uid-description-is-unmeasured.md), which published the counts
  and recorded what they were measured over.
- 2026-09-13: the trigger has not fired and the two limits were checked against the harness.
  `test_uid_reading_live.py` has one commit, the one that wrote it, and neither `UID_HELP` nor
  `NOT_FOUND` has changed since. In the harness, `_READ_ASK` asks for "her message about the
  electricity bill" against the listing subject "Electricity bill, final notice", `DRAWS` is 20, and
  the after-not-found row runs three conditions over those twenty seeds, which is the sixty draws
  above.
- 2026-09-15: read again with the three email entries beside it and nothing has moved. What this
  adds is where the entry belongs: closing it needs another run on the cortex tier, which is a GPU
  measurement rather than a mailbox one.
- 2026-09-19: the claims held and the trigger was repaired. It named only a second run, which is the
  work that would close this entry, so a rewording or a new cortex pick that left the published
  counts describing words or a model that no longer ship would not have fired it. It now names those
  two directly, with the files they are read from. None has fired: `values.py` was last changed by
  the commit that put the correction into `NOT_FOUND`, which precedes the harness's one commit;
  `DEFAULT_CORTEX_FILE` is still the gemma-4-12B pick, as is the `CORTEX_MODEL_FILE_CORTEX` default
  in `docker/docker-compose.gpu.yml`; and neither run since, on 2026-09-17 or 2026-09-19, uses this
  harness. `_READ_ASK` and `DRAWS = 20` are unchanged, and the sixty draws are the three
  after-not-found conditions of the 2026-09-06 session, each `retried=20/20`
  ([docs/readings/imap-server-answers.md](../../readings/imap-server-answers.md)).
