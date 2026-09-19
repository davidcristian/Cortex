# Fencing a recap of tainted turns

**Status:** done 2026-08-06
**Area:** session-history
**Origin:** [ADR-0038](../../adr/ADR-0038-ranked-recall.md)

The entry's own premise was wrong and the real exposure has a different shape. An untrusted tool
result is never in the prefix a recap reads: `TurnEngine.handle_turn` appends exactly two messages
per turn, the raw `Role.USER` text and the guardrail-scrubbed `Role.ASSISTANT` reply
(`engine.py`), and the in-turn `Role.TOOL` message that held the payload is turn-local and is
discarded with the turn. Nor is there a taint bit to reject on: a stored `Message` has role, text,
timestamp and turn id, taint is a turn-local ledger rebuilt each turn, and `SessionStore` has no
verb that would report it.

What is reachable is the assistant's own quotation. The security preamble expressly permits
quoting untrusted content ("You may quote or summarize"), so a reply to "summarize this email" can
put the injection verbatim into stored history, and from there into the recap. The recap then did
two things the plain window does not: it fed that text to a model under an instruction to process
it, and it turned the answer into a durable, cached `Role.SYSTEM` message folded forward for the
life of the session, which raises both its trust and its lifetime.

Both ends are now fenced, with no condition on it. The recap prompt includes the standard
`SECURITY_PREAMBLE` and quotes the transcript and the previous account inside `wrap_untrusted`
under a nonce created for that call; the recap enters the turn through `fence_recap`, wrapped
under a second nonce created after the model has spoken, which stops a summarizer talked into
copying the closing marker it was shown from ending the fence its own words sit in. Neither wrap
takes an argument or sits behind a branch, so no state of the window produces an unfenced recap,
and the markers explain themselves in the recap's own text because the turn they are in may have
neither tools nor taint to justify a preamble. Checked with an injection payload placed in a
dropped assistant reply and asserted absent from everything outside the fences, in both directions
(a hostile prefix, and a summarizer that repeated the payload), with each of the five fence sites
shown able to fail its own test.

The cost is stated plainly: the recap now reads as data rather than as the assistant's own notes,
so the model is told to rely on it for facts and never for instructions, and whether a fenced
recap still answers the booking-reference question as well as the unfenced one was left unmeasured
([R-033](033-fenced-recap-usefulness.md)). Taint is deliberately not spread by a recap.

## History

- 2026-08-06: Fenced at both ends. Settling it corrected the entry's own premise and found
  something wider, which became its own entry in the untrusted-content area: a quoted injection
  re-enters through the plain history window, unfenced and untainted, and fixing it needs a stored
  per-turn taint marker.
- 2026-08-06: The fence's cost was left unmeasured, the live run having been made before the fence
  existed, so the usefulness question was opened as [R-033](033-fenced-recap-usefulness.md).
- 2026-08-06: The reason taint is deliberately not spread by a recap was recorded: the plain
  history window hands the model the same assistant messages unfenced on every turn until they age
  out, so a recap that tainted its turn would be narrower than its own source.
