# A constrained request loses the thinking switch the subagent tier relies on

**Status:** done 2026-08-26
**Area:** subagents
**Origin:** [ADR-0049](../../adr/ADR-0049-thinking-switch-and-trace-budget.md)

Both subagent model families are reasoning models, and unbounded thinking on this CPU tier is
minutes per call, so it is turned off per server: every subagent `llama-server` this repo ships
starts with `--chat-template-kwargs '{"enable_thinking": false}'`. `PlacedAttempt` therefore sends
no per-request thinking key on purpose, and `build_payload` only emits `chat_template_kwargs` when
a bound asks for it, the argued reason being that saying it again per request would change the
request for a deployment whose template writes the flag differently.

Measured, that server-side switch works on a plain request and stops working once the request has a
`response_format`. On the same body, the same server and the same session, the raw run's first
reply token arrives 13.1 to 14.2 s in, immediately after prompt eval, and the constrained run's
arrives 210.9 to 505.0 s in. A probe at a cap of 200 on the constrained shape decoded 200 tokens of
which none were reply text and 763 characters were reasoning, opening `Here's a thinking process to
ensure all details are captured accurately`. Read off the wire, the same request is 200 SSE lines
over 156.3 s with not one content delta among them and a longest gap of 3.46 s, so nothing is
stalled and the 600 s stall ceiling never comes near it; `stream_tool_loop` simply discards every
reasoning delta unread.

The consequence is the whole of [R-431](431-the-token-cap-fires-on-the-shape-that-ships.md). The
shipped tool-less configuration spends most of a cap sized on reply length on text no reader sees:
a cap on a reasoning model with thinking left on deletes the reply rather than shortening it. One
narrow summarization in three reached the cap and came back a refusal, and the two that finished
returned shorter replies than the same bodies raw, 158 and 1176 characters against 1559 and 2211.

The obvious fix is the one `build_payload` already has: give a constrained subagent attempt a
`GenerationBounds` with `thinking=False`, so the request sends
`chat_template_kwargs: {"enable_thinking": false}` itself rather than trusting a server flag a
`response_format` overrides.

## History

- 2026-08-26: opened by the close of
  [R-431](431-the-token-cap-fires-on-the-shape-that-ships.md), whose paired run traced the
  envelope's cost to a reasoning trace the shipped constrained request re-enables.
- 2026-08-26: closed, and not by the fix this entry named. The proposed fix was built (a
  constrained `PlacedAttempt` building `GenerationBounds(max_tokens=..., thinking=False)`, sent
  with the constraint rather than the cap so an uncapped constrained attempt sent it too) and
  measured against the live CPU tier at the same cap of 200 that produced the defect reading: no
  change at all, 200 decoded tokens, 0 reply characters, 709 characters of reasoning, first reply
  token 150.0 s in against the before run's 159.7 s. So it was reverted, and the wire was read
  instead of the port. The flag that does reach the model is `--reasoning-budget 0`, which the
  trace-budget work (ADR-0049) had measured on the cortex tier and then declined to give the
  subagent tier on the grounds its deliberation was already off at the template. It now sits beside
  the kwarg in `docker/docker-compose.subagents.yml`, in the roster override, and in the model
  host's `_REASONING_OFF`, at a fixed zero the deployment's own `CORTEX_REASONING_BUDGET` cannot
  reach. Live proof through `brain/packages/orchestrator/tests/test_envelope_cost_live.py`, one
  body at a cap of 200, both rows measured on this machine in this session: kwarg only, first reply
  token 159.7 s, 200 tokens, capped, 0 reply characters, 671 of reasoning, refused; kwarg and
  budget, first reply token 17.5 s, 50 tokens, finished, 151 reply characters, 0 of reasoning,
  answered. So the answer to this entry's open half is per tier, and the argued comment on
  `PlacedAttempt._generation` stands unamended. Recorded in ADR-0049. Four things came with it:
  [R-458](458-the-ports-thinking-switch-is-conditional.md), the port's own switch being known to be
  conditional with four shipped bounds resting on it;
  [R-459](459-what-the-envelope-costs-the-answer.md), the constrained reply this proof returned
  being 151 characters describing the task rather than performing it;
  [R-460](460-the-reasoning-off-pair-is-spelled-in-three-places.md), the flag pair now appearing in
  three files with nothing comparing them; and
  [R-461](461-the-tiers-thinking-flag-is-deprecated.md), the older of the two flags being one the
  shipped image already prints a deprecation warning for on every boot.
- 2026-08-27: the mechanism recorded above is wrong, corrected by the close of
  [R-458](458-the-ports-thinking-switch-is-conditional.md). The E4B template does read the kwarg,
  measured on a prompt that invites deliberation: a plain request writes 654 characters of trace
  without the switch and none with it. What the `response_format` costs is the switch's effect and
  not its delivery, so this entry's own original reading was right and the correction that replaced
  it was not. Nothing done here moves: the fix is still `--reasoning-budget 0` at the tier, and the
  per-request key would still have bought nothing.
