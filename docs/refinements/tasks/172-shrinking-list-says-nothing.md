# A list that shrinks saying nothing

**Status:** landed 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-06 by the caret
rule further above, which is named rather than pointed at now that its chord entry and that
entry's own two successors stand between them. The caret's landings all put focus on a control
whose accessible name says what it is
("Delete Reminders and recurrence", "Cancel delete", the pencil carrying the new title), which is
why no live region was added with the rule; but the change to the LIST is silent. A reader who
deletes a chat hears the name of the control they landed on and never hears that a row left, that
one row is left, or that the list is now empty, where the arrival rule's own region says which chat
arrived (`overlay/notice.ts`). The shapes are a second region for the list, a `role="status"` line
inside the switcher, or extending `notice` to carry more than a chat title, and the third is the one
that risks the most: that region is read by the panel's own announcer and its contract today is "the
conversation that arrived". Wants a measurement in a real reader before a shape is picked. Nothing
blocks it.
- **LANDED 2026-08-07 as the third of those shapes, which the entry ranked riskiest and the
  measurement ranked safest** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The
  region carries what just happened to the panel: a chat that arrived, a list that shrank, or both
  in one sentence when a delete did both.
  **What was measured first, and what the entry got wrong.** Chromium 1228 headless at 900x900
  against the demo bridge, reading the devtools accessibility tree (`Accessibility.getFullAXTree`)
  plus a `MutationObserver` on every node in the document carrying `aria-live`, `role="status"`,
  `role="alert"` or `role="log"`. The whole live-region roster of a resting overlay is **two
  nodes**, neither carrying an explicit `aria-live` or `aria-atomic`, both computing
  `live: "polite"`, `atomic: true`, `relevant: "additions text"`: `div.announcer`, empty, and
  `span.linkdot.ok`, named "Brain ready: cortex-orchestrator demo". The capture ring's region and a
  failed reply's alert are in no resting tree, each mounting with its event. The entry's central
  claim reproduced, and on the reminder stack too, which it did not name: deleting a chat that was
  not the open one, deleting down to the empty line, acking a reminder, and acking the last one so
  the section left, all produced **zero** mutations in any live region on the page.
  **Three things it did not have.** The first decided the shape: **deleting the open chat is not
  silent**, that arm already speaking, so the commit that shrinks the list is also the commit that
  announces (`Switched to New chat`, one `childList` mutation). The reader still hears nothing
  about the row that left, which is the entry's point, but any second region would have two
  announcements in flight at once. The second is a location: the entry called the region "the
  panel's own announcer" and it is deliberately OUTSIDE the panel, a sibling at the overlay's root,
  which is the fact that rules out one of its three shapes. The third was checked rather than
  assumed, per the standing warning: the cycle-keys entry's count key still holds, three
  consecutive `Ctrl+N` presses each removing the region's child and adding a fresh one with
  identical text.
  **Why widening `notice` is the safe shape and not the risky one.** A second region puts two
  announcements in one commit and hands the ordering to the reader's speech queue, which is
  observable in NVDA and not in an accessibility tree; a `role="status"` line inside the switcher
  is worse, since the reminder stack's whole section is unmounted with its last row (measured:
  `.reminders` is not in the document afterwards), so a region inside it would leave in the same
  commit as the sentence saying it is empty. One region has neither problem, because the order is
  written into the string. And the region was never only about arrivals: `deleteSession` has been
  one of its four writers all along, naming the empty chat that takes the deleted one's place.
  **What it says.** `Chat deleted. 2 chats left.`, `Chat deleted. 1 chat left.`,
  `Chat deleted. No other chats yet.`, `Reminder dismissed. 2 reminders left.`,
  `Reminder dismissed. No reminders left.`, and for the delete that also swaps,
  `Chat deleted. 1 chat left. Switched to New chat.` The deleted title is not repeated, the control
  pressed being labelled "Confirm delete <title>"; what is news is that the write landed, since a
  failed delete leaves the row, and what the list has become. The empty-list words are
  `NO_OTHER_CHATS`, exported from `overlay/notice.ts` and rendered by `SessionList`, so the line on
  screen and the sentence are one string. `Switched to <title>` gained a full stop, being sometimes
  the second clause now.
  **What it cost**: `overlay/notice.ts` grew from 41 lines to 93 and is now the whole of what the
  region may carry (`speak` counts and joins, `arrived`/`chatDeleted`/`reminderDismissed` build);
  `Notice.title` became `Notice.text` and `Announcer` renders it rather than composing a prefix.
  Both arms were already reducer arms, so nothing was plumbed: `sessionState.deleteSession` speaks
  on both of its paths and `overlayState`'s `reminderDismissed` on its one, each guarding on the
  list having really shrunk so a repeated dispatch claims no row.
  **After, measured the same way.** Every list change now produces exactly ONE `childList` mutation
  on `.announcer` and nothing anywhere else; the connection dot's region never moves. The roster is
  still two regions with the same computed attributes, the empty line still reads `No other chats
  yet` in the list's own subtree, and the caret still lands where the caret rule put it
  (`button[Delete Everything about model swaps]`, `button[Recent chats]`, `textarea[Message]`).
  **What could not be measured here** is whether a reader SPEAKS it, and what happens when the
  polite update and the composer's focus announcement land in the same commit, which is what
  deleting the open chat does. That is a Windows sitting with NVDA, filed at
  [host/overlay-screen-reader.md](../../host/index.md#overlay-screen-reader) rather than left here: the
  shape was pickable from the tree and only the speech is not.
  **And one silence was left deliberately**, recorded rather than counted because it is a decline
  on merits: a list that shrinks for a reason the reader did not cause stays quiet.
  `remindersLoaded` and `sessionsLoaded` replace their lists wholesale on every summon, so a
  reminder acked on another surface leaves without a sentence. Announcing a change nobody made
  turns the region into a feed, and no second surface exists to make one. It reopens with one.

## Trail

- 2026-08-06: Opened by the caret rule, whose landings put focus on controls whose accessible names
  say what they are while the change to the list itself stayed silent.
- 2026-08-07: Landed as the third of its own three shapes, the one the entry ranked riskiest and the
  measurement ranked safest, one out and none in, with the header count walked entry by entry
  beforehand and agreeing with the index cell one for one. The measurement came before the shape and
  moved it, and the two corrections that decided it are the open chat's delete already speaking and
  the region living outside the panel. Its sibling, the held chord, was read with it and
  deliberately left open. What only a real reader can settle went to the overlay screen-reader
  sitting as a Windows measurement rather than staying here.
