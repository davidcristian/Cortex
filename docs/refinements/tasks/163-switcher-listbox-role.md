# The chat switcher's disputed listbox role

**Status:** landed 2026-08-03
**Area:** body-overlay
**Origin:** [ADR-0035](../../adr/ADR-0035-console-and-motion.md)

Opened 2026-08-03 by the pass
that gave the console's tab strip its keyboard half ([ADR-0035
addendum](../../adr/ADR-0035-console-and-motion.md)), which checked the overlay's other lists for the
same shape of gap and found one that is not the same shape at all. `SessionList.tsx` puts
`role="listbox"` on its `<ul>`, and its children are `<li>` elements holding four ordinary buttons
each (the row itself, then pin, rename and trash) with no `role="option"` anywhere, so a listbox
is announced whose required children are missing; measured in Chromium at 900x900, one open
switcher with two rows offers eight tab stops. The strip's problem was a correct role with half a
keyboard, which completing is additive. This is the opposite: the role and the interaction model
disagree, and settling it means choosing between two shapes rather than filling one in. Either the
rows become options and the list becomes one tab stop moved through with `aria-activedescendant`
(which then has to say what happens to the three per-row buttons, since an option is a leaf and
they are not), or `role="listbox"` comes off and it is the list of composite rows it already
behaves like, in which case the rows need `role="listitem"` semantics and nothing else changes.
Whichever wins has to be reconciled with Ctrl+Up and Ctrl+Down, which cycle sessions overlay-wide
without moving focus at all and would be the obvious keys for a listbox to answer with focus. The
reminder stack was read in the same pass and needs nothing: its `<ul>` claims no role its children
have to satisfy, and tabbing through rows of buttons is correct for it. A section rolling shut was
read too and is deliberately left alone: `.collapse` hides its overflow while its height animates
to zero and the clipped content keeps its place in the tab order, but it is also still in the
accessibility tree, so both channels agree, which is the standard the strip's pass applied rather
than a violation of it. Nothing blocks this; it is a design decision plus its wiring.
- **LANDED 2026-08-03, the same day it was opened, on the user's answer: the role comes off**
  ([ADR-0035 addendum](../../adr/ADR-0035-console-and-motion.md)). The switcher announces the list
  of composite rows it already behaved like. `role="listbox"` is off the `<ul>`, the `aria-label`
  stays and now names a list, all four buttons per row keep their own tab stops, `Ctrl+↑` and
  `Ctrl+↓` are untouched, and neither `aria-activedescendant` nor `role="option"` went in. Two of
  the entry's own claims want correcting. **The role cost more than the role.** A `<li>` inside a
  listbox is not a listitem, so the rows did not merely fail to be options, they were announced
  as nothing at all: read out of Chromium's accessibility tree at 900x900, the container was
  `listbox "Recent chats"` over three children of role `none`, each holding its four buttons
  directly, which is a listbox with no options in it and twelve loose buttons inside. With the
  role off, the same tree reads `list "Recent chats"` over three `listitem`s, and nothing had to
  be written on the `<li>` to get them back; the implicit roles return on their own, leaving the
  reminder stack's arrangement exactly (`Reminders.tsx` is a named `<ul>` with no role either).
  **And "nothing else changes" was wrong by one channel.** Which chat is open was carried by a
  background tint and by nothing else, and this answer drops the one shape that could have
  carried it, `aria-selected` needing the listbox, so the row's own button now carries
  `aria-current`, `true` on the open row and `false` on the others, the pin toggle's
  `aria-pressed` idiom. The value is `true` rather than one of the tokens because a chat is none
  of the enumerated kinds, not a page, a step, a location, a date or a time. The entry's eight
  tab stops were right for the list it measured and are eight no longer, the demo having seeded a
  third chat since the row exit landed: the same list offers twelve, four to a row, identical
  before and after in count and in order, with the whole tab cycle at 24 both times.
  `Ctrl+↑` and `Ctrl+↓` needed no reconciliation in the end, being an application-wide cycle and
  not navigation inside a list. Measured, a press changes the chat with focus left where it was
  and closes the switcher, and reopening it puts `aria-current="true"` on the chat the keys
  landed on. What that leaves behind is the entry below: the swap is silent. Three notes for
  whoever measures next. The header's chats button carries the same accessible name as the list,
  which was read in the same pass and deliberately left, the two announcing with different roles.
  jsdom does not reproduce the finding at all, `dom-accessibility-api` mapping `<li>` to
  `listitem` whatever an ancestor claims, so the Vitest suite pins what it can see (no listbox in
  the tree, a named list, a listitem per row, four buttons each at `tabIndex` 0, and
  `aria-current` true on the open row and false on the rest) and the browser is where the `none`
  rows live. And `aria-current` cannot be read back from CDP: its accessibility domain has no
  `current` among its property names, so it was verified per row in the live DOM instead, beside
  roles that did come out of the tree. Putting the role back and taking `aria-current` off each
  make the new test fail, checked in place and restored.

## Trail

- 2026-08-03: Opened by the pass that gave the console's tab strip its keyboard half, which checked
  the overlay's other lists and found one whose gap is a different shape.
- 2026-08-03: Closed the same day by the user's answer, the role coming off. The ledger reads the
  entry as right that this was a decision rather than a defect list and as understating the defect
  twice, in what a `<li>` inside a listbox is announced as and in the channel its "nothing else
  changes" missed.
