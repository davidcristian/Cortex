# Raw GBNF grammar alternative

**Status:** open, waiting for a consumer
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Trigger:** the first constrained caller whose output shape JSON cannot express, which neither shipped envelope is.
**Verified:** 2026-09-19

Left behind by [R-068](068-grammar-constrained-subagent-output.md): a raw GBNF `grammar` as an
alternative to the JSON envelope. The ADR defers it only if a non-JSON shape is ever wanted, and
nothing wants one.

It is not a keyword's worth of work. The port takes `schema: JsonSchema | None` where `JsonSchema`
is a `Mapping[str, object]`
([ports.py](../../../brain/packages/core/src/cortex_core/ports.py),
[inference.py](../../../brain/packages/core/src/cortex_core/inference.py)), a GBNF grammar is a
string, and `build_payload` wraps a present schema unconditionally into
`response_format.json_schema`
([request.py](../../../brain/packages/inference/src/cortex_inference/request.py)) with no
free-form sampling slot anywhere on the path. So an alternative needs the port widened, a branch
in the request builder, and a second path beside `unwrap_envelope`, which parses JSON and nothing
else ([subagent_reply.py](../../../brain/packages/core/src/cortex_core/subagent_reply.py)).

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
