# Readings: the search for a store tool on a request to remember

How often a request to remember makes the cortex search its tool list for a tool that stores the
fact, how long that trace is, and how often the reply tells the person the fact is kept only for
this chat. The brain stores every exchange at turn end and has no such tool
([ADR-0008](../adr/ADR-0008-memory-v1.md)); the task is
[R-995](../refinements/tasks/995-a-request-to-remember-spends-its-thinking-looking-for-a-tool-to-store-the-fact.md).

## Rows and the rule, 2026-11-07

Written before any draw. The rig is the `cortexn15` stack over `Converse` (the cortex gemma-4-12B
at context 16,384, llama-server build `b12169-3ed7284f2`, schedules on), a new chat for each draw,
every card approved. Three brain containers run beside each other through one recording proxy
against that stack's model server and stores. `memories` is emptied at each draw's start, so no
draw recalls another's fact.

| Row | Message | Fact searched for |
| --- | --- | --- |
| R01 to R10 | `Please remember this: ` and, in order, my brother's name is Luca; I work as a nurse; my car is a red Fiat; my daughter is allergic to peanuts; my bank closes at four on Fridays; my landlord is called Mr Weber; my favourite tea is jasmine; my passport expires in March; my neighbour's dog is called Rex; I take the train at 7:40 | `Luca`, `nurse`, `Fiat`, `peanuts`, `Fridays`, `Weber`, `jasmine`, `March`, `Rex`, `7:40` |
| R11 | `Remember that my wifi router is in the hallway.` | `hallway` |
| R12 | `Note that my mother's birthday is on 12 May.` | `12 May` |
| R13 | `Keep in mind that I am vegetarian.` | `vegetarian` |
| R14 | `Please remember this: my sister's name is Ana.` | `name is Ana` |
| R15 | `Please don't forget this: my gym class is on Tuesday.` | `Tuesday` |

The builds, each drawn once on every row, in turn, the build that goes first rotating by row:

- **Base**: a `git archive` build of the head commit, the shipped behaviour.
- **A**: base, plus one system message on a turn whose message `asks_kept` reads, saying that the
  exchange is stored when the turn ends and recalled in later chats, so remembering needs no call.
- **B**: base, plus a note the brain appends after a typed check of the reply: when memory stores
  the turn and a sentence of the reply says the fact is kept for this chat, conversation or
  session, the reply ends with a note saying the exchange is stored and recalled in later chats.

What each draw counts:

- **Search**: the trace names, as an identifier, a tool that is not in the request's tool list and
  whose name holds `remember`, `save`, `store`, `add`, `memor`, `note`, `record` or `fact`.
- **Trace characters**: the length of the `thinking` text the turn streamed.
- **Chat only**: a sentence of the reply, read by hand, says the fact is kept, remembered or kept
  in mind for, during or in this or our chat, conversation or session. The hand reading defines the
  form; B's reader is what is tested against it.
- **Forget**: the turn calls `forget_memories`, read from a `ToolActivity` event or a card.
- **Stored**: a `memories` row holds the fact after the draw.

The first requests of the builds are compared before any item is read. B changes nothing before
the reply, so its first request should equal base's but for the turn id and time. If it does, an
item about the search, the trace, the chat-only rate, the forget calls or the stored rows would
measure only draw noise between base and B, so B is judged on its note alone.

- **B ships** when its note follows every B draw whose reply has the chat-only form and no B draw
  whose reply lacks it, and the reader, replayed over every reply recorded tonight (slot 1's five,
  and every base, A and B reply here), flags each hand-read chat-only reply and no other. How often
  the form occurs is a separate count and decides nothing; if no B draw shows it, the replay alone
  decides.
- **A ships** when its search count is at most 2 of 15 against at least 10 of 15 on base, no A
  reply has the chat-only form, A calls `forget_memories` in no more draws than base, and A stores
  the fact in no fewer draws than base less one. A is a prompt change, so B is preferred: when both
  pass, B ships tonight and A's sentence is written as the next step for the search alone.
- The null result is a build that fails any part of its rule: it is not shipped, and the task
  stays open with the counts written here.

## The draws, 2026-11-07

Run log `rows.jsonl`, with `spans.txt` naming each draw's lines of the proxy's `req.log` and
`analysis.txt` reading them, in
`/tmp/claude-1000/-home-david-Files-Git-Cortex/37073e3c-5ca6-42f6-aae1-df9e67b0e4db/scratchpad/slot5/`.
Base was built from `84bff1ba2`. All 45 draws ended `turn_complete`, and the SM clock read 0.57 of
its maximum at the start and at the end.

On all 15 rows B's first chat completion request equals base's once turn ids and times are
masked, and A's holds one more system message. So B is judged on its note alone.

| Build | Search | Median trace characters | Chat only | Forget | Stored | Note shown |
| --- | --- | --- | --- | --- | --- | --- |
| Base | 15 of 15 | 3,025 | 0 of 15 | 0 | 15 of 15 | no such note |
| A | 5 of 15 | 430 | 0 of 15 | 0 | 15 of 15 | no such note |
| B | 15 of 15 | 3,035 | 0 of 15 | 0 | 15 of 15 | 0 of 15 |

- **B ships.** No draw of any build had the chat-only form, so the replay decides. The reader
  flags the two slot 1 replies that keep the fact "for our conversation" and none of the other
  three slot 1 replies or the 45 here; over slot 2's 15 and slot 4's 65 forget replies it flags
  none. "For our future conversations", the closing of 7 of the 45 replies, is not flagged. The B
  image was built before the reader skipped a possessive ("this session's notes"); no recorded
  reply has one, so the replay over the shipped reader decides.
- **A does not ship.** It searched in 5 of 15 draws against 15 of 15 on base, above its bound
  of 2. It cut the median trace to a seventh of base's and the median turn time to 0.32 of base's
  on this machine, with every fact stored and no forget call. One of the five (R14) named
  `list_memories`, a lookup the rule's word list counts; without it A is 4 of 15 and still fails.
- The chat-only form occurred in 0 of 45 draws here and in 2 of 5 when the task was filed. Those
  five drew with 11 rows in `memories` and these with none; whether recall moves the form is
  untested.
