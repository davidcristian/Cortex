# Readings: the embedder's input

How many tokens of `nomic-embed-text-v1.5` a text costs, and how long an input the shipped
embedder takes. Cited by [ADR-0008](../adr/ADR-0008-memory-v1.md) decision 4, which bounds what the
core embeds by these numbers.

## Characters per token

**2026-10-07.** A CPU `llama-server` started as the memory stack starts `llama-embed`
(`ghcr.io/ggml-org/llama.cpp:server`, `nomic-embed-text-v1.5.Q8_0.gguf`), counted through its
`/tokenize`, which leaves out the model's two framing tokens. A character is a Python code point.

| text | characters | tokens | characters per token |
| --- | --- | --- | --- |
| English prose, `docs/adr/*.md` (74 files) | 923,338 | 247,918 | 3.72 |
| English prose, `docs/readings/*.md` (67 files) | 579,491 | 176,380 | 3.29 |
| the densest English file | 2,193 | | 2.68 |
| Python, `cortex_core` (131 files) | 434,371 | 119,774 | 3.63 |
| Rust, `body/crates` (88 files) | 491,831 | 145,303 | 3.39 |
| TypeScript, `body/app/src` (158 files) | 806,312 | 260,764 | 3.09 |
| the densest code file | 1,192 | | 2.34 |
| `package-lock.json` | 142,682 | 63,977 | 2.23 |
| Romanian | 306 | 121 | 2.53 |
| Hindi | 321 | 156 | 2.06 |
| UUIDs, hex digests, base64 | 26,548 | 18,880 | 1.37 to 1.43 |
| Korean | 185 | 138 | 1.34 |
| Greek, Russian, Arabic | 943 | 762 | 1.22 to 1.27 |
| random code points across the BMP (5 runs of 800) | 4,000 | 3,119 | 1.26 to 1.31 |
| Japanese | 163 | 157 | 1.04 |
| Chinese | 175 | 175 | 1.00 |
| runs of punctuation, dashes, dotted letters | 1,679 | 1,679 | 1.00 |

No text measured more than one token per character. The tokenizer splits each CJK character and
each punctuation mark into a token of its own and turns a Hangul syllable into one token, while
combining marks, full-width forms, ligatures and emoji cost less than one token per character.

## The input bound

**2026-10-07**, same server, started with `--batch-size 2048 --ubatch-size 2048`. An input of
2046 tokens of text embedded; one of 2047 failed with `500`, `input (2049 tokens) is too large to
process`, for both `東` and `-` repeated. The two framing tokens count against the 2048, so the
text has 2046. At one token per character, 1800 characters is at most 1800 tokens, 246 below
that bound.

## A long exchange, recorded and recalled

**2026-10-07**, a scratch stack (compose project `cortexs15`, its own volumes) built at the bound
of 1800 characters, with the cortex on the GPU. One session pasted 12,000 characters of ADR text
after a one-line fact and asked for a one-sentence reply; the exchange came to 12,377 characters
and 3,390 embedder tokens. It was stored whole, with no `memory write unavailable` line in the
brain's log; the embedder's only refusals were the four inputs `boundary.py` sent past its bound.
A new session then asked for the neighbour's pet, and the cortex answered from the recalled
memory: "a blue-tailed skink named Sorin, which lives in Timisoara".

Method: `measurements/embedding-input-2026-10-07/`: `measure.py` and `adversarial.py` for the
ratios, `boundary.py` for the bound, `live.py` with `up.sh` for the stack, and the brain's and the
embedder's logs. The integration-marked `test_the_input_bound_holds_on_the_live_server` in
`brain/packages/embedding/tests/test_embedder_live.py` checks the bound again against a running
server.
