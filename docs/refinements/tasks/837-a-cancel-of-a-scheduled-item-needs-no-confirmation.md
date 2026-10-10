# A cancel of a scheduled item needs no confirmation

**Status:** open, actionable
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)
**Verified:** 2026-10-10

`cancel_scheduled` deletes an item for good and runs with no confirmation card, so only the
model's reading of tool results stands between a request and a cancel the person never asked for.
On a full schedule the cortex once cancelled 13 items nobody named, and in a baseline of five
chats it cancelled one ([readings](../../readings/schedule-full-cancel.md#results)). The
full-schedule result now says `NOT SCHEDULED` and tells the model to ask the person which item to
cancel, and no chat after that change called `cancel_scheduled`; a structural guard is still
missing.

Adding `cancel_scheduled` to the default `CORTEX_TOOLS_GATED` does not work as it stands. A
schedule holding one item made on a tainted turn makes `list_scheduled` return an `UNTRUSTED`
listing, which taints the turn, and `ToolDispatcher` refuses every confirmed call on a tainted
turn without showing a card. Both requested cancels in row H failed that way.

## What to do

Design a confirmation for `cancel_scheduled` that still works after a listing with a tainted item:
for example, a card that the dispatcher may show on a tainted turn for this tool, or a listing that
keeps the item's provenance mark but stops tainting the turn for a cancel by id. The card should
name the item's text and due time, since the call's arguments hold only its id. Measure with rows G
and H of the readings, with tainted items in the schedule.

## History

- 2026-10-10: filed from the one-time and daily rows.
- 2026-10-10: the full-schedule result text changed; the card was tried, failed row H on a
  listing with tainted items, and was backed out. The false claim seen in one chat is
  [R-836](836-a-recalled-exchange-is-claimed-again-with-no-call.md).
