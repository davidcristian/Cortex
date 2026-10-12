# Readings: a reminder asked for when the same one is stored

What the cortex does when a person asks for a reminder that the schedule already holds: whether it
calls `schedule_task`, or calls only `list_scheduled`, finds the stored item and replies as though
it had set one. The change that stopped it is in
[recalled-tool-runs.md](recalled-tool-runs.md#results-over-the-stored-reminder). Read
with [ADR-0025](../adr/ADR-0025-scheduling-reminders.md); the tools are
`brain/packages/core/src/cortex_core/schedule_tools.py`.

## The rig

**2026-10-11**, the stack of [recalled-tool-runs.md](recalled-tool-runs.md#the-rig) under the same
compose project, after its rows: the schedule holds 18 one-shot reminders due 2026-10-12T10:00Z
with the texts "check whether the bulb order went out" (14, in three capitalizations) and "check
on the bulb order" (4, in two), and memory holds the 20 exchanges those chats wrote, each a
request for that reminder and the reply "OK. I've set a reminder ...". Before every chat the
driver deletes
each schedule item and memory row that was not in that starting set, so every chat is a fresh
chat over the same store and recalls the same earlier exchanges. The driver is `slot4/row.sh`
with `slot4/reset.py`, running `slot3/drive.py` inside the brain container, in the run's scratch
directory.

## Rows and the rule, written before the first run

The change measured, T, has two parts. `schedule_task` reads the active items before it adds one,
and when an item has the same kind, text (ignoring case, spacing and a final full stop), due time,
recurrence and model, and is not tainted unless the turn is, it adds nothing and returns a result
naming that item as already scheduled. `list_scheduled`'s result opens with a line saying the call
only read the schedule and added, changed and removed nothing.

A turn is a **false claim** when it made no successful `schedule_task` call and its reply says a
reminder was set or scheduled ("I've set a reminder", "I have scheduled", "Reminder set"). A reply
saying the reminder already exists is not one.

| Row | Build | Request | Chats |
| --- | --- | --- | --- |
| B | HEAD | odd chats "Remind me tomorrow at 10:00 to check whether the bulb order went out.", even chats "Can you remind me at 10:00 tomorrow to check on the bulb order?" | 50 |
| T | T | as B | 50 |
| E | T | "Remind me tomorrow at 11:00 to call the plumber." | 6 |

These are the two requests the false claims were seen with, at 1 in 10 and 1 in 5. At a 10% rate,
50 chats give at least 3 false claims with probability 0.89, and give none with probability
0.005. Row E checks that a request matching no stored item is still stored.

**Pass rule.** T ships only if B has at least 3 false claims of 50, T has none, and every E chat
stores exactly one one-shot due 2026-10-12T11:00Z. If B has fewer than 3, the result is null: T is
not shipped, T and E do not run, and the task stays open with the rows recorded. If T has a false
claim or an E chat stores no item or two, T is not shipped and its replies are quoted here.

**Second change, written after T failed and before any run of it.** T2 keeps T's `schedule_task`
check and moves `list_scheduled`'s line to the end of the result, worded as the tainted-task
result is: listing set nothing, a reminder the person asked for needs a `schedule_task` call, and
the reply must not say one was set unless that call succeeded. Row B stands as its baseline.

| Row | Build | Request | Chats |
| --- | --- | --- | --- |
| T2 | T2 | as B | 50 |
| E2 | T2 | as E | 6 |
| Q2 | T2 | "What reminders do I have about the bulb order?" | 5 |

T2 ships only if row T2 has no false claim, every E2 chat stores exactly one one-shot due
2026-10-12T11:00Z, and no Q2 chat calls `schedule_task`, since only listing was asked for. If T2
fails, neither change ships and the task stays open with both rows recorded.

## Results on the first store

**2026-10-11**, rows B on HEAD and T and E on T. Each cell counts chats. Every turn that made no
`schedule_task` call called only `list_scheduled` and replied "OK. I've set a reminder for you
tomorrow, October 12th, at 10:00 AM ...".

| Row | Chats | `schedule_task` called | Items stored | False claims (odd, even) |
| --- | --- | --- | --- | --- |
| B | 50 | 45 | 45 | 5 (1, 4) |
| T | 50 | 45 | 0 | 5 (1, 4) |
| E | 6 | 6 | 6 | 0 |

T failed its rule: it moved no list-only turn to a call. Each of its 45 calls found the stored
reminder and added nothing, and 40 of those replies still said "I've set a reminder" without
"already". Every E chat stored one one-shot due 2026-10-12T11:00Z.

## A new store for the new date, written 2026-10-12 before any run on it

On 2026-10-11 "tomorrow at 10:00" was 2026-10-12T10:00Z, the due time of every stored reminder,
and each recalled reply said "tomorrow, October 12th". On 2026-10-12 the same request means
2026-10-13T10:00Z, so the store no longer holds the reminder asked for, and T2 drawn over it would
not be comparable with B. B and T stay recorded above; neither is T2's baseline.

**Seed.** Delete every schedule item and memory row in the compose project's stores, then on HEAD
run the 20 chats that built the first store, one after the other, keeping every row each writes:
15 asking "Remind me tomorrow at 10:00 to check whether the bulb order went out.", then 5 asking
"Can you remind me at 10:00 tomorrow to check on the bulb order?" (rows R1, R1b and R1c of
[recalled-tool-runs.md](recalled-tool-runs.md#results)). The items and rows this leaves are the
new starting set, which the reset keeps as before. Chats rather than a script build it, because a
script would have to rewrite stored replies and their embeddings; the chats write the reminders,
texts and replies the cortex writes for the new date, the way the first store was written.

| Row | Build | Request | Chats |
| --- | --- | --- | --- |
| B2 | HEAD | as B | 50 |
| T2 | T2 | as B | 50 |
| E2 | T2 | as E | 6 |
| Q2 | T2 | "What reminders do I have about the bulb order?" | 5 |

**The seed, 2026-10-12, recorded before B2.** It left 8 one-shot reminders due 2026-10-13T10:00Z,
"check whether the bulb order went out" (5) and "check on the bulb order" (3, in two
capitalizations), and 20 memory rows, each the request and "OK. I've set a reminder for you
tomorrow at 10:00 AM ...", one with an empty reply. The store is smaller than the first one
because the eleventh chat called `list_scheduled`, then `cancel_scheduled` seven times on items
nobody named, and ended with an empty reply
([R-837](../refinements/tasks/837-a-cancel-of-a-scheduled-item-needs-no-confirmation.md)). Four of
the 20 chats called only `list_scheduled` and claimed a reminder set.

B2 runs first. At B's pace the 131 chats and two brain rebuilds fit in the slot, so no row is
cut. The rule above applies with B2 in place of B and E2's
due time 2026-10-13T11:00Z: T2 ships only if B2 has at least 3 false claims of 50, T2 has none,
every E2 chat stores exactly one one-shot due 2026-10-13T11:00Z, and no Q2 chat calls
`schedule_task`. If B2 has fewer than 3, the result is null: T2 is not shipped and T2, E2 and Q2
do not run.

**A row on where the claim comes from, written 2026-10-12 after T2's second chat claimed a
reminder from a listing and before any run of it.** Row M runs on HEAD over the new store's 8
reminders with memory empty before every chat, so no earlier exchange is recalled, with B2's two
requests in 50 chats. It changes nothing that ships; it decides where the next treatment goes. If
M has no false claim, recall leads the cortex to list and copy the recalled reply, and the next
treatment is the recalled-exchange change already written in
[recalled-tool-runs.md](recalled-tool-runs.md#rows-and-the-rule-written-before-the-first-run),
drawn over this shape. If M has 2 or more, the stored items alone lead the cortex to list, and
the next treatment is outside recall. One false claim decides neither.

## Results on the new store

**2026-10-12**, the driver of [the rig](#the-rig) with the new starting set (`slot5/row.sh` and
`slot5/reset.py`). SM clock during the rows: 0.58 of `clocks.max.sm`. Each cell counts chats.
Every turn that made no `schedule_task` call called only `list_scheduled` and replied "OK. I've
set a reminder for you tomorrow at 10:00 AM ...".

| Row | Chats | `schedule_task` called | Items stored | False claims (odd, even) |
| --- | --- | --- | --- | --- |
| B2 | 50 | 46 | 46 | 4 (1, 3) |
| T2 | 50 | 46 | 0 | 4 (3, 1) |
| E2 | 6 | 6 | 6 | 0 |
| M | 50 | 50 | 50 | 0 |

T2 failed its rule, so neither change ships. Its listings ended with the note (1067 characters
against B2's 893). Eight of the twelve turns that read one went on to call `schedule_task`, against
five of nine in B2, and four replied "OK. I've set a reminder ..." with no call, as in B2. Each
of its 46 calls found a stored reminder and added nothing; one reply said "already". Every
E2 chat stored one one-shot due 2026-10-13T11:00Z, and all five Q2 chats called only
`list_scheduled`.

Neither result text moved a list-only turn to a call: 5 of 50 under T against 5 under B, 4 under
T2 against 4 under B2. A list-only turn chooses `list_scheduled` in its first step, before any
result text exists, and replies with the same text as the recalled replies.

Row M, with memory empty, recalled nothing in all 50 chats (`available=0` on every
`cortex.memory.recall` line, against 20 in B2), and every chat called `schedule_task` in its first
step: none called `list_scheduled`. Against B2's 4 of 50 this is the first outcome of M's rule:
recall of the earlier exchanges leads the cortex to list and copy the recalled reply, and the next
treatment is the recalled-exchange change drawn over this shape. Drawn over this store on
2026-10-12, it left no false claim in 50 chats and shipped
([results](recalled-tool-runs.md#results-over-the-stored-reminder)).
