# Batching and per-tool session allowlists

**Status:** open, waiting for its trigger
**Area:** email-confirmer
**Origin:** [ADR-0022](../../adr/ADR-0022-email-write-confirmer.md)
**Verified:** 2026-09-19
**Trigger:** a deployment where confirmations arrive often enough that the user starts approving
them without reading them. Which tools can produce one is read off the shipped default,
`confirm_names` in `brain/packages/orchestrator/src/cortex_orchestrator/config_tools.py`, and how
many one turn can raise is `MAX_TOOL_DISPATCHES` in `brain/packages/core/src/cortex_core/tool_budget.py`. This entry's
history records what both said when that was last read.

Every call that needs confirmation is confirmed on its own and nothing is remembered between calls.
`ToolDispatcher._confirmed` in `brain/packages/core/src/cortex_core/dispatch.py` builds one
`ConfirmationRequest` per call and asks the confirmer, so two sends in one turn are two cards and a
send approved a minute ago buys the next one nothing. `DispatchPolicy.confirm_names` is frozen at
construction and read as a membership test, so there is nowhere to hold an approval.

The entry was filed about sends, and the surface is wider now. The shipped `CORTEX_TOOLS_GATED`
default is two names, `escalate_to_brain` and `send_email`, so a turn that sends no mail can still
raise a card: the escalation confirmation asks the user to approve a model swap (ADR-0030). A fix
aimed at sends would leave the other half where it is.

One direction is already bounded. Within a turn, a model emitting such calls cannot flood the user,
because `dispatch` checks the caller's refusal ahead of the confirmation, so a spent budget or a
recognized repeat returns before the confirmer is consulted, and `MAX_TOOL_DISPATCHES` is 32.
`config_tools.py` relies on exactly that where it says why `send_email` is deliberately unpriced.
What is unbounded is the count across turns.

Either shape works behind the unchanged `Confirmer` port, since both are decisions the dispatcher
makes before it calls one. Batching means holding a turn's calls and asking once over the set, which
needs a card that can show several actions and a resolution that can approve some of them. A session
allowlist means remembering an approval per tool for the session, which needs somewhere to keep it
that survives a model swap, so the `SessionStore` rather than the dispatcher, plus a decision about
what ends the permission. The second is the smaller build and the larger design question, because an
allowlist over `send_email` is a permanent approval to send mail.

## History

- 2026-09-09: Claims held against the code, and the entry was re-aimed. It described the fatigue as
  coming from sends, which was the whole confirm set when it was filed and is not now. The old
  trigger named an observation with no reading behind it, and it now names two things a reader can
  check without a deployment. The within-turn flood was found already bounded by the refusal check
  that runs ahead of the confirmation.
- 2026-09-13: Claims held again and both readings are unchanged. The entry named the policy class
  wrong: the frozen set lives on `DispatchPolicy` in `dispatch.py`, and no `ToolPolicy` exists
  anywhere in the brain. This tree runs no deployment, so the trigger has not fired.
- 2026-09-19: Claims held and both readings are unchanged. The one commit since 2026-09-13 that
  touched `config_tools.py` left the default at `escalate_to_brain` and `send_email`;
  `MAX_TOOL_DISPATCHES` is still 32, `_confirmed` still builds one `ConfirmationRequest` per call,
  and the refusal check still returns first. The default is still the whole set that can raise a
  card: `dispatch` checks the advertised flag or the set, the only built-in advertising its own flag
  is `escalate_to_brain`, and the tools adapter builds no remote spec with the flag set.
