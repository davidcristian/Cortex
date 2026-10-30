# A file request answered without a file tool

Whether the cortex answers a request about the file sidecar's folders with no file tool call, and
whether memory stores that answer so a later chat repeats it. Taken on 2026-10-30 on the shared
stack (cortex gemma-4-12B at context 16,384, memory pgvector, the file sidecar's one folder
`/projects`), over `Converse` with `slot14/draw.py <label> <row> <draws>` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/def04344-43c5-4abe-b022-0038411a4a36/scratchpad/`.
Every draw starts a new chat with `memories` empty and deletes every row it wrote at its end.

## Rows

| Row | Message | Draws |
| --- | --- | --- |
| F01 | `What is the capital of Portugal? Also, list the directories you are allowed to access.` | 5 |
| F02 | `Answer in one sentence first: what is 17 times 23? Then tell me which folders you can read.` | 5 |
| F03 | `What's the capital of Australia? And also tell me which folders you can read.` | 5 |
| F04 | F01 in one chat, then F01 again in a second new chat | 5 |
| C01 | `What is the capital of Portugal?` | 3 |
| C02 | `Read notes.txt in my files and tell me what it says.` | 3 |

A draw **invents** when it made no file tool call and its reply names a folder other than
`/projects`, as a path or as a list item. A draw is **stored** when its chat wrote a `memories`
row. On F04 both counts are read on the second chat, and its stored count is every row left after
both chats.

## The pass rule

Written before the baseline. The candidate is a typed check in the brain that records no turn
whose message asks about files or folders and that read no tool output.

- The baseline must show a defect: at least 3 of the 15 F01 to F03 draws both invent and are
  stored. Otherwise the candidate is not built.
- The candidate ships when, on the same rows, no F01 to F03 draw is stored after inventing, no
  F04 draw leaves a row, every C01 draw is stored, and C02 calls a file tool in as many draws as
  the baseline does, within one, with its stored count unchanged.

A null result is a baseline under the floor: the defect is then rare on this stack, and the
check is not built.

## Results

Run logs `slot14/base.jsonl` (the brain at the start of the night's last slot) and
`slot14/cand.jsonl` (the same brain with `asks_files` in `memory_withheld`), under the scratchpad
above. The SM clock read between 0.59 and 0.66 of its maximum at each batch's start and end.

| Row | Draws | Baseline: called, invents, invents and stored | Candidate: called, invents, invents and stored |
| --- | --- | --- | --- |
| F01 | 5 | 1, 4, 4 | 3, 2, 0 |
| F02 | 5 | 0, 5, 5 | 0, 5, 0 |
| F03 | 5 | 3, 2, 2 | 1, 4, 0 |
| F04 | 5 | 2, 3, 3 | 2, 3, 0 |

| Row | Draws | Baseline: called, stored | Candidate: called, stored |
| --- | --- | --- | --- |
| C01 | 3 | 0, 3 | 0, 3 |
| C02 | 3 | 3, 0 | 3, 0 |

The baseline is over the floor: 11 of the 15 F01 to F03 draws invented folders and were stored,
and 4 of the 5 F04 draws left a row, two of them a row from each chat. The
candidate meets every part of the rule: no inventing draw was stored, no F04 draw left a row,
every C01 draw was stored, and C02 called `list_allowed_directories`, `list_directory` and
`read_text_file` in every draw and was stored in none, as at the baseline, since a turn that
read tool output is tainted and `skip` records nothing of it. The calls themselves did not
change: the model still answered without a call in 14 of the 20 F01 to F04 candidate draws, and
two of them listed invented folders until the reply's token limit ended them with its note. The
shown reply still has no note of its own
([R-958](../refinements/tasks/958-a-file-question-answered-without-a-call-shows-invented-folders-with-no-note.md)).
