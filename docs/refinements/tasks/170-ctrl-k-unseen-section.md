# Ctrl+K toggling a section nobody can see

**Status:** done 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

`toggleSwitcher` set no mode, so `Ctrl+K` from a dismissed panel mounted the list with its rows and
turned the chats button's `aria-expanded` true with nothing on screen, and pressed with the console
up it did the same behind a chat view that is `inert` and `aria-hidden`. The next summon then found
the list open without anybody having opened it.

The rule that shipped: a global key aimed at one of the panel's surfaces puts that surface on
screen, and off the chat the press opens rather than toggling, because what a reader can see is a
closed switcher and a closed console whatever the flags say. A dismissed press is a request to come
back, which is what `Ctrl+N` already means one key over. The console case follows the precedent in
`openSession`, where loading a conversation behind an open console is treated as a surprise and
answered by removing the console. Doing nothing was refused, because the state it leaves is a flag
the screen disagrees with.

The overlay owns exactly six global keys, all on one `window` keydown listener in
`components/Overlay.tsx`: `Escape`, `?`, `Ctrl+N`, `Ctrl+K`, `Ctrl+↑` and `Ctrl+↓`. Four already had
an answer for a surface nobody can see. Two did not, and the entry counted one: `?` had the same
defect while the panel was dismissed, mounting the console and taking the chat view `inert` behind a
panel that was not on screen.

`Ctrl+↑` does nothing anywhere, measured rather than assumed: `cycleTarget` does not wrap
(`overlay/sessionState.ts`), the demo's restored chat is the newest, and an out-of-range target
reads back as null. It mounts nothing off screen, so it is left as it is.

What shipped is nine lines in `overlay/chromeState.ts`. One helper puts the state on the chat
(`mode: "panel"`, `consoleTab: null`, `touched: true`), and both toggles read "already showing"
against the screen instead of the flag. `onChat` now decides whether the press is a toggle or a
request. Five mutations, five distinct failures, nothing else in the 673-test suite moving.

One property worth writing down: on the real Win32 body a window that is not shown receives no keys
at all, so the dismissed half of this is reachable through the orb and the preview, which are modes
with the window up and the panel away, and through a dismissed overlay whose window the shell still
holds. That is true of the whole key table, not of this change.

## History

- 2026-08-07: Opened by the entry above, which measured the path and declined to answer it there.
- 2026-08-07: Closed as the first of the three options, filed about one key and answered for a table
  of six. The entry named one broken key where the measurement found two. Nothing was deferred
  behind it.
