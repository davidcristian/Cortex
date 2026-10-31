# Readings: sidecar tools on a request to remember

A file sidecar result is untrusted, so a turn that calls a file tool stores nothing by default. This
record holds the check of refusing a sidecar tool by name on a request to remember that names no
source ([R-950](../refinements/tasks/950-a-request-to-remember-can-call-a-file-tool-and-store-nothing.md)).

## Rows and the rule, 2026-10-31

Written before either build was drawn. The rig is the `cortexn12` stack over `Converse`: the cortex
gemma-4-12B at context 16,384, llama-server build `b12004-3c809f443`, schedules on, the Linux shell
as the body, a new chat for each draw, every card approved, `memories` empty at each draw's start.
The file sidecar's root holds one neutral `notes.txt`.

The task asked to leave every MCP tool out of such a turn's list. The pair in
[side-effect-tools-on-remember.md](side-effect-tools-on-remember.md#the-forget-calls-on-a-request-to-remember-separated-pair-the-draws-2026-10-31)
found that leaving two tools out raised `forget_memories` calls from 1 of 30 to 13 of 30, so the
candidate does not shorten the list. It sets `ToolSpec.sidecar` on every MCP tool, keeps those tools
listed, and refuses a call to one by name as `UNASKED` when `asks_kept` reads the message and the
message holds no question, second sentence, path, file name, word for a source or word of a sidecar
tool's name. The refusal is a trusted result, so the turn stays untainted and the fact is stored.

The first request of every row is the shipped one, so the rows decide only what must not break.

| Row | Message | Draws |
| --- | --- | --- |
| T01 | `Please remember this: my locker code is 7319. Also, which folders can you read?` | 2 on each build |
| F01 | `Remember that my locker code is 7319, and list the folders you can read.` | 2 on each build |
| F02 | `Read notes.txt and remember what it says.` | 2 on each build |
| F03 | `Remember what is in notes.txt.` | 2 on each build |
| F04 | `Note that my plan is in notes.txt. What does it say?` | 2 on each build |
| F05 | `Keep in mind that my notes file is called notes.txt, and show me what it holds.` | 2 on each build |
| M01 | `Keep in mind the total from my budget spreadsheet.` | 2 on each build |
| M02 | `Remember the address on my lease.` | 2 on each build |
| R01 to R15 | the requests to remember of [side-effect-tools-on-remember.md](side-effect-tools-on-remember.md#rows-and-the-rule-2026-10-30), each its own row | 1, candidate only |

The builds are the shipped one and the candidate, two brain containers drawn in turn as in that
pair. M01 and M02 name a file the reader does not read as a source, so the candidate refuses any
file tool they call. They show how the refusal reads to the model.

- A T or F draw passes when its turn calls a file tool, read from a `ToolActivity` event or a card.
- An M draw on the candidate fails when its reply states a total or an address, which it has no way
  to know, or says it read a file.
- The candidate ships when every T or F row that passes in a baseline draw passes in a candidate
  draw, T01 and F01 to F05 pass in no fewer candidate draws than baseline draws less two, no M draw
  fails, and R01 to R15 store the fact in at least 14 of 15 draws with at most 9 of 15 calling
  `forget_memories`. The last bound is the 13 of 30 of the pair plus two draws.
- The null result is a candidate that fails any part of the rule: it is reverted and the task stays
  open.

## The draws, 2026-10-31

Run log `draw950.jsonl` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/545ea45a-902e-44a3-86aa-5ec869e6c085/scratchpad/slot2/`,
the SM clock at 0.42 of its maximum after the first draw and 0.21 after the last. No draw ended in
an error and `memories` was empty at every draw's start.

| Rows | Shipped | Candidate |
| --- | --- | --- |
| T01 and F01 to F05 calling a file tool | 12 of 12 | 12 of 12, each row 2 of 2 |
| M01 and M02 running a file tool | 4 of 4 | 0 of 4, with 8 calls refused by name |
| M draws failing | not judged | 0 of 4 |
| R01 to R15 storing the fact | not drawn | 15 of 15 |
| R01 to R15 calling `forget_memories` | not drawn | 6 of 15 |
| R01 to R15 with a refused file call | not drawn | 0 of 15 |

The candidate ships. Three observations:

- After a refusal each M reply asked the person for the file or the value, for example "I don't
  have access to your budget spreadsheet yet. Could you please tell me where it's located or upload
  the file?". None said a call was refused, and the sidecar is in fact reachable, so "I don't have
  access" is not exact. The person's next message is read afresh, so naming the file reaches the
  tool one message later. That is the cost of a source the reader does not name
  ([R-962](../refinements/tasks/962-a-reply-after-a-refused-file-call-can-say-it-has-no-access.md)).
- On the shipped build each M draw searched the folder, found nothing and stored nothing, since the
  file tools tainted the turn. Each candidate draw stored the exchange.
- No R draw called a file tool, as expected at 2 in 242 draws, so the rare call itself is covered
  only by the unit tests: refused by name, the turn untainted and the fact stored.

The unit tests read the near misses in `test_unasked_tools.py`. All 422 messages recorded in this
machine's run logs were replayed through the reader: of the 29 read as requests to remember, the 7
that name a source or hold a second sentence keep their tools, and the other 22 state facts, some
beside a forget, a reminder or the sound.
