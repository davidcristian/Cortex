# A long generation the server holds back reads as a stalled server

**Status:** open, actionable
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack, a turn asking the cortex to read three 300-line logs with
`read_multiple_files` and count their `ERROR` lines ended after 144.3 s with the error event
`inference_failed: llama-server sent nothing for model 'cortex' within its ceiling`. The model
host's log shows the cortex was decoding the whole time: its fourth completion of the turn
started from a prompt of about 6,700 tokens, ran for 127 s and was cancelled at `n_tokens =
15172`, so about 8,500 tokens were decoded while the brain received no chunk for 120 s
(`CORTEX_INFERENCE_STALL_TIMEOUT_S`). The person saw an error instead of an answer or a note that
the reply was cut, and the error names a silent server that was not silent.

Not known yet: what the 8,500 tokens were. A tool call that llama-server parses before it streams
would send nothing until it is complete, which fits; a reasoning trace would have streamed.

Reproduction: row "one read of three files" in
[tool-result-room.md](../../readings/tool-result-room.md#an-answer-from-cut-results), draw 5 of
the baseline; one draw in five reached it.

## What to do

1. Replay the turn's fourth request against the cortex tier with `stream: true` and save the raw
   event stream, to see what was decoded and whether any of it was sent.
2. If the server holds back a tool call it is still writing, decide whether the stall bound
   should count decoded tokens the server reports (the `timings` it sends) rather than chunks, or
   whether the turn needs a token cap on a tool-calling completion, and name the bound in the
   error either way.

## History

- 2026-10-28: filed from the baseline of the cut-results rows on the `cortexn9` stack.
