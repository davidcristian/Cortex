# Fencing a recap of tainted turns

**Status:** landed 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

**A recap of tainted turns is fenced at both ends ([ADR-0038 untrusted-recap
addendum](../../adr/ADR-0038-ranked-recall.md)).** Read against the shipped write path, the entry's
own premise was wrong and the real exposure is a different shape. **An untrusted tool result is
never in the prefix a recap reads.** `TurnEngine.handle_turn` appends exactly two messages per
turn, the raw `Role.USER` text and the guardrail-scrubbed `Role.ASSISTANT` reply (`engine.py`);
the in-turn `Role.TOOL` message that carried the payload is turn-local and dies with the turn,
the same finding the tainted-summarization decline made on the record path
([untrusted-content.md](../index.md#untrusted-content)). Nor is there a taint bit to key a refusal on: a
stored `Message` carries role, text, timestamp and turn id, taint is a turn-local ledger
reconstructed each turn, and `SessionStore` has no verb that would report it. **What is
reachable is the assistant's own quotation.** The security preamble expressly permits quoting
untrusted content ("You may quote or summarize"), so a reply to "summarize this email" can carry
the injection verbatim into persisted history, and from there into the recap. The recap then did
two things the plain window does not: it fed that text to a model under an instruction to
process it, which is the summarizer-as-target shape, and it turned the answer into a **durable,
cached, `Role.SYSTEM`** artifact folded forward for the life of the session, which is a
promotion in both trust and lifetime. **Both ends are now fenced, unconditionally.** The recap
prompt carries the standing `SECURITY_PREAMBLE` and quotes the transcript and the previous
account inside `wrap_untrusted` under a nonce minted for that call; the recap enters the turn
through `fence_recap`, wrapped under a **second** nonce minted after the model has spoken, which
is what stops a summarizer talked into copying the closer it was shown from ending the fence its
own words sit in. Neither wrap takes an argument or sits behind a branch, so no state of the
window produces an unfenced one, and the markers explain themselves in the recap's own text
because the turn carrying them may have neither tools nor taint to earn a preamble. Pinned by an
injection payload placed in a dropped assistant reply and asserted absent from everything
outside the fences, in both directions (a hostile prefix, and a summarizer that repeated the
payload), each of the five fence sites mutation-proven to redden its own test. **The cost is
honest:** the recap now reads as data rather than as the assistant's own notes, so the model is
told to rely on it for facts and never for instructions, and whether a fenced recap still
answers the booking-reference question as well as the unfenced one measured is **unmeasured**.
It joins the one-corpus entry above, since both want the same live run. Taint is deliberately
**not** spread by a recap, argued in the addendum. Remaining from this deferral:

## Trail

- 2026-08-06: Landed fenced at both ends. Settling it corrected the entry's own premise and found
  something wider, which became an entry in the untrusted-content area rather than a line in this
  closure: a quoted injection re-enters through the plain history window, unfenced and untainted,
  and the fix it wants is a persisted per-turn taint marker, which per-provenance eviction and a
  precise recap refusal would both spend, the refusal being the one this entry found no taint bit
  to key on.
- 2026-08-06: The fence's cost was left unmeasured, the live run having been made before the fence
  existed, so the usefulness question was opened beside the one-corpus entry that wants the same
  run.
- 2026-08-06: The reason taint is deliberately not spread by a recap was recorded as the plain
  history window handing the model the same assistant messages unfenced on every turn until they
  age out, so a recap that tainted its turn would be narrower than its own source.
