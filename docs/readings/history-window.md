# Readings: history window tokens

What the history window's character budget comes to in tokens on the cortex's and the deep
candidates' tokenizers, and what else a turn's prompt holds beside it. Cited by
[ADR-0014](../adr/ADR-0014-history-windowing.md) decisions 4, 7 and 8, and by
[ADR-0008](../adr/ADR-0008-memory-v1.md) decision 4 for the recalled memories. Token counts depend on the text and
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

## Recalled memories in the prompt

**2026-10-07**, a scratch stack (compose project `cortexs16`, its own volumes) with the cortex
gemma-4-12B on the GPU at `--ctx-size 16384`, counted through its `/tokenize`, at SM 0.65 to
0.67 of `clocks.max.sm`. Ten exchanges were recorded in ten sessions, each a one-line fact before the first
10,000 to 12,000 characters of an ADR, with a one-sentence reply: 7,537 to 12,362 characters each.

| block, as the turn renders it | characters | tokens | characters per token |
| --- | --- | --- | --- |
| five recalled exchanges, whole | 50,847 | 13,292 | 3.83 |
| the same five within a budget of 6000 characters | 6,312 | 1,620 | 3.90 |
| the five longest of the ten, whole | 56,943 | 15,190 | 3.75 |

Before the budget, the fifth record turn recalled four whole exchanges, its prompt filled the
context (16,305 tokens and `truncated = 1` in the engine's log), and its reply was only the
length-limit note. The whole five-exchange block with the 4,873 fixed tokens of a full tool stack
is 18,165 tokens, past the context before any history. With the budget, a new session asked about
the fact the exchanges shared; the turn completed with no overflow or length note in 4,380 tokens
of prompt and reply, and named six of the seven details asked for. The seventh was in a sixth
matching exchange, which the recall's five did not include. The real stores held too little to
size the block: 2 memories of at most 41 characters, and 73 exchanges of at most 2,013 characters
in test sessions.

Method: `measurements/recall-budget-2026-10-07/`: `live.py` for the turns, `blocktokens.py` for the
counts, the engine's and the brain's logs, and `exchanges.json` and `sorin.json` for the texts.

## The deep tier at 16384

**2026-09-30**, the deep pick `gemma-4-31B-it-qat-q4_0` alone on the card, llama.cpp `server-cuda`
`b10680-d7bd3bfca` (`sha256:952424b09abc`), the build of the pick's 8192 [stop
row](deep-candidates.md#the-stop-rows), started with the argv `ModelHostConfig(...).tiers()` builds
at the shipped default (`-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 0`) under the
model host's caps. The stop row was redrawn as the 8192 one was, and one fit probe followed. Before
the load the card read 2,239 MiB used of 24,463 and an SM clock of 0.71 of max. The predictions are
R-736's, written before the draw.

| reading | predicted | read | held |
| --- | --- | --- | --- |
| stopped with a reply, of 12 | 12 (10 to 12) | 12 | yes |
| right by hand, of 12 | | 11 | |
| reasoning tokens a draw, median (range) | 1434 (1000 to 2000) | 1434 (832 to 8341) | yes |
| reply tokens a draw, median (range) | | 680 (69 to 895) | |
| VRAM above idle at ready | 19,796 MiB (19,700 to 20,000) | 19,603 MiB | no, 97 under |
| decode, of the 8192 row's rate on the same draw | 1.0 (0.95 to 1.05) | 0.86 (0.83 to 0.92) | no |
| fit probe status | 200 | 200 | yes |
| fit probe prompt tokens | 13,050 to 13,150 | 12,909 | no |
| fit probe first event, of the 120 s stall bound | under 0.25 | 0.097 | yes |

The stop row ran at SM 0.58 of max (0.43 to 0.68) under a power ceiling of 0.85, against 0.57 and
0.87 for the 8192 row, and the fit probe at 0.51. The load took 0.39 of the 300 s load bound.

**The draws are the 8192 row's.** Eleven of the twelve replies match the 8192 row's character for
character. On Q4 d3, the one 8192 draw that did not stop, the reasoning repeats all 7,923 tokens
that draw spent, then runs 418 more and replies in 788: its 266 prompt tokens and 9,134 generated
are 1,208 past 8192. That draw was cut by the context, not a runaway, and the larger context changed
no sampled token. Its reply is right (16 hours, a roster that covers every shift); the wrong one is
Q4 d1, as at 8192.

**The cost.** 19,603 MiB is 465 over the 8192 row's 19,138, where 658 was read on 2026-08-04 on an
earlier build ([model lineup](model-lineup.md)). The two loads are on different nights, and both
rows read about the same memory used at the median of their busy readings (21,806 and 21,810 MiB),
so the step between them is the difference in the idle floor read before each load. That floor
moves: it fell 233 MiB during this row, and against the 2,006 MiB read after the removal the cost
is 19,836. The null bound, 1,150 over the 8192 figure, was not reached. Read in one session
([below](#decode-at-16384-in-one-session)), the step is 664 to 667 MiB and the cost 19,788 to
19,803, inside the prediction.

**The decode rate.** The 8192 row decoded the same tokens, so each draw's work was the same. The SM
clock does not account for the gap: the Q3 draws read 0.85 to 0.87 at SM 0.59 to 0.60 against 0.56
to 0.57, and Q4 d1, at the same enforced limit, 0.86 of `power.max_limit`, and a draw of 0.85 of it
in both rows, read 0.91. The ratio rose over this row, 0.83 on the first draw to 0.92 on the
eleventh, and neither row recorded the memory clock. In one session the two contexts decode at the
same rate ([below](#decode-at-16384-in-one-session)), so the gap is the two sessions' card state,
and so is most of the stop-row wall a draw, 1.20 of the 8192 row's median at the median.

**The fit probe** sent the plain preamble and the first 48,000 characters of `cortex_core`'s modules
in sorted order, then "Reply with the single word OK.", with `max_tokens` 32. It was answered with
12,909 prompt tokens, 2,046 more than the largest full handoff prompt above (10,863), leaving 3,475.
The engine reported 12,768 as `prompt_n` and 141 reused from the previous draw. The prediction added
the 313 tokens of the 1,386-character `SECURITY_PREAMBLE`, where the driver sends the 598-character
plain preamble, a difference of about the gap's size that was not counted on its own.

Method: `measurements/sitting-2026-09-30/736.log` and `736pick16k/` (draws, clock readings, the fit
probe and the server log), driver `stop_row_16k.py` over `deeplib.py` and `questions.py` in that
run's `drivers/`, run from a `git archive` copy of the tree.

## Decode at 16384 in one session

**2026-09-30**, 05:35 to 06:00, three hours after the stop row above: the same pick, build and image,
alone on the card, loaded four times in the order 8192, 16384, 8192, 16384, each the tier's argv
with only `--ctx-size` changed. Each load drew the stop row's Q1 and Q3 at seeds 101 to 103 and 301
to 303, and a sampler read the card every 5 s, now with `clocks.current.memory`. Written before the
draw: each 16384 load's median rate over its six draws, against the same draws on the 8192 loads
beside it, reads 0.80 to 0.93 on both if the context costs decode; 0.97 to 1.03 on both is the null
result, which puts the stop row's 0.86 on that night's card.

| load | context | decode median, of load 1's | draws, of load 1's | above idle at ready, MiB | SM of max, median (range) | memory clock, of load 1's | power ceiling of max | cap active |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 8192 | 1.000 | 0.973 to 1.012 | 19,121 | 0.58 (0.51 to 0.64) | 1.00 | 0.89 | 58 of 58 |
| 2 | 16384 | 0.999 | 0.970 to 1.007 | 19,788 | 0.58 (0.51 to 0.60) | 1.00 | 0.88 | 58 of 58 |
| 3 | 8192 | 1.000 | 0.982 to 1.013 | 19,139 | 0.58 (0.45 to 0.62) | 1.00 | 0.88 | 58 of 58 |
| 4 | 16384 | 1.002 | 0.998 to 1.005 | 19,803 | 0.58 (0.55 to 0.63) | 1.00 | 0.89 | 57 of 57 |

Clock columns are the busy readings (utilization 50% or more) over each load's draws; the memory
clock read one value on every reading of the row. All 24 draws stopped, and each seed gave the same
tokens on all four loads.

**The null result on both loads.** Against the same draws on the 8192 loads beside it, load 2 read
0.999 at the median draw (0.978 to 1.009) and load 4 0.998 (0.991 to 1.024); the ratio of the
medians is 1.001 and 1.003. The 16384 context does not slow decode, and the clocks, the power
ceiling and the cap state were the same on every load. The stop row's draws decoded at 0.91 (0.88
to 0.92) of this session's 16384 loads on the same argv and seeds, and the 2026-09-26 8192 row's at
1.06 (1.04 to 1.07) of its 8192 loads, all at SM 0.56 to 0.60. Decode rates from different sessions
therefore differ by up to a seventh at one SM clock, for a reason those rows did not record.

Method: `measurements/sitting-2026-09-30b/757.log` and `757ctx/` (draws, the row's clock readings,
props per load and the server log), driver `ctx_alt.py` over `deeplib.py` and `questions.py` in that
run's `drivers/`, pre-registration in its `prereg.md`, run from a `git archive` copy of the tree.
