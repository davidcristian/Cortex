# The reworded email corrections are unmeasured across the three variants

**Status:** open, actionable
**Area:** untrusted-content
**Origin:** [ADR-0013](../../adr/ADR-0013-untrusted-content.md)
**Verified:** 2026-09-23

Decision 11 of [ADR-0013](../../adr/ADR-0013-untrusted-content.md) runs
`test_unfenced_correction_live.py` and `test_own_texts_bridge_live.py` again when a sidecar
sentence changes. On 2026-09-23 `SEARCH_REFUSED` and `FOLDER_UNKNOWN` were reworded in
`cortex_email/values.py` and `cortex_orchestrator/own_texts.py` after the paired draws in
[model-read-wording](../../readings/model-read-wording.md), which drew only the shipped variant,
old wording against new. Neither harness has run on the new wording.

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

## History

- 2026-09-23: opened by the email texts' rewording under
  [R-707](707-model-read-texts-keep-banned-words.md).
