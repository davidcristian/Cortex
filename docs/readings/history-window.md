# Readings: history window tokens

What the history window's character budget comes to in tokens on the cortex's and the deep
candidates' tokenizers, and what else a turn's prompt holds beside it. Cited by
[ADR-0014](../adr/ADR-0014-history-windowing.md) decision 4. Token counts depend on the text and
the vocabulary, not on the machine, so they are given as counts.

## A full window and what comes with it

**2026-09-28.** Each text was counted with `llama-tokenize` from the `full-cuda` image (build
b10438), which reads the vocabulary alone and never the weights (its log reads a training context
of 0), on the CPU with no GPU reserved. The counts include the one start token the tokenizer adds.

| text | characters | gemma-4 (cortex 12B and deep pick 31B) | Qwen3.8-27B |
| --- | --- | --- | --- |
| plain English, the GPL-3 and GFDL-1.3 texts, spaces collapsed | 48,000 | 10,254 | 10,326 |
| this repo's own ADR prose, ADR-0001 onward | 48,000 | 13,401 | 12,790 |
| Python source, `cortex_core` in file order | 48,000 | 12,743 | 11,617 |
| `SECURITY_PREAMBLE` | 1,386 | 314 | 310 |
| the deep phase's 8 built-in tool schemas as the request's `tools` JSON | 7,293 | 2,165 | 2,095 |

The two gemma-4 artifacts gave identical counts on every text. The tool row is the JSON
`to_openai_tools` sends for the built-ins a handoff offers (the volume pair, `escalate_to_brain` and
the five schedule tools), not the form a chat template renders them in; the MCP sidecars' tools,
recalled memory, the recap and the handoff's loop tail were not counted and come on top.

Against the contexts the model host starts, a full 48,000-character window plus the preamble and
those schemas is:

| context | plain English | ADR prose |
| --- | --- | --- |
| deep tier, `CORTEX_CTX_SIZE_BRAIN` 8192 | 12,733, 1.55 times the context | 15,880, 1.94 times |
| cortex, `CORTEX_CTX_SIZE` 16384 | 12,733, 3,651 tokens left | 15,880, 504 tokens left |

For scale, the deep pick's stop-row draws decoded a median of 1434 reasoning tokens and its replies
a median of 643 ([deep candidates](deep-candidates.md#the-stop-rows)).

Method: each text is the first 48,000 characters of its source, and each count is
`docker run --rm --entrypoint /app/llama-tokenize ghcr.io/ggml-org/llama.cpp:full-cuda
-m <artifact> -f <text> --show-count --log-disable`.

## What the engine answers to a prompt longer than its context

**2026-09-28**, llama.cpp `server` (CPU) build `b10680-d7bd3bfca`, the build the deep candidates
were drawn on, serving Qwen3.5-0.8B Q8_0 at `--ctx-size 512`. A streamed chat request of 1559
prompt tokens was answered at once with HTTP 400 and this body, before any token was generated:

```json
{"error":{"code":400,"message":"request (1559 tokens) exceeds the available context size (512 tokens), try increasing it","type":"exceed_context_size_error","n_prompt_tokens":1559,"n_ctx":512}}
```

`test_context_overflow_live.py` (`integration`-marked) re-takes it against the server at
`CORTEX_OVERFLOW_ENDPOINT` serving `CORTEX_OVERFLOW_MODEL`, sized from that server's own `/props`
context, and checks both that the adapter raises `ContextOverflowError` and that a deep phase over
the real adapter ends with `BRAIN_OVERFLOW_NOTE`. Both passed on this server.
