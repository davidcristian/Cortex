# A long generation the server holds back reads as a stalled server

**Status:** open, waiting for its trigger
**Area:** inference
**Origin:** [ADR-0005](../../adr/ADR-0005-llamacpp-engine.md)
**Trigger:** a cortex turn ends in `sent nothing for model 'cortex'` while the model host's log shows its slot still decoding
**Verified:** 2026-10-28

On 2026-10-28, on the `cortexn9` stack, a turn asking the cortex to read three 300-line logs with
`read_multiple_files` and count their `ERROR` lines ended after 144.3 s with the error event
`inference_failed: llama-server sent nothing for model 'cortex' within its ceiling`. The model
host's log shows the cortex was decoding the whole time: its fourth completion of the turn
started from a prompt of about 6,700 tokens, ran for 127 s and was cancelled at `n_tokens =
15172`, so about 8,500 tokens were decoded while the brain received no chunk for 120 s
(`CORTEX_INFERENCE_STALL_TIMEOUT_S`). The person saw an error instead of an answer or a note that
the reply was cut.

What the 8,500 tokens were is not known, and they were not a tool call or a trace sent the way
this build sends them. On llama-server build b11913 the cortex's reasoning and a tool call's
arguments both reach the brain one token to a chunk, and the server sends `timings` only with its
last chunk ([readings](../../readings/tool-result-room.md#a-held-back-generation-and-an-unread-file)).
So the server's parser held back text it could not yet place; that is an inference. It means the
longest silence of a working stream is not always the time to first token, which is how ADR-0005
sizes the stall bound.

Reproduction: row "one read of three files" in
[tool-result-room.md](../../readings/tool-result-room.md#an-answer-from-cut-results). One draw in
five reached it at baseline. None of thirty draws behind a recording proxy on the build with the
shipped cut note did, and none of thirty-six host replays of recorded fourth requests.

## What to do

1. When the trigger fires, save the model host's log and `GET /slots` (`is_processing`,
   `next_token.n_decoded`) before anything is recreated. With the recording proxy of the readings
   rig in place, also replay the recorded request through `/completion` on the rendered prompt,
   which streams the decoded text with no parsing, to see what the parser held.
2. Then decide between a token cap on a tool-calling completion and a stall check that asks
   `/slots` whether the slot is still decoding before it fails the turn. A bound that counts the
   server's `timings` cannot work, since they arrive only at the end.

## History

- 2026-10-28: filed from the baseline of the cut-results rows on the `cortexn9` stack.
- 2026-10-28: corrected and set to wait for its trigger. Thirty draws behind a recording proxy and
  thirty-six replays found no silence, and the recorded streams showed that this build streams
  tool calls and reasoning token by token, so the held text was something else.
