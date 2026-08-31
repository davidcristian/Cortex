# Ctrl+K toggling a section nobody can see

**Status:** landed 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-07 by the close above, which
measured the path and declined to answer it there. The chords are deliberately live while the
panel is not on screen, which is right for the ones that summon it (`Ctrl+N` and the cycle keys
set `mode: "panel"` on their way through), and `toggleSwitcher` sets no mode at all: measured at
900x900, `Ctrl+K` from a tucked panel mounts the list with its three rows and turns the chats
button's `aria-expanded` true with nothing on screen, and pressed with the console up it does the
same behind a chat view that is `inert` and `aria-hidden`. The next summon, or the next Escape out
of the console, then finds the list open without anybody having opened it in front of them. The
announcement rule above stands down for both, so the overlay no longer claims otherwise, but the
toggle itself is untouched. The shapes are for the key to summon the panel the way `Ctrl+N` does,
for it to be refused while the chat is not the view on screen, or for nothing at all on the
argument that a section found already open costs one press to shut. Each is a decision about what
the overlay's keys mean while it is tucked, which reaches the whole key table rather than this one
key, and that is why it is here rather than in the close above. Wants the same trace across a
summon that lands on an already open list. Nothing blocks it.
- **LANDED 2026-08-07 as the first of the three shapes, and the entry named one key where the
  measurement found two** ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The rule
  is that a global key aimed at one of the panel's surfaces puts that surface on screen, and that
  off the chat the press OPENS rather than toggling, because what a reader can see is a shut
  switcher and a shut console whatever the flags say.
  **The key table, enumerated from the code rather than from the entry.** The overlay owns exactly
  six global keys, all six on one `window` keydown listener in `components/Overlay.tsx`: `Escape`,
  `?`, `Ctrl+N`, `Ctrl+K`, `Ctrl+↑` and `Ctrl+↓`. The summon is not among them, being a host
  hotkey that arrives as the `cortex:activate` event (`overlay/activation.ts`), and every other
  key in the overlay belongs to a field or a control that has to be reached first. Four of the six
  already had an answer for a surface nobody can see. `Ctrl+N` and the two cycle keys set
  `mode: "panel"` and clear the console on their way through, which `sessionState.ts` argues in
  those exact terms, and `Escape` acts on whatever is topmost and is a no-op with nothing up.
  **Two did not, and the entry counted one of them.** `Ctrl+K` is the one it names. `?` has the
  same defect in the tucked case: measured at 900x900 over the demo bridge, pressing it from a
  tucked panel mounted the console and took the chat view `inert` and `aria-hidden` behind a panel
  that was not on screen, with `document.activeElement` still on `body`. It is the undercount
  lesson for the sixth entry running, and this time the sixth of a table of six.
  **Before, measured in headless Chromium at 900x900 against the demo bridge**, each press taken
  from a fresh page in one of four setups, reading the panel's visibility, the switcher's mounted
  rows, `aria-expanded` on the chats button, whether the console is up, the chat pane's `inert`
  and `aria-hidden`, `document.activeElement` and the live region's text.

  | key | on the chat | tucked | behind the console | behind the console, list open |
  | --- | --- | --- | --- | --- |
  | `Escape` | dismisses, caret to `body` | nothing | console leaves, caret to composer | console leaves, caret to composer |
  | `?` | nothing, the caret being in the composer where it is a character | **console mounts, chat pane goes `inert`, panel not on screen, caret on `body`** | console leaves | console leaves |
  | `Ctrl+N` | fresh chat, announced | summons, caret to composer, announced | console leaves, fresh chat, announced | console and list leave, fresh chat, announced |
  | `Ctrl+K` | list opens, `aria-expanded` true, `Recent chats open. 3 chats.` | **3 rows mount and `aria-expanded` turns true with the panel off screen, silent, caret on `body`** | **3 rows mount and `aria-expanded` turns true behind the `inert` pane, silent, console stays up** | **the list shuts behind the console, silent** |
  | `Ctrl+↑` | nothing | nothing | nothing | nothing |
  | `Ctrl+↓` | swaps chat, announced | summons, swaps, announced | console leaves, swaps, announced | console and list leave, swaps, announced |

  `Ctrl+↑` doing nothing anywhere is not a fifth invisible path and is measured rather than
  assumed: `cycleTarget` does not wrap (`overlay/sessionState.ts`), the demo's restored chat is at
  the newest end, and an out of range target reads back as null, so the key means "the previous
  chat" and there is not one. It mounts nothing where nobody can see it, which is the property
  this entry is about, so it is left exactly as it is.
  **The argument for summoning rather than refusing or leaving it.** The tucked press is a request
  to come back: a reader who presses the chats key while the overlay is away is asking for their
  chats, which is what `Ctrl+N` already means one key over, and refusing it would make this the
  one key on the table that is live and inert at the same time. The console case decides itself on
  the precedent already written into `openSession`, where the cycle keys loading a conversation
  behind a standing console is called a surprise and answered by taking the console off; the
  switcher's list is a part of the chat view, so a key that opens it is aimed at the chat and
  lands there. And doing nothing was refused because the cost is not one press to shut: the state
  it leaves is a flag the screen disagrees with, which is what made the announcement stand down in
  the first place and what would keep making every later rule ask a second question.
  **What shipped is nine lines in `overlay/chromeState.ts`.** One helper lands the state on the
  chat (`mode: "panel"`, `consoleTab: null`, `touched: true`, the last of them for the reason the
  summon sets it, so a cold start adoption cannot replace what a key just put up), and both
  toggles read their "already showing" against the screen instead of the flag. `onChat` is not
  retired by this and changes job: it decided whether the sentence would be true, and now decides
  whether the press is a toggle or a request, which is the same question asked one step earlier.
  The announcement's own guard is gone with the state it guarded, since the arm cannot open a list
  off the chat any more, and `Ctrl+K` from a tucked panel now speaks the sentence truthfully.
  **After, same instrument, same four setups.** The whole first column is bit identical, which is
  the part worth checking first: on the chat nothing about any of the six keys moved.

  | key | tucked | behind the console | behind the console, list open |
  | --- | --- | --- | --- |
  | `?` | panel summons, console up, caret on the selected tab | console leaves | console leaves |
  | `Ctrl+K` | panel summons with 3 rows on it, `aria-expanded` true, caret to composer, `Recent chats open. 3 chats.` | console leaves, list opens, caret to composer, announced | console leaves, the list is still open, caret to composer |
  | `Ctrl+N` | unchanged | unchanged | unchanged |
  | `Ctrl+↑` / `Ctrl+↓` | unchanged | unchanged | unchanged |
  | `Escape` | unchanged | unchanged | unchanged |

  The last cell is the "summon that lands on an already open list" trace the entry asked for, and
  it is the open-rather-than-toggle rule paying for itself: the old code shut that list, so a
  reader who could not see it lost it to the press meant to show it.
  **The mutation proof.** Five mutations, five distinct failures, nothing else in the 673 test
  suite moving under any of them: stopping the helper from setting `mode` fails three cases (the
  two tucked ones and the existing open-then-shut case, which the key can only satisfy by
  summoning); letting it leave `consoleTab` alone fails the behind-the-console case; restoring
  the bare `!state.switcherOpen` flip fails the open-rather-than-toggle case; asking the console
  toggle for the flag alone rather than the flag and the mode fails the `?` case; and dropping
  `touched` fails both tucked cases.
  One property is worth writing down rather than filing: on the real Win32 body a window that is
  not shown receives no keys at all, so the tucked half of this table is reachable through the orb
  and the preview, which are modes with the window up and the panel away, and through a dismissed
  overlay whose window the shell still holds. That is true of `Ctrl+N` and the cycle keys exactly
  as it is of these two, so it is a property of the whole table and not of this change. Nothing
  was deferred behind this.

## Trail

- 2026-08-07: Opened by the close above, which measured the path and declined to answer it there.
- 2026-08-07: Landed as the first of the three shapes, the area going 11 to 10, one out and none in,
  filed about one key and answered for a table of six. The entry named one broken key where the
  measurement found two, which is the sixth entry in this chain to undercount its own paths and this
  time the sixth of a table of six. Nothing was deferred behind it.
