# Spawn spec uptake

What the cortex writes into a `spawn_subagents` item when the spec offers it a named choice. The
`role` property is [ADR-0072](../adr/ADR-0072-subagent-roles.md)'s; the reading of the `model`
choice, taken 2026-08-04, is stated in [ADR-0018](../adr/ADR-0018-heterogeneous-subagents.md)
decision 8.

## The role property

**2026-09-29**, gemma-4-12B QAT q4_0, the cortex pick, on CPU while another run held the card:
`ghcr.io/ggml-org/llama.cpp:server` at `sha256:db057ec90de0`, `build_info` `b10680-d7bd3bfca`, under
`docker --cpuset-cpus 12-23`, with the cortex tier's argv at `-ngl 0` (`--ctx-size 16384 --parallel 1
--jinja --cache-ram 8192`, no projector, no reasoning budget) and `--threads 12`. Requests were
unseeded at the server's default sampler, temperature 1.0. `spawn_subagents` was the only tool,
built as the shipped wiring builds it: the default one-entry roster, so no `model` property, and
`SHIPPED_ROLES`. Each turn is one ask inviting delegation ("I would rather you hand this to a
subagent than do it yourself.") of one summary, one extraction or one lookup over one of four short
notes, and stops at its first dispatch, so no subagent ran. Written before the first row: no item
naming a role is the null result, and a kind whose items name a wrong role more often than the
matching one says the names or descriptions mislead the cortex. The row is two passes of the twelve
asks, drawn by `test_the_cortex_names_the_role_of_the_subtask_it_delegates` in
`brain/packages/orchestrator/tests/test_spawn_nudge_live.py`; the logs are under
`measurements/role-uptake-2026-09-29/`.

| ask | expected | turns delegating | items naming a role | naming the expected one | named instead |
| --- | --- | --- | --- | --- | --- |
| "Summarize the note below in two sentences, keeping its figures, names and dates." | `precis` | 8/8 | 8/8 | 8/8 (0.68 to 1.00) | none |
| "List every date the note below mentions." | `excerpt` | 8/8 | 8/8 | **0/8 (0.00 to 0.32)** | `answer`, 8 |
| "What total cost does the note below state?" | `answer` | 8/8 | 8/8 | 8/8 (0.68 to 1.00) | none |

Each turn wrote one batch of one object item, so the 24 items are the 24 turns. Intervals are Wilson
95%. The property is taken up: every item named a role, none outside the enum. The summary and the
lookup named their own role every time, and every extraction named `answer`, so on this condition
the extraction kind's wrong name outnumbers its right one. The four notes read alike in every cell.
Two further extraction turns, drawn after the row to print each item as written, named `answer`
again and put the note inside the instruction with no `context`.

A turn evaluated 857 prompt tokens cold and 111 to 127 once the engine's prompt cache held the
header and the tool declaration, and wrote 186 to 1024 tokens of reasoning and call, 318 at the
median. No wall clock is quoted: the other run shared the machine throughout.

**2026-09-30**, the same condition, image, build and argv, to read whether the extraction result
rests on the one ask's "List": a second extraction wording, "Extract every number from the note
below.", the verb of the measured extraction shape, drawn beside the first extraction ask as a
same-session control. Two draws of each over the four notes, 16 turns, fixed before the first
draw with the null result and the rule above; the new ask is the `numbers` entry of the probe's
`_ROLE_ASKS`, and the logs are under `measurements/role-uptake-2026-09-30/`.

| ask | expected | turns delegating | items naming a role | naming the expected one | named instead |
| --- | --- | --- | --- | --- | --- |
| "Extract every number from the note below." | `excerpt` | 8/8 | 8/8 | **0/8 (0.00 to 0.32)** | `answer`, 8 |
| "List every date the note below mentions." | `excerpt` | 8/8 | 8/8 | **0/8 (0.00 to 0.32)** | `answer`, 8 |

Each turn again wrote one batch of one item holding only `instruction` and `role`, with the note
inside the instruction. The control repeats the first row, and the second wording names `answer`
every time too, so on this condition the extraction result does not rest on the verb "List" or on
dates. A turn wrote 260 to 553 tokens of reasoning and call, 306 at the median.

**2026-09-30**, the replication on the card, written down before it was drawn: the cortex tier's
argv as `llama_server_argv` builds it (`-ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram
8192`), `ghcr.io/ggml-org/llama.cpp:server-cuda` at `sha256:952424b09abc`, `build_info`
`b10680-d7bd3bfca`, the build of the CPU rows. The SM clock read 1830 to 2070 MHz over the row's 19
samples, 1912 at the median, of a 3090 MHz maximum, with the software power cap not active. The
row ran unattended from a copy of the tree taken before the probe gained its `numbers` ask, so
`-k role` at `CORTEX_ROLE_UPTAKE_DRAWS=4` drew the first row's three asks over the four notes, four
draws each: 48 turns. The rule: it replicates if the extraction asks again name `answer` more often
than `excerpt`. The log is `measurements/sitting-2026-09-30/756.log`.

| ask | expected | turns delegating | items naming a role | naming the expected one | named instead |
| --- | --- | --- | --- | --- | --- |
| "Summarize the note below in two sentences, keeping its figures, names and dates." | `precis` | 16/16 | 16/16 | 15/16 (0.72 to 0.99) | `answer`, 1 |
| "List every date the note below mentions." | `excerpt` | 16/16 | 16/16 | **0/16 (0.00 to 0.19)** | `answer`, 16 |
| "What total cost does the note below state?" | `answer` | 16/16 | 16/16 | 16/16 (0.81 to 1.00) | none |

Each turn wrote one batch of one item. Every extraction named `answer`, so the CPU reading
replicates on the card. The extraction items put the note inside the instruction on 14 of 16 and in
`context` on 2; the one summary naming `answer` put it in `context`. A turn wrote 171 to 822 tokens
of reasoning and call, 330 at the median.

**2026-09-30**, a new `excerpt` description, on CPU in the condition of the CPU rows above (image,
build, argv, threads and cpuset), from a copy of the tree whose one change is that description: "a
list of every item of one kind the text states, each written exactly as the text writes it, for a
subtask that asks for all of them rather than one fact", in place of the shipped "each item the
subtask asks for, written exactly as the text writes it". All four asks over the four notes, one
draw each: 16 turns, fixed before the first draw. The rule: the description moves the cortex if
the extraction asks name `excerpt` more often than `answer`, and it pulls another kind if the
summary or the lookup names its own role on fewer than 3 of 4. The logs are under
`measurements/role-uptake-2026-09-30-excerpt/`.

| ask | expected | turns delegating | items naming a role | naming the expected one | named instead |
| --- | --- | --- | --- | --- | --- |
| "Summarize the note below in two sentences, keeping its figures, names and dates." | `precis` | 4/4 | 4/4 | 4/4 (0.51 to 1.00) | none |
| "List every date the note below mentions." | `excerpt` | 4/4 | 4/4 | 4/4 (0.51 to 1.00) | none |
| "Extract every number from the note below." | `excerpt` | 4/4 | 4/4 | 3/4 (0.30 to 0.95) | `answer`, 1 |
| "What total cost does the note below state?" | `answer` | 4/4 | 4/4 | 4/4 (0.51 to 1.00) | none |

The extractions named `excerpt` 7 of 8 (0.53 to 0.98), against 0 of 8 on each earlier CPU row, and
the summaries and lookups kept their own role, so on this condition the description moves the
cortex. It is one condition's row; the card row is written down in
[R-756](../refinements/tasks/756-the-cortex-names-answer-for-an-extraction.md). A turn wrote 191 to
735 tokens of reasoning and call, 372 at the median.
