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
