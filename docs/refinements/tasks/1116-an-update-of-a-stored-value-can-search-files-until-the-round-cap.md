# An update of a stored value can search files until the round cap

**Status:** open, actionable
**Area:** memory
**Origin:** [ADR-0019](../../adr/ADR-0019-tainted-memory-recording.md)
**Verified:** 2026-11-10

In u2 draw 2 of [the readings](../../readings/correction-keeps-old-value.md), `Update my gym locker
number: it is 5512, not 5521.` called `list_allowed_directories`, `search_files`, `list_directory`,
`read_text_file`, `directory_tree` and `spawn_subagents` for 8 rounds and stopped at the round cap
with no reply. The seed row holding 5521 stayed, nothing of the turn was stored, and the only text
was the round cap note, which does not say the new value was not kept. One of three u2 draws; u2
draw 1 also called a file tool and a subagent before replying.

## What to do

1. Draw the u2 correction 8 times on a candidate through the proxy and count the turns whose first
   request already offers file tools and whose first call is one, before deciding anything.
2. If the form repeats, weigh closing a round cap turn on a message holding a value with
   `UNKEPT_CLAIM_NOTE` (it states only that nothing was kept) against a change to the file tool
   descriptions. The note invites no forget.

## History

- 2026-11-10: filed from u2 draw 2 in [the readings](../../readings/correction-keeps-old-value.md).
