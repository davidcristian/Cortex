# A full handoff prompt leaves the alternate deep model too little context to reply

**Status:** open, actionable
**Area:** inference-model-manager
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-11-23

Behind a handoff prompt of 10,800 tokens, which leaves 5,584 of the deep tier's 16384 context,
gemma-4-31B's `UD-Q4_K_XL` file stopped with a reply on 9 of the 12 stop-row draws
([readings](../../readings/deep-handoff-room.md)). Q4 d1 and d2 spent the whole room reasoning and
wrote no reply, and Q2 d3 was cut 442 tokens into its reply. The rule written before the draw files
this task at 10 or fewer of 12. The deep pick stopped on 11 of 12 at its default `medium`.

The deep phase reads the cortex's character budget, `CORTEX_HISTORY_CHAR_BUDGET`, and keeps no
number of tokens free for the trace and the reply
([ADR-0014](../../adr/ADR-0014-history-windowing.md) decision 8), so a deployment that names the
alternate loses the deep reply on a long chat whenever its trace passes what the window left.
Neither remedy is drawn:

- A deep context above 16384, which ADR-0014 decision 7 leaves to a deployment. The alternate's
  file is already over the model budget at 16384
  ([R-1264](1264-gemma-4-31b-at-16k-is-over-the-model-budget-with-every-layer-on-the-card.md)).
- A lower `CORTEX_HISTORY_CHAR_BUDGET` in a deployment that names the alternate, which shortens
  the cortex's window too. A deep budget of its own is rejected in ADR-0014 decision 8.

What would close it: a row of the alternate behind the same prompt with one remedy in place,
stopping on 11 or more of 12; or a decline stating 9 of 12 in ADR-0004 decision 8 as a cost of the
alternate that a deployment naming it accepts.

## History

- 2026-11-23: filed by the rows behind a full handoff prompt
  ([R-1271](1271-no-stop-row-is-drawn-beside-a-full-handoff-prompt.md)).
