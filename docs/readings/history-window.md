# Readings: history window tokens

What the history window's character budget comes to in tokens on the cortex's and the deep
candidates' tokenizers, and what else a turn's prompt holds beside it. Cited by
[ADR-0014](../adr/ADR-0014-history-windowing.md) decisions 4 and 7. Token counts depend on the text and
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
context. It checks that the adapter raises `ContextOverflowError`, that a deep phase over the real
adapter ends with `BRAIN_OVERFLOW_NOTE`, and that a cortex turn over it completes with
`CONTEXT_OVERFLOW_NOTE`. All three passed on this server, and the cortex case failed with the
engine catching only `MalformedToolCallError`.

## The cortex's whole prompt

**2026-09-28**, llama.cpp `server` (CPU) build `b10680-d7bd3bfca` serving the cortex's gemma-4-12B
artifact with `--jinja` at `--ctx-size 16384`. It rendered each request with `POST /apply-template`
and counted it with `POST /tokenize` (special tokens parsed, no start token added), so no request
generated a token. The tool stack's two sidecars (`docker-compose.tools.yml`,
`docker-compose.email.yml`) ran on the CPU, and the tools were listed through the brain's own
`build_tool_registry` and `build_cortex_tools`, with every built-in a full deployment offers.

| tools | count | request JSON, characters | request JSON, tokens | as the template renders them |
| --- | --- | --- | --- | --- |
| built-ins: `spawn_subagents`, the volume pair, `capture_screen`, `escalate_to_brain`, five schedule tools | 10 | 9,982 | 2,804 | 2,635 |
| MCP: three email tools and the ten allowlisted filesystem tools | 13 | 9,651 | 2,383 | 1,910 |
| all of them, what a cortex turn is offered | 23 | 19,633 | 5,185 | 4,545 |
| the deep phase's set, without `capture_screen` | 22 | 18,032 | | 4,175 |
| the eight built-ins of the first table | 8 | 7,293 | | 2,009 |

`send_email` is offered only when sending is on, and was not counted. The template adds 15 tokens
to a system message and one user message beyond their text, and 5 for each further message. The
window's texts, counted the same way:

| characters | plain English | ADR prose | Python source |
| --- | --- | --- | --- |
| 16,000 | 3,378 | 4,311 | 4,242 |
| 24,000 | 5,008 | 6,293 | 6,360 |
| 32,000 | 6,731 | 8,540 | 8,556 |
| 48,000 | 10,253 | 13,400 | 12,759 |

At 48,000 the plain and prose counts are the first table's less its start token, and the source
count is 16 tokens over it; the cause was not read. With the preamble (313), the template (15) and
all 23 tools (4,545), 4,873 tokens are fixed before the window:

| window | plain English | ADR prose | Python source |
| --- | --- | --- | --- |
| 48,000 in the cortex's 16,384 | 15,126, 1,258 left | 18,273, 1,889 over | 17,632, 1,248 over |
| 24,000 in the cortex's 16,384 | 9,881, 6,503 left | 11,166, 5,218 left | 11,233, 5,151 left |
| 24,000 in the deep tier's 8,192, its 22 tools | 9,511, 1.16 times | 10,796, 1.32 times | 10,863, 1.33 times |
| 24,000 at a deep context of 16,384 | 6,873 left | 5,588 left | 5,521 left |

The deep rows are rendered on the cortex artifact's template, not the deep pick's own. Recalled
memories, the recap (at most 2,000 characters) and in-turn tool steps come on top of every row.
The 48,000-character ADR prose row, sent to the same server as a streamed chat request with the 23
tools, was refused at once with `exceed_context_size_error` and `n_prompt_tokens` 18274, the count
above plus the start token.
