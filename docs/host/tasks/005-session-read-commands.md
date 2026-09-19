# The session-read Tauri commands

**Status:** never attempted
**Session:** windows-desktop
**Capability:** W
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)

**What only this proves.** That the two glue commands, which need no approval, take the reads across
the real IPC hop. Both ends are already proven: the brain half was Docker-validated against real
Redis on 2026-07-07, and the overlay reducer is covered at 100%.
[ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)'s consequences say the same: the Tauri
`list_sessions` and `session_messages` commands (`src-tauri/src/sessions.rs`) are host-validated
glue, in the same class as the `converse` command. Auto-restore was added on 2026-07-12, so expect
the most recent chat to restore rather than a blank one.

**Do.** In the running overlay: open the switcher with the header's **Recent chats** button (the
two overlapping speech bubbles), or `Ctrl+K` from the keyboard, then `Ctrl+↑`/`Ctrl+↓` to cycle.
Restart the app and summon again. **Corrected 2026-07-19:** this line named the `⌄` control, which
is the header's rightmost button and dismisses the overlay (`TuckIcon`), so following it literally
ended the check instead of starting it.

**Pass.** The switcher lists prior chats with their derived titles and previews, most recent first;
cycling moves through them and loads each one's history; a restart restores the most recent chat.

**Fail.** An empty list against a brain that has sessions is the IPC hop or the token. A list that
appears but whose messages never load is `session_messages` specifically.

**Record it.** Edit [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md) in place so it no longer
lists the Windows-native Tauri `list_sessions` and `session_messages` commands as host validation
still to run; then delete this section.

## Notes

- The session doc numbers this check **4**, and ADR-0021 cites it by that number.
- It needs a brain with prior chats in its store.
