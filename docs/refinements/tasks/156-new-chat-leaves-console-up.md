# A new chat leaving the console open

**Status:** done 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

`Ctrl+N` and the header's pencil cleared the switcher and any pending confirm but not `consoleTab`
(`overlay/overlayState.ts`, case `newChat`), so the panel created the session and emptied the chat
behind the console while Appearance or Shortcuts stayed on screen. Measured 2026-07-20 at 900x900:
open the console, press Ctrl+N, and the live tabpanel still read "Appearance" while the title behind
it had gone back to "New chat". This predates the console, since neither of the two sheets it
replaced was cleared by `newChat` either.

Which way to fix it was a preference, not a defect, so it was left for the maintainer. He answered
on 2026-08-03: Ctrl+N closes the console, because a keystroke aimed at the conversation should put
you in the conversation.

`openSession` had the same hole and is reachable by keyboard, since Ctrl+Up and Ctrl+Down cycle
chats from anywhere in `Overlay.tsx`. So the rule that shipped is that a conversation arriving on
the panel brings the chat with it, rather than a special case for one keystroke. `deleteSession` and
`adoptSession` deliberately keep the tab and are unchanged, with their reasons now written down: a
delete comes from a switcher row, so the user is managing chats, and `adoptSession` is a cold-start
restore that must take nothing off the panel. Both halves are covered in
`overlay/overlayState.test.ts`, and each clear was proven necessary by removing it and watching the
test fail.

## History

- 2026-07-20: Opened while verifying the console merge.
- 2026-08-03: Closed on the maintainer's answer. It was one line in one reducer case as described,
  plus a second line in a second case the entry had not noticed.
