# ADR-0035: One console, and how the panel moves

**Status:** Accepted (2026-09-19)

## Context

After [ADR-0034](ADR-0034-panel-views.md) the panel had three views: the chat, settings and a
shortcut sheet. The user chose one tabbed console with theme choices drawn as miniatures of the
panel. Watching the running overlay then turned up motion defects (the reasoning trace appearing in
one frame, the switcher's list flashing back after every close, scrollbars pushing content sideways,
the first message shrinking the panel), each recorded at 60 Hz before it was touched.

This record states how the console is built and the rules the panel's geometry follows. Where the
caret goes and what the overlay announces is
[ADR-0052](ADR-0052-overlay-focus-and-announcements.md).

## Decision

### The console

1. **The panel's other views are one console with a tab strip.** The views are `chat` and `console`,
   and one field, `consoleTab: "appearance" | "shortcuts" | null`, says which tab is up, so Esc
   leaves in one press. The hint strip's sliders button and the empty state's mark open the
   appearance tab, `?` opens the shortcut list, the strip switches with an idempotent `openConsole`,
   and `closeConsole` is the one way out. The tabs are labelled **Face · Chords**, what the console
   shows and what you play on it; the reducer keys stay `appearance` and `shortcuts`.
   - **Face** has three rows of swatches named for what the face has: **Light**, the theme, each
     tile a miniature of the panel drawn from that theme's own tokens (`components/ThemeMini.tsx`),
     with Auto split on the diagonal between the two themes it resolves to; **Iris**, the bubble
     mark, drawn by the real `BubbleMark` at 40px because the styles differ by how they move; and
     **Dream**, the window edge ([ADR-0036](ADR-0036-window-edge.md)). Each row maps over its
     registry, so a new entry appears with no change to the view. A row's note is centred under its
     tiles; the Auto tile has no caption.
   - **Chords** is the binding list in three groups (Ink, Chats, The window), each key its own `<b>`
     cap. Modifiers are written in full; only return and the cycle arrows are drawn. Every cap is a
     flex box no smaller than the widest single key, so keys line up, as in the hint strip.

### The panel's motion

2. **Coming back to the chat restores it.** The chat's held bottom edge is stored when the chat is
   left and restored on return. Entering the console resizes in place on the chat's edge
   ([ADR-0034](ADR-0034-panel-views.md)); `VIEW_CHANGE_RECENTRES` in `overlay/panelEdge.ts` keeps
   the old slide to the centre one flag away, and with it on, the stored edge restores the chat.
3. **Another chat is not another view.** The view name has no session id, so a new or different chat
   resizes from the held edge like any other size change.
4. **The held edge is remembered unclamped, and the ceiling bounds the height, not the edge.**
   `clamped(held)` is `max(0, held)`, so a grow-then-shrink round trip is exactly reversible, and a
   shrink on the ceiling moves neither the panel's bottom edge nor the composer.
5. **The panel follows a section's roll.** `data-morphing` holds the height a section is rolling to,
   so the panel predicts its coming height (now, less the section's, plus the target) and slides
   over the same `MORPH_ROLL_MS` and curve. An ease already in flight continues through the roll
   rather than being cancelled, which handed the height back to layout in one frame.
   `cortex:morphend` stays: measuring again at the end keeps the prediction correct.
6. **A closing roll holds its collapsed height until React removes it**, so the section does not
   repaint at full size before the unmount. An opening roll does not fill.
7. **A move is paced by its distance**: the further edge's travel at one pace, at least 120 ms and
   at most `MAX_DURATION_MS` (380 ms), the full duration reached at 240 px, the panel's longest
   move. A flat 380 ms left it a line behind a streamed reply. The cap is exported because the
   outgoing view's fade in `Panel` is timed to outlast every resize.
8. **A summon centres on what the panel arrives with.** For the summon's 0.44 s transform transition
   every placement centres, including the one that follows a roll, so a section rolling in behind
   the summon leaves the panel centred in one movement; anything later is growth and holds the edge.
   The window is a duration, since a settled-size test cannot tell a finished summon from a pause
   between tokens. It ends at the first `pointerdown`, `keydown` or `click` in the window, heard in
   the capture phase; input while the panel is shut is what summoned it and does not count.
9. **Heights are read transform-free; the bottom edge off the rect.** The panel is scaled through
   every summon, so rect heights read about 8% short. Heights are the used value off the computed
   style (`heightOf`, decision 33); the rect's bottom is exact because `transform-origin` is the
   panel's own bottom edge.
10. **A prediction is capped at the panel's ceiling**, so a roll cannot aim it below the screen.
11. **A render that does not redirect the panel resumes its move.** A placement with the same
    destination animates from where the eye is over the time left, so a line of growth settles 120
    ms after it appeared however many tokens arrive meanwhile.
12. **The chat has a minimum height, the empty state it replaces.** The log's content has a
    `min-height` of `--chat-floor` (decision 35), so the first exchange cannot leave the panel
    shorter than the invitation. The minimum is on the content, so a squeezed history scrolls rather
    than pushing the composer off the panel, and its spare height sits above the bubbles
    (`justify-content: flex-end`), because the auto-scroll ends on space reserved under the last
    one. The example chips hold one row and shrink to an ellipsis, taking width out of the empty
    state.
13. **The live activity chip and the settled Thoughts disclosure are one row in two states**, both
    no shorter than `--trace-row` (decision 35) and swapped in place, so a settling turn keeps its
    size.
14. **A roll announces its start.** `Collapse` dispatches a bubbling `cortex:morphstart` after
    setting `data-morphing`, because a roll inside a message renders nothing above it; that order is
    the contract. The panel reads what it places for from a ref assigned during render, since the
    event arrives inside a layout effect before any passive effect has re-subscribed. The disclosure
    is a button with `aria-expanded` over a `Collapse`, since `<details>` cannot animate. Under
    `prefers-reduced-motion` a roll commits its end state and announces nothing.
15. **Scroll anchoring is off in the history** (`overflow-anchor: none`). Keeping the reader at the
    tail and following a roll (decision 38) decide the position; the engine read a roll as the log
    shrinking.
16. **The ceiling is a whole number of pixels**, because the same number is written to `max-height`
    and predicted against; a fifth of a pixel between the two stepped the bottom edge at each roll.

### The composer

17. **Past one line the composer is two rows**: the field spans the pill and the send button drops
    to its own row, in the same place as before, because a button column down a multi-line pill
    makes every line stop short. The layout is decided at the inline width whatever is on screen
    (`scrollHeight > clientHeight` of a `rows={1}` field at `height: auto`), so it depends on the
    text alone and cannot oscillate; the cost is a band of a few characters where the pill rests
    stacked with one line. The pill transitions named properties, never `all`.
18. **The log holds its tail across the pill's growth.** `Composer` calls `onResize` when the pill's
    height changes and `ChatView` scrolls to the tail if the reader was there; a callback rather
    than a `ResizeObserver` on the log, so a Thoughts roll still leaves `scrollTop` alone. The
    measurement fixes the pill's `min-height` while it runs, or the engine clamps `scrollTop` to the
    shorter reading.
19. **When the column runs out, the draft's window pays, not the panel's edge.** The stacked pill's
    `min-height` is `--pill-floor` (84px: one row of field plus the button's row), the stacked field
    is `flex: 0 1 auto`, and the history is `flex: 1 100000 auto`, a weight that means "shrink
    last". The history yields first, then the sections (decision 34), then the draft's window.
20. **A window that cuts a line fades it, and never on the writer's line.** `mask-image` fades the
    field's padding band at each end and `scroll-padding-block` keeps the caret's line out of it.
    The line box is fixed at 16 px, which the field, the pill minimum and the fade are read off.
21. **The layout decision re-runs on a window resize**, the listener removed on unmount.

### Chrome

22. **A scrollbar is reserved chrome.** All seven scroll regions have one 6 px rail (`--rail`) and
    reserve it (`scrollbar-gutter: stable`), each taking it from its own inline-end padding, so
    overflowing moves nothing. The other axis is closed: text containers break long tokens
    (`overflow-wrap: anywhere`, the streaming word span `pre-wrap`) and `.history` clips it. The
    standards properties are fenced behind `@supports not selector(::-webkit-scrollbar)`, since
    Chromium honours `scrollbar-width` over the pseudo-elements. The arithmetic is in [overlay-ux.md
    §2](../design/overlay-ux.md).
23. **The connection dot and the capture ring open the header's button cluster, and the title takes
    the row**, inset 10 px beyond the header's padding so its left and top clearances are equal.

### Decisions taken since

24. **The console's header is one line**: the back chevron, then the tab strip centred by a spacer
    the chevron's width, on its centre line. The console's foot inset equals its side inset (16px on
    `.rows` plus the 1px border): an inset with a neighbour is read off the neighbour.
25. **Dismissing leaves the console open; the next summon closes it**, since clearing it on dismiss
    morphed the panel under a window already fading. `Panel` holds the last tab in a ref.
26. **Switching tabs is not a view change.** Both tabs share one grid cell and the chrome holds
    still while the content cross-fades. Within `TAB_SPREAD_PX` (15px, `ConsoleView.tsx`) the tabs
    share the taller height; past it the panel resizes as inside any view. The spread is measured
    with the panes unstretched, in a layout effect that runs before the panel's own.
27. **The panel has one bound, the clear space at the top of the screen, applied to its height.**
    `maxHeight(viewport, bottom)` is `0.88v - bottom`, rounded (`MIN_TOP_RATIO` 12%). A placement
    measures under the loosest cap any edge allows (`openHeight`, `0.76v`), works out the edge, then
    applies the real cap, saving every scroll position inside the panel first and restoring it
    after. During a roll the real ceiling is written to the element and during a move it is a
    keyframe beside the height, so neither overshoots; a roll's end placement reads the height
    before the measuring cap goes on.
28. **No scrollbar thumb for a size the panel is only passing through.** `data-resizing` is set
    while the panel's own move runs, and the history's thumb is hidden then and while the aside
    rolls; the thumb and not the overflow, which would freeze the auto-scroll.
29. **The reminder stack is the empty chat's aside.** It rolls away when the first message is sent
    or a chat is opened. `centringHeight` (`overlay/panelParts.ts`) leaves an aside out of the
    height the panel centres on only when it is inside the view being placed, and the prediction
    that follows a roll uses the same function, with the aside at its settled height, bounded at
    `openHeight` before the aside comes off. The bell and the check are centred on a reminder card.
30. **A trip to the console leaves the chat as it was.** `.view.out` sets a `bottom`, so the view
    being left fades inside the panel. `ChatView` stores the log's position on the reader's own
    scrolls and restores it on return, a reader at the tail coming back to the tail. Programmatic
    focus uses `preventScroll`, since the clipped panel is a scroll container the engine can scroll.
31. **A dismiss is not a placement.** The closing panel keeps its geometry while it fades and the
    summon centres for itself; a panel never placed is the exception.
32. **The panel watches its own box** (`overlay/panelWatch.ts`) and places on what it reports, so a
    resize no render reaches (the composer growing a line) is eased too. It answers nothing while a
    section's roll owns the height. During the panel's own ease it asks what the panel would be by
    handing the box back to layout for one read (`height: auto !important` beside the cap), so a
    resize inside a move is answered the next frame. It compares against `Memory.placedFor`, and it
    is lifted for the frame the panel writes in. `cortex:morphend` stays, because a roll ends
    without resizing anything.
33. **Heights keep their sub-pixel fraction end to end.** The panel's height and a roll's target and
    mid-roll reading are all `heightOf`; the bottom edge is written unrounded; `data-morphing`
    publishes the fraction; the whisper bubble publishes `tH.toFixed(1)`, the rounding its box is
    written with ([ADR-0037](ADR-0037-whisper-streaming.md)).
34. **The panel's height is a budget and its sections use what is left.** `overlay/panelBudget.ts`
    writes `--ceiling` beside every `max-height`, which a descendant cannot read. `--reserved` takes
    the fixed parts of the column off the top (2 px of border, the 54 px header, the history's 10 px
    padding, the composer's 11 px and 9 px margins, `--pill-floor`, the 33 px hint strip), so the
    composer and hints stay on the panel. With both sections open the switcher gets four sevenths of
    the rest and the reminder stack three, so each shows fewer rows rather than one showing none;
    alone, a section gets it all. The share caps the roll's frameless wrapper and the card gets the
    share less its padding, so a share of zero costs zero. It reads the roll's target
    (`.view:has(> .collapse.aside:not([data-morphing="0"]))`) and both caps ease over the roll's
    clock while both are open. The two `vh` caps inside the history stay.
35. **The two floors are measured off the elements they copy.** `overlay/measured.ts` publishes
    `--chat-floor` from the empty state's box (a reading on attach, then a watch, since the chips
    settle once fonts resolve) and `--trace-row` from the live chip's box. Nothing is rendered for
    the probe, neither reading can feed itself, and `:root` keeps 185px and 24px for when nothing
    was measured. The empty state does not scroll: `.log.bare` shrinks, centres and clips.
36. **A row leaves on its own roll, and the write does not wait for it.** `overlay/usePresence.ts`
    keeps an item that left the caller's list rendered, marked `leaving`, until its `Collapse` calls
    `onClosed`, after the `cortex:morphend` dispatch; the ack or delete goes upstream at once. Its
    memory of the last commit is written in a layout effect, so a render stays pure under
    `StrictMode`. A leaving row returns under the row it was under (its key, the index as fallback).
    Each `<li>` sits outside the roll, so the lists stay lists. Rows do not roll in.
37. **The switcher's empty line waits for the row it replaces, and a moved row travels.** The line
    is asked of `sessions`, renders below the rows and grows in over the last row's roll
    (`Collapse`'s `enter`, read once at mount); it goes in the frame a chat arrives. A reorder plays
    through `overlay/useTravel.ts`: each row, remembered by its element, decays a `translateY` over
    the roll's clock, composed when interrupted; during a roll the record refreshes each frame and
    only a commit animates.
38. **The log follows a roll.** While the reader is at the tail (read off the box on the roll's
    first frame), `overlay/logRoll.ts` keeps the distance from the end of the content constant on
    every frame, both ways, with no clock of its own. A reader scrolled up is left alone and any
    other movement stops it. For a section inside the log it stops when the section's top reaches
    the window's top. `useLogScroll` listens on the chat's column, so rolls in the chrome count.
39. **Chrome details.** The send button's hover lifts the arrow 3px over 0.28s while the cap holds;
    streaming, the stop turns `--halt` red (as the row's trash does) and its square eases to 0.84. A
    theme change sets `data-swapping` before the tokens, one transition on everything for
    `THEME_SWAP_MS` (400ms), removed on a timer; the theme applied at boot does not cross. A
    switcher row is title and preview, then right to left time, hoist, pencil and trash, the time
    right-aligned in a reserved `--time-col` (55 px).

## Consequences

- The panel's geometry is split by question across `overlay/panel*.ts` (arithmetic, memory, edge,
  parts, roll, watch, budget, placement), with `usePanelMotion` deciding when to place.
- Arrival is detected by three capture-phase listeners that note only that the user is there; a list
  of controls would fall out of date with the chrome and still be wrong about the composer.
- `--pill-floor` was measured on Chromium under Linux and the body renders on WebView2 with Segoe
  UI, so a stacked pill may rest a pixel off there. A squeezed panel shrinks the draft's window and
  a first send shows the spare height above the bubbles; both are deliberate.
- Below a 218 px viewport the column holds only the header, a history and a pill at their minimum
  heights, and the hint strip is clipped. The body's window is 640x720 and does not resize.
- The rail's width is assumed: the padding arithmetic takes the reserved band to be `--rail`, true
  wherever `::-webkit-scrollbar` sets it (Chromium; WebKit's gutter is unmeasured). On an engine
  without it, Gecko in practice, `thin` picks the width and the inline-end margin reads wider, and
  nothing shifts. The switcher and the reminder stack pad by exactly one rail, so the rail is their
  inset, and each row's own padding keeps text 9 px to 11 px clear.
- `--accent` is a gradient, so a colour that asks for it computes to `inherit`. A hoisted chat's toggle
  asks for `--text`; the thinking chip's label and the rename box's border are left asking.

## Alternatives rejected

- **Holding the clamped edge instead** and saving each section's pre-roll edge: it gains nothing the
  unclamped edge does not and leaves the panel on its tallest moment's edge.
- **Composing the follow-the-roll animation additively on `auto`**: Chrome demotes an additive
  `height` animation over `auto` to a replacing one.
- **Stepping the draft's window in whole lines**: a `ResizeObserver` stepping the field in 16 px
  jumps through every roll, where the fade costs no frame. **Retargeting on every frame the box
  watch reports**: 24 animations for one growth instead of 2.

## Related

- [ADR-0033](ADR-0033-panel-growth.md), [ADR-0034](ADR-0034-panel-views.md),
  [ADR-0036](ADR-0036-window-edge.md), [ADR-0037](ADR-0037-whisper-streaming.md),
  [ADR-0052](ADR-0052-overlay-focus-and-announcements.md).
- [overlay-ux.md](../design/overlay-ux.md) §2 and §3 (the design);
  [body-app.md](../modules/body-app.md) (the mechanisms, file by file);
  [panel-motion.md](../readings/panel-motion.md), the measurements decisions 7, 8, 11, 12, 32, 33
  and 34 rest on. `scripts/overlaycouplings.py` compares the names the overlay's TypeScript
  publishes with the ones its CSS uses.
