# The deep phase sends a history window sized for the cortex's context

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)
**Verified:** 2026-09-26

`CORTEX_HISTORY_CHAR_BUDGET`, 48,000 characters, is sized as "about 12K tokens of history against
the 16K-token cortex context" (ADR-0014 decision 4). It is the one budget `build_history_window`
reads, and `for_stream` in `engines.py` builds the deep phase's window from it too
(`window=self._window(self.backend, brain)`), so a handoff can send the same 48,000 characters to a
deep tier started at `CORTEX_CTX_SIZE_BRAIN` 8192 ([ADR-0004](../../adr/ADR-0004-model-lineup.md)
decision 11). The security preamble, recalled memory, the schemas of the cortex's tools and the
deep builtins, and the handoff record's loop tail come on top. Nothing in the tree records the gap,
and what the engine and the brain do with a prompt longer than the context has not been drawn.

Two readings of 2026-09-26 bear on it ([deep candidates](../../readings/deep-candidates.md)). The
same 3400-word text was 4018 tokens for the pick's tokenizer and 6184 for Qwen's, a prompt of rare
words and so only an indication that a full window alone can pass 8192 on either. And with a prompt
of about 300 tokens, the pick filled the 8192 context with reasoning on 1 of 3 draws of one stop-row
question and Qwen3.8-27B at its default effort on 2 of 3, so a long handoff prompt leaves less room
for the reply the tier exists for.

What would close it:

1. Count a full window, the preamble, the tool schemas and a loop tail on each deep candidate's
   tokenizer (`POST /tokenize`), and send one over-length handoff through the deep phase, recording
   what fails and what the user is told.
2. Choose between a history budget of the deep tier's own and a larger `CORTEX_CTX_SIZE_BRAIN`:
   16384 costs the pick 658 MiB more and Qwen3.8-27B 511 MiB more.
3. Draw the stop row at the chosen context, the four questions in the readings with three seeds
   each, the pick first, its prediction written here before the draw.

## History

- 2026-09-26: filed by the deep candidates' measurement.
