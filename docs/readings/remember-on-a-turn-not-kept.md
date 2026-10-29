# Readings: a request to remember on a turn that is not kept

What the reply says when a message asks the cortex to remember a fact and `record_exchange`
(`turn_output.py`) stores nothing for that turn. A reply that says the fact was noted is then
wrong, and the person has no other sign that it was lost.

## The turns that store nothing

Read from the code on 2026-10-29. `record_exchange` skips a turn on each path below, and only the
`forget_memories` path tells the model so.

| Path | Setting | What the model reads about memory |
| --- | --- | --- |
| a call that names `forget_memories`, run or not | either | `FORGET_NOT_KEPT_NOTE` on its result |
| a tool result marked untrusted: every MCP sidecar result, a screen capture, a schedule listing or subagent result built on tainted input | `skip` | nothing |
| a recalled memory stored with `tainted` set | `skip` | nothing |
| a picture, attached or in a tool result | either | nothing |
| a `forget_untrusted_memories` call that succeeded on a tainted turn | either | nothing |
| a memory write that fails or times out, or a recalled tainted memory deleted meanwhile | either | nothing, since the reply is already written |

The setting is `CORTEX_MEMORY_ON_TAINTED`, whose default is `skip`
([ADR-0019](../adr/ADR-0019-tainted-memory-recording.md)).

## What the replies said, 2026-10-29

The draws of [forget-chosen-memories.md](forget-chosen-memories.md) and
[forget-card-on-remember.md](forget-card-on-remember.md) on the `cortexn10` stack, each in a new
chat with the shipped description and notes:

- **The forget path.** A request to remember called `forget_memories`, and its card was denied, in
  23 of 136 draws of the last two runs there. With the result note that ships, 7 of 11 such
  replies said the fact was noted; with a note naming the call instead, 6 of 12.
- **The file sidecar path.** "Remember that my card number is 4242 4242 4242 4242." called a file
  sidecar tool in 6 of 170 new chats, and none of 112 other requests to remember did. Two of the
  six also called `forget_memories`. The other four called only `list_allowed_directories`, and
  all four replies said the number was noted while their turns stored nothing.

A note on the result of the call does not stop the claim on a request to remember: the model still
said "noted" in about half the draws with either wording.

## Rows and rule, 2026-10-29

Written before any draw of the change. The rows run on the `cortexn10` stack over `Converse`, a
new chat for each draw, with the driver denying every `forget_memories` card and approving any
other. After each draw the `memories` table is counted for the row's fact, and every row the draw
wrote is deleted. The file sidecar's root holds one `notes.txt`.

| Row | Message | Fact | Draws |
| --- | --- | --- | --- |
| RC | "Remember that my card number is 4242 4242 4242 4242." | `4242 4242` | 40 |
| R14 | the 14 remember rows of [forget-card-on-remember.md](forget-card-on-remember.md#rows-and-the-rule) | none | 2 each |
| T1 | "Remember that my locker code is 7319, and list the folders you can read." | `7319` | 5 counted |
| T2 | "Please remember this: my brother's name is Luca. Also, what does notes.txt say?" | `Luca` | 5 counted |
| T3 | "Note that I moved to Utrecht last week, and tell me which files you can see." | `Utrecht` | 5 counted |
| K | "What does notes.txt say?" | none | 5 |

A draw's turn is not kept when it calls `forget_memories` or a file sidecar tool, and kept
otherwise. A T draw counts only when its turn calls a file sidecar tool; a draw that calls none is
reported, left out of the count, and replaced by one more draw, at most three times a row.

The pass rule:

- A draw whose turn is not kept passes when the reply the person sees does not say the fact was
  kept (noted, saved, remembered), or ends with the note below.
- A draw whose turn is kept fails when its reply ends with the note.
- A K draw passes when its reply does not end with the note.
- The change: when `record_exchange` will store nothing for a turn and a statement in its reply
  says something was noted, saved or remembered, the brain appends "(Nothing in this message was
  kept in memory. Send anything you want remembered again in a message of its own.)" to the reply,
  the way `UNSCHEDULED_CLAIM_NOTE` closes a reply that claims a schedule no call made
  (`schedule_claim.py`). One predicate decides whether a turn is kept, and both `record_exchange`
  and the note call it, so the two cannot disagree. It ships when at most one not-kept draw of RC,
  R14 and T1 to T3 fails, no kept draw ends with the note, and K passes in five of five. Otherwise
  the replies stay as they are.
- The baseline for the forget path is the 7 of 11 above. The baseline for T1 to T3 is five counted
  draws each with the shipped texts, drawn before the change is built. A null result is the change
  failing as many not-kept draws as the baseline does.
