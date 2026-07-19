# Overlay UX & visual language

The design source of truth for the Cortex body overlay (Slice 8, [ADR-0011](../adr/ADR-0011-body-v1.md)).
Agents building or changing overlay components follow this; deviations need a note here first.
It describes the **target** experience and marks what ships in v1 vs. what waits on the seam.

## 1. Identity and what it should feel like

A **sleek, modern** assistant you summon in a keystroke and dismiss without a thought. One that
**comes alive with color while it works**.

**The core rule: color is the signal of *activity*.** At rest the overlay is calm and
near-monochrome: a clean glass surface, restrained type, one quiet chosen neutral, no gradients on
resting chrome or composed messages. **Color (the accent gradient) is reserved for *working*
affordances**: a model thinking, text streaming in, the minimized orb, progress. So "the assistant
is alive / doing something" reads at a glance, and the resting UI stays modern and out of the way.

Three adjectives, in priority order: **sleek** (minimal, precise, current, never loud at rest),
**alive** (it breathes, streams fluidly, and *blooms* with color while thinking), **bubbly** (soft,
rounded, springy shapes and motion, friendly and never sharp). It ships **light and dark** from day
one and is **theme-customizable** later (a token swap). It is an *overlay*, not an app: fast to
summon, effortless to dismiss, and it never nags. Motion is fluid and purposeful: text *streams* in
rather than popping, the panel *travels* when it minimizes/maximizes, and the orb's bubble *warps*
as its film turns under the light. All of it respects `prefers-reduced-motion`.

## 2. Visual language (design tokens)

Everything is CSS custom properties, so the whole surface restyles from one place and a theme
is a token swap, not a rewrite.

- **Two grounds, light and dark, both sleek** (mandatory in v1). Switched by `[data-theme]` (with
  `prefers-color-scheme` as the default). Both are frosted glass with `backdrop-filter: blur(28px)
  saturate(140%)`, over a *chosen* neutral biased a hair toward the accent, never a pure grey:
  - Dark: `--panel: rgba(18,16,28,0.72)`, text `#F3F1FA`, muted lavender-grey `#A79FC4`, hairline
    `rgba(255,255,255,0.10)`.
  - Light: `--panel: rgba(250,250,253,0.72)`, text `#1A1726`, muted cool-grey `#6C6880`, hairline
    `rgba(20,16,40,0.10)`.
  - **Custom themes are a later token-swap** (user-defined `--panel`/`--text`/`--accent` sets).
- **Accent gradient (activity only).** `--accent: linear-gradient(135deg, #8B5CF6, #E24BC4 52%,
  #FF7A6B)` plus a mint spark `--spark: #4FE3D0`. It appears **only** on *working* affordances: the
  thinking dots, the streaming caret and a faint reveal shimmer on incoming text, the minimized
  orb, and progress bars. It **never** touches resting chrome, buttons, or composed messages, the
  single most important rule (see §1). Exact hues are provisional; keep it a warm-leaning gradient.
- **Bubbles (neutral at rest).** Both user and assistant bubbles use a quiet raised neutral fill
  (a subtle tint of the ground, e.g. `rgba(127,110,190,0.14)` for the user in dark). The **only**
  color is *transient*: while a reply streams, a soft accent glow/shimmer rides the in-progress
  bubble, then settles to neutral on completion. `border-radius: 20px`, one tail corner tightened.
- **Radius scale:** panel `28px`, bubbles `20px`, input pill `22px`; the orb is the bubble mark
  (§4), an off-round film rather than a disc, so it has no radius of its own. Generous, uniform.
- **Typography:** a clean modern sans for everything (system stack in v1; a licensed sans inlined
  as a `@font-face` data URI later; no CDN). Assistant text ~15px/1.5, never cramped. Sleek, not
  decorative. The personality is in motion + the color bloom, not a novelty face.
- **Motion:** `--spring: cubic-bezier(.34,1.56,.64,1)` for shape; `--ease: cubic-bezier(.4,0,.2,1)`
  for fades. Three signatures, detailed in §4:
  - **Fluid streaming**. Each incoming token *fades and rises* into place (opacity + a few px +
    a brief blur), never a pop. The stream feels like it flows.
  - **Traveling morph**. Minimize/maximize animate real *movement*: the panel glides along a path
    between center and the corner while it scales to/from the orb (FLIP), so you see it travel.
  - **A warping bubble**. The orb's mark is a soap bubble whose outline warps on its own clock
    while the film turns under a fixed highlight; the anchor point holds rock still (no breathing
    scale, no positional drift, per 2026-07-03 user refinements), so it reads as alive without
    wandering. The stillness is structural, not a rule to remember: every harmonic is of order two
    or higher, which fixes the centroid and the mean radius (§4, ADR-0031).
  - Durations: micro 120ms, standard 240ms, morph ~360ms. `prefers-reduced-motion: reduce` →
    collapse to ≤120ms opacity fades, no travel, the mark frozen at a still pose with no
    animation frames scheduled at all.

## 3. Anatomy of the panel

Top-to-bottom, the summoned panel is:

1. **Header** is the current chat's title (auto-derived from its first message; "New chat" until
   then) and a set of **outline icon buttons that share one vocabulary** (1.7px round-cap strokes
   on a 24 grid, `currentColor`, hollow, in `components/icons.tsx` + `ThemeIcon.tsx`; 2026-07-07
   revision): a **chat-switcher** (two speech bubbles) opening the recent-chats list, lit while
   open (`aria-expanded`); the **theme toggle** (an outline sun that *morphs* into an outline
   crescent, as the two forms cross-fade and spin, the rays retract; never a glyph swap); a **new
   chat** (pencil for "compose a new one"); and **dismiss** (a downward "tuck-away" chevron, since
   dismissing only hides; the chat is saved and re-summoning restores it, so the glyph tells the
   truth, not an `×`). A **connection indicator** leads the row (landed 2026-07-16): a 7px dot,
   green when the brain answered ready, **amber when it answered and is not serving** (a non-OK
   status, an unreadable reply, or a future not-ready health reply), red when nothing answered,
   and neutral before anything has been asked. While a probe is out it keeps the last known
   colour and pulses, so a reconnect neither flashes green nor forgets it was red; a routine
   probe on a healthy link does not pulse at all. Its label is both the tooltip and the
   accessible name, because a colour alone explains nothing. v1 shipped this as an always-green
   decoration and the 2026-07-03 pass removed it: chrome earns its place by meaning something,
   and the difference now is that the signal is real (ADR-0011 addendum: derived from the turn's
   own events, a probe per summon, and a recovery re-check only while an unhealthy link is on
   screen, never a poll on a timer). The three status hues come from the mark's own palette,
   deepened in the light theme; they are the only colour in the overlay that is not activity.
2. **History** is the scrollable conversation: alternating user/assistant bubbles, newest at the
   bottom, auto-scrolling as tokens stream (but *not* if the user has scrolled up to read;
   landed 2026-07-12). Tool-activity and status appear as slim inline chips between bubbles
   ("📧 reading inbox…", "swapping model…"), not as bubbles (landed 2026-07-12: a neutral pill
   with a pulsing accent dot, above the streaming bubble, gone on completion). A `"thinking"`
   status chip reads distinctly (landed 2026-07-13: `chip-think`, the dot carrying the reasoning
   bob and the label the accent, so deliberation is not mistaken for tool action). The **approval
   card** (§4, ADR-0022) is this inline layer's first real occupant. Empty state: the mark +
   "Ask me anything" + a couple of example prompts as tappable chips (landed 2026-07-12). The
   mark here is also the **mark picker** (§4, ADR-0031): clicking it opens the bubble styles,
   drawn live, and choosing one applies to the empty state and the orb at once.
3. **Composer** is a rounded pill textarea (`⏎` sends, `⇧⏎` newlines, auto-grows to a few lines;
   grow + focus-on-summon landed 2026-07-12),
   a glowing accent focus ring when active, and a gradient **send** button (an outline up-arrow,
   `components/icons.tsx`) that springs on press; its gradient **fades in** as the field gains
   content (an opacity overlay, since gradients can't interpolate, and a hard swap pops). **While
   streaming the button is a real stop** (a filled square, lit): it cancels the turn. A `stop`
   reducer action drops the bridge stream and ends the reply in place, keeping the partial text
   (distinct from dismiss, which minimizes to the orb). Landed 2026-07-07.
4. **Hint strip** is a subtle one-line footer of the live shortcuts (§6), dimmed and **centered**,
   with a `?` that opens the full shortcut sheet (landed 2026-07-12; the `?` key works too,
   outside the composer, and Esc closes the sheet before it dismisses the panel). The sheet is
   not frosted: the panel's own backdrop-filter bounds the backdrop root, so a child's blur
   cannot reach the history beneath it, and the sheet layers the panel tint over the solid
   ground instead. The kbd glyphs are outline icons matching the
   header set (return / shift / cycle chevrons), not raw Unicode symbols (2026-07-07).

## 4. The interaction state machine (the heart)

The overlay is a small, explicit state machine. The **user's signature behavior** (*dismissing
while a turn is processing must not lose it*) lives here. States:

```
        summon (hotkey)                     submit
 HIDDEN ───────────────▶ PANEL(composing) ─────────▶ PANEL(streaming)
   ▲                          │  ▲                      │        │
   │ dismiss (idle)           │  │ click orb / hotkey   │        │ complete/failed
   └──────────────────────────┘  └───────────┬─────────┘        ▼
                              dismiss (Esc / click-away) │   PANEL(done)
                                    while streaming ─────┘        │ dismiss (idle)
                                          │                       ▼
                                          ▼                    HIDDEN
                                   ORB(thinking) ──complete──▶ PREVIEW ──auto (Ns)──▶ HIDDEN
                                          ▲                       │
                                          └──── click ────────────┘ (→ PANEL(done))
```

- **PANEL(composing / streaming / done):** the full centered panel, sleek and near-monochrome at
  rest (composing/done). **Streaming** is where color blooms: a "thinking" shimmer holds the
  assistant bubble until the first token, then tokens **flow in fluidly** (fade + rise, never a
  pop) behind an accent caret, with a soft accent glow on the in-progress bubble that settles back
  to neutral on completion.
- **Dismiss while idle** (composing or done): the panel springs out **at center** (a scale-fade,
  no corner travel, per 2026-07-03 user direction; summon pops in from center the same way) →
  **HIDDEN**. Nothing is lost, because the chat is persisted; re-summoning restores it. The corner
  travel is reserved for the orb morph below.
- **Dismiss while streaming** (Esc or click-away): the panel **morphs**, scaling and gliding down
  to a corner (default **bottom-right**, configurable), shedding its chrome, into a small **ORB**.
  This is one continuous transform (FLIP-style), not a disappear-then-appear, and the reverse
  (maximize) *travels* it back from the corner to center. You always **see it move**, both ways.
- **ORB(thinking):** the **bubble mark** at the corner (~64px; replaced the living rings
  2026-07-19, ADR-0031, because concentric turning rings read as another product's identity). It
  is a soap bubble: an off-round film, lit from the upper left by a light that never moves, with
  the **same eight-stop gradient** the rings carried (the user's palette is one gradient, not two
  arcs: `#43d675 #ffb347 #ff5f6d #e055d8 #3fa2ff #6a5cff #c44fd8 #ffd23f`) stroked thickly just
  inside the rim, where a real film thins and colors, over a soft bloom. Its outline is a circle
  modulated by sine harmonics, all of order two or higher, so the **centroid and the mean radius
  are fixed by the maths**: no breathing scale, no positional drift, the anchor holds still while
  the shape moves. Under reduced motion the mark freezes at a still pose and schedules no frames.
  It reads as alive, not a static badge, and means "still working." **Click** it → morph back to
  **PANEL(streaming)** (the in-progress turn, right where it is). It never covers active work,
  thanks to small, corner-pinned, click-through-safe margins.
- **Which bubble is a choice** (ADR-0031). Four styles ship: **Wobble** (two slow modes roll the
  outline; the default), **Sheen** (near circular, the film crawling underneath), **Ping** (still,
  then a ripple runs the rim and decays), **Foam** (three lobes jostling as one). They are data in
  a registry (`mark/marks.ts`), the twin of the theme registry, so a fifth is a literal and no
  code. The picker is the empty state's own mark: clicking it opens the styles drawn live, rather
  than adding a fifth header button that would put the accent palette on resting chrome.
- **PREVIEW:** when the turn **completes while minimized**, the orb **expands** into a compact
  card near the corner: the answer (a few-line clamp) and a hairline accent progress bar
  counting down the auto-dismiss (~6s) and **nothing else** (the "reply ready"/"click to open"
  captions and then the mini mark were removed 2026-07-03 as redundant: the card appearing *is*
  the signal, and the draining bar says it will go). **Hover pauses** the countdown (landed
  2026-07-12: the fade timer itself pauses, not just the bar; leaving restarts the full
  countdown rather than resuming, with the drain bar remounting in step, so what the bar shows
  always matches the timer); **click**
  morphs to **PANEL(done)** (full answer in context); ignore it and it **fades out** → HIDDEN
  (still persisted). A failed turn previews as a soft error card (same shape, red-tinted) that
  does *not* auto-fade, because errors wait to be seen.
- Re-summoning the hotkey from HIDDEN always returns to **PANEL** on the current chat.

This gives the "fire it, keep working, glance when it pings me" flow the maintainer asked for, and it
is coherent with the hard rule: dismissing is purely a *view* change. The turn keeps streaming to
the store, so nothing depends on the window staying open.

**The approval card (Slice 8.8, [ADR-0022](../adr/ADR-0022-email-write-confirmer.md)).** A gated
(outbound/irreversible) tool call pauses its turn mid-stream on the user's explicit approval; the
card is that question. It renders in the **history's inline layer** (below the streaming bubble),
neutral like the rest of the resting chrome: an outline shield + the tool name, the draft's
fields as **verbatim** key→value lines (falling back to the raw JSON string if the arguments
aren't one JSON object, since what you approve is what runs, so nothing is prettified away), the
brain's reason line, and **Deny / Approve**. Approve is the one place the accent gradient
appears. It is the working affordance that runs the action; Deny stays neutral. Semantics:
**Approve** sends the answer back over the turn's stream and the tool runs; **Deny** returns a
user-declined result the model relays; either way the card leaves immediately (a second click is
a no-op). Everything else is a deny by **fail-closed** construction: dismissing, stopping the
turn, switching chats, or simply walking away all drop or abandon the question, and the brain
denies on its own timeout. **A question the brain has closed leaves the screen too**: when it
stops waiting (its timeout, or its input stream ending) it says so, and the card goes without
waiting for the turn to end, because a card that can no longer be answered is a lie and a click
on it would look like it did something. The explanation is the reply itself, which resumes
saying the action was not performed; the card does not linger to repeat it. Nothing ever runs without an explicit Approve. Two rules carry over
from the machine above: a confirm arriving **while minimized** surfaces the preview exactly like
a completed turn, but the preview **does not auto-fade** while the question is open ("errors wait
to be seen" extends to questions, so the countdown starts once it resolves); and only a **live**
turn can raise the card. A cancelled turn's late request changes nothing.

**v1 window scope (Slice 8).** This whole state machine ships in v1, but it runs *inside* a fixed,
frameless, **opaque** always-on-top window (640×720, centered): the panel/orb/preview live within
that window and every morph/drift/preview animation plays there. The **OS-window-level** moves are
deferred to a later overlay-polish pass, to be done together: a **transparent** window so only the
panel floats over the desktop (a first pass bled through the panel and left a window border, so it
waits to be done properly with **click-through** on the empty margins), morphing the window to a
true *screen* corner (v1's orb sits at the window's own corner), and **hide-on-blur** (v1 toggles
with the hotkey instead). Host bring-up and the running list of these deferrals live in
[body-overlay.md](../runbooks/body-overlay.md).

## 5. Chats, history, and sessions

**A chat is a session.** Each chat maps to a `session_id`; the brain persists that session's
messages (`SessionStore`, the hard rule), so history is durable and survives model swaps and app
restarts. The overlay is a *view* of store-backed state, never the user of it.

- **New chat** (＋ / `Ctrl+N`): mint a fresh `session_id`, clear the panel to the empty state. The
  previous chat is already saved.
- **Cycle chats** (`Ctrl+↑` / `Ctrl+↓`): move through recent chats, newest first; the switcher (⌄)
  opens a slim list with titles + relative timestamps + a one-line preview. Selecting loads that
  chat's history.
- **Titles:** derived from the first user message (later: a brain-generated summary title).

**Seam dependency delivered in [Slice 8.7](../ROADMAP.md) ([ADR-0021](../adr/ADR-0021-session-read-seam.md)).**
Listing chats and loading a chat's history require the brain to expose session data over the
seam. That landed:
- **v1 (Slice 8):** the overlay kept the **current app run's** chats + history in memory.
- **Now (Slice 8.7):** read-only `ListSessions` + `GetSessionMessages` RPCs feed the
  `BrainBridge` (`listSessions`/`sessionMessages`); `useOverlay` owns the `session_id` (minted per
  new chat), loads the list on mount + after each turn, and loads a chat's history on
  select/cycle. The chat list, the switcher (`⌄` / `Ctrl+K`), and `Ctrl+↑/↓` cycling are
  store-backed and survive restarts. **Cold start opens a new chat**; prior chats are reachable
  via the switcher and cycling (auto-restoring the most-recent chat on launch is a recorded
  deferral). Titles are still derived from the first user message (brain-generated summary
  titles remain a later refinement, deferred).

## 6. Keyboard shortcuts

Keyboard-first; the hint strip shows the contextually-relevant subset, `?` shows all.

| Keys | Action |
|---|---|
| `Ctrl+Alt+Space` (configurable) | Summon / focus the overlay |
| `Enter` | Send |
| `Shift+Enter` | Newline |
| `Esc` | Dismiss (→ orb if a turn is streaming; else hide) |
| `Ctrl+N` | New chat |
| `Ctrl+↑` / `Ctrl+↓` | Previous / next chat |
| `Ctrl+K` | Chat switcher / command palette (palette is later) |
| `click orb` | Reopen the minimized turn |
| `?` | Shortcut sheet |

## 7. Accessibility & restraint

- **Reduced motion:** honor `prefers-reduced-motion` with no morphs/springs, just quick opacity
  fades; the orb still shows, its bubble held at a still pose (no frames scheduled at all).
- **Focus:** the composer is focused on summon; focus is trapped in the panel; visible focus rings.
- **Contrast:** text on glass/gradient must clear WCAG AA. Verify bubble text over the accent.
- **Non-intrusive:** the orb/preview never steal focus from the app the user is using and stay
  out of the way (corner-pinned, small, dismissible). Sound is off by default.

## 8. How it maps to the architecture

- Components depend on the **`BrainBridge` port** (`src/bridge/types.ts`), never on Tauri directly
  (ADR-0011 addendum), so the whole UX runs in a browser against a fake bridge for dev + tests.
- The turn stream folds through the pure **`overlayState` reducer**; this design's broader machine
  (visibility mode + per-chat history + multi-chat) extends that pure core, so state logic stays
  100%-tested while animation lives in CSS (no JS branches to leave uncovered).
- `session_id` is the chat identity; new-chat/cycle operate on it; history is store-backed.

## 9. Decisions this design left to the user

Four of the five are settled; the list is kept whole so the reasoning is not lost. Host work that
is still outstanding lives in [docs/host/](../host/index.md).

- **Corner** for the minimized orb/preview defaults to bottom-right; top-right if the taskbar area
  is busy. (Configurable.) *Not decidable yet:* v1's orb sits at the fixed window's own corner, so
  this becomes a real choice only with the deferred window morph in section 4, and it is folded
  into that host-side pass.
- **Auto-dismiss timing** for the completed preview (default ~6s; hover-to-pause). *Settled
  2026-07-12:* the default and hover-to-pause both shipped, and the preview does not auto-fade
  while a confirm question is open.
- **Theme:** ship dark-glass only in v1, or also a light theme token set now? *Settled 2026-07-03:*
  both themes ship, with the toggle in the panel header.
- **Palette:** the violet→fuchsia→cyan accent is a starting proposal. Lock the exact hues.
  *Settled 2026-07-03:* locked to the user's one eight-stop gradient, which the connection dot's
  `ok`/`warn`/`bad` trio later drew from.
- **Sound:** a soft completion chime as an opt-in later, or never? *Still open*, and the only line
  here that is.
