# ADR-0052: Where the overlay's focus goes, what its keys do, and what it announces

**Status:** Accepted (2026-09-19)

## Context

The overlay's panel changes under the reader's hand in many ways: a conversation replaces the one on
screen, a row leaves a list, a section rolls shut, a console tab changes, the whole panel is
dismissed while staying mounted. Each of those can remove the control that had the keyboard focus,
and the browser then puts focus on `<body>`, outside the panel. Several of them also replace what is
on screen without moving focus at all, so a reader who cannot see the panel hears nothing. Traced in
Chromium with `document.activeElement` sampled per frame and the devtools accessibility tree read
beside a `MutationObserver` on every live region, most gestures did one of the two.

This record decides where focus goes after each kind of change, which keys the overlay responds to
and where, what is taken out of the tab order, what the one live region says, and whose text a draft
is. The console and the panel's motion are [ADR-0035](ADR-0035-console-and-motion.md). The
mechanisms, file by file, are in [body-app.md](../modules/body-app.md).

## Decision

### What is hidden

1. **`aria-hidden` and `inert` are written together, by one function, wherever the overlay keeps
   something mounted that is not on screen.** `withdrawn(away)` in `overlay/withdrawn.ts` returns
   the pair, and it is spread on the panel while it is dismissed, on the view being left for the
   length of its morph, on the console tab not showing, and on a list row on its way out. The two do
   different things: `aria-hidden` leaves the tab order alone and is refused over an ancestor of the
   focused element, while `inert` takes the subtree out of the tab order and the pointer's reach and
   blurs what it contains. `aria-hidden` is written both ways; `inert` only as present, since
   `inert="false"` would be an inert element.
2. **`inert` is written as the empty string.** React 18 has no prop entry for it and drops a boolean
   custom attribute, but writes a string one: `inert=""` is how HTML writes the attribute present.
   What React 18 lacks is the type, which one module augmentation in `overlay/withdrawn.ts` adds,
   narrowed to `""` so no call site can write the form React drops.
3. **A section rolling shut stays tabbable**, being still on screen and still in the accessibility
   tree; it is not a pane that has been left.

### The console's tab strip

4. **The strip is one stop in the tab order**, a roving `tabIndex` that is 0 on the selected tab and
   -1 on the other, so the tab with focus and the tab selected are one fact.
5. **Selection follows focus.** One arrow press moves the keyboard and changes the tab, as one click
   does, because both tabs are already mounted and within `TAB_SPREAD_PX` share a height. A future
   tab far enough apart to put the panel into a morph on every arrow is the signal to revisit this.
6. **Left and Right walk the strip and wrap; Home and End go to the ends.** Up and Down are left
   alone, Ctrl with them being the chat cycle. The four keys are `preventDefault`ed, because the
   clipped panel is a box the engine would scroll; every other key passes to the overlay's listener.
   The map is pure, `nextTab(key, tabs, from)` in `overlay/tabStrip.ts`, returning null on an empty
   strip.
7. **Focus follows the selection at every switch.** A layout effect focuses the tab that is up, with
   `preventScroll`, which also covers `?` changing the tab while the keyboard is inside the tab
   about to go inert. Each tab has `aria-controls` naming its pane, over an id from `useId`. A tab
   panel with nothing focusable in it takes no tab stop of its own.

### The switcher

8. **The switcher is a named list of rows.** It has no `listbox` role: the `<ul>` keeps its
   `aria-label` (`RECENT_CHATS`, shared with the header's chats button and the announcement) and the
   implicit list and list-item roles, and each row's four buttons stay individually reachable. The
   row's own button has `aria-current`, `true` on the open chat and `false` on the others. `Ctrl+↑`
   and `Ctrl+↓` are an application-wide cycle, not movement in the list.

### A conversation arriving

9. **A conversation arriving brings the chat with it.** `newChat` and `openSession` set
   `mode: "panel"` and clear `consoleTab`, so `Ctrl+N` and the cycle keys end in the conversation
   they were aimed at. `deleteSession` keeps the console and the switcher, being fired from a
   switcher row, and cold-start `adoptSession` changes nothing on the panel and gives way to
   `touched`. The four branches live in `overlay/sessionState.ts` and each answers the same three
   questions: what is announced (decision 13), where focus goes (decision 10), and what becomes of
   the draft (decision 11).
10. **Focus follows the conversation.** `OverlayState.arrival` is a count raised by every branch
    that replaces the conversation, and the composer focuses its field whenever the count changes
    (`arrival: number | null`, null while the panel is shut or the console is up, so a summon and
    leaving the console end there too), at the commit rather than after any roll. It is a count and
    not the session id, so re-selecting the open chat still counts. No flag travels with the action:
    every gesture into a branch ends in the same place.
11. **A draft belongs to the conversation it was typed into.** `OverlayState.drafts` holds unsent
    text keyed by session id (`overlay/drafts.ts`), and the composer is a controlled field over the
    entry for the chat on screen, so a swap hands over the arriving chat's own text in the same
    commit. An empty field is stored as no entry, which is the whole eviction policy. Sending
    empties the field only when the text sent is the field's own (`turnState.submit`), so an example
    chip leaves a half-typed question alone, and a rejected send costs nothing. Typing sets
    `touched`, so a cold-start restore cannot replace a conversation with a sentence waiting in it.
    A restored draft puts the caret at its end. Drafts live in the body's reducer and die with the
    process: the rule that state survives a model swap is met by being in the body at all, and a
    draft needs no store, being text nobody sent that only its field reads.

### The live region

12. **The overlay has one polite live region, and it says what just happened to the panel.**
    `components/Announcer.tsx` renders it at the overlay's root, outside the panel, since a
    dismissed panel is `inert` and a global key can put the panel on screen and change the chat in
    one commit. Every string it may hold is built in `overlay/notice.ts`. A `Notice` is `text` plus
    a `count`, and the region's child is keyed on the count, because a live region reports a
    mutation and identical text would otherwise announce nothing.
13. **The gesture decides whether a swap speaks.** `openSession`, `newChat` and `toggleSwitcher`
    take an `announce` flag set by the gesture, because one branch serves several gestures. A swap
    speaks when the control that fired it named no chat: the cycle keys, `Ctrl+N`, a reminder's open
    control, and the fresh chat after deleting the open one. It stays silent when the control's own
    name is the arriving title (a switcher row, the header's pencil, labelled "New chat").
    Cold-start adoption never speaks. The sentence is `Switched to <title>.`, the title computed by
    the same `headerTitle` the header uses, after the load succeeded. A silent swap clears the
    notice.
14. **A list that shrinks under the reader's gesture says so.** A delete says `Chat deleted. 2 chats
    left.` (or `No other chats yet.`, the empty line's own words through the shared
    `NO_OTHER_CHATS`), an ack says `Reminder dismissed. 1 reminder left.`, and a delete of the open
    chat says both, in order, in one string, so no ordering is left to a screen reader's queue. The
    deleted chat's title is not repeated, the pressed control having named it. Each branch speaks
    only when its list really shrank. A list replaced wholesale on a summon says nothing, since
    nobody made that change.
15. **Opening the switcher says what it holds**: `Recent chats open. 3 chats.`, or `Recent chats
    open. No other chats yet.` `Ctrl+K` announces and the header's chats button, whose
    `aria-expanded` already says it under the focus, does not. Closing says nothing, focus going to
    that button (decision 18). A silent toggle keeps the current notice rather than clearing it, the
    panel's contents being unchanged.

### Where focus goes in a list

16. **A list that reshapes under the hand keeps the focus** (`overlay/rowCaret.ts`). A row that
    changes shape hands it to the control that replaces the one that left: a rename opens on its
    editor with the title selected and closes, either way, on its pencil; a delete opens on the
    confirm's cancel, never on its destructive half, and closes on the trash. A row that leaves
    hands it to the same control in the row that takes its place (below, else above), so deleting
    several chats is one gesture repeated. A list left empty hands it to its anchor: the header's
    chats button for the switcher, the composer for the reminder stack. The `pinned` toggle survives
    its own regroup and needs no rule. The move happens at the commit, in a layout effect, to a
    control named by `data-caret` and looked up inside the list.
17. **Escape closes the innermost thing.** The rename editor and the delete confirm stop a
    cancelling Escape at the row, so it does not also dismiss the panel. The `?` guard asks about
    `HTMLInputElement` as well as `HTMLTextAreaElement`, so any field is covered on the day it is
    added.
18. **A section the reader closes hands focus to its anchor**, only when the focus is inside it
    (`useSectionCaret` in `overlay/sectionCaret.ts`): `Ctrl+K` from a row goes to the header's chats
    button, and `Ctrl+K` from the composer leaves the sentence being typed alone. It does nothing
    when a conversation arrived in the same commit, so focus does not visit two controls. An example
    chip unmounts its own section in the commit that sends, so it hands focus to the composer itself
    (`handOff`). The reminder stack needs no wiring: every way it closes is answered by a rule
    above. A dismissed panel leaves focus on `<body>`, nothing being on screen to hold it.
19. **Focus does not move into a list the reader opens.** The guard a close needs would let it
    through only from the chats button, which already reports the open; an empty list has no row to
    receive it; and no row is obviously the right one. The header's buttons keep their visual order.

### Keys

20. **A field keeps the chords it would lose text to** (`overlay/fieldKeys.ts`). `chord(press)` is
    the overlay's one definition of a modified press (Ctrl, or Cmd on the Mac), shared with
    `components/Overlay.tsx`; `fieldKey(press)` answers `cancel`, `hold` or `pass`. The rename
    editor keeps every chord with `stopPropagation` and never `preventDefault`, so the field's own
    uses of a chord (select all, undo, the caret jumps that `Ctrl+↑` and `Ctrl+↓` are in a field)
    still work, and Enter or Escape settles the name first. The composer keeps its text per chat and
    passes chords; the delete confirm holds no text and passes them too.
21. **A kept chord stays silent.** The rule covers every chord, not the four the overlay binds, and
    most chords still do something to the field, so any sentence raised there would be false at most
    presses; a description on the input would be the key table in the markup. A kept chord destroys
    nothing, so there is nothing to report.
22. **A global key aimed at a part of the UI puts that part on screen, and opens the chat rather
    than toggling.** The overlay's window listener answers six keys: Escape, `?`, `Ctrl+N`,
    `Ctrl+K`, `Ctrl+↑` and `Ctrl+↓`; the summon arrives separately as the host's `cortex:activate`.
    `ontoChat` in `overlay/chromeState.ts` sets `mode: "panel"`, clears `consoleTab` and sets
    `touched`. The switcher opens unless it is already open on screen, and `?` toggles only when the
    panel is up on the shortcut tab, so a press never closes something the reader was not shown.

## Consequences

- Nothing here proves how a screen reader speaks the region, or in what order against a focus move
  in the same commit; that measurement is [host task 016](../host/tasks/016-live-region-speech.md).
- A reader who deletes the open chat ends in the new chat's composer with the switcher still open
  behind it, several Shift+Tab presses away.
- The header's chats button and the switcher share the name "Recent chats"; they announce with
  different roles.
- "Draft" also names an approval's arguments (`components/draftValue.ts`) and a row's in-progress
  rename; the composer's draft is what the overlay's docs mean by the word.
- Nothing suppresses a repeated keydown in a field. Anything that later speaks per keydown there has
  to bring its own guard.
- On the Win32 body a hidden window receives no keydown, so the tucked cases of decision 22 are
  reached from the orb, the preview and a dismissed overlay whose window the shell still holds. The
  rule is written on `mode === "panel"` for that reason.

## Alternatives rejected

- **A listbox with `aria-activedescendant`** for the switcher: it needs one stop for rows of four
  buttons each, and would have moved focus on the cycle keys.
- **Focus to the header's chats button after a swap**, or keeping it in the switcher after a delete:
  the composer is where a summon ends and puts the reader in the conversation that arrived.
- **A second live region, or a status line inside a list**: two regions mutating in one commit hand
  the order to the screen reader, and a region inside the reminder stack leaves with the sentence
  saying the stack is empty.
- **Committing or cancelling a rename before running the chord**: the first writes a half-typed
  name, or clears a custom title from an emptied editor; the second destroys the same work.
- **A store-backed draft**: a proto message, an adapter and an eviction policy, spent per keystroke,
  for a sentence a restart loses anyway.
- **Refusing `Ctrl+K` off the chat, or ignoring it**: it is a request to come back, as `Ctrl+N` is,
  and ignoring it leaves a flag the screen disagrees with.

## Related

- [ADR-0035](ADR-0035-console-and-motion.md) (the console and the panel's motion);
  [ADR-0021](ADR-0021-session-read-rpcs.md) (the switcher's catalog);
  [ADR-0025](ADR-0025-scheduling-reminders.md) (reminders and their ack).
- [body-app.md](../modules/body-app.md), the module contract;
  [overlay-ux.md §6 and §7](../design/overlay-ux.md) (keyboard and accessibility).
- [host task 016](../host/tasks/016-live-region-speech.md): the screen-reader measurement.
