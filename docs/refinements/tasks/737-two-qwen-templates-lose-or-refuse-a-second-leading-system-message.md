# Two Qwen templates lose or refuse a second leading system message

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0004](../../adr/ADR-0004-model-lineup.md)
**Verified:** 2026-09-26

A turn can open with up to three system messages: the security preamble, the recalled memory, and
the recap `SummarizingHistoryWindow` puts first once the window has folded older turns
(`assemble_inference_messages` in `turn_context.py`, `select` in `summarizing.py`). The deep phase
assembles its prompt the same way. A delegated task opens with two when subagent tools are wired
and its context is untainted (`task_messages` in `subagent_attempt.py`). `build_payload` sends each
as its own `role: "system"` message, and what a template does with a second one differs by family:

- **Qwen3.6-27B, the deep alternate**, merges the first two and skips any later system message. A
  live `POST /apply-template` of preamble, memory and recap on `b10680-d7bd3bfca` (2026-09-26) kept
  the first two and dropped the recap
  (`measurements/deep-2026-09-26/alt-r12c-stop/alt.render.three-system.txt`).
- **Qwen3.5**, one template by SHA-256 across the cortex alternate `Qwen3.5-9B-UD-Q4_K_XL` and the
  subagent entries `Qwen3.5-0.8B`, `Qwen3.5-2B` and `Qwen3.5-4B`, raises
  `System message must be at the beginning.` on any system message after the first. On a live
  `Qwen3.5-2B-Q4_K_M` server (`server` image, `b10680-d7bd3bfca`, 2026-09-26) one system message
  renders and answers with HTTP 200, and two fail both `POST /apply-template` and
  `/v1/chat/completions` with HTTP 500 and that exception. So every recalling cortex turn on the
  alternate and every two-system delegated task on the Qwen roster alternate fails.
- **Qwen3.8** merges every leading system message (live, 2026-09-26), and the gemma templates render
  each later one as a system turn of its own.

The injection harness and the switch probe send one system message at most, so neither shows it.
What would close it: one leading system message per request, merged in the core's assembly or in
`build_payload`, with a test asserting that a turn with memory and a recap sends one; or a recorded
decision that those entries are never deployed with recall or subagent tools.

## History

- 2026-09-26: filed by the deep candidates' measurement, whose alternate row rendered the drop live.
