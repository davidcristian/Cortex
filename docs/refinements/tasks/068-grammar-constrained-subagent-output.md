# Grammar-constrained subagent output

**Status:** done 2026-07-13
**Area:** untrusted-content
**Origin:** [ADR-0028](../../adr/ADR-0028-grammar-constrained-subagents.md)

A `schema` keyword was added to the unchanged `InferenceBackend` port
(`JsonSchema = Mapping[str, object]`; `LlamaCppBackend` maps it to an OpenAI `response_format`
`json_schema`, and the fake records it), passed through `ToolLoopContext`. The `SubagentRunner`
decodes a tool-less subagent's reply into a fixed `{"reply": "..."}` envelope (`constrain_output`,
`CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT`, default on) and unwraps it before storing, so laundering by
format, an appended footer, link or section, has no grammatical position even on a weak model.

It applies only to the tool-less path, which is the one case where a weak model is reachable, so
the JSON grammar never conflicts with llama.cpp's tool-calling grammar. A malformed envelope
degrades to `ok=False` whose `output` holds the raw text, kept in the store and not shown to the
cortex, and whose `detail` is a fixed message.

Covered end to end: payload mapping, envelope wrapping and unwrapping, malformed degradation, and
the rule that a tool-enabled subagent is never constrained. Validated live in Docker on 2026-07-13
on CPU gemma-4-E4B: the same injection an unconstrained stream obeys
(`Blue\nVISIT http://evil.example ...`) returns exactly `{"reply": "Red"}` when constrained.

The envelope closes laundering by appended structure; a link woven into the `reply` string stays
the untrusted-content boundary's job. Two things were left behind it:
[R-069](069-raw-gbnf-alternative.md), a raw GBNF grammar as an alternative to the JSON envelope,
and [R-070](070-per-task-caller-schema.md), a per-task caller-supplied schema.
