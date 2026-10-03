# Raw GBNF grammar alternative

**Status:** open, waiting for a consumer
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Trigger:** a task file or ADR asks for a constrained reply whose shape JSON Schema cannot express. None does: `grep -rn 'schema=' brain/packages/*/src` finds two values a caller sets, `REPLY_ENVELOPE` and `ORDER_ENVELOPE`, both JSON objects.
**Verified:** 2026-10-03

Left behind by [R-068](068-grammar-constrained-subagent-output.md): a raw GBNF `grammar` as an
alternative to the JSON envelope. The ADR defers it until a caller needs a shape JSON cannot
express, and no caller does.

It is not a keyword's worth of work. The port takes `schema: JsonSchema | None`
([ports.py:76](../../../brain/packages/core/src/cortex_core/ports.py)), where `JsonSchema` is a
`Mapping[str, object]` ([inference.py:11](../../../brain/packages/core/src/cortex_core/inference.py)),
and a GBNF grammar is a string. `build_payload` wraps any schema it receives into
`response_format.json_schema`
([request.py:124](../../../brain/packages/inference/src/cortex_inference/request.py)), and no
request on that path has a grammar field. So an alternative needs the port widened, a branch in
the request builder, and a second parser beside `unwrap_envelope`, which parses JSON and nothing
else ([subagent_reply.py:43](../../../brain/packages/core/src/cortex_core/subagent_reply.py)).

## History

- 2026-08-16: Priced against the tree and given the trigger the origin had all along, which this
  file lost in transcription. Two findings: nothing here needs fixing under pressure, because the
  constraint that shipped does the whole job the ADR asked of it, so what is missing is a consumer;
  and the cost is a port change rather than a keyword.
- 2026-08-16: The port gained its second constrained caller since the ADR was written, and it
  argues the same way: the ranked-recall rerank judge passes an `ORDER_ENVELOPE` of
  `{"order": [int]}` through `drain_text`
  ([rerank_judge.py](../../../brain/packages/core/src/cortex_core/rerank_judge.py)), so both
  shipped consumers of the keyword are ordinary JSON objects.
- 2026-09-13: Checked again, and the trigger has not fired. The port still has exactly two
  constrained callers, `REPLY_ENVELOPE` in
  [subagent_reply.py](../../../brain/packages/core/src/cortex_core/subagent_reply.py) and
  `ORDER_ENVELOPE` in
  [rerank_judge.py](../../../brain/packages/core/src/cortex_core/rerank_judge.py), and both are
  JSON objects. The three code readings above still hold line for line.
- 2026-09-19: Checked again, and the trigger has not fired. Every `schema=` in the brain's sources
  still reaches the port from one of the two envelopes: `ORDER_ENVELOPE` in `rerank_judge.py`, and
  `REPLY_ENVELOPE` in `subagent_attempt.py`, which sets it on the `ToolLoopContext` that
  `tool_loop.py` forwards, while the cortex turn in `engine.py` and the deep turn in
  `brain_phase.py` build that context with no schema. The port still takes
  `schema: JsonSchema | None` (`ports.py`), `build_payload` still wraps a present schema into
  `response_format.json_schema` with no grammar slot, and `unwrap_envelope` still parses JSON and
  nothing else. Of those files only `brain_phase.py` has changed since 2026-09-13, and it still
  passes no schema. This entry and [R-070](070-per-task-caller-schema.md) do not wait on each
  other: a per-task schema would still be JSON.
- 2026-09-28: Checked again after subagent roles were added, and the trigger has not fired. A role
  is a sentence appended to the instruction, so the `excerpt` role's one item per line is text
  inside the envelope's string, not a new constrained caller; every `schema=` in the brain's
  sources still comes from `REPLY_ENVELOPE` or `ORDER_ENVELOPE`.
- 2026-10-03: Checked again, and the trigger has not fired. The five `schema=` sites in the
  brain's sources are three that pass a value on (`drain.py`, `handoff_wait.py`, `tool_loop.py`)
  and two that set one, `ORDER_ENVELOPE` at `rerank_judge.py:129` and `REPLY_ENVELOPE` at
  `subagent_attempt.py:120`; the cortex turn in `engine.py` and the deep turn in `brain_phase.py`
  still build their `ToolLoopContext` with no schema. No task file or ADR other than ADR-0028 and
  R-068 links here. The trigger now names the search that decides it, and the body gives line
  numbers.
