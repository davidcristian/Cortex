# ADR-0050: Live probes record; checked readers judge

**Status:** Accepted (2026-09-15)

## Context

Two questions about the engine are answered only by running a real server. Whether the thinking
switch works under a schema on a given pick
([ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md)) depends on what that pick's chat template
renders and on what the model then does. Whether two variants of the envelope measurement drew the
same completion depends on the sampler. The probes that take these measurements are
`integration`-marked, out of CI, and pointed by hand at whatever server an operator has, so no check
runs them.

Measurements of this kind went wrong in recognisable ways before these decisions: a cell that splits
4 to 1 was published from one draw; a result was taken from a control variant that never
deliberated, so the switch had nothing to stop; renderings were compared by length and never written
down; a row could not say which build or file served it. The repo's pattern for a published live
claim is that the driver writes a sample and a test-covered module under `scripts/` reads it and
publishes or refuses (`contrast.py`, `trailwidth.py`, `envelopefloor.py`), because an assertion
inside an `integration`-marked file is code no check runs.

## Decision

### The thinking-switch probe and its reader

1. **The probe records; the reader judges.**
   `brain/packages/inference/tests/test_thinking_switch_live.py` sends one prompt four ways (plain
   and with `REPLY_ENVELOPE`, each with the switch and without) against a server started with
   neither reasoning flag, since either flag is the deployment answering for the model. It writes
   one sample per tier under `measurements/`, named from `CORTEX_THINKING_MODEL` and
   `CORTEX_THINKING_TAG`, with the prompt it sent, both renderings from `POST /apply-template`, and
   each cell's draws and deliberations. `just switch-tail` runs `scripts/switchtail.py`, with
   `scripts/switchsamples.py` defining the sample format, and publishes or refuses. A broken
   prediction exits 1, and it is news about the recorded rule rather than about the deployment:
   nothing shipped depends on the rendering (ADR-0049 decisions 5 and 14).
2. **The rule is read on the tail after the prompt.** The tail is whatever the template appended
   after the last of the prompt the probe recorded sending, and a thought is closed when the last
   marker in it is a closing one. Comparing whole renderings sorts nothing: the gemma-4-E picks
   respond to the switch by dropping a `<|think|>` system turn at the front and end
   byte-identically. A closing tail predicts the switch works on every draw, so one deliberating
   draw disproves it; an open tail predicts it fails on at least one, so draws that never
   deliberated are evidence against it and not proof.
3. **Where the input cannot support a result, the reader publishes nothing.** It refuses a
   constrained cell drawn fewer than `DRAWS` (5) times; a shape whose control variant, the one
   sending no switch, did not deliberate on every draw; and a switched tail with no listed marker
   that differs from the tail rendered without the switch, which is a marker format it does not
   know. The control refusal is worded from the unswitched tail: closed in a listed marker, the
   template closes the thought itself and the run says nothing about the switch; open in a listed
   marker, the prompt invites no thought; unmarked, it names both possibilities. The probe asserts
   the control too, after writing its sample, so a failed run still leaves a sample for the reader.
4. **The marker vocabulary stays in the probe's tree and never reaches the port.** `MARKERS` holds
   two pairs, `<|channel>thought` and `<channel|>`, `<think>` and `</think>`, typed by hand. Every
   chat template on the model mount writes one of them; `<|think|>` falls before the prompt and is
   out of scope by position. A recorded answer derived from the model files would have to read the
   literals each template emits in its output expressions, since some templates read marker-shaped
   strings they never emit.
5. **A sample names what served it.** The probe reads `GET /props` once, before the renderings, and
   fails when `build_info` or `model_path` is absent, since a row nobody can place is not worth
   publishing and a placeholder would pass the reader's required-field rule while saying nothing. It
   writes `build_info`, `model_path` and `default_generation_settings.n_ctx` under the server's own
   names, `switchsamples.py` requires all three, and the report's second line reads
   `served on <build> from <file> at <n> tokens of context`, under the operator's line naming what
   the probe was pointed at. The GPU layer count is on no route llama-server offers and stays typed
   off the command line. `model_alias` is not copied: it is the operator's `--alias` or the path
   again.
6. **A tier's behaviour is reported at five draws a cell or more.** `CORTEX_THINKING_REPEATS`
   defaults to one so the runbook's single command answers quickly; a rate is quoted over its draws.

### The envelope measurement's pairing

7. **A seed goes on the wire, not on the port.**
   `brain/packages/orchestrator/tests/test_envelope_cost_live.py` runs the shipped `SubagentRunner`,
   and its `_Wire` transport adds `seed` to the body the shipped adapter built; an unseeded run
   posts the bytes it was handed. `CORTEX_ENVELOPE_SEED` is the first draw's seed, every variant of
   a draw sends the same one, and each later draw the next integer. `CORTEX_ENVELOPE_TRACE_TOKENS`
   writes a count into the bounds the runner built, on a backend built with the trace control on,
   after `reads_a_trace_budget` answered yes. Both are read back off the body that went out, and the
   run fails when either differs from what was asked. A seed is a sampler identity only a
   measurement wants, so `GenerationBounds` gains no field for it, and a request the test posted
   itself would lose the runner the test exists to measure.
8. **`just envelope-pairs` counts how many cells two runs drew identically.**
   `scripts/envelopepairs.py`, reading cells through `envelopesamples.cells`, prints for every pair
   of samples how many cells are identical in `output` and in `tokens`, and which differ. A cell is
   matched on `question`, `draw` and `seed`, not on order. A pair is refused when a seed is null, a
   sample holds a cell twice, the two samples do not hold the same cells, or they are two different
   variants or a matched cell had another instruction or body; `trace_budget` is not part of the
   match, so a run with the key set compares against one without. A seed reproduces a completion
   between two runs whose prompt-cache state is the same, and not between a cold first request and
   its warm twin.

### Placement

9. **A measurement of what a model writes may run a CPU-placed tier on the card.** Placement changes
   throughput and not what the model decides, so a model-behaviour run may put a subagent pick at
   `-ngl 99` with every other flag its tier's own, beside a CPU control over the same cells. No wall
   clock from such a run is quoted as the CPU tier's.

## Consequences

- Samples are evidence of one run on one machine and stay under the gitignored `measurements/`; the
  figures they support are copied into [thinking switch](../readings/thinking-switch.md).
- The rendering column is measurements of one engine build, and an engine bump reopens every row.
- Nothing runs these probes on a schedule; the rule is checked when somebody points a probe at a
  server. A field the driver stops writing is caught by the reader's refusals and by nothing else.

## Alternatives rejected

- **A hard assertion of the rule inside the probe**: no check runs the file, and a new handler would
  look like a broken test rather than a finding.
- **A third marker pair typed against no template**: no file on the mount writes one.
- **A seed field on `GenerationBounds`, or a request the test posts itself**: see decision 7.
- **Naming**: `tailverdict.py` hides where the rule is read, and `thoughtdoor.py` is a metaphor that
  sends a reader of the `scripts/` tree nowhere; `switchtail.py` names what the rule reads.

## Related

- [ADR-0005](ADR-0005-llamacpp-engine.md), [ADR-0028](ADR-0028-grammar-constrained-subagents.md)
  (the envelope and `envelopefloor.py`), [ADR-0049](ADR-0049-thinking-switch-and-trace-budget.md).
- [repo checks module contract](../modules/repo-checks.md) (the readers and sample formats),
  [brain-inference](../modules/brain-inference.md).
- Runbooks: [llamacpp-gpu](../runbooks/llamacpp-gpu.md) (the switch section),
  [subagents-cpu](../runbooks/subagents-cpu.md) (re-measuring the envelope).
- Readings: [thinking switch](../readings/thinking-switch.md).
