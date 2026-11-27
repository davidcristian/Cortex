# Readings: the embedder's input

How many tokens of `nomic-embed-text-v1.5` a text costs, how long an input the shipped embedder
takes, and what the model card's task prefixes change in recall. Cited by
[ADR-0008](../adr/ADR-0008-memory-v1.md) decision 4, which bounds what the core embeds by these
numbers, and by [ADR-0077](../adr/ADR-0077-model-card-settings.md) decision 6, which lists the
prefix as a difference from the card.

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

## The task prefix

**2026-11-24.** The memory stack's `llama-embed` image (`ghcr.io/ggml-org/llama.cpp:server`, build
`b10680-d7bd3bfca` off `GET /props`), `nomic-embed-text-v1.5.Q8_0.gguf` and its argv
(`--embeddings --batch-size 2048 --ubatch-size 2048 -ngl 0`), called through `LlamaCppEmbedder`
and `embedding_input`. The set is the corpus of the ranked recall readings (`recall_corpus.py`,
41 notes, 22 answerable questions), ranked by cosine over every note. The card's prefixes are
`search_document: ` on a stored text and `search_query: ` on a query. All 150 vectors came back
identical when drawn a second time. A count is of the 22 questions whose gold note is first, in
the top 3 (the `k` of those readings), in the top 5 (`DEFAULT_RECALL_K`) or in the top 20 (the
shipped pool). The separation is the lowest gold score less the highest best hit of the four
`ABSENT` questions, as in [the relevance floor](ranked-recall.md#a-relevance-floor).

| stored rows | query | first | top 3 | top 5 | top 20 | MRR at `k` 3 | separation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| no prefix | no prefix (ships) | 18 | 22 | 22 | 22 | 0.902 | -0.1582 |
| prefix | prefix | 19 | 22 | 22 | 22 | 0.924 | -0.0919 |
| no prefix | prefix | 19 | 22 | 22 | 22 | 0.932 | -0.1514 |
| gold with none, every other row with the prefix | prefix | 16 | 20 | 20 | 22 | 0.818 | -0.1524 |

The first row equals the published cosine column: MRR 0.902, `TRAP` 0.806 and the 0.6325 adjacent
best hit. Three questions move. Under both prefixes the phone number question (`STALE`) rises from
second to first and the Friday release question (`TRAP`) falls from second to third; under the
query prefix alone the release question rises to first; under either, the question where the
conversation state is kept (`TRAP`) rises from third to second. The last row is the worst case of
a store whose newer rows have the prefix and whose older rows do not. Against a prefixed query, a
row with the document prefix scores above the same row without it in 1,298 of the 1,394 question
and note pairs (median +0.0499), so an old gold row falls behind new rows: the state question from
third to nineteenth, the release question from second to sixth. With the roles reversed, the gold
row prefixed and the rest not, 21 of 22 come first. Every separation stays below zero, so no
relevance floor parts the populations under any of the forms. Method: `draw.py` and `offset.py` in
`~/.cache/cortex-run/2026-11-24/s4/`, with the rows of each question in `rows-N.jsonl`,
`rows-P.jsonl`, `rows-M.jsonl`, `rows-W.jsonl` and `rows-W2.jsonl`.

## The task prefix over near-miss notes

**2026-11-27.** The image, build, file, argv and calls of the section above. The set is
`near_miss_corpus.py` in `brain/packages/inference/tests/`: 44 answerable questions over 92
notes, each question with one gold note and one or two near-miss notes that share its words or its
subject and do not answer it, written before any vector was drawn. Each question is ranked by
cosine over every note of that set. All 272 vectors came back identical when drawn a second time.
`/tokenize` counts `search_query: ` and `search_document: ` at 4 tokens each, so a prefixed text of
1800 characters stays 242 tokens under the 2046 a text may take.

| stored rows | query | first | top 3 | top 5 | top 20 | MRR at `k` 3 |
| --- | --- | --- | --- | --- | --- | --- |
| no prefix | no prefix | 43 | 44 | 44 | 44 | 0.989 |
| prefix | prefix | 43 | 44 | 44 | 44 | 0.989 |
| no prefix | prefix | 43 | 44 | 44 | 44 | 0.989 |
| gold with none, every other row with the prefix | prefix | 42 | 44 | 44 | 44 | 0.977 |

The first three forms put every gold note at the same rank. The one gold note not first under any
of them answers how much notice to give: the superseded contract note comes first and the current
one second. In the last form the rent question's gold row falls from first to second, behind a
prefixed note of another question. The rule of
[R-1321](../refinements/tasks/1321-the-embedder-prefixes-need-a-pass-that-embeds-stored-rows-again.md),
written before the rows, reads the first and top 5 counts: the query prefix alone ties both
prefixes and no prefix on each, so it is the form that ships, with no pass. With 43 of 44 first
under no prefix, this set leaves almost no room to separate the forms; the 22 questions above are
the rows where they differ. Method: `draw.py` in `~/.cache/cortex-run/2026-11-27/c1/`, with the
rows of each question in `rows-N.jsonl`, `rows-P.jsonl`, `rows-M.jsonl` and `rows-W.jsonl`.

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
