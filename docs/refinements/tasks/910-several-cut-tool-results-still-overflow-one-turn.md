# Several cut tool results still overflow one turn

**Status:** open, actionable
**Area:** tools
**Origin:** [ADR-0009](../../adr/ADR-0009-tools-mcp.md)

`cut_result` (`tool_round.py`) cuts each tool result to `MAX_RESULT_CHARS` (6,000 characters),
but nothing bounds their sum. A loop runs up to `MAX_TOOL_STEPS` (8) rounds of up to
`MAX_CALLS_PER_ROUND` (16) calls, and every result stays in the loop's messages until the reply.
Decision 20 of ADR-0009 prices one cut result at 3,640 tokens and leaves 2,860 of the cortex's
16,384 to reply, so a few more full results end the turn the way one uncut result did.

Reproduction (2026-10-26, the `cortexn8` stack, the cortex at context 16,384): four log files of
about 19,000 characters each in the file sidecar's root, then over `Converse` "Call
read_text_file four times in one step, once each for /projects/alpha.log, /projects/bravo.log,
/projects/charlie.log and /projects/delta.log (not read_multiple_files), then tell me which worker
appears most often across them." The cortex made six `read_text_file` calls (alpha.log three
times, each other file once), each result was cut to 6,000 characters, and the next request was
17,851 tokens. llama-server answered 400 `exceed_context_size_error`, and the turn ended with the
note about a conversation longer than the context and no answer.

## What to do

1. Give the loop one budget for the tool results it holds: the context left after the fixed
   prompt, the history window and the room to reply. Cut each new result to what is left of that
   budget, with the note saying the turn's room for results is used up; a result with no room left
   gets the note alone.
2. Test it over fakes for several results in one round and for results across rounds, and repeat
   the reproduction: the turn must end with an answer.

## History

- 2026-10-26: filed from an audit of the tool result cut, reproduced on the `cortexn8` stack.
