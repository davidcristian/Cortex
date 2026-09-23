# ADR-0032: The user's preference record, and the settings view that uses it

**Status:** Accepted (2026-07-19)

## Context

The overlay had two appearance choices, the theme and (since
[ADR-0031](ADR-0031-bubble-mark.md)) the mark style, and neither survived a restart: both were
`useState` in `components/App.tsx`. The theme had worked that way since Slice 8 and nobody had
minded, because the default follows the system scheme and the toggle is one click. The mark made
it matter: four styles ship, the user chooses one deliberately, and losing that choice on every
restart makes it feel like a demo rather than a setting.

The deferred entry recorded two options and deliberately did not choose between them:
`localStorage` in the webview, a few lines that die with a reinstall and are invisible to
everything except this window, or a record the brain owns. The maintainer chose the brain's record.

The same slice closes the other recorded overlay deferral, because they turn out to be one
problem. The mark chooser lived on the panel's empty state and was reachable **only** there, so
once a chat had messages there was no way to change the mark at all, and no click-away close.
Both are symptoms of the overlay having no settings view, and storing the mark would not have
helped a user who could no longer reach the chooser that changes it.

## Decision

1. **The record is opaque key/value pairs the brain stores and never parses.** `Preference{key,
   value}`, `GetPreferences` and `SetPreference` on `BrainService`. Keys are namespaced strings
   the caller owns (`overlay.theme`, `overlay.mark`); values are short strings the brain treats as
   bytes. The alternative, a typed `Preferences{theme, mark}` message, makes every new setting a
   proto change plus two stub regenerations plus a Rust and a TypeScript field. The opaque form
   means **a new preference needs no change to the gRPC contract at all**, which is what keeps a
   settings view cheap to grow.

2. **`PreferenceStore` is a port in the core, adapted to Redis in `cortex_session`.** `all()` and
   `set(key, value)`, with a fake and a contract suite both implementations pass
   (ports before adapters). Redis rather than Postgres because it is where the conversation state
   already lives, it is in the base compose file rather than an optional override, and it persists
   the same way (append-only, named volume), so the record survives a brain restart, a Redis
   restart, and the body reinstall this ADR exists for. The store is optional in `RpcPorts`: with
   none configured, reads return empty and writes are accepted and discarded, the `ScheduleStore`
   precedent, so a brain without the capability still lets a body apply a choice for the session.

3. **An empty value CLEARS a key.** This follows the `rename_session` empty-title convention, and
   it is the reason the overlay can express "follow the system" at all: `theme = null` is stored
   as a cleared key, not as the string `"auto"`, so the default lives in one place (the reader)
   instead of being a special value the store would have to handle. Cleared means *absent*, never
   present-and-empty; a reader that found the key present would apply `""` as a choice.

4. **Reads retry, writes do not.** `GetPreferences` is one of the repeatable reads.
   `SetPreference` follows the catalog-write convention (`RpcMethod::SetPreference` is not
   repeatable): last write wins in the store so a repeat cannot duplicate an effect, but a lost
   reply must not silently reapply a value the user's next change reversed.

5. **The write is optimistic and its failure is not fatal.** `usePreferences` applies the choice
   to the current render and starts the RPC without waiting for it, so a slow or unreachable brain
   can never make choosing a theme feel stuck. A failed write costs durability only; the choice
   still holds for the session. A failed *read* leaves the defaults, which is exactly what a first
   run shows.

6. **Loading the record never overwrites a choice already made.** The record arrives one round
   trip after mount, and a user who chooses a mark inside that window would otherwise watch it
   revert. A per-key flag keeps the later, more deliberate choice. This is the one race in the
   feature and it has its own test.

7. **A settings sheet, opened from the hint strip and from the mark itself.** It holds the theme
   (Auto plus every registered theme) and the mark styles drawn live. It is where "follow the
   system" is chosen, which the header's toggle cannot express: that toggle names the opposite
   theme outright and can only ever select one of the two. `settingsOpen` is reducer state beside
   `sheetOpen`, so Esc closes it first and a dismissed panel does not come back to settings.
   Clicking the backdrop closes it; clicking the card does not.

8. **The empty state's mark opens that sheet instead of its own chooser.** `MarkPicker` is
   deleted. One chooser in one place, reachable from a chat with messages, and the click-away
   problem disappears rather than being patched: there is no inline popover left to click away
   from.

## Consequences

- New in the brain: `PreferenceStore` (port, fake, contract suite), `RedisPreferenceStore`,
  `PreferenceRpcMixin`, and the store in `RpcPorts` and `wiring`. New on the body: two
  `BrainTransport` methods, `RpcMethod` variants, `body_rpc::preferences`, two Tauri commands,
  two `BrainBridge` methods, `usePreferences`, `SettingsSheet`.
- The hint strip ran out of room once the settings button joined it (measured: it wanted 573 px of
  a 558 px row and wrapped to two lines), so the `Esc dismiss` hint was dropped from the strip.
  The shortcut list beside it still shows every binding, and that one is the complete list.
- **Decision 7's sheet is now a tab**, first a view of the panel
  ([ADR-0034](ADR-0034-panel-views.md)) and then the appearance tab of one console it shares with
  the shortcut list ([ADR-0035](ADR-0035-console-and-motion.md) decision 1). Nothing about the
  record or the choices moved: the theme row (Auto plus every registered theme) and the mark row
  (every style, drawn live) are the same two choices over the same RPCs, shown as swatches instead
  of segmented rails. What did change is the state behind them, from `settingsOpen` beside
  `sheetOpen` to one `consoleTab`, and with it the backdrop click this decision mentions, which no
  longer exists to click.
- A brain that is unreachable at startup means the overlay opens with default appearance and then
  does not correct itself until the next launch: the record is read once per mount, not
  subscribed to. At personal scale, with the body starting alongside the brain, that is a fair
  trade against polling; if it becomes a problem, the fix is to read again on the same rising edge
  of visibility the reminder fetch already uses.
- The record is readable by any future part of the product, which was the point of choosing the
  brain over `localStorage`, and is also the reason keys are namespaced from day one.
