# A held keyboard shortcut saying nothing about being held

**Status:** declined 2026-08-07
**Area:** body-overlay
**Origin:** [ADR-0052](../../adr/ADR-0052-overlay-focus-and-announcements.md)

When the rename editor holds a keyboard shortcut, the press is stopped, the editor stays as it was,
and nothing is announced. For a sighted reader the state on screen is the explanation. For a screen
reader user there is no event, no focus move and no announced change, so nothing distinguishes a
shortcut the editor held from one the application ignored. Four options were weighed: the overlay's
live region, a `role="status"` line the editor owns, an `aria-describedby` line on the input, or
nothing.

All four are declined. The deciding fact is that the hold is not four keys, it is every modified
press: `fieldKey` asks whether a press is modified and nothing else, deliberately, so that what
counts as a shortcut has one definition on both sides of the window listener. Nine presses were
measured through that one branch, every one stopped from reaching the window, and seven of the nine
did something in the field anyway, two of them changing the text (`Ctrl+Backspace` deleted a word
and `Ctrl+Z` undid the whole edit).

So the live region is refused because the sentence would be false for most of the shortcuts it would
fire on: a reader who pressed `Ctrl+Z` and watched their name come back would be told the editor is
waiting. Making it true means teaching `fieldKeys.ts` which shortcuts the overlay binds, which is
the coupling the hold rule removed and which goes stale the day a fifth one is bound. The
`role="status"` line is refused because the editor is unmounted by Enter and by Escape, so a region
inside it leaves in the commit after the sentence it would hold, and it would compete with the
existing region. The description is refused because an accurate one enumerates the bound keys in the
markup and is spoken on every rename.

The silence also passes the test the region's contract sets, which is what a gesture destroys. A held
shortcut destroys nothing, measured to the attribute: the focused node reads `textbox`, named "New
chat name", with the same value before and after each press. The editor announces itself when it
opens and again when it closes, and Escape and Enter each leave the caret on a rename button whose
name reads back the settled title. The instrument was shown to work, the same observer catching
`Chat deleted. 2 chats left.` on a delete.

The repeat policy is left unanswered rather than answered, since a rule that announces nothing needs
no guard. It was measured anyway: thirty `keydown` events with `repeat: true` all reached the
editor's handler, nothing in the path filtering them. CDP does not synthesise platform autorepeat,
so what was measured is the absent guard rather than the repeat itself.

What only a real screen reader can settle is filed at
[host/overlay-screen-reader.md](../../host/index.md#overlay-screen-reader). If a reader there cannot
tell a held shortcut from a dead application, that reopens this as a rule about the whole key table
rather than about one field.

## History

- 2026-08-07: Opened by the shortcut entry above, whose answer is deliberately silent.
- 2026-08-07: Read alongside the silent-shrink entry when that one closed, and deliberately not
  bundled with it. The shared question closed for both, the region being allowed to hold more than
  an arrival.
- 2026-08-07: Declined, all four options, on the measurement that the rename editor holds every
  modified press and that seven of the nine measured do something in the field anyway. Nothing
  opened behind it.
