# Readings: a reply that repeats one line

What the cortex writes once it starts repeating itself, and whether a sampling setting or a check
on the streamed reply ends the loop before the length limit. This record holds the rig, the rows
and the pass rule, written before any baseline row was drawn.

## What bounds a looping reply today

Read on 2026-10-13 from the test stack's cortex server (`/props`, build `b11552-23b0202a1`) and the
tree:

- The brain sends no sampling field, and with `CORTEX_REPLY_MAX_TOKENS` at its default 0 it sends
  no `max_tokens`, so a reply is bounded only by the slot's context: 16384 tokens less the prompt,
  5,374 tokens on the rig's state below, so about 11,000 tokens of reply.
- The server's defaults have both repetition samplers off: `repeat_penalty` 1.0 and
  `dry_multiplier` 0.0. The others are `temperature` 1.0, `top_k` 64, `top_p` 0.95, `min_p` 0.05
  and `n_predict` -1. The model host starts the cortex tier with no sampling flag.
- In the brain, `REDUNDANT_MSG` refuses an exact repeated tool call, and nothing reads repeated
  text. The stall ceiling sees only silence, and the token cap of
  [ADR-0048](../adr/ADR-0048-generation-bounds.md) applies to a delegated run, not to the cortex.

The probe row of the [cut off tool call](tool-call-cut-off.md#results) rows looped in the reply,
not in `reasoning_content`: its 3,764 words arrived as text from 21.4 s into the turn, and they
open with the model's own plan, "The user wants to know who sings in week 2 according to the
`choir-rota.txt` file.", a trace written as reply text. Two lines then alternate 357 times each.

## The rig

A replay of that probe row at the engine. One cut off read row was drawn with a packet capture
beside the model host, which recorded every request the brain sent: the system prompt, the 20 tool
definitions and each tool result as the model reads it. The rig's state is that request with the
probe row's own calls: `list_allowed_directories` and `list_directory` succeed, then
`read_text_file`, `read_file` and `read_text_file` fail as unknown tools, a fourth read is refused
as an exact repeat, and `list_directory` fails as an unknown tool. Each draw posts the state to the
cortex server, not streamed, with `max_tokens` 1536 to bound its cost.

- **Without a prefill** the next completion is a tool call or a short apology: 0 of 3 probe draws
  looped.
- **With the probe row's first reply sentence as an assistant prefill** (it ends "I'll try to read
  it again using `read_text_file`."), 3 of 3 probe draws looped to 1536 tokens, one line repeated
  18 to 47 times in each. The rig therefore measures what happens once the model has started
  writing its plan into the reply, the state the probe row shows. It does not measure how often a
  turn reaches that state.

Two controls use the same system prompt and tools:

- **Tool call control**: the state after `list_directory` succeeds, before any read. A draw passes
  when it calls `read_text_file` or `read_file` with the path `/projects/choir-rota.txt`.
- **Format control**: a new conversation whose message is "Without using any tool, write twelve
  lines, one per month from January to December, each exactly in the form `<Month>: choir practice
  on the first Tuesday at 7 pm`." A draw passes when its reply holds all twelve lines in that form.
  It tests a sampling setting against a reply that must repeat its own words.

## The rows

- **Baseline**: 10 rig draws, 10 tool call control draws and 10 format control draws, at the
  server's defaults.
- **Candidate A, DRY**: the same 30 draws with `"dry_multiplier": 0.8` in each request, which is
  what a cortex tier started with `--dry-multiplier 0.8` applies to every request. The other DRY
  values stay at the server's defaults (base 1.75, allowed length 2).
- **Candidate B, a repeated line check**: read off the baseline draws, with no new draw. It ends a
  reply as soon as one line of at least 20 characters, holding at least one letter, arrives for
  the third time, and appends a note saying the reply was stopped because it repeated itself. Its
  rows are where it stops each rig draw, in words of reply counting the prefill, and whether it
  stops any control draw of either phase.
- SM clock read after each phase with `nvidia-smi`.

## How a draw is classed

- **Loops**: one line of the reply appears three times or more, or the draw stops at its 1536
  token limit.
- **Calls**: the draw ends with a tool call.
- A control draw passes or fails as its control defines above.

## The pass rule

- **The defect reproduces** on the rig when at least 7 of the 10 baseline rig draws loop.
  Otherwise neither candidate is judged on this rig.
- **Candidate A ships** as a flag of the cortex tier when at most 2 of its 10 rig draws loop, all
  10 of its tool call control draws pass, and its format control passes no more than one draw
  fewer than the baseline's.
- **Candidate B ships** when it stops every looping baseline rig draw but at most one within the
  first 400 words of reply, and stops no control draw in either phase.
- **When both pass, candidate B ships**: it changes only a reply that already repeats, and it reads
  the stream the brain already has, on every tier and engine. Candidate A is then filed as its own
  task and measured again with B in place.
- Any other result changes nothing, and the rows are recorded here.

## Results

None yet beyond the probe draws above.

Method: the capture and replay drivers in the run's scratch directory, against the test stack's
cortex server on `127.0.0.1:8080`.
