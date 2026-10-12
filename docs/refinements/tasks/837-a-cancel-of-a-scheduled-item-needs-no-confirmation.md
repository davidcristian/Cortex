# A cancel of a scheduled item needs no confirmation

**Status:** done 2026-10-12
**Area:** scheduling
**Origin:** [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md)

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
- 2026-10-12: seen again far from a full schedule. Asked to set a reminder while nine copies of it
  were stored, the cortex listed them and cancelled seven, which nobody named, with no card, until
  the turn ran out of tool rounds ([readings](../../readings/reminder-already-stored.md)).
- 2026-10-12: done. `cancel_scheduled` needs confirmation in code, and its card is a record card:
  the dispatcher shows it on a tainted turn too, with the stored item's listing line as its reason
  ([ADR-0022](../../adr/ADR-0022-email-write-confirmer.md) decision 2,
  [ADR-0025](../../adr/ADR-0025-scheduling-reminders.md) decision 3). A listing with a tainted item
  still taints the turn, so every other confirmed tool stays blocked after it. Rows G2, U1, U2, H2
  and R passed the rule written before them
  ([readings](../../readings/schedule-full-cancel.md#a-cancel-card-shown-on-a-tainted-turn)); the
  date misreading two G2 replies showed was fixed by naming each listed due time's day
  ([readings](../../readings/schedule-full-cancel.md#a-next-day-item-read-as-tomorrow)).
