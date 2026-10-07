# A body started before the brain opens a new chat, not the last one

**Status:** open, waiting for its trigger
**Area:** body-overlay
**Origin:** [ADR-0021](../../adr/ADR-0021-session-read-rpcs.md)
**Trigger:** a History line in this file recording the maintainer's pick of A or B.
**Verified:** 2026-10-07

Cold start adopts the most recent chat when the first chat list arrives, and only while the
reducer's `touched` flag is unset (ADR-0021 decision 6). `useSessionCatalog.ts` lists the chats on
mount and again on each summon, and the summon's `open` action sets `touched` before that list
returns. So when the brain cannot be reached at mount, the first list to arrive is the summon's,
and adoption is refused: the panel shows `New chat`, and the person's last chat is reached only
through the switcher. On the Linux shell on 2026-10-07, with the shell started 8 s before the
brain and the brain healthy before the summon, each summon opened on `New chat` in two runs, while
the switcher listed every stored chat
([readings](../../readings/overlay-session-resume.md#chats-across-a-restart)). With the brain up
at the shell's start, the first summon opened on the newest chat. The overlay is the same on
Windows, where the body starts at login and the brain only once Docker is up, so Windows has it
too.

## Proposal

- **A. A summon does not block adoption** (recommended). The summon stops setting `touched`, and
  the actions that put something in front of the person still do: submit, typing, attaching a
  picture, new chat, cycle and opening a chat. The last chat then replaces the empty state a moment
  after a summon, which is a change under the person's eyes rather than before the panel shows.
  ADR-0021 decision 6 drops the summon from the actions it names as setting `touched`, and
  ADR-0052's rule that adoption never moves focus or speaks stays as it is.
- **B. Keep the summon winning.** The empty chat stays, as now, and the runbook says that `Ctrl+Up`
  reaches the last chat. Nothing changes in the code.

## History

- 2026-10-07: filed from the session and preference flows run on the Linux shell, whose
  preference half was fixed the same night.
