# The stall bound times a whole prompt evaluation as one silence

**Status:** open, waiting for its trigger
**Trigger:** Qwen3.8-Flash-Next or another candidate clears every row its pick needs but the
first-token floor, or a change sets out to shorten the CPU pool's 600 s stall ceiling.
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-10-01

The adapter's per-read stall ceiling (`CORTEX_INFERENCE_STALL_TIMEOUT_S`, 120 s, and
`CORTEX_SUBAGENTS_STALL_TIMEOUT_S`, 600 s) bounds the gap between two streamed chunks, and
`build_payload` does not ask for `return_progress`. llama-server therefore sends nothing until the
first token, and the ceiling has to clear the whole prompt evaluation. With `return_progress` set,
the server sends a `prompt_progress` chunk after each prompt step, so the ceiling would bound one
step instead, and a stuck server would still be caught within it.

On Qwen3.8-Flash-Next at the shipped 24g cap the 6184-token prompt sent its first delta at 198.0 s,
while the longest gap between two progress chunks was 88.1 s
([Qwen3.8-Flash-Next](../../readings/flash-next.md)). Under progress chunks that row would clear
the 120 s bound. At a prompt batch of 8192 the longest gap rose to 97.2 s, so this route suits the
engine's default batch better.

What to check before building it:

1. The shape of a progress chunk on the deployed build, and that `consume_chunk` in
   `cortex_inference/decode.py` reads it as a chunk with no text rather than a protocol error.
2. That the CPU pool's `server` image sends progress chunks too, and what one step costs there,
   since its 600 s ceiling was sized on a whole first token.
3. Whether the stall bound should then be sized on a step, and how the floor in
   [ADR-0004](../../adr/ADR-0004-model-lineup.md) decision 8 is written, since it names the first
   chunk of the 3400-word prompt.

## History

- 2026-10-01: filed by
  [735](735-flash-nexts-feasibility-row-is-not-complete-at-the-shipped-memory-cap.md), whose first
  row at the shipped cap logged the progress chunks its driver asked for.
- 2026-10-02: trigger not fired. With context checkpoints off at a prompt batch of 8192 the server
  took the 6184-token prompt in one step, its progress chunks coming at 0 s and at 186.8 s with the
  first delta ([771](771-flash-nexts-first-prompt-step-is-a-54-token-checkpoint.md)), so this
  route bounds a step only where the batch or a checkpoint splits the prompt.
