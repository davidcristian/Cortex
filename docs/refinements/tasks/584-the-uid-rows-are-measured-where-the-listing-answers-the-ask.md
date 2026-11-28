# The uid rows are measured where the listing already answers the request

**Status:** done 2026-11-27
**Area:** email
**Origin:** [ADR-0056](../../adr/ADR-0056-email-reader-answers.md)

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

## The rule for the second run

Written 2026-11-27, before the first launch.

- **The request.** Both requests say "the one where she warns that my power will be cut off". The
  request shares no word of four letters or more with any subject on the listing, and the sender
  is on every line, so only the meaning of the request picks "Electricity bill, final notice"
  (uid 1238). The harness fails a request that names a subject word.
- **The draws.** The cortex tier as the stack starts it: the model host on compose defaults, the
  tree's model manager and core bound over the image's packages. A request sends the tools, the
  messages and a seed, nothing else, so the tier's own sampling defaults apply; seeds 0 to 19,
  twenty draws a variant. The server's sampling defaults are read from `/props` and the argv from
  the running process, and both go into the readings. Each variant also reports how many distinct
  calls its twenty draws made: a variant with one distinct call is one answer, not a rate.
- **Reading the uid right.** The first `read_email` call names `INBOX` and uid `1238` copied digit
  for digit: `right`. A listed uid of another line is `other-line`, a uid not on the listing
  (the missing `1224` included) is `unlisted`.
- **`UID_HELP` holds** when the described variant of the copied row shows `unlisted` at most 1/20,
  and the described variant of the `carried` row shows `carried` at most 1/20. A count of 2/20 or
  more on either files a task with the draws; `UID_HELP` does not change on this run.
- **The decision on `NOT_FOUND`**, over the shipped variant of the after not found row. The
  correction names the listing in the turn as well as the search when `unlisted` is 2/20 or more
  (the sentence does not keep the retry on the listing) or `searched` is 10/20 or more (the model
  follows the sentence and spends a call the listing already answers). Before that change ships,
  seeds 20 to 39 must meet the same threshold, and the new text is drawn once and must show
  `unlisted` at most 1/20. Otherwise, with `unlisted` at most 1/20 and `searched` at most 9/20,
  `NOT_FOUND` stays as it is: this tier's own recovery reads the listing, and the search is the
  correction for a turn that holds none.

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
  ([docs/readings/cortex-uid-reads.md](../../readings/cortex-uid-reads.md)).
- 2026-09-30: the claims held and the trigger has not fired. `values.py` changed once since
  2026-09-19, on 2026-09-23, when the search refusal and the folder texts were reworded, and that
  diff leaves `UID_HELP` and `NOT_FOUND` as they were. `DEFAULT_CORTEX_FILE` and the
  `CORTEX_MODEL_FILE_CORTEX` default are still the gemma-4-12B pick. `test_uid_reading_live.py` has
  four commits since, all on 2026-09-23 and all renames, and no run under `measurements/` names it.
  `_READ_ASK` and `DRAWS = 20` are unchanged.
- 2026-10-04: the claims held and the trigger has not fired. `values.py` has no commit since
  2026-09-23, `UID_HELP` and `NOT_FOUND` read as they did then, and `NOT_FOUND` still sends the
  model to search the folder again. `DEFAULT_CORTEX_FILE` and the `CORTEX_MODEL_FILE_CORTEX` default
  are still the gemma-4-12B pick; the one commit to either file since 2026-09-30 rewrote a comment
  on the model host's caps in `docker/docker-compose.gpu.yml`. No run under `measurements/` names
  `test_uid_reading_live.py`, tonight's queue included, and `_READ_ASK` and `DRAWS = 20` are
  unchanged.
- 2026-10-17: checked again and not fired. The change to `values.py` on 2026-10-14 rewords neither
  `UID_HELP` nor `NOT_FOUND`, and `DEFAULT_CORTEX_FILE` has no commit since 2026-10-07.
- 2026-10-25: checked again and not fired: no commit since touched the UID reading files, and the
  cortex file default is unchanged.
- 2026-11-10: checked again and not fired: neither `values.py` nor the model host's `config.py` has
  a commit since 2026-10-25, and no second live run is recorded.
- 2026-11-27: the trigger fired. `DEFAULT_CORTEX_FILE` moved on 2026-11-16 from
  `google/gemma-4-12B-it-qat-q4_0-gguf/gemma-4-12b-it-qat-q4_0.gguf` to
  `unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`, whose chat template differs
  ([R-1238](1238-the-lineups-readings-were-drawn-on-files-the-mount-no-longer-holds.md)), so the
  2026-09-06 counts describe a file that no longer ships. `UID_HELP` and `NOT_FOUND` are unchanged,
  and no second live run is recorded. The work is a count slot on the cortex tier and draws no rate.
- 2026-11-27: done on the rule above. The cortex tier as the stack starts it drew 20/20 `right`
  in every variant of all three rows, each variant one distinct call, so each row is one answer at
  the tier's own sampling defaults; five seeds of a free text request gave four distinct replies,
  so the seed reaches the sampler. `UID_HELP` holds, and with `unlisted` 0/20 and `searched` 0/20
  `NOT_FOUND` stays as it is ([cortex uid reads](../../readings/cortex-uid-reads.md)). The
  turn that holds no listing went to
  [1382](1382-the-not-found-correction-is-undrawn-on-a-turn-that-holds-no-listing.md).
