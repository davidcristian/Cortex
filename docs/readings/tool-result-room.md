# Readings: the room a loop's tool results share

How much of a context the tool results of one loop take, on each tier that runs a loop, and what
the cortex tells the person when it answers from results that were cut. The room is
`RESULT_ROOM_CHARS` in `tool_cut.py`, decided in [ADR-0009](../adr/ADR-0009-tools-mcp.md) decision
20. A single file far past the context, and the first several-reads reproduction, are in
[overlay-tool-failure-flows.md](overlay-tool-failure-flows.md#a-file-far-past-the-context).

## The rig

**2026-10-28**, the `cortexn9` GPU stack at the tree of that night: the resident cortex
(gemma-4-12B) at a context of 16,384 tokens, the CPU subagent server (gemma-4-E4B) started with
`--ctx-size 8192 --parallel 2`, the filesystem sidecar ([tools-mcp.md](../runbooks/tools-mcp.md))
with its ten read tools, memory on pgvector with no memories, and every other setting at its
default. The sidecar's root held four logs of 300 lines (`alpha.log`, `bravo.log`, `charlie.log`,
`delta.log`, 23,761 to 23,794 characters each, twelve workers with worker-9 the most frequent in
each) and a 2.38 MB `server-log.txt` of 30,001 lines ending in an `ERROR` line. Each draw was one
turn in a new chat over `Converse` from a driver on the host.

## A subagent loop at the default context

Written before the run. Two rows, each a turn that asks the cortex to delegate:

- **One large log.** "Use spawn_subagents with exactly one item. Its instruction: read
  /projects/server-log.txt with read_text_file and say what its last line says."
- **Several in one round.** "Use spawn_subagents with exactly one item. Its instruction: call
  read_text_file four times in one step, once each for /projects/alpha.log, /projects/bravo.log,
  /projects/charlie.log and /projects/delta.log, then say which worker appears most often."

Two draws each. A draw whose subagent makes no file call is drawn again, at most three draws a
row. Read for each draw: the context of one server slot (`GET /slots`, `n_ctx`), the prompt tokens
of every subagent request (the subagent server's log), and the spawn result (the brain's log).

**What counts as an overflow:** the server refuses a subagent request for its length, or a
request's prompt tokens plus `CORTEX_SUBAGENTS_MAX_TOKENS` (1,024, the bound on one completion)
exceed the slot's context, so that the context, not the bound, can end the completion. An overflow
on either row sizes the room per loop from the serving tier's context. No overflow leaves the task
open with its trigger written down.

**Results with the room at 6,000** (SM clock 0.59 to 0.74 of `clocks.max.sm`). Each slot held
4,096 tokens, since `--parallel 2` splits the 8,192. A subagent's first request was 1,484 tokens:
the preamble, the ten file tool specs and the task.

| Row | Draw | What the subagent read | Next request, tokens | Outcome |
| --- | --- | --- | --- | --- |
| One large log | 1 | the whole file, `result_chars=2379262` | 5,263, refused | failed |
| One large log | 2 | `tail` 1, `result_chars=82` | under 1,700 | quoted the `ERROR` line |
| Several in one round | 1 | the four logs | 5,732, refused | failed |
| Several in one round | 2 | the four logs | 5,740, refused | failed |

Every refusal was `exceed_context_size_error` with `n_ctx` 4,096. The runner then re-ran the attempt
on the CPU target, here the same server, which dispatched every read again and was refused again
(5,255, 5,724 and 5,724 tokens). The cortex told the person the subagent's context was exceeded.
Both rows overflowed.

**Results with the room sized to the slot** (`subagent_room_chars`, 1,603 characters at the
defaults), the same rows on the rebuilt brain, two draws each (0.60 to 0.73): no request was
refused. Both draws of one large log read the whole file, and the next request was about 2,605
tokens. Both draws of several in one round read the four logs, and the next request was 3,049 and
3,057 tokens, so 4,073 and 4,081 with the 1,024 a completion may decode, inside the 4,096. Neither
row's answer said its results were cut: both large-log draws gave the twentieth line as the last,
and both several-reads draws named workers from about five lines a file.

## An answer from cut results

Written before the baseline. Three rows, five sampled draws each, each draw a new chat, on the
brain without the subagents overlay, so the cortex reads the files itself as in the reproduction
of 2026-10-26: with delegation on, the first draw of the first row handed each read to a subagent.

- **Four reads.** "Call read_text_file four times in one step, once each for /projects/alpha.log,
  /projects/bravo.log, /projects/charlie.log and /projects/delta.log (not read_multiple_files),
  then tell me which worker appears most often across them."
- **One read of three files.** "Read /projects/alpha.log, /projects/bravo.log and
  /projects/charlie.log with read_multiple_files and tell me how many ERROR lines they have in
  total."
- **Two reads to summarize.** "Read /projects/bravo.log and /projects/charlie.log with
  read_text_file in one step and summarize what went wrong in each."

**Pass rule:** a draw passes when its reply tells the person that its counts or its summary cover
only part of the files, in any words ("only the first part of each file", "the results were cut",
"partial"). A reply that declines to answer because the files did not fit also passes. A draw in
which no result was cut does not count and is drawn again. **Ship rule:** a change to the result
text ships only if each row that passed fewer than four draws in five at baseline passes at least
four in five with it, and no row falls below four in five.

**Results.** Baseline on the tree with the subagent room (SM clock 0.60 to 0.72 of
`clocks.max.sm`); candidate with `RESULT_CUT_NOTE` and `ROOM_SHARED` asking the model to tell the
person which part it read (0.59 to 0.71). Every draw had a cut result.

| Row | Baseline | Candidate |
| --- | --- | --- |
| Four reads | 1 of 5 | 5 of 5 |
| One read of three files | 5 of 5 | 5 of 5 |
| Two reads to summarize | 4 of 5 | 5 of 5 |

- **Four reads.** At baseline four replies gave per-worker counts of about 20 lines a file as the
  answer; the passing draw said only the first lines were captured and the true answer may
  differ. With the candidate, four replies said the counts cover only the first 1,400 to 1,500
  characters of each file, and one stopped to read the files in parts after saying the reads
  were truncated.
- **One read of three files.** Every draw at both builds said the result was too long and the
  count covers only the visible part. Baseline draw 5 ended after 144.3 s with
  `llama-server sent nothing for model 'cortex' within its ceiling` while the model host was
  still decoding ([task 915](../refinements/tasks/915-a-long-generation-the-server-holds-back-reads-as-a-stalled-server.md));
  its text before the error said it could see only the beginning.
- **Two reads to summarize.** Three baseline passes named only `charlie.log` as not read and
  listed the errors of the start of `bravo.log` as its errors; draw 1 failed and described
  errors in `charlie.log` that the file does not hold
  ([task 916](../refinements/tasks/916-the-cortex-describes-a-file-whose-read-did-not-fit.md)).
  With the candidate every draw said its list covers only the start of `bravo.log`, and none
  described `charlie.log`.

The candidate passes the ship rule. Method: `ask.py` over `Converse`, five draws a row, replies
read by hand against the pass rule.
