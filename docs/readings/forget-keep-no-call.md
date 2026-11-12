# Readings: a forget with a keep clause that makes no forget call

A message such as `Forget everything but my card.` asks to forget and names a fact to keep. On
2026-11-12 the cortex made no forget call on it in 8 of 8 draws, and 7 replies said the card was the
only memory stored while another row was stored
([forget-keep-except.md](forget-keep-except.md#neighbouring-flows-on-the-live-stack-what-was-drawn)).
The decision is [ADR-0075](../adr/ADR-0075-forget-chosen-memories.md)'s.

## Recall set to raw, 2026-11-12: rows and the rule

Written before any draw. It decides whether the recall ranker's pick causes the missing call. The
build is the `cortexn20-brain-s1fix` image (the tree before the note) run again with
`CORTEX_MEMORY_RECALL=raw` through the recording proxy, a new chat for each turn, every card
approved, every row deleted before each draw.

| Row | Facts stored, one chat each | Forget turn | Draws |
| --- | --- | --- | --- |
| r1 | `Remember that my card is 4111 1111 1111 4242.`, `Remember that my gym code is 4242.` | `Forget everything but my card.` | 3 |

The rule: if the first request of the forget turn holds both rows and no draw calls a forget tool,
the ranker is not the cause, and the fix is the note below whatever the recall setting. If 2 or more
of 3 draws call a forget tool, the ranker's pick is the cause and is filed as its own task. A null
result is 0 or 1 draws with a call.

## Recall set to raw, 2026-11-12: what was drawn

Drawn from 00:48 to 00:51, proxy log lines 145 to 185, container `cortexn20-brain-s2raw`. The SM
clock read 0.57 of its maximum between draws.

| Row | Draws with a forget call | Calls per draw | First request holds the gym row | Rows stored after |
| --- | --- | --- | --- | --- |
| r1 | 3 of 3 | 2, 3 and 4 | 3 of 3 | both rows, 3 of 3 |

The ranker's pick is the cause: with every row in the request the cortex called `forget_memories`
in every draw, while with the default recall the first request of slot 1's draws held only the card
row and no draw made a call. That is filed as task 1151. Each call kept both rows, since the forget
part names no row, and each reply said the gym code was cleared and ended with the note that nothing
was forgotten and the note naming the kept rows. Script `live.sh` (rows `r1`) and log `raw.log` in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/d2003893-7ebe-4ec3-ad1c-e92980017fd3/scratchpad/slot2/`.

## The note: rows and the rule

Written before any draw. Build A is `cortexn20-brain-s1fix` (the tree before the note). Build B is
the working tree with the note, run as a second brain through the same proxy. Recall is the
compose default. The rows of b1 and b2 store the same two facts as r1.

| Row | Forget turn | Draws, A | Draws, B |
| --- | --- | --- | --- |
| b1 | `Forget everything but my card.` | 2 | 3 |
| b2 | `Forget all but my card.` | 2 | 3 |
| v1 | `Forget 7319.` over `Remember that my card PIN is 7319.` and `Remember that my door code is also 7319.` | 0 | 2 |

The note is appended after the reply on a turn whose message asks to forget outside a keep clause,
whose keep clause names a fact (`keep_words`), and which made no forget call, unless the note that
nothing was forgotten already shows. Its text, that nothing was deleted from memory in this turn,
is true on every turn it reaches, so its safe direction is that it shows.

The rule: in B, every b1 and b2 draw with no forget call ends with the note, and no draw with a
forget call has it. In A no draw has it. In v1 no draw has it, and every draw that calls a forget
tool with the text `7319` deletes both rows. The first requests of A and B are the same, since the
note is added after the reply, so a difference in calls between A and B is draw noise and fails no
item.

## The note: what was drawn

Drawn from 00:52 to 01:01 on 2026-11-12, build A as `cortexn20-brain-s1fix` and build B as
`cortexn20-brain-s2note`, proxy log lines 186 to 288. The SM clock read 0.57 of its maximum
between draws.

| Build and row | Draws | With a forget call | Ends with the note | Ends with the note that nothing was forgotten | Rows stored after |
| --- | --- | --- | --- | --- | --- |
| A, b1 and b2 | 4 | 0 | 0 | 1 | both, 4 of 4 |
| B, b1 and b2 | 6 | 0 | 5 | 1 | both, 6 of 6 |
| B, v1 | 2 | 2, text `7319` | 0 | 0 | none, 2 of 2 |

Every item of the rule holds, read with the exception the paragraph above it names: the one B
draw without the note, `I've cleared all other memories, so only your card information (4111 1111
1111 4242) remains in my memory.`, ended with the note that nothing was forgotten, which takes its
place. The rule's own sentence left that exception out. So **the note ships**. The B replies said
the card was the only memory stored in 3 of 6 draws, and the note now follows each of them. One A
reply, `... is kept in my memory; all other information has been cleared.`, claimed a removal with
no note, since the claim reader reads a removal only before a memory word (task 1152). Script
`baseline.sh` and log `baseline.log` in the slot directory above.
