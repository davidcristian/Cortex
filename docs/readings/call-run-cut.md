# Readings: closing a round's stream during a run of calls

A round can hold a run of calls the model does not stop writing. In one draw of `Please remember this:
I work as a nurse.` on a build listing `set_volume`, the cortex wrote its reply and then `set_volume`
calls with no arguments until the length limit: the turn took about 10 times the row's median, nothing
was shown during the wait, and the reply ended in the length note
([draws](unasked-tools-listed-on-remember.md#the-draws-2026-10-31)).

`plan_round` (`tool_round.py`) keeps `MAX_CALLS_PER_ROUND` calls and one more, so reading further only
costs time. `_round_pieces` (`tool_loop.py`) cannot stop the read: the adapter assembles calls only as
the stream ends, and the stream contract says a call never precedes the words beside it, so no
`ToolCall` reaches the loop until the generation is over. A stop written in the loop passes a scripted
test and does nothing on the real backend. So `LlamaCppBackend.stream` (`backend.py`) leaves the read
once `round_is_full` (`decode.py`) reads that a call past those has started, which also means the kept
calls are whole, and `finish_calls` reads only the kept ones, so a call the close interrupted cannot
fail as unreadable.

## The real server, 2026-10-31

One request through the changed adapter to the `cortexn12` stack's cortex (gemma-4-12B at context
16,384, llama-server build `b12004-3c809f443`) asked for 60 calls of a `set_volume` tool in one reply,
with `max_tokens` 1,200. Script and log: `freeslot.py` and `freeslot.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot4/`.

- The first attempt wrote the run. 17 `ToolCall` events crossed the port, and no `DecodeStop`.
- The server logged `srv stop: cancel task, id_task = 290334`, then `slot release: id 0 | task 290334
  | stop processing`, with the generation over 1,025 tokens of slot content, so a closed stream ends
  the generation and frees the slot. Another client's turn ran on that slot next, as the `id_task` in
  `/slots` showed, and a following request answered.

A turn over the changed adapter whose round is cut answers all 17 kept calls, refuses the last as
`ROUND_OVERSIZED`, goes on to its next request and ends with no length note, since the stream ended
before the engine reported one (`test_call_run_cut.py`).
