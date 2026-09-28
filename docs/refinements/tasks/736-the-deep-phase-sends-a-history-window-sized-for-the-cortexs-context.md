# The deep phase sends a history window sized for the cortex's context

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)
**Verified:** 2026-09-28

`CORTEX_HISTORY_CHAR_BUDGET`, 48,000 characters, is the one budget `build_history_window` reads,
and `for_stream` in `engines.py` builds the deep phase's window from it too
(`window=self._window(self.backend, brain)`), while the model host starts the deep tier at
`CORTEX_CTX_SIZE_BRAIN` 8192 ([ADR-0004](../../adr/ADR-0004-model-lineup.md) decision 11). The
brain never reads the deep tier's context, so nothing compares the two.

A full window does not fit. Counted on the tokenizers
([history window readings](../../readings/history-window.md)), 48,000 characters is 10,254 gemma-4
tokens of plain English and 13,401 of this repo's ADR prose, so with the security preamble and the
eight built-in tool schemas a handoff's prompt is 1.55 to 1.94 times the 8192 context before the
MCP tools, recalled memory, the recap and the loop tail. The engine refuses such a prompt with HTTP
400 before generating, and the phase now tells the user that the conversation outgrew the deep
model's context (`BRAIN_OVERFLOW_NOTE`), where it used to say the model had stopped partway. The
handoff still costs a full swap before the refusal.

The remedy the entry first proposed does not hold on either branch:

- **A larger `CORTEX_CTX_SIZE_BRAIN` of 16384** leaves 3,651 tokens after a full window of plain
  English and 504 after one of ADR prose, against the pick's median of 1434 reasoning and 643
  reply tokens a stop-row draw. A context that serves a full dense window is 24576 or more, whose
  VRAM on the pick has not been read (16384 costs 658 MiB more than 8192).
- **A history budget of the deep tier's own** fights the recap. `SummarizingHistoryWindow` keeps
  one stored recap a session, and a stored recap that covers more than the current boundary is
  refolded from the start. A smaller deep budget would fold a recap past the cortex's boundary
  during the handoff, and the cortex's next turn would then refold the whole dropped prefix,
  itself possibly longer than its context. A deep budget needs either a recap the deep phase
  reads without storing, or a trim that keeps the stored recap and drops the turns between.

What would close it:

1. With the card free, read the pick's VRAM at `--ctx-size` 24576 and 32768 beside the 8192 row,
   and decide between a larger deep context and a deep budget with one of the two recap designs
   above.
2. Draw the stop row at the chosen context, the four questions in the readings with three seeds
   each, the pick first, its prediction written here before the draw.

## History

- 2026-09-26: filed by the deep candidates' measurement.
- 2026-09-28: premise confirmed with tokenizer counts on the CPU and the engine's refusal drawn on
  a small CPU server; a deep phase refused for length now ends with `BRAIN_OVERFLOW_NOTE` through a
  typed `ContextOverflowError`. The proposed remedy was corrected: 16384 does not hold a dense full
  window, and a deep budget conflicts with the single stored recap. The cortex's own margin went
  to [R-747](747-the-cortexs-history-budget-leaves-almost-no-reply-room-on-dense-text.md).
