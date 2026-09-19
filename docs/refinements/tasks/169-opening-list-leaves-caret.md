# A list the reader opens leaving the caret behind

**Status:** declined 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

Opening the switcher leaves the caret where it was, so a keyboard reader who asks for the chat list
is shown it and left far from it in the tab order. Measured at 900x900, `Ctrl+K` from the composer
leaves the caret in the field with its draft intact, and from the header's chats button the fourth
Tab press is the first row's title.

Moving the caret into the list is declined, for three measured reasons. A guard is not optional,
because `Ctrl+K` is pressed as often from the composer as from the list, so the rule would have to
be the mirror of the close rule's, "only when the caret is on the anchor", and the anchor is the
chats button, whose `aria-expanded` already reports the change. Everything the guard would let
through is the one path already answered. It cannot answer an empty list, there being no row to hand
the caret to. And it would have to choose a row without one being obviously right, since a fresh
chat is unlisted until it is written to. Reordering the header is declined too: it buys three Tab
presses at that already-answered path by moving a control for a reading-order reason.

What the measurement found instead is that an opening list is inaudible, and that is what was fixed.
Eleven of the thirteen paths move no caret, change no control the reader is on, and announce
nothing; the only channel is `aria-expanded` on a button the reader is not on. So a list the reader
opens now says what it contains: `Recent chats open. 3 chats.`, or the switcher's own words when it
has none. It is the contents and not the toggle, which is why there is no mirror for closing: a
close is already answered by the caret arriving on the chats button. The path decides rather than
the reducer case, so `Ctrl+K` announces and the header's button does not. A list opened where nobody
can see it says nothing.

Cost: `overlay/chromeState.ts`, 66 lines holding the switcher's toggle and the console's three
cases, split off `overlayState.ts` at 291 lines against the 300-line limit; `switcherOpened` in
`overlay/notice.ts`; `RECENT_CHATS` exported beside `NO_OTHER_CHATS` so the header control, the
list's label and the sentence are three renderings of one name.

Afterwards the nine keyed paths produce exactly one `childList` change on `.announcer` and nothing
elsewhere, the two button paths and the two off-screen paths stay silent, and the caret is unmoved
on all thirteen. Six mutations, six distinct failures, nothing else in the 670-test suite moving.

The entry's central claim held and every number in it was wrong. Walked with the keyboard rather
than counted from the markup, the six Shift+Tab presses are ten on the empty state and two in a chat
with messages. And the paths are thirteen where the entry counted two: the switcher has one opening
case, but what a rule has to answer is where the caret is when it fires.

## History

- 2026-08-07: Opened by the close rule above, which left the opening direction as it found it.
- 2026-08-07: Closed hours later with the caret declined on three measured reasons, the header
  reorder declined with it, and an announcement added in their place. It opened the entry about the
  key toggling a section nobody can see.
