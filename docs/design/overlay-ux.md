# Overlay UX and visual language

The design reference for the Cortex body overlay ([ADR-0011](../adr/ADR-0011-body-v1.md)). Agents
building or changing overlay components follow it, and a change that departs from it is written here
first. Each numbered decision is argued in the ADR beside it, and the panel's motion was measured in
[panel motion](../readings/panel-motion.md).

## 1. Identity

A sleek assistant you summon with one keystroke and dismiss without thinking about it. **Colour
means activity**, the most important rule here: at rest the overlay is calm and almost monochrome,
frosted glass and plain type with no gradient on resting chrome or on a finished message, and the
accent gradient appears only where work is happening, on a model thinking, text streaming in, the
minimized orb, a progress bar and the Approve button.

Three words, in order: sleek (minimal, precise, never loud at rest), alive (it breathes, streams and
blooms with colour while thinking), bubbly (soft, rounded, springy shapes). Light and dark ship
together, another theme is a token swap, text streams rather than appearing, and all of it respects
`prefers-reduced-motion`.

## 2. Visual language (design tokens)

Everything is a CSS custom property, and a theme change crosses the whole surface at once over
400ms, with one transition put on every element for the length of the change.
- **Two grounds**, selected by `[data-theme]` with `prefers-color-scheme` as the default, both
  frosted glass (`backdrop-filter: blur(28px) saturate(140%)`) over a neutral biased toward the
  accent rather than a pure grey. Dark: `--panel: rgba(18,16,28,0.72)`, `#F3F1FA`, `#A79FC4`,
  hairline `rgba(255,255,255,0.10)`. Light: `--panel: rgba(250,250,253,0.72)`, `#1A1726`, `#6C6880`,
  hairline `rgba(20,16,40,0.10)`.
- **Accent gradient:** `--accent: linear-gradient(135deg, #8B5CF6, #E24BC4 52%, #FF7A6B)`, with a
  mint `--spark: #4FE3D0`. Used only where §1 allows.
- **Bubbles are neutral at rest**, a tint of the ground (`rgba(127,110,190,0.14)` for the user in
  dark), `border-radius: 20px` with one tail corner tightened. Their only colour is the streaming
  mist: no glow, ring or caret.
- **Radius scale:** panel `28px`, bubbles `20px`, input pill `22px`. The orb is the bubble mark
  (§4), an off-round film rather than a disc, so it has no radius.
- **Typography:** one modern sans (the system stack in v1, a licensed face inlined as a `@font-face`
  data URI later). Assistant text about 15px at 1.5 line height.
- **Motion tokens:** `--spring: cubic-bezier(.34,1.56,.64,1)` for shape, `--ease:
  cubic-bezier(.4,0,.2,1)` for fades, `--roll: 300ms` for a section's roll and the two rules that
  move with one; the last two repeat `EASING` and `MORPH_ROLL_MS` from `overlay/morph.ts`, and
  `crosscheck.py` compares the copies. Otherwise micro 120ms, standard 240ms, morph about 360ms.
  Under `prefers-reduced-motion: reduce` all of it collapses to opacity fades of 120ms or less, with
  no travel and the mark held still with no frames scheduled.
- **Scrollbars are resting chrome, never a control**
  ([ADR-0035](../adr/ADR-0035-console-and-motion.md) decision 22): one `--rail: 6px` bar per scroll
  region, a rounded 4px thumb mixed from `--muted` at 38% and 62% under the pointer, no arrows, no
  accent, and **its width reserved whether or not the region scrolls**. Only that axis is reserved,
  so a region showing text it did not write sets `overflow-wrap: anywhere`.

**The window's edge is a choice** ([ADR-0036](../adr/ADR-0036-window-edge.md)), four styles named
for depths of sleep, chosen in the console beside the theme and the mark. **Still** is crisp glass;
**Lucid**, the default, melts the outline with the mark's own arithmetic, using whole wave orders
around the closed perimeter so the shape never tears or drifts; **Reverie** adds a soft glow along
it, accent-coloured while a turn runs; **Trance** widens that glow and keeps a low accent light on
at rest, the one written exception to §1. The animated clip goes on a background-only glass layer,
text never sits on the warping layer, and a liquid panel uses `--panel-solid` rather than a backdrop
blur, which Chromium composites without the clip path.

Five motion signatures:
- **Whispered streaming** ([ADR-0037](../adr/ADR-0037-whisper-streaming.md)). Letters clear through
  a nine-letter band of blur on one continuous front whose speed eases toward its backlog and never
  resets, paced per letter rather than timed. One accent mist breathes where the text will start,
  glides along the front and evaporates at the end, one element for that whole lifecycle and the
  bubble's only colour; the bubble is a pill around it, then grows at the front's pace.
- **Traveling morph.** Minimizing and maximizing glide the panel along a path between the centre and
  the corner while it scales to or from the orb (a FLIP animation).
- **Paced, not timed.** A move takes as long as its distance warrants, at one pace between a 120ms
  floor and a 380ms ceiling, and a render that does not change the destination continues the move
  already running over the time it had left.
- **Arriving centred, then growing upward** ([ADR-0033](../adr/ADR-0033-panel-growth.md),
  [ADR-0034](../adr/ADR-0034-panel-views.md) decision 2). A summon centres the panel on what it
  arrives with, for the length of its own pop. After that it is anchored by its **bottom** edge, so
  nothing resizes the composer under the hand that just typed, and it stops growing at `12vh` of
  clear space. That bound is on the height, not the edge, and the edge is remembered unclamped, so a
  grow-then-shrink round trip returns to it. **The edge nearest the hand holds still**: the bottom
  edge in the chat, the **top** edge elsewhere.
- **Rolling sections.** A section that comes and goes (the switcher list, the reminder stack, a
  Thoughts trace) animates its own height between nothing and its content and stays mounted through
  the close, the panel following it frame by frame. A roll past the panel's ceiling moves the
  panel's bottom edge over the same roll, and one inside the conversation hands its growth to the
  scroll, capped so the trace's top edge stays in the window.
- **A warping bubble.** The orb's mark warps on its own clock while the film turns under a fixed
  highlight, and its anchor does not move: every harmonic is of order two or higher, which fixes the
  centroid and the mean radius ([ADR-0031](../adr/ADR-0031-bubble-mark.md)).

## 3. Anatomy of the panel

1. **Header.** The chat's title starts the row, inset 10px beyond the header's 16px padding, so the
   glyphs sit 27px from the panel's outer edge and 27px from its top; every other view opens with a
   back button, which supplies its own inset. Then outline icon buttons drawn to one vocabulary
   (1.7px round-cap strokes on a 24 grid, `currentColor`, hollow, in `components/icons.tsx` and
   `ThemeIcon.tsx`): the connection indicator, the capture ring, a chat switcher lit while open
   through `aria-expanded`, a theme toggle that morphs a sun into a crescent rather than swapping
   glyphs, new chat, and dismiss as a downward chevron, because dismissing only hides. The indicator
   is a 7px dot, green when the brain replied ready, amber when it replied and is not serving, red
   when nothing replied and neutral before anything was asked, pulsing on its last colour while a
   probe is out; its label is the tooltip and the accessible name, and its three colours are the
   only colour that is not activity. The capture ring has two steps that differ by addition only, an
   open ring for the assistant asking to look and a pupil for the body replying that the screen was
   read, and it never weakens (ADR-0029 decision 18).
2. **History.** The conversation scrolls, newest at the bottom, following the stream unless the user
   has scrolled up. Tool activity and status are slim inline chips between bubbles, not bubbles: a
   neutral pill with a pulsing accent dot above the streaming bubble, and `chip-think` for a
   `thinking` status. The approval card (§4) also renders there. The empty state is the mark, "Ask
   me anything" and example prompts as chips, the mark opening the appearance tab. Two floors keep a
   running turn from shrinking the panel ([ADR-0035](../adr/ADR-0035-console-and-motion.md)
   decisions 12, 13 and 35): the empty state publishes its height as `--chat-floor` and the bubbles
   keep at least that height, the chips staying on one row; and the live chip and the collapsed
   Thoughts disclosure that replaces it are one row in two states. That disclosure is a button over
   a rolling section, not a `<details>`.
3. **Composer.** A rounded pill textarea: `Enter` sends, `Shift+Enter` inserts a newline, the field
   grows to a 120px ceiling, focus arrives here on summon. It has an accent focus ring and a
   gradient **send** button (an outline up-arrow) that springs on press, whose gradient fades in as
   the field gains content; on hover the arrow rises 3px, the cap does not move, and the glyph stays
   white, which is what makes it legible on the gradient. **While streaming the button is a stop**,
   a filled square that cancels the turn and turns red (`--halt`) on hover, the only hover that
   changes hue; it drops the bridge stream and ends the reply in place, keeping the partial text.
   Three rules hold the pill together as it grows (same ADR, decisions 17, 19 and 20): past one line
   the field spans the pill and the button drops to its own row beneath, in the same corner of the
   same content box, with the layout decided at the inline width; a pill with nowhere left to grow
   scrolls its own window; and a window that cuts a line fades it, in the field's 9px padding.
4. **Hint strip.** A dimmed, centred one-line footer of the live shortcuts (§6), its key glyphs the
   header's outline icons, with two openers at its end, a sliders button and a `?`, each arriving on
   the console tab it names.

## 4. The interaction state machine

The overlay is a small explicit state machine over four states, HIDDEN, PANEL (composing, streaming
or done), ORB and PREVIEW. A summon opens the panel and a submit starts streaming; a dismiss while
idle hides it and a dismiss while streaming minimizes it to the orb, which a click or the hotkey
opens again; a turn completing while minimized opens the preview, which a click takes to PANEL(done)
and its own countdown takes to HIDDEN. Its signature behaviour is that dismissing the panel while a
turn is running must not lose the turn.

- **PANEL** is the full centred panel, almost monochrome except while streaming, where the whisper
  of §2 is the only colour. **Dismissing while idle** springs it out at the centre, a scale and fade
  with no corner travel, and summon pops in the same way; nothing is lost, since the chat is stored.
  **Dismissing while streaming** (Esc or a click away) scales and glides it to a corner,
  bottom-right by default, in one transform the reverse travels back.
- **ORB(thinking)** is the bubble mark at the corner, about 64px
  ([ADR-0031](../adr/ADR-0031-bubble-mark.md)): an off-round film lit from the upper left by a light
  that never moves, with the eight-stop gradient `#43d675 #ffb347 #ff5f6d #e055d8 #3fa2ff
  #6a5cff #c44fd8 #ffd23f` stroked thickly just inside the rim, over a soft bloom. Clicking it
  morphs back to PANEL(streaming) at the point the turn has reached. **Which bubble is a choice**,
  the four named as movements of thought: **Mull** (two slow modes turn the outline over; the
  default), **Muse** (near circular, drifting under a calm surface), **Hunch** (still, until a
  ripple strikes the rim) and **Tangent** (two side thoughts on slow arcs). Each is stored under a
  key matching its label, the keys they first used (wobble, sheen, ping, foam) remain as aliases,
  and all four are data in `mark/marks.ts`.
- **CONSOLE** is the panel's one other face: everything that is not the conversation, behind a
  chevron back to the chat and a tab strip, which Esc leaves in one press. **Face** is the
  appearance tab ([ADR-0032](../adr/ADR-0032-preference-record.md)), three rows of swatches, each
  named for what it varies and each choice made by looking rather than reading: **Light** is the
  theme as miniatures of the panel drawn from its own tokens, with **Auto** split diagonally between
  the two it resolves to; **Iris** is the mark as tiles drawing the real bubble at 40px; **Dream**
  is the window edge as portraits of that window gone liquid. Every row maps over its registry and
  every choice is stored in the brain's settings record. **Chords** is the complete list of key
  bindings, grouped (Ink, Chats, The window), each key its own cap. Selection anywhere in the
  console is a lift, never an accent.
- **Switching console tabs is the panel's one morph**: it resizes downward from a held top edge and
  crosses as a pure fade, while a change between the chat and the console keeps the small rise and
  sink. **Focus travels with the view** and **what is hidden is unreachable**
  ([ADR-0052](../adr/ADR-0052-overlay-focus-and-announcements.md) decisions 4 to 7): the strip is
  one tab stop where the horizontal arrows wrap and selection follows focus, focus returns to the
  composer with its draft and caret, and anything off screen leaves the tab order in the same frame
  it leaves the accessibility tree.
- **PREVIEW.** A turn completing while minimized expands the orb into a compact card near the
  corner: the answer clamped to a few lines, a hairline accent bar counting down the automatic
  dismiss of about 6s, and nothing else. Hovering pauses the timer itself and leaving restarts the
  full countdown, with the bar remounting in step. Clicking morphs to PANEL(done); ignoring it fades
  to HIDDEN, still stored, and a failed turn previews as a red-tinted card that does not fade on its
  own. **The card always uses Lucid**, because it is the one surface that arrives unbidden.

**The approval card** ([ADR-0022](../adr/ADR-0022-email-write-confirmer.md)). A tool call that sends
something out or cannot be undone pauses its turn until the user approves it. The card renders in
the history's inline layer below the streaming bubble, neutral like the rest of the resting chrome:
an outline shield, the tool name, the draft's fields as verbatim key and value lines (or the raw
JSON string when the arguments are not one JSON object, since what you approve is what runs), the
brain's reason line, and **Deny** and **Approve**. Approve takes the accent gradient because it runs
the action. Everything else denies by construction: dismissing, stopping the turn, switching chats
or walking away all drop the question, and the brain denies on its own timeout. A confirmation while
minimized raises the preview, which does not fade while it is open.

**v1 window scope.** The state machine ships inside a fixed, frameless, opaque, always-on-top window
of 640x720, centred, and every animation plays inside it. Three moves at the level of the OS window
are deferred to one later pass: a transparent window with click-through on the empty margins,
morphing the window to a true screen corner, and hiding on blur, replaced for now by the hotkey
([body-overlay](../runbooks/body-overlay.md) has the bring-up).

## 5. Chats, history and sessions

**A chat is a session.** Each chat maps to a `session_id` and the brain stores that session's
messages through `SessionStore`, so history survives a model swap and an app restart; the overlay is
a view of stored state and never the owner of it. **New chat** (the pencil or `Ctrl+N`) mints a
fresh `session_id` and clears the panel to the empty state, and **cycling** (`Ctrl+↑` and `Ctrl+↓`)
moves through recent chats, newest first. The switcher opens a slim list of titles, relative
timestamps and a one-line preview, each title taken from its first user message.

**A row** runs title and preview on the left, then right to left: the time, the `pinned` toggle, the
pencil, the trash, the three controls revealed on hover in the order they escalate. The time sits
11px inside the row's right edge, which is what the title sits inside its left, and its width is
reserved at 55px, right-aligned, so the column stays still as the clock runs.

Listing chats and loading their history use the read-only `ListSessions` and `GetSessionMessages`
RPCs ([ADR-0021](../adr/ADR-0021-session-read-seam.md)). `useOverlay` owns the `session_id`, loads
the list on mount and after each turn, and loads a history on select or cycle.

## 6. Keyboard shortcuts

| Keys | Action |
|---|---|
| `Ctrl+Alt+Space` (configurable) | Summon or focus the overlay |
| `Enter` | Send |
| `Shift+Enter` | Newline |
| `Esc` | Leave the console (one press, whichever tab), else dismiss (to the orb while streaming) |
| `Ctrl+N` | New chat |
| `Ctrl+↑` / `Ctrl+↓` | Previous or next chat |
| `Ctrl+K` | Chat switcher (a command palette is later) |
| `click orb` | Reopen the minimized turn |
| `?` | The console's shortcut list |

The hint strip shows the common subset, minus `Esc`, for which it has no room; the console's
shortcut tab is the complete list, stating both halves of what Esc does in the order the panel tries
them. Both surfaces draw a chord as the keys it is, one cap each, and **every cap is at least as
wide and as tall as the widest and tallest single key**, a minimum, so the named keys keep their own
widths and a row of caps lines up.

## 7. Accessibility and restraint

**Reduced motion** means no morphs or springs, only quick opacity fades; the orb still shows, held
at a still pose with no frames scheduled, and a liquid edge holds one pose per state. **Focus** goes
to the composer on summon and on every return to the chat view, and to the tab the console is
showing; it stays inside the panel and its rings stay visible. **Contrast:** text on glass and on
the gradient must clear WCAG AA. The orb and the preview never take focus from the app the user is
in, and stay small, corner-placed and dismissible. Sound is off by default.

## 8. How it maps to the architecture

Components depend on the `BrainBridge` port (`src/bridge/types.ts`) and never on Tauri directly
([ADR-0011](../adr/ADR-0011-body-v1.md) decision 6), so the whole interface runs in a browser
against a fake bridge for development and tests. The turn stream folds through the pure
`overlayState` reducer, which visibility mode, per-chat history and multiple chats extend, so the
state logic stays fully tested while animation lives in CSS.

## 9. Open questions

**Sound:** a soft completion chime as an opt-in later, or never? Still open. **Corner:** the orb
and preview default to bottom-right and are configurable, a real choice only once the window morph
of §4 is done, which is host work ([docs/host/](../host/index.md)).
