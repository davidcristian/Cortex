# Batching and per-tool session allowlists

**Status:** open, fix when it bites
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-09
**Trigger:** a deployment where gated confirmations arrive often enough that the user starts
approving them without reading them. Which tools can produce one is read off the shipped default,
`gated` in `brain/packages/orchestrator/src/cortex_orchestrator/config_tools.py`, and how many one
turn can raise is `MAX_TOOL_DISPATCHES` in `brain/packages/core/src/cortex_core/tool_budget.py`.
This entry's trail records what both said when that was last read.

Every gated call is confirmed on its own and nothing is remembered between calls.
`ToolDispatcher._confirmed` in `brain/packages/core/src/cortex_core/dispatch.py` builds one
`ConfirmationRequest` per call and asks the confirmer, so two sends in one turn are two cards and a
send approved a minute ago buys the next one nothing. There is no batching shape and no per-tool
allowlist to hold an approval in: `ToolPolicy.gated_names` is frozen at construction and read as a
membership test.

The entry was filed about sends, and the surface is wider than that now. The shipped
`CORTEX_TOOLS_GATED` default is two names, `escalate_to_brain` and `send_email`, so a turn that
sends no mail can still raise a card: the escalation gate asks the user to approve a model swap
(ADR-0030), with its own reason text rather than the generic outbound line. Fatigue therefore
arrives from the pair rather than from mail alone, and a fix aimed at sends would leave the other
half where it is.

One direction is already bounded and needs nothing from this entry. Within a turn, a model
emitting gated calls cannot flood the user, because `dispatch` checks the caller's refusal ahead of
the gate, so a spent budget or a recognized repeat returns before the confirmer is consulted, and
`MAX_TOOL_DISPATCHES` is 32. `config_tools.py` leans on exactly that where it says why `send_email`
is deliberately unpriced: a human saying yes thirty two times is the tighter bound. What is
unbounded is the count across turns, which is the fatigue this entry is about.

**What would close it.** Either shape works behind the unchanged `Confirmer` port, since both are
decisions the dispatcher makes before it calls one. Batching means holding gated calls of one turn
and asking once over the set, which needs a card that can show several actions and a resolution
that can approve some of them. A session allowlist means remembering an approval per tool for the
session, which needs somewhere to keep it that survives a model swap, so the `SessionStore` rather
than the dispatcher, and a decision about what ends the permission. The second is the smaller build
and the larger design question, because an allowlist over `send_email` is a standing approval to
send mail.

## Trail

- 2026-09-09: claims held against the code, and the entry re-aimed. It described the fatigue as
  coming from sends, which was the whole gated set when it was filed and is not now: the shipped
  default gates `escalate_to_brain` beside `send_email`, so a card can arrive with no mail
  involved. The old trigger named an observation with no reading behind it, and the clause now
  names the two things a reader can check without a deployment. The per-call confirmation and the
  absent allowlist were confirmed in `dispatch.py`, and the within-turn flood was found already
  bounded by the refusal check that runs ahead of the gate.
