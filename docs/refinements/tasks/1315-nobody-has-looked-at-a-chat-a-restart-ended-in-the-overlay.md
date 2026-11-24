# Choose which copy of a restart's record the overlay shows

**Status:** open, actionable
**Area:** body-overlay
**Origin:** [ADR-0074](../../adr/ADR-0074-replayed-tool-runs.md)
**Verified:** 2026-11-24

Boot recovery appends a reply to the chat of a handoff a restart of the brain ended, with the text
of `UNANSWERED_HANDOFF_NOTE` and the run `escalate_to_brain` `ok: false` (`record_unanswered` in
[stranded_handoff.py](../../../brain/packages/core/src/cortex_core/stranded_handoff.py)). The next
reply in that chat ends with the same text (`unanswered_handoff_note`).

The overlay was read in headless Chromium against a stack brain whose boot recovery wrote such a
record ([readings](../../readings/handoff-restart-record.md#the-overlays-view-2026-11-24)). The
pass rule written before the look was: the switcher row shows the record's text, and a reader of
the restored chat sees the text once. The switcher half passes. The restored-chat half fails: after
one more turn the chat shows the text twice, once as the record's own bubble and once at the end of
the new reply. The screenshots are in `~/.cache/cortex-run/2026-11-24/c2/shots/`:
`before-switcher.png`, `before-chat.png`, `after-switcher.png` and `after-chat.png`.

What remains is a visual pick for the user: which of the two copies the overlay shows.

1. **The record only (recommended).** The restored chat keeps the record where boot recovery put
   it, right after the handoff it belongs to, and shows the later reply without its closing copy.
   The chat reads the same before and after the next turn, and the text sits beside the request it
   is about.
2. **The closing copy only.** The restored chat leaves the record out once a later reply has its
   text. This matches what a body that ran across the restart shows, by the code: the overlay
   reads a chat's history only when it mounts and when a chat is opened from the switcher
   (`useSessionCatalog.ts`), so its open chat never gets the record. The cost is that the chat
   changes shape across the next turn: the bubble after the handoff goes, and the text moves under
   a reply about something else.
3. **Both, with the record drawn as a notice rather than a reply.** A new style, and still two
   copies.

A case not yet seen as one view, from the two readings: an overlay that loaded the chat after the
restart (a body started again, or the chat opened from the switcher) already shows the record, and
the next turn's streamed reply ends with the copy, so the open panel shows both until the chat is
opened again. Choices 1 and 2 both leave that case.

Proposal for the code, with no visual change: the brain can already tell the record by its run and
text (`records_no_answer` in `stranded_handoff.py`), so `message_to_proto` can set a new
`SessionMessage` field from it. The overlay then has a typed mark to choose by, for the restored
chat and for the streamed reply alike, instead of matching text.

## History

- 2026-11-23: filed when R-1257 was declined, which named the overlay view as not yet seen.
- 2026-11-24: the overlay read before and after one more turn; the second copy shows, so the task
  now holds the choice of copy, with a recommendation.
