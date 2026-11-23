# Nobody has looked at a chat a restart ended in the overlay

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-11-23

Boot recovery appends a reply to the chat of a handoff a restart of the brain ended, with the text
of `UNANSWERED_HANDOFF_NOTE` (`record_unanswered` in
[stranded_handoff.py](../../../brain/packages/core/src/cortex_core/stranded_handoff.py)). By the
code, three things follow in the overlay, and none has been seen:

- The switcher lists that chat first after any hoisted chat, previewed with the record's first 96
  characters, because the record's time is the boot's.
- A restored chat shows the record as a reply of its own (`GetSessionMessages` returns it).
- The next reply in that chat ends with the same text (`unanswered_handoff_note`), so the
  restored chat shows it twice, once as the record and once under that reply.

What would close it: the overlay in headless Chromium against a brain whose store holds such a
chat, read before and after one more turn in it. Pass rule, written before the look: the switcher
row shows the record's text, and a reader of the restored chat sees the text once. If the second
copy shows, the next step is to choose which of the two copies the overlay shows, with the
record's run (`escalate_to_brain`, `ok: false`) as the field that marks the record.

## History

- 2026-11-23: filed when R-1257 was declined, which named the overlay view as not yet seen.
