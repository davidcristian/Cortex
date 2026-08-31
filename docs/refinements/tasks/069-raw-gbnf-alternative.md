# Raw GBNF grammar alternative

**Status:** open, dead until a consumer
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)
**Trigger:** the first constrained caller whose output shape JSON cannot express, which neither shipped envelope is.

It was recorded inside the grammar-constrained subagent output entry, in its list of what remains
behind the same seam (ADR-0028 deferred). The fragment, verbatim: a raw GBNF `grammar`
alternative to the JSON envelope.

## Trail

- 2026-08-16: Priced against the tree and given the trigger the origin had all along, which this
  file lost in transcription: the ADR defers it "only if a non-JSON shape is ever wanted". Two
  things came out of the reading. **The bucket was wrong.** Nothing bites here, because the
  constraint that shipped does the whole job the ADR asked of it; what is missing is a consumer,
  which is the same state its sibling [R-070](070-per-task-caller-schema.md) was already filed in
  from the same deferred list. And **the cost is not a keyword.** The port carries
  `schema: JsonSchema | None` where `JsonSchema` is a `Mapping[str, object]`
  ([ports.py](../../../brain/packages/core/src/cortex_core/ports.py),
  [inference.py](../../../brain/packages/core/src/cortex_core/inference.py)), a GBNF grammar is a
  string, and `build_payload` wraps a present schema unconditionally into
  `response_format.json_schema`
  ([request.py](../../../brain/packages/inference/src/cortex_inference/request.py)) with no
  free-form sampling slot anywhere on the path, so an alternative needs the port widened, a branch
  in the request builder, and a second settle path beside `unwrap_envelope`, which parses JSON and
  nothing else ([subagent_reply.py](../../../brain/packages/core/src/cortex_core/subagent_reply.py)).
  The ADR's "no new port" reading covers what landed rather than this.
- 2026-08-16: The seam gained its second constrained caller since the ADR was written, and it
  argues the same way: the ranked-recall rerank judge passes an `ORDER_ENVELOPE` of
  `{"order": [int]}` through `drain_text`
  ([rerank_judge.py](../../../brain/packages/core/src/cortex_core/rerank_judge.py)), so the two
  shipped consumers of the keyword are both ordinary JSON objects and the ADR's "None (every
  caller today)" is now out of date in the direction that favours the envelope.
