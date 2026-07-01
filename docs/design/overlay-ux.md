# Overlay UX & visual language

The design source of truth for the Cortex body overlay (Slice 8, [ADR-0011](../adr/ADR-0011-body-v1.md)).
Agents building or changing overlay components follow this; deviations need a note here first.
It describes the **target** experience and marks what ships in v1 vs. what waits on the seam.

## 1. Identity and what it should feel like

A friendly, *alive*, colorful assistant you summon in a keystroke and dismiss without a thought.
Three adjectives drive every choice: **bubbly** (soft, rounded, and springy, never sharp or
static), **alive** (it breathes, streams, and reacts; the "thinking" state feels present, not a
spinner), and **colorful** (a vibrant accent gradient is the brand and never a flat grey box). It
should read like the best modern LLM UIs: glassy panel, gradient accents, springy motion, gentle
token reveals. But it is an *overlay* and not a full app, fast to summon, effortless to dismiss, and
it never nags. Motion is generous but quick; it always respects `prefers-reduced-motion`.

## 2. Visual language (design tokens)

Implement as CSS custom properties so the whole surface restyles from one place.

- **Accent gradient** (the signature): a 3-stop violet→fuchsia diagonal,
  `--accent: linear-gradient(135deg, #7C5CFF 0%, #C15CFF 45%, #FF6AD5 100%)`, with a cyan spark
  `#5CE1FF` reserved for the "alive"/thinking accents. Tune freely, but keep it a *gradient*.
- **Surface:** frosted dark glass via `--panel: rgba(20, 18, 34, 0.72)` over a `backdrop-filter:
  blur(24px) saturate(140%)`, with a 1px gradient-tinted border and a soft outer glow
  (`box-shadow` in the accent hue at low alpha). A light theme is a later token swap, not a v1 need.
- **Bubbles:** user = accent-gradient fill, white text, right-aligned; assistant = translucent
  neutral glass (`rgba(255,255,255,0.06)`), left-aligned. Both `border-radius: 20px` with one
  "tail" corner tightened (16px → 6px) so they read as speech bubbles.
- **Radius scale:** panel `28px`, bubbles `20px`, input pill `22px`, orb `50%`. Generous, uniform.
- **Typography:** system UI stack; assistant text ~15px/1.5; a slightly rounded display face for
  the header/title if available (fallback to system). Never cramped (line-height ≥ 1.5).
- **Motion tokens:** `--spring: cubic-bezier(.34,1.56,.64,1)` (the bouncy one) for
  entrances/morphs; `--ease: cubic-bezier(.4,0,.2,1)` for fades. Durations: micro 120ms,
  standard 220ms, morph 320ms. Under `prefers-reduced-motion: reduce`, collapse all of these to a
  ≤120ms opacity fade and drop transforms.

## 3. Anatomy of the panel

Top-to-bottom, the summoned panel is:

1. **Header** is the current chat's title (auto-derived from its first message; "New chat" until
   then), a small **connection dot** (green = brain ready, amber = model loading/status, red =
   unreachable), a **＋ new chat** button, and a **chat switcher** affordance (⌄) opening the list.
2. **History** is the scrollable conversation: alternating user/assistant bubbles, newest at the
   bottom, auto-scrolling as tokens stream (but *not* if the user has scrolled up to read).
   Tool-activity and status appear as slim inline chips between bubbles ("📧 reading inbox…",
   "swapping model…"), not as bubbles. Empty state: a centered, gently-breathing accent orb +
   "Ask me anything" + a couple of example prompts as tappable chips.
3. **Composer** is a rounded pill textarea (`⏎` sends, `⇧⏎` newlines, auto-grows to a few lines),
   a glowing accent focus ring when active, and a gradient **send** button that springs on press.
   While streaming, send becomes a **stop** (■) control.
4. **Hint strip** is a subtle one-line footer of the live shortcuts (§6), dimmed, with a `?` that
   opens the full shortcut sheet.

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

- **PANEL(composing / streaming / done):** the full centered panel. Streaming renders tokens into
  the assistant bubble with a gentle per-chunk reveal; a "thinking" shimmer sits on the bubble
  until the first token.
- **Dismiss while idle** (composing or done): the panel springs out, backdrop clears → **HIDDEN**.
  Nothing is lost. The chat is persisted; re-summoning restores it.
- **Dismiss while streaming** (Esc or click-away): the panel **morphs**, scaling and gliding down
  to a corner (default **bottom-right**, configurable), shedding its chrome, into a small **ORB**.
  This is one continuous transform (FLIP-style), not a disappear-then-appear.
- **ORB(thinking):** a ~56px living blob at the corner, with the accent gradient slowly rotating, a
  soft breathing scale pulse, a faint pulsing halo. It means "still working." **Click** it → morph
  back to **PANEL(streaming)** (the in-progress turn, right where it is). It never covers active
  work (small, corner-pinned, click-through-safe margins).
- **PREVIEW:** when the turn **completes while minimized**, the orb **expands** into a compact
  card near the corner: the chat title, the answer (or a 2-3 line snippet with a fade if long),
  and a hairline accent progress bar counting down the auto-dismiss (~6s). **Hover pauses** the
  countdown; **click** morphs to **PANEL(done)** (full answer in context); ignore it and it
  **fades out** → HIDDEN (still persisted). A failed turn previews as a soft error card (same
  shape, red-tinted) that does *not* auto-fade. Errors wait to be seen.
- Re-summoning the hotkey from HIDDEN always returns to **PANEL** on the current chat.

This gives the "fire it, keep working, glance when it pings me" flow the maintainer asked for, and it
is coherent with the hard rule: dismissing is purely a *view* change. The turn keeps streaming to
the store, so nothing depends on the window staying open.

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

**Seam dependency (staged).** Listing chats and loading a chat's full history require the brain to
expose session data over the seam; today's `proto` has only per-turn `Converse`. So:
- **v1 (Slice 8):** the overlay keeps the **current app run's** chats + history in memory (fed by
  the streams it renders), supports new-chat and the full animation/state machine, and one live
  session at a time is fully functional. Re-summoning within a run restores the in-memory chat.
- **Later (a seam slice):** add `ListSessions` + `GetSessionMessages` RPCs so history and the chat
  list load from the store. Then cross-restart persistence and cycling are real, not in-memory.
  The UX above is the target; the build reaches it without changing this design.

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
  fades; the orb still shows but without the pulse.
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

## 9. Open decisions (user)

- **Corner** for the minimized orb/preview defaults to bottom-right; top-right if the taskbar area
  is busy. (Configurable.)
- **Auto-dismiss timing** for the completed preview (default ~6s; hover-to-pause).
- **Theme:** ship dark-glass only in v1, or also a light theme token set now?
- **Palette:** the violet→fuchsia→cyan accent is a starting proposal. Lock the exact hues.
- **Sound:** a soft completion chime as an opt-in later, or never?
