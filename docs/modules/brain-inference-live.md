# brain/packages/inference: the live tests

Part of [`cortex_inference`](brain-inference.md), whose contract, invariants and shared port
contracts are there. This document lists the tests that need a real `llama-server` and what each
one measures.

All are `integration`-marked, excluded from CI and coverage, and run per
[docs/runbooks/llamacpp-gpu.md](../runbooks/llamacpp-gpu.md).

- `tests/test_backend_live.py` streams against a real `llama-server`.
- `tests/test_finish_reason_live.py` caps a real request at eight tokens and follows the answer
  through the shipped `PlacedAttempt`. `tests/test_cut_tool_call_live.py` caps a request while the
  model is writing a tool call's `arguments`, asserts the server reports the cap before the assembly
  fails, and follows the same `PlacedAttempt` to a `TRUNCATED` outcome (ADR-0048). It needs a server
  started the way a subagent tier is, with deliberation off at the server, since the attempt sends
  no `thinking` of its own.
- **`tests/test_thinking_switch_live.py` measures whether a deployment honours `thinking=False` at
  all** (ADR-0049). It sends one prompt in four shapes against one endpoint, plain and with
  `REPLY_ENVELOPE`, each with the switch and without it, and reports per request shape rather than
  per tier because that is how the answer came out: over every chat entry of the lineup, all of them
  honour it plain and the two gemma-4-E entries deliberate straight through it under a
  `response_format`, the shipped E4B pick on 14 of 15 draws across three builds and the E2B on 10 of
  10 (the lineup table is in [thinking switch](../readings/thinking-switch.md)). It requires a
  server started with **neither** `--chat-template-kwargs` nor `--reasoning-budget`, since either
  flag is the deployment answering for the model, and it **asserts its control**: the requests that
  send no switch must deliberate, or the prompt invited no thought and the run is discarded. Each
  case is drawn `CORTEX_THINKING_REPEATS` times, 1 by default and 5 or more for anything quoted as a
  tier's behaviour. Before the cases it reads the **rendered prompt** for all four shapes off the
  server's own `POST /apply-template` and asserts that the two shapes with one switch render the
  same prompt, which establishes that a difference between their results comes from the schema
  rather than from the prompt. That rendering is also the **predictor**, read on the prompt's tail
  (ADR-0050 decision 2). Both renderings go into one JSON sample per tier (`CORTEX_THINKING_OUT`,
  `CORTEX_THINKING_TAG`) beside the build, the model file and the context size `GET /props` reports,
  and `just switch-tail` fails instead of publishing a run whose prediction and measurement
  disagree; the probe itself asserts nothing.
- **`tests/test_trace_budget_live.py` measures the same question for the budget** (ADR-0049). It
  asks the endpoint whether the engine parses a per-request trace budget, then draws the one case
  the switch loses, a constrained reply into the fixed envelope, with the budget and without it. It
  requires a server started with neither reasoning flag and **asserts the same control**, and
  `CORTEX_TRACE_REPEATS` sets the draws, 1 by default. Measured on the shipped subagent pick at
  `-ngl 0` on `b10666-4e97ac86e`: the switch alone deliberated on **17 of 20** and returned an empty
  capped reply every time, while `trace_tokens=0` held on **20 of 20**. The leak the earlier build
  showed did reproduce once, inside the payload rather than in front of it (`{"reply": "thought"}`,
  1 of 58 budgeted draws, and 0 of 20 against a tier with the same sampler as a flag), so the file
  prints a leak count rather than asserting on one. Re-drawn at a hundred draws a case on both
  builds, the leak did not reappear and the budgeted case held the trace at 0 on 200 of 200.
- **`tests/test_system_join_live.py` checks the join of leading system messages** (ADR-0071)
  against the server at `CORTEX_SYSTEM_JOIN_ENDPOINT`. It asks the probe's question for two and
  three messages, checked against `CORTEX_SYSTEM_JOIN_EXPECT` (`2=yes,3=no`) when set. It sends
  the brain's own turn with a recalled memory, a recap and a tool through the adapter and asserts
  the posted messages are joined exactly when the probe says the template cannot take them, and
  sends a tool task with a plain context and asserts it is not an inference failure;
  `tests/system_led.py` builds both through the real core. It times the probe idle and beside a
  streaming generation against its 2.0 s timeout, and prints `timings.prompt_n` and `cache_n` for
  two turns in each layout. The results are in
  [system message templates](../readings/system-message-templates.md).
