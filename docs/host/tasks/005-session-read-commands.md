# The session-read Tauri commands

**Status:** never attempted
**Sitting:** windows-desktop
**Capability:** W
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-seam.md)

**Until 2026-07-19 this was recorded in exactly two places, both of them prose, and one of them was
about to be cleaned.**

**What only this proves.** That the two ungated glue commands carry the reads across the real IPC
hop. Both ends are already proven: the brain half was Docker-validated against real Redis on
2026-07-07, and the overlay reducer is gated at 100%.

The paragraph below was the ROADMAP's status for that slice; it was **preserved here when the
ROADMAP was slimmed on 2026-07-19** and is no longer in that file. The live one-line form is
[ADR-0021](../../adr/ADR-0021-session-read-seam.md)'s 2026-07-07 addendum, "the Windows-native Tauri
`list_sessions`/`session_messages` commands remain host validation":

> **Host half (host-validated on Windows):** the `list_sessions`/`session_messages` Tauri commands
> (`src-tauri/src/sessions.rs`), the same ungated-glue class as the `converse` command. **Cold
> start opens a new chat**; prior chats are reachable via the switcher/cycling (auto-restore
> deferred).

The parenthetical is stale and is kept only because the sentence is quoted: **auto-restore landed
2026-07-12** ([refinements/session-read-seam.md](../../refinements/index.md#session-read-seam)). Expect the
most recent chat to restore, not a blank one.

**Do.** In the running overlay: open the switcher with the header's **Recent chats** button (the
two overlapping speech bubbles), or `Ctrl+K` from the keyboard, then `Ctrl+↑`/`Ctrl+↓` to cycle.
Restart the app and summon again. **Corrected 2026-07-19:** this line named the `⌄` control, which
is the header's rightmost button and dismisses the overlay (`TuckIcon`, "tuck it away"), so
following it literally ended the check instead of starting it.

**Pass.** The switcher lists prior chats with their derived titles and previews, most recent first;
cycling moves through them and loads each one's history; a restart restores the most recent chat.

**Fail.** An empty list against a brain that has sessions is the IPC hop or the seam token. A list
that appears but whose messages never load is `session_messages` specifically.

**Record it.** A dated addendum to [ADR-0021](../../adr/ADR-0021-session-read-seam.md), whose
2026-07-07 live-validation addendum closes with "the Windows-native Tauri
`list_sessions`/`session_messages` commands remain host validation" (many later addenda follow
it, so search for the sentence rather than reading the file's end); then delete this section.

## Notes

- The sitting doc numbers this check **4**, and ADR-0021 cites it by that number.
- The host index's roll call adds that it needs a brain with prior chats in its store.
