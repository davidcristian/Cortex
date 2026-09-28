# The cortex's history budget leaves almost no reply room on dense text

**Status:** open, actionable
**Area:** session-history
**Origin:** [ADR-0014](../../adr/ADR-0014-history-windowing.md)
**Verified:** 2026-09-28

ADR-0014 sized `CORTEX_HISTORY_CHAR_BUDGET` at 48,000 characters on four characters a token,
leaving about a quarter of the cortex's 16384-token context for everything else. Counted on the
cortex's tokenizer ([history window readings](../../readings/history-window.md)), a full window is
10,254 tokens of plain English but 13,401 of this repo's ADR prose and 12,743 of Python source.
With the security preamble (314) and the eight built-in tool schemas (2,165), the dense window
leaves 504 tokens, before the MCP sidecars' tool schemas, recalled memory, the recap, in-turn tool
steps and the reply.

When the prompt does not fit, the engine answers 400 with `exceed_context_size_error` and the
adapter raises `ContextOverflowError`. `TurnEngine` catches only `MalformedToolCallError`, so on the
cortex the overflow reaches the gRPC boundary as an error, with no note of the kind the deep phase
now writes.

What would close it:

1. Count the MCP sidecars' tool schemas as the cortex receives them, with the tool stack up, and a
   rendered prompt through `POST /apply-template` so the template's own tokens are included.
2. Decide between a lower default, a budget stated in tokens with a per-deployment ratio, and
   leaving the budget and ending an overflowing cortex turn with a note, and write the choice into
   ADR-0014 decision 4.

## History

- 2026-09-28: filed while checking
  [R-736](736-the-deep-phase-sends-a-history-window-sized-for-the-cortexs-context.md), whose
  tokenizer counts showed the cortex's own margin.
