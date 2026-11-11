# Readings: a question asking to note a fact

`asks_kept` (`memory_request.py`) does not read `Can you note that Anna likes plants?`, so
`unasked_sidecar_tools` refused no file tool on it, and a file call tainted the turn and lost the
fact ([R-1129](../refinements/tasks/1129-a-question-asking-to-note-a-fact-is-not-read-as-a-request-to-remember.md)).
`_ASKS_TO_NOTE` (`unasked_tools.py`) now reads a message that is one question of `can`, `could`,
`would` or `will you`, then `note`, `remember` or `keep in mind`, `that` and a subject, and only
`unasked_sidecar_tools` reads it, over the words after `that`. This record holds its replay and
its draws.

## Replay, 2026-11-11

6,177 strings: every backticked or double-quoted string of 6 to 300 characters in
`docs/readings/*.md`, and every user message the `cortexn19` recording proxy logged on 2026-11-11
up to 05:16. Each was read by the old and the new `unasked_sidecar_tools` over eight file tool
names.

| Reader | Strings refused | Changed |
| --- | --- | --- |
| old | 174 | |
| new | 174 | 0 |

No recorded string has the question form alone. The readings hold it only inside the two-sentence
draw message `Anna said: "remind me every day at 8 to water the plants". Can you note that she
likes plants?`, whose second sentence keeps every tool on both readers. Method: `replay1129.py
<old module copy> docs/readings <proxy all.jsonl>` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/f3217b06-cdcf-4ffa-92c2-cc5df81e7d11/scratchpad/slot15/`.

## The draws, 2026-11-11

Rule, written before the first draw: on the new build no file call succeeds, and a turn with no
successful file call keeps a memory row; the base build's count of turns that call a file tool is
the form's frequency, a separate count.

The rig is the `cortexn19` stack over `Converse`: the cortex gemma-4-12B at context 16,384, two
brain containers through the recording proxy, the base built from the tree before the change and
the new one from the tree holding it, drawn in turn. Each draw sent `Can you note that Anna likes
plants?` in a new chat with `memories` empty and every card approved. The first model request of
a base and a new draw differ only in the date-time in the `schedule_task` description, so the
calls below differ by draw noise until a file tool is called. 05:18 to 05:23, SM clock 0.57 of
`clocks.max.sm` at both ends.

| Build | Turns calling a file tool | File calls that ran | `forget_memories` calls | Rows kept |
| --- | --- | --- | --- | --- |
| base | 0 of 6 | 0 | 5 of 6 | 1 of 6 |
| new | 2 of 6 | 0 | 1 of 6 | 5 of 6 |

On the new build both file calls (`list_allowed_directories`, draws 4 and 5) were refused by name
and both turns kept the row. The rule's first part holds in 6 of 6. Its second part holds in 5 of
6: the one miss, new draw 2, called no file tool and lost the row to a `forget_memories` call that
matched nothing, as did all five base forget calls. Each such reply said `I've noted that Anna
likes plants.` above the notes that nothing was kept and nothing deleted. That forget call on a
message with no forget word is the cause of
[R-1112](../refinements/tasks/1112-a-question-in-a-new-chat-called-forget-memories.md), and it
lost the fact in 6 of 12 draws here against 2 file calls in 12.

Method: `draw1129.sh` and `calls.py <proxy chat files>` in the slot directory above, logs
`draw1129.log` and `rows1129.jsonl`, proxy chats `n19s15-p-base1..6` and `n19s15-p-new1..6`.
