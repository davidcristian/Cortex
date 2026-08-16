# The user's half of an opaque turn

**Status:** open, fix when it bites
**Area:** vision
**Origin:** [ADR-0029](../../adr/ADR-0029-vision-screen-capture.md)
**Trigger:** the first thing a user asks the assistant to remember during a capture turn and later finds it has forgotten.

Opened 2026-08-16 by the per-source memory rules decline
([R-260](260-per-source-memory-rules.md)), which found that the loss that entry was written around
needs no source identifier at all. `record_exchange` returns before the write on
`taint.opaque`, and the text it would have written is `render_exchange`'s
`User: <message>\nAssistant: <reply>`
([turn_output.py](../../../brain/packages/core/src/cortex_core/turn_output.py)), so a capture turn
drops the user's own sentence along with the transcription the drop exists for. The reason the
drop exists is that the assistant half of a capture turn **is** the untrusted payload, in the one
form that survives; the user's half is not, being text the user typed and an attacker cannot write.
Recording only that half preserves "remember that my invoice number is 4021" while persisting no
pixel-derived prose at all.

What makes it a decision rather than a two-line change is what a bare half means on recall. Most
capture turns open with a question, and `User: what does this say?` stored alone is noise a later
recall would rank against real memories, so this wants either a salience judgement at record time
([R-093](093-write-salience-policy.md), whose own cost correction is the recaller's non-optional
return) or a rule narrow enough to state without one. It also needs the origin's licence rewritten
rather than assumed: the opaque drop is an explicit decision in the vision record and in the
tainted-recording record beside it, so a change here is an addendum at both, not an edit to a
condition.
