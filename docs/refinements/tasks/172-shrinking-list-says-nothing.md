# A list that shrinks saying nothing

**Status:** done 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

The caret rule puts focus on a control whose accessible name says what it is, so no live region was
added with it. But the change to the list itself was silent: a reader who deleted a chat never heard
that a row left, that one row is left, or that the list is now empty. Measured with a
`MutationObserver` on every live region: deleting a chat that was not the open one, deleting down to
the empty line, acknowledging a reminder, and acknowledging the last one all produced zero changes.

Fixed by widening the existing region, which the entry ranked riskiest and the measurement ranked
safest. A second region puts two announcements in one commit and hands the ordering to the reader's
speech queue, which is not observable in an accessibility tree. A `role="status"` line inside the
switcher is worse, since the reminder stack's whole section is unmounted with its last row, so a
region inside it would leave in the same commit as the sentence saying it is empty. One region has
neither problem, because the order is written into the string. And the region was never only about
arrivals: `deleteSession` has been one of its four writers all along.

What it says: `Chat deleted. 2 chats left.`, `Chat deleted. 1 chat left.`, `Chat deleted. No other
chats yet.`, `Reminder dismissed. 2 reminders left.`, `Reminder dismissed. No reminders left.`, and
for the delete that also swaps, `Chat deleted. 1 chat left. Switched to New chat.` The deleted title
is not repeated, since the control pressed is labelled "Confirm delete <title>". The empty-list words
are `NO_OTHER_CHATS`, exported from `overlay/notice.ts` and rendered by `SessionList`, so the line on
screen and the sentence are one string.

Cost: `overlay/notice.ts` grew from 41 lines to 93 and is now the whole of what the region may say;
`Notice.title` became `Notice.text`. Both reducer cases were already reducer cases, so nothing was
plumbed through, and each checks that the list really shrank so a repeated dispatch claims no row.

Two corrections decided the shape. Deleting the open chat was not silent, that case already
announcing, so the commit that shrinks the list is also the one that announces. And the region is
deliberately outside the panel, a sibling at the overlay's root, which rules out one of the three
options.

Afterwards every list change produces exactly one `childList` change on `.announcer` and nothing
elsewhere. Whether a reader speaks it, and what happens when the polite update and the composer's
focus announcement arrive in the same commit, is a Windows measurement with NVDA, filed at
[host/overlay-screen-reader.md](../../host/index.md#overlay-screen-reader).

One silence was left deliberately: a list that shrinks for a reason the reader did not cause stays
quiet. `remindersLoaded` and `sessionsLoaded` replace their lists on every summon, so a reminder
acknowledged on another surface leaves without a sentence. Announcing a change nobody made turns the
region into a feed, and no second surface exists yet to make one.

## History

- 2026-08-06: Opened by the caret rule, whose results put focus on controls whose accessible names
  say what they are while the change to the list itself stayed silent.
- 2026-08-07: Closed by widening the existing region. The measurement came first and moved the
  shape. Its sibling, the held shortcut, was read with it and deliberately left open.
