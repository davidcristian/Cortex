# Readings: leading system messages and the chat templates

What each model family's chat template does with a request that opens with two or three system
messages, and what the adapter's join of those messages costs and changes
([ADR-0071](../adr/ADR-0071-leading-system-messages.md)). Engine `b10680-d7bd3bfca` throughout,
the `server` image on the CPU at `-ngl 0` and `server-cuda` on the card, each at its tier's argv.
The logs are in `measurements/system-join-2026-09-26/`.

## Written before any server started (2026-09-26)

- **Probe answers.** gemma-4 12B, E4B and E2B render every marker for 2 and 3 system messages;
  Qwen3.5 0.8B, 2B and 9B render neither count; Qwen3.6-27B renders 2 and not 3; Qwen3.8-27B
  renders 2 and 3.
- **Deciding latency.** On the 12B on the card, the median probe with a generation in flight is
  under 10 ms, and no probe on any answering server exceeds the 2.0 s timeout. A miss stops the
  change, because the probe runs on every request that opens with several system messages and a
  cache in its place would send a stale answer after a model file changes.
- **Qwen3.5-2B on the CPU.** The brain's real three-system turn and its tool task with a plain
  context each get HTTP 500 from the parent commit's code and HTTP 200 from this change's.
- **The card.** On Qwen3.5-9B a three-system turn through `LlamaCppBackend` answers 200; on the
  gemma 12B the posted body equals the unjoined one; on Qwen3.6-27B the joined request renders the
  recap.

Every one of them held. The live probe ran on the five servers in the second table below. The
answers for gemma-4-E2B, Qwen3.5-0.8B and Qwen3.8-27B come from the vocabulary-only render under
the templates, and Qwen3.8-27B's also from the live render of three system messages in the
[deep candidates](deep-candidates.md#qwen38-27b) readings.

## The templates (2026-09-26)

Six templates by SHA-256 across the google and unsloth files on the models mount. "Merges" means
each system text is trimmed of the engine's whitespace (C `isspace`) and the texts are joined with
one `\n`.

| template | files | two system messages | three |
| --- | --- | --- | --- |
| `ae53464b` | gemma-4 12B, 26B-A4B, 31B | a turn each | a turn each |
| `0a2c8073` | gemma-4 E2B, E4B | a turn each | a turn each |
| `7f0e5290` | Qwen3.5 0.8B, 2B, 4B, and 9B outside the MTP folder | raises `System message must be at the beginning.` | raises |
| `8452ca85` | Qwen3.5-9B UD-Q4_K_XL and Q8_0 from the MTP folder | merges | merges the first two, drops the third |
| `55d49314` | Qwen3.6-27B, its MTP file, the three 35B-A3B files | merges | merges the first two, drops the third |
| `12827f24` | Qwen3.8-27B, Qwen3.8-Flash-Next | merges | merges |

gemma puts the first system text in the header turn with the tool declarations right after it, and
each later one in a system turn of its own after them. The same held with tools and without, and
with thinking on and off. `chat_template_caps.supports_system_role` in `GET /props` is true for all
six, Qwen3.5 included, so it cannot tell them apart.

The llmfan46 files hold five more templates, and no tier, alternate or roster entry names one. Put
through the probe's two and three markers with the engine's template code, `a4aee8af` (the
Qwen3.5-9B Nikusui files) raises like `7f0e5290`, and `2611268e` (Qwen3.5-9B), `e7018ebe`
(Qwen3.6-27B and 35B-A3B), `16e455bc` (gemma-4 12B) and `24d32be0` (gemma-4 26B-A4B and 31B)
render every marker in order, so the probe reads each of them.

Method: the files were rendered through the engine's own template code at a vocabulary-only load,
which matched live `POST /apply-template` on 64 of 64 requests (gemma-4-E2B and Qwen3.5-0.8B).
Five were then asked live through the probe (`test_the_probe_answers_as_the_template_renders` in
`test_system_join_live.py`, with `CORTEX_SYSTEM_JOIN_EXPECT` set to the answers above):

| server | argv | two | three |
| --- | --- | --- | --- |
| gemma-4-E4B, CPU | the subagent entry's, `--parallel 1` | renders | renders |
| gemma-4-12B, card | the cortex tier's | renders | renders |
| Qwen3.5-2B, CPU | the subagent entry's | HTTP 500 | HTTP 500 |
| Qwen3.5-9B UD-Q4_K_XL, card | the cortex tier's | HTTP 500 | HTTP 500 |
| Qwen3.6-27B, card | the deep tier's | renders | drops the third |

## The brain's own requests (2026-09-26)

A cortex turn with the security preamble, a recalled memory holding one trusted and one fenced
note, a stored recap and one tool, and a delegated task with the tool and a plain context, both
built through the real core (`tests/system_led.py`). Method: `test_system_join_live.py`; the
"before" column is the same builders over a `git archive` of the parent commit.

| server | before, turn and task | after |
| --- | --- | --- |
| Qwen3.5-2B, CPU | `/v1/chat/completions` HTTP 500, the template's exception, both | probe HTTP 500, then 200 with one system message, both |
| Qwen3.5-9B, card | the same 500, both | the same probe, then 200, both |
| gemma-4-12B, card | | the posted messages equal the unjoined ones, three system entries; answered |
| gemma-4-E4B, CPU | | the same |
| Qwen3.6-27B, card | | joined and answered 200, its reply cut at the 2048-token cap inside its reasoning |

`POST /apply-template` of the brain's turn on the Qwen3.6-27B server: the unjoined request renders
no part of the recap, and the joined one renders it whole. Both prompts equal the offline renders
byte for byte.

## The probe's cost (2026-09-26)

`test_the_probe_answers_fast_idle_and_beside_a_generation`: 20 or 40 probes of three markers idle,
then the same number while a completion streams on the server.

| server | probes each way | median beside a generation, of the idle median | worst, of the 2.0 s timeout |
| --- | --- | --- | --- |
| gemma-4-12B, card, one slot | 40 | 0.98 | 0.012 |
| Qwen3.5-9B, card, one slot | 40 | 1.04 | 0.013 |
| gemma-4-E4B, CPU, one slot | 20 | 1.02 | 0.011 |
| Qwen3.5-2B, CPU, two slots | 20 | 1.10 | 0.002 |

The deciding row's median beside a generation was 2.41 ms on the 12B, under the 10 ms written
before the run; the card's SM clock read 1815 to 1867 MHz against a 3090 MHz ceiling. A probe
takes no slot: on a one-slot server it answered while the slot was decoding.

## What joining would cost gemma (2026-09-26)

`test_a_turn_per_system_message_keeps_the_tool_block_cached` on the 12B at the cortex tier's argv
(`--cache-ram 8192`), offering ten built-in tools: spawn, the two volume tools, capture,
escalation and the five schedule tools. Each pair is two turns whose recalled memory differs, sent
in the shipped layout (a system turn each) and joined, five pairs each, reading
`timings.prompt_n` and `timings.cache_n` at `max_tokens` 1:

| history before the question | shipped layout | joined |
| --- | --- | --- |
| none | the second turn reuses 2961 tokens and evaluates 244 to 248, 5 of 5 | the second turn reuses 1 and evaluates 3194 to 3202, 5 of 5 |
| 16 turns, about 6570 tokens in all | one turn of each pair reuses 2960, 5 of 5 | every turn reuses 1, 10 of 10 |

The 2960 reused tokens are the header turn, the preamble and the tool declarations, which the
shipped layout keeps ahead of the memory. SM clock 1815 to 1890 MHz against 3090 MHz.

The shipped layout's reuse holds only on a short turn. The 12B's sliding-window layers keep the
last `n_swa` positions plus one micro-batch (`--ubatch-size`), and the engine continues from a shared
prefix only while those cells still cover it, or from a checkpoint, which it takes at user-turn
starts and just before a prompt's end, never ahead of the memory (`tools/server/server-context.cpp`
and `src/llama-kv-cache-iswa.cpp` at `b10680-d7bd3bfca`). So a slot keeps the tool block past a
changed memory only when its last prompt ran less than about one micro-batch beyond it, as in the
no-history row, where 244 to 248 tokens follow the shared prefix.

The 16-turn row does not measure the layout. In rep 0 its first turn reused 2960 tokens straight
after a joined request, whose prompt has no tool block ahead of the memory, so they came from a
state the server kept in host memory (`--cache-ram`); and which turn of a pair reused anything
changed between rep 0 and reps 1 to 4. It depends on what ran before it. A default turn with a
recap follows the memory with about 48,000 characters of kept history, and neither layout was drawn
at that size.
