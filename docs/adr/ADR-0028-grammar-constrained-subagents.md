# ADR-0028: Grammar-constrained subagent output

**Status:** Accepted (2026-09-13)

## Context

[ADR-0017](ADR-0017-subagent-model-safety.md) decides which model may reply: a weak,
injection-susceptible subagent model is reachable only for a subagent with no tools on an untainted
turn. It leaves open what form of output that model may emit. Even there a weak model can smuggle
content past the reader by appending a footer, a link or an extra section to an otherwise correct
answer.

llama.cpp's server supports constrained decoding: a `response_format` of
`{"type": "json_schema", "json_schema": {...}}` forces every emitted token to conform. Decoding a
subagent's reply into a fixed one-field JSON envelope leaves no grammatical position for content
outside the answer. A URL written inside the `reply` string is still grammatical; that case belongs
to the untrusted-content boundary ([ADR-0013](ADR-0013-untrusted-content.md)), since the result goes
back to the cortex, which taints it and, where the trust rules apply, redacts it. The two boundaries
combine.

Measured after the envelope shipped, the schema turned out to reach the grammar and never the model:
`POST /apply-template` renders a byte-identical prompt with the envelope and without it. On a
subtask that invites deliberation the default model then spent the field on a plan, answering one
time in four, and only words in the subtask changed that. So the contract has two halves, a grammar
the server enforces and a sentence the model reads, and the rates they produce need an instrument
whose results a check can compare. The measurements are in [reply
envelope](../readings/reply-envelope.md).

## Decision

### The envelope

1. **An added `schema` keyword on the `InferenceBackend` port, no new port.**
   `stream(model, messages, *, tools=(), schema=None)` takes an optional JSON Schema
   (`JsonSchema = Mapping[str, object]`). `LlamaCppBackend` maps a schema to `response_format`
   `{"type": "json_schema", "json_schema": {"name", "schema", "strict": true}}`, the form a live
   probe confirmed; without one, the request sends none. The fake records the keyword so the
   contract is asserted without a server. A wrapper adapter would pass the same schema to the same
   request, so the keyword is the whole interface. Two callers use it: the subagent runner, and the
   ranked recall's rerank judge, which passes `ORDER_ENVELOPE` (`{"order": [int]}`) through
   `drain_text` ([ADR-0038](ADR-0038-ranked-recall.md)).

2. **A fixed reply envelope, `{"reply": <string>}`, not a per-task schema.** `REPLY_ENVELOPE` in
   `cortex_core/subagent_reply.py` has one required string field and `additionalProperties: false`.
   A caller-supplied schema is a larger attack area (the cortex would write it, an injected
   instruction could shape it) for no gain against smuggled content, and since the model never reads
   a schema, a richer one could not explain anything to it either.

3. **Constrained only where a weak model is reachable: the path with no tools.** The attempt
   constrains when it has no dispatcher and `CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT` is on (the default);
   off restores the raw stream for the same case. Both subagent servers run `--jinja`, whose
   tool-calling grammar would compete with a JSON grammar over the same output, and limiting this to
   the path with no tools makes that impossible: a subagent with tools is forced to the
   injection-resistant model and is never constrained. The cortex turn is never constrained.

4. **The runner unwraps the envelope before storing, in a fixed order.** `settle_reply` reads a
   finished attempt in this order: a run cut at a token limit is `TRUNCATED` with the cap refusal
   (`GENERATION_CAP_MSG`), since a reply the server stopped ends mid-envelope and is not a model
   breaking its grammar; an unconstrained run passes its text through; a constrained run is
   unwrapped by `unwrap_envelope`, and an envelope that does not parse is `MALFORMED`, with the raw
   text in `output` for the store and the fixed `MALFORMED_ENVELOPE_MSG` in `detail`. The spawn
   aggregate passes a failed result's `detail` to the cortex and never its `output`, so raw,
   possibly attacker-written text stays in the store and never reaches the cortex conversation.

### The sentence

5. **What the envelope cannot say is said in the subtask, beside the grammar in the core.**
   `REPLY_INSTRUCTION` and `instruct_reply(instruction)` live in `cortex_core/subagent_reply.py`
   with both directions of the envelope, because they are one contract stated twice: once to the
   server, which enforces it, and once to the model, which reads only words. The sentence is: "Your
   entire response must be the answer itself, not the text you were given. Do not describe the task,
   plan an approach, announce what you are about to write, or repeat the input back." Each half
   names one failure: the narration the first wording was written for, and the report body handed
   back as a summary. It names the answer rather than a genre, since a subtask here is a
   summarization, an extraction or a lookup, and naming the genre gained nothing on that genre.

6. **It is appended to the instruction, last, inside the user message.**
   `task_messages(task, *, constrain)` sends `f"{task.instruction} {REPLY_INSTRUCTION}"` on the
   constrained path and exactly what the cortex wrote otherwise. Last is the position that survives
   an instruction the cortex composed out of content it read, and a subtask is one request. Decision
   3 applies the sentence to exactly the runs the envelope reaches, so the halves cannot come apart.

7. **It has no setting of its own.** `CORTEX_SUBAGENTS_CONSTRAIN_OUTPUT` turns the grammar and the
   sentence off together. A deployment that wants the raw stream back wants the raw contract back,
   and a setting that left the grammar on with the sentence off would reproduce a measured defect.
   The comparison a measurement needs is a variant in the test driver (decision 10).

8. **One wording ships to every roster entry.** A per-entry wording on `SubagentProfile` is
   declined. A roster entry is a name over an endpoint (`subagent` from the flat
   `CORTEX_SUBAGENTS_*` environment, `qwen` from `docker/docker-compose.subagents-roster.yml`);
   which GGUF runs there is a `command:` argument of a `llama-server` container that nothing in the
   brain reads, so a wording stored under a name would describe whatever weights the operator
   started. It would ship empty on every shipped stack, nothing measured says what to put in it, and
   an empty override is decision 7's rejected setting made per entry. The entries do differ: the
   sentence is a large improvement on the default model, and on the roster alternate it beats the
   first wording but not the envelope alone
   ([R-657](../refinements/tasks/657-the-roster-alternate-hands-the-report-back-under-the-new-sentence.md)).
   Reopened by a wording measured to recover a failing entry without costing another of its subtask
   kinds, by a roster entry that fixes its model file
   ([R-508](../refinements/tasks/508-a-roster-entry-names-an-endpoint-and-not-a-model.md)), or by a
   stack shipping a failing model as a roster entry instead of an override.

9. **A reply that is not an answer is not detected by the runner, and stays `ok=True`.** Nothing in
   the core can tell a plan from an answer without judging prose. A keyword detector misfires on an
   answer whose subject is a request, and destroying an answer the cortex had is worse than passing
   a non-answer. A structural detector cannot exist, since the problem is specific to a field whose
   value is prose (a layout like `ORDER_ENVELOPE` leaves a preamble nowhere to go). A second
   completion on the same tier, asked whether its reply answered, was measured against a standard
   written first and fails it on every model: the default model's judge calls one answer in five a
   non-answer, and on the Qwen entries its results do not separate the two populations. Comparing a
   reply with the context it was given is the remaining option for the copy case, in R-657.

### The envelope measurement

10. **One committed test driver runs the variants.**
    `brain/packages/orchestrator/tests/test_envelope_cost_live.py` runs the shipped `SubagentRunner`
    over four report bodies. Its variants (`CORTEX_ENVELOPE_ARMS`) are `raw` (no schema, no
    sentence), `constrained` (the shipped path), `bare` (the shipped path with the sentence removed
    on the wire, asserting it removed one), and `described` and `prefaced`, which vary the schema. A
    subtask is given by `CORTEX_ENVELOPE_INSTRUCTION`, so a candidate wording can be measured
    through `bare` without editing a constant. Seeds, their pairing and placement at `-ngl 99`
    follow [ADR-0050](ADR-0050-live-probe-records.md) decisions 7 to 9. The driver writes one sample
    per variant under the ignored `measurements/`, recording per turn the instruction it sent and
    the body (`context`) it sent it about, and per sample whether the variant is the `control`, the
    one whose request has no schema. It computes no rate.

11. **A fully covered reader publishes the comparison or refuses.** `just envelope-floor` runs
    `scripts/envelopefloor.py`, with `scripts/envelopesamples.py` reading the sample format and
    `scripts/envelopejudges.py` the judges. An assertion inside the integration-marked driver would
    be code no check runs; the refusal belongs where the comparison is published. Exit 0 means
    published, 1 refused (no control variant, or one proven under the minimum), 2 could not read a
    sample. A sample missing `instruction`, `context` or `control` is refused by name, which is what
    holds the driver to its half of the contract.

12. **Two rates per cell.** A run passed (published as `stood`) when it shows none of four faults,
    checked in order: `refused` (the runner said so, whatever the text contained), `empty`, `echo`
    (the reply equals the instruction over letters and digits) and `copy` (decision 15). A reply
    `delivered` when the judge declared for its subtask kind reads it as an answer. On the declared
    kinds `stood` bounds `delivered` from above: a refused run, an empty reply and a copy deliver
    nothing, and no instruction contains the body's numbers or period, so an echo fails.

13. **The control variant must reach nine tenths, one-sided, per subtask kind.** A cell is refused
    only when its whole Wilson 95% interval lies under `FLOOR = 0.9`: at 32 runs that is 25 or
    fewer, at 96 it is 80, and at four runs half must fail. Refusing on a point estimate would fail
    a long measurement on sampling noise. Below nine tenths a control does no better than the
    envelope variants it exists to explain, whose worst cells sat at 66 and 70 of 96. The minimum
    applies per subtask kind, since a model at the top on one kind and at the bottom on another has
    an average that describes neither, on both rates (`delivered` only where a judge is declared),
    and the result is taken under the tabled reading whatever columns the flags print. The control
    is the sample's `control` field, not a variant name; a run with no control is refused as no
    comparison, and there is no `--floor`.

14. **A judge is declared per subtask kind, beside the instruction.** `JUDGES` holds four kinds:
    "Summarize the report below, keeping every detail", "Summarize the report below, keeping its
    figures" and "Extract every number from the report below", judged by number recall against the
    body at a half threshold, and "What reporting period does the report below cover", judged by the
    body's own reporting period named back. A run belongs to a kind when its instruction opens with
    it, so the variant with the sentence and the variant without it share a judge. Any other
    instruction is judged by nothing and its cell publishes `stood` alone beside the line
    `no judge is declared for this shape`. The three decisions the hand-read tables made are stated
    columns, each a `Reading` field and a flag, `--comma` (default charitable, the better of reading
    a comma as a thousands separator or a list separator), `--refusal` (default strict, a refused
    run is a non-delivery) and `--naming` (default strict, the period as the body writes it), and
    every report begins with the reading it used. A flag moves a column and never a result.

15. **The body handed back is a fault.** `copied(reply, body)` scores the two with
    `difflib.SequenceMatcher` over letters and digits, its popular-character heuristic off, and a
    score of at least `COPIED = 0.9` is a copy; a reply more than about a fifth shorter or longer
    than its body cannot reach it. The threshold is the top of the band where rewordings a reader
    accepted and one a reader called a copy sit together, so it is not fitted to one reader's
    leniency. A copy delivers nothing under every reading, since it contains every number its body
    states. It is checked on every declared kind, the lookup included, and on no other, because a
    hand-typed instruction may ask for the body back.

16. **A lookup reply naming an instance its body does not state is not the period.** `invents` reads
    four kinds of instance, a capitalised month name, a year from 1900 to 2099, a day ordinal, and a
    numbered period of the body's unit; one is invented when the body does not state it. An instance
    the body states elsewhere may come back as evidence, and the body's own period number may come
    back as a day or a numbered period. `names_the_period` returns a naming only when the reply
    invents nothing, under both naming columns.

## Consequences

- **Covered in CI:** the keyword through the port and the fake; the request mapping, with and
  without a schema; the runner's wrap, sentence, unwrap and settling order, with three unit tests in
  `brain/packages/core/tests/test_runner.py` asserting that a constrained request includes the
  sentence and an unconstrained or tool-enabled one does not; the setting's wiring; and the reader
  modules under `scripts/tests/`.
- **Live, integration-marked:** `test_constrained_decoding_kills_format_laundering_on_the_weak_tier`
  in `brain/packages/inference/tests/test_backend_live.py` sends an "append this footer" injection
  to the weak tier. Unconstrained, the tier obeys it; constrained, it returns a single well-formed
  envelope. It asserts the structural guarantee, which no envelope measurement since has broken:
  every constrained reply decoded into the envelope it was asked for. Steps in
  [subagents-cpu](../runbooks/subagents-cpu.md).
- **The rates are measurements of one engine image and one set of report bodies.** The current
  table, its image and the per-model copy and reasoning-channel counts are in [reply
  envelope](../readings/reply-envelope.md); the subagent runbook's override table quotes them beside
  the conditions they were measured under. An image update reopens every cell, and on the current
  table the smallest model's lookup control falls under the minimum, so that comparison is refused.
- **The usual failure is not reported.** On every model most constrained non-deliveries come back
  `ok=True`, a copy or a plan handed to the cortex as an answer. Reading a delegated answer stays
  the operator's check, and on the Qwen entries a cap refusal on narrow work is a numeric runaway,
  never the reasoning channel.
- **The reader finds faults a machine can name and judges three kinds of subtask.** A reply's form
  or role (a summary where an extraction was asked, a span the body does state given the wrong role)
  is outside it ([R-639](../refinements/tasks/639-the-envelope-judges-read-no-form.md)), and the
  subtask kinds are written in the driver and in `JUDGES` with nothing comparing the two
  ([R-541](../refinements/tasks/541-the-measured-subtask-instructions-are-written-in-two-trees.md)).
- **Deferred until a consumer exists:** a raw GBNF `grammar`
  ([R-069](../refinements/tasks/069-raw-gbnf-alternative.md)), needed by the first constrained
  caller whose output JSON cannot express. It is not a keyword: a grammar is a string, so the port
  widens, `build_payload` gains a branch and `settle_reply` a second path, and decision 3 still
  applies. A per-task caller schema ([R-070](../refinements/tasks/070-per-task-caller-schema.md))
  waits for a structured-result feature. Constraining a reasoning stream is moot while the subagent
  tier runs with thinking off.

## Alternatives rejected

- **A raw GBNF grammar instead of the envelope**: the envelope is the whole requirement, and JSON
  schema is the portable way to write it. **Constraining every subagent**: no benefit on the
  injection-resistant model, and it would have to combine with the tool-calling grammar. **A
  `ConstrainedBackend` wrapper**: see decision 1.
- **Explaining the field in the schema**: a `description` on `reply`, and a required field ahead of
  it for narration, changed the answer rate by nothing; the model narrated into both.
- **A per-entry wording, a setting for the sentence, a keyword or same-tier detector**: see
  decisions 7, 8 and 9.
- **"The control variant must lead"**: the largest model's constrained variant once delivered more
  than its own raw variant, so the rule would fail on a true result. **A `--floor` setting**: the
  reader who reaches for it is the one whose control just failed.
- **A judge per run, another completion as the judge, or matching a subtask kind by equality**: the
  first is a hand-written result with nothing tying it to its reply, the second a measurement with
  its own failure rate inside the first, and the third would declare a judge for the control and
  none for the variant with the sentence.
- **Exempting the lookup from the copy fault**: a lookup answered with the whole body names the
  body's period and would pass; the fault cannot misfire on a correct lookup answer.

## Related

- [ADR-0017](ADR-0017-subagent-model-safety.md) (which model),
  [ADR-0013](ADR-0013-untrusted-content.md) (content inside the field),
  [ADR-0004](ADR-0004-model-lineup.md) (the subagent models the rates describe),
  [ADR-0018](ADR-0018-heterogeneous-subagents.md) (the roster),
  [ADR-0048](ADR-0048-generation-bounds.md) (the cap),
  [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md) (the reasoning channel under a schema),
  [ADR-0050](ADR-0050-live-probe-records.md) (seeds, pairing, placement),
  [ADR-0059](ADR-0059-prompt-cache-per-tier.md) (the prompt cache the subagent servers turn off).
- Modules: [brain-core](../modules/brain-core.md), [brain-inference](../modules/brain-inference.md),
  [repo checks](../modules/repo-checks.md) (the envelope readers).
- Runbook: [subagents-cpu](../runbooks/subagents-cpu.md) (the live probe, the measurement run and
  the override table). Measurements: [reply envelope](../readings/reply-envelope.md).
