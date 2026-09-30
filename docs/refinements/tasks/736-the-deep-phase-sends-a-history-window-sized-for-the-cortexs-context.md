# The deep phase sends a history window sized for the cortex's context

**Status:** done 2026-09-30
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)

`CORTEX_HISTORY_CHAR_BUDGET`, 24,000 characters, is the one budget `build_history_window` reads,
and `for_stream` in `engines.py` builds the deep phase's window from it too. At the deep tier's
earlier context of 8192 a full window with the deep phase's 22 tools was 1.16 to 1.33 times the
context ([history window readings](../../readings/history-window.md#the-cortexs-whole-prompt)).
`CORTEX_CTX_SIZE_BRAIN` now defaults to 16384, the cortex's context, which leaves 5,521 to 6,873
tokens after a full window, and a deep budget of its own was rejected because of the one stored
recap ([ADR-0014](../../adr/ADR-0014-history-windowing.md) decision 8). No row has been drawn on
the pick at 16384 on the current engine build, and its 658 MiB context cost was read on an earlier
one.

**What would close it.** Draw the stop row at 16384 on the pick: the four questions of the [stop
rows](../../readings/deep-candidates.md#the-stop-rows), three seeds each, drawn as the pick's row
was, then one fit probe, the plain preamble and the first 48,000 characters of `cortex_core` in
file order (12,759 gemma-4 tokens, more than a full handoff prompt) with `max_tokens` 32. Record
the VRAM above idle at ready, the SM clock and the free memory before the load. The driver is
`measurements/sitting-736/drivers/stop_row_16k.py`, started by `launch_736.sh` beside it from a
`git archive` copy of HEAD once no other run holds the card; about 25 minutes at the pick's 8192
pace, under a 65 minute cap.

**Prediction, written 2026-09-29 before the draw.** Stopped with a reply: 12 of 12 (10 to 12), the
8192 row's one runaway draw now having room to stop; apart from the pick's 11 of 12 only at 5 or
fewer. Reasoning tokens a draw, median 1434 (1000 to 2000). VRAM above idle at ready 19,796 MiB
(19,700 to 20,000), 658 more than the 19,138 at 8192. Decode 1.0 of the 8192 row's rate (0.95 to
1.05) at a matched SM clock. The fit probe answers 200 with `prompt_n` 13,050 to 13,150 and a first
event inside a quarter of the 120 s stall bound. A null result is a stop count of 5 or fewer, a
refused probe or a cost over 1,150 MiB above the 8192 figure: the first two reopen the decision,
the third moves the runbook's 20783 MiB fit figure.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-28: premise confirmed with tokenizer counts on the CPU and the engine's refusal drawn on
  a small CPU server; a deep phase refused for length now ends with `BRAIN_OVERFLOW_NOTE` through a
  typed `ContextOverflowError`. The proposed remedy was corrected: a deep budget conflicts with the
  single stored recap, and with the history budget at 24,000 characters, sized on the cortex's
  whole prompt with the tool stack, a deep context of 16384 leaves the cortex's own margin.
- 2026-09-29: decided and built the larger context. `CORTEX_CTX_SIZE_BRAIN` defaults to 16384 in
  the model host and the GPU override, and a roster test fails at 8192. With the other tiers
  evicted the pick at 16384 was put at 19,796 MiB above idle, the 8192 row's 19,138 plus the 658
  MiB step an earlier build read, on a 24,463 MiB card whose idle floor was recorded at 1,529 to
  3,339 MiB; the fit figure for this card rose by the same 658 MiB. The stop row waits for the
  card, and its prediction is above.
- 2026-09-30: done. The stop row at 16384 stopped with a reply on 12 of 12 draws (held), each the
  8192 row's draw token for token, whose one miss was cut by the context mid-reasoning. The fit
  probe was answered with 12,909 prompt tokens (held on status, not on the count, which assumed
  the longer preamble). The pick read 19,603 MiB above idle (not held, 97 under) and decoded 0.86
  of the 8192 rate (not held), filed as
  [R-757](757-measure-whether-the-deep-tiers-16384-context-slows-decode.md). No null bound fired,
  so the decision and the 20783 MiB fit figure stay
  ([readings](../../readings/history-window.md#the-deep-tier-at-16384)).
