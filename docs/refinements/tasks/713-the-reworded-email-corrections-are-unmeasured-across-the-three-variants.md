# The reworded email corrections are unmeasured across the three variants

**Status:** done 2026-09-24
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)

Decision 11 of [ADR-0013](../../adr/ADR-0013-untrusted-content.md) runs
`test_unfenced_correction_live.py` and `test_own_texts_bridge_live.py` again when a sidecar
sentence changes. On 2026-09-23 `SEARCH_REFUSED` and `FOLDER_UNKNOWN` were reworded in
`cortex_email/values.py` and `cortex_orchestrator/own_texts.py` after the paired draws in
[model-read-wording](../../readings/model-read-wording.md), which drew only the shipped variant,
old wording against new. `test_unfenced_correction_live.py` has not run on the new wording.

Those draws also read the old refused-search correction at 6 of 20 corrected queries. On
2026-09-04 the same variant read 13 of 20, and the fenced control and the bare failure 3 of 20 each
([untrusted-framing](../../readings/untrusted-framing.md#a-sidecars-correction-fenced-and-unfenced)).
The conditions differ: the tool list gained the uid description of `read_email` on 2026-09-05, and
the paired driver turned the engine's prompt cache off on each request, which the harness does not.
So whether the unfenced correction still does better than the bare failure on the cortex is
unmeasured.

**What would close it.** `test_unfenced_correction_live.py` run on the reworded tree, both rows and
all three variants, with its counts replacing the 2026-09-04 table in untrusted-framing.md, and
`test_own_texts_bridge_live.py` run against a Bridge per
[email-imap](../../runbooks/email-imap.md). If the shipped refused-search variant no longer reads
above the bare failure, decision 10 of ADR-0013 has lost the reading it cites for the
refused search, and that decision is examined again.

`test_own_texts_bridge_live.py` ran on the new wording on 2026-09-24 at 01:46, from a frozen copy
of the tree, against the Bridge on 127.0.0.1:1143: three rows passed, and the refused-search
row passed its trusted assertions and then skipped its send half, since `~/.cortex/email.env` has
no SMTP credentials. Log: `measurements/sitting-2026-09-24/713b.log`.

**Pre-registered 2026-09-24.** The unattended run logged at `measurements/sitting-2026-09-24/`
draws both correction rows of `test_unfenced_correction_live.py` from a frozen copy of the
reworded tree, one pytest process and one load per row (`713s.log`, `713f.log`), twenty seeds per
variant as the file sets them and the prompt cache on as the file leaves it. A recorder writes each
reply's tool calls with their arguments to the row's `.calls.jsonl`. The deciding count is the
refused-search row's corrected queries, unfenced against the bare failure: the unfenced variant
reads above it when a two-sided Fisher exact test on the twenty draws each reads p below 0.05,
which against a bare 3 needs 10 or more. Predicted, with a 90% range: unfenced 6 (2 to 12), fenced
3 (0 to 7), bare 3 (0 to 7), not apart; the folder row 20 of 20 in each variant (18 to 20).

## History

- 2026-09-23: opened by the email texts' rewording under
  [R-707](707-model-read-texts-keep-banned-words.md).
- 2026-09-24: done. Drawn as pre-registered, the refused-search row read unfenced 2, fenced 6 and
  bare 2 of 20, and every folder variant 20 of 20. Unfenced against bare reads p 1.0, so the
  unfenced correction does not read above the bare failure, and the prediction held in every
  variant. The replies' recorded calls agree with the harness marks; one fenced draw counted as
  corrected searched `ALL` and dropped the sender. The table in
  [untrusted-framing](../../readings/untrusted-framing.md#a-sidecars-correction-fenced-and-unfenced)
  now holds these counts. Examined again, decision 10 of
  [ADR-0013](../../adr/ADR-0013-untrusted-content.md) stands on the send the taint would cost, and
  no longer names the correction as a reason. The draws that did not correct the query called
  `list_folders` first. Drawn again the same day with that call answered by the sidecar's listing,
  the query after it read unfenced 19, fenced 19 and bare 17 of 20, p 0.60 unfenced against bare,
  so decision 10 stands unchanged.
