# ADR-0071: Leading system messages a template cannot take

**Status:** Accepted (2026-09-26)

## Context

The core opens a request with up to three system messages, each a typed `Message` of its own. A
cortex turn and the deep phase send the security preamble, then the recalled memory when recall
found something, then the recap `SummarizingHistoryWindow` puts first once the window has folded
older turns (`assemble_inference_messages` in `turn_context.py`). The window is on by default, so
a long conversation has a recap even when nothing was recalled. A delegated task sends two when it
has tools and an untainted context: the preamble, then the context (`task_messages` in
`subagent_attempt.py`). `build_payload` mapped each to its own `role: "system"` message.

What a chat template does with the second and third differs by family, measured on
`b10680-d7bd3bfca` ([system message templates](../readings/system-message-templates.md)):

- **gemma-4**, every pick, renders each in a system turn of its own.
- **Qwen3.8** merges every leading one into one system turn.
- **Qwen3.6** and the Qwen3.5-9B file in the MTP folder merge the first two and drop the third
  without an error. On the deep alternate, Qwen3.6-27B, a recalling deep turn lost its recap.
- **Qwen3.5**, one template across 0.8B, 2B, 4B and 9B, raises `System message must be at the
  beginning.`, which the server answers as HTTP 500. On the cortex alternate, Qwen3.5-9B, every
  turn with a memory or a recap failed. A tool task with a plain context failed wherever a Qwen3.5
  file served the default subagent entry, which the override table offers. The roster alternate
  was never reached this way: `SubagentRoster.resolve` sends a task with tools, or a tainted one,
  to the default entry.

`GET /props` cannot tell these apart: `chat_template_caps.supports_system_role` is true for all
six templates. And `ScriptedInferenceBackend` accepted a request the real stack refused, so no core
test could fail on it.

## Decision

1. **The core keeps the system messages separate.** The preamble, the memory, the recap and a
   task's context are different things with different framing, and whether a template takes two
   of them is a property of one GGUF's template. Engine facts stay in the adapter
   ([ADR-0005](ADR-0005-llamacpp-engine.md) decision 10).

2. **The adapter joins a leading run of two or more system messages, only where the leased server
   does not render every one of them in order.** A request with one system message, and a system
   message that follows any other role, are sent as they are. So the gemma picks, Qwen3.8, and
   Qwen3.6 at two messages receive the bytes they received before this record.

3. **It asks the leased server on every such request.** Inside the model lease, before the
   completion, `delivers_system_messages` (`system_probe.py`) sends one `POST /apply-template` to
   `lease.endpoint`: as many system messages as the request opens with, each holding a distinct
   marker, then a user message `.`, with no tools and no template arguments, and a 2.0 s timeout of
   its own. `/apply-template` renders the template and nothing else: it takes no slot and decodes
   nothing, so it answers while a one-slot server is decoding. The answer is not cached, because
   the file behind an endpoint can change while the brain runs (the model host restarted with
   another `CORTEX_MODEL_FILE_*`, or a subagent server recreated from an override), and a stale
   "renders" would fail every such turn on Qwen3.5 or drop the recap without a sign on Qwen3.6.

4. **What counts as an answer.** HTTP 200 whose `prompt` holds every marker, each after the one
   before it, means the template renders them: send the messages unchanged. HTTP 200 with a marker
   missing or out of order, or HTTP 500, which the engine answers when a template raises, means it
   does not: join. Anything else is a failure: another status, a transport error, a body that is
   not JSON or has no `prompt` string. A failure joins too and logs a warning, since every template
   takes one system message and the join is the request that cannot fail for this reason.

5. **The join.** Each text in the run is stripped at both ends of `" \t\n\v\f\r"`, the bytes the
   engine's Jinja `trim` removes (C `isspace`); `str.strip()` would also remove Unicode spaces the
   engine keeps. A text that is empty after stripping is left out, and the rest are joined with one
   `\n`, in the core's order: preamble, memory, recap for a turn, preamble and context for a task.
   That is byte for byte what Qwen3.6 renders for two separate messages and what Qwen3.8 renders for
   two and three; a blank line between them matches no template. The joined message has the first
   message's timestamp and turn id.

6. **No setting.** A switch to force the join everywhere would change the gemma picks' prompts,
   and one to turn it off would bring the failures back, so neither is offered.

7. **The port says it.** The stream contract (`tests/stream_contract.py`) holds a twelfth
   obligation over a fifth world: a request that opens with several system messages is answered,
   and the engine receives every system text in the core's order, run against an engine whose
   template refuses a second one. The world records what the engine received: the body the
   adapter posted, with the texts joined, and the messages the core's twin was handed, unchanged.

8. **The log says which layout an endpoint got.** `system message probe answered` at `INFO`, with
   `endpoint`, `system_messages` and `delivers`, and `system message probe failed; joining the
   leading system messages` at `WARNING`, with `endpoint`, `system_messages` and `error`. Each is
   written when the outcome for an endpoint and a count changes, not on every request.

## Consequences

- Every measured row stays valid: a server whose template renders every system message, the gemma
  picks and Qwen3.8 among them, gets the request it got before, so the injection, recap preface and
  envelope readings describe what it receives. A failed probe is the exception: it joins that one
  request, and the warning names the endpoint.
- A completion that opens with two or more system messages costs one extra render request. The
  worst of 240 probes over four servers, idle and beside a generation, was 0.013 of the timeout.
- Production has two layouts, and only the probe's log line shows which one an endpoint receives.
- The joined layout has no injection or framing measurement on the Qwen alternates
  ([R-744](../refinements/tasks/744-the-joined-system-message-is-unmeasured-on-the-qwen-alternates.md)).
- On a turn that also recalls a memory, the deep alternate's prompt now includes the recap it used
  to drop, up to `RECAP_MAX` (2000 characters) plus the preface, against its 8192-token context;
  the fit is
  [R-736](../refinements/tasks/736-the-deep-phase-sends-a-history-window-sized-for-the-cortexs-context.md)'s
  subject.
- A template that rendered every marker outside the system role would read as rendering them. None
  of the six does.
- On a joining endpoint the memory and the recap fall inside what the preamble calls "this system
  message", the one text besides the user's own messages it lets direct the model. The fenced
  memory and the recap keep their fences and prefaces byte for byte, but the trusted memory lines,
  which include earlier assistant replies (`render_exchange`), sit inside it unfenced. Qwen3.6 at
  two messages and Qwen3.8 at two and three already render this layout on their own. No reading
  covers it
  ([R-744](../refinements/tasks/744-the-joined-system-message-is-unmeasured-on-the-qwen-alternates.md)).
- A stored system message next to the prefix would be joined into the preamble's message. No
  writer stores one, and the codecs still decode one
  ([R-743](../refinements/tasks/743-the-session-and-handoff-codecs-decode-a-system-role-no-writer-stores.md)).

## Alternatives rejected

- **Joining for every model.** It changes both gemma picks' prompts on every turn with a memory or
  a recap, to fix alternates no default deploys. That would need a paired draw on each tier, as a
  new wording of model-read text does ([ADR-0040](ADR-0040-prose-and-comment-style.md)), and the
  last such draw, of the recap preface, failed its fixed count at 4 obeyed of 110 against 1. On a
  turn whose memory changed and whose text after the memory fits in about one micro-batch, it also
  costs the 12B its reuse of the tool declarations: 2961 tokens reused against 1. Past that size
  the engine's sliding-window cache cannot go back to the tool block from the slot in either
  layout, and neither was drawn at a default turn's size
  ([readings](../readings/system-message-templates.md#what-joining-would-cost-gemma-2026-09-26)).
- **A system-context value in the core.** It moves one engine family's template limit into the
  core, with the same cost on gemma.
- **`chat_template_caps` from `GET /props`.** It reports the system role for every template.
- **A per-tier flag, or a table of template hashes.** Either drifts from the file actually served;
  the Qwen3.5-9B file in the MTP folder has a template of its own.
- **A probe at boot, or a cache per endpoint.** Stale once a model file changes.
- **Retrying a 500 with the messages joined.** It misses Qwen3.6, which answers 200 and drops the
  recap.
- **A task's context in the user message.** The subagent pick obeyed an injection there on 42 of 74
  draws, against 29 of 75 as a system message
  ([subagent CPU rows](../readings/subagent-cpu-rows.md#framing-a-tainted-tasks-context)).
- **Never deploying the Qwen alternates with recall.** The recap alone fails Qwen3.5-9B, and the
  window is on by default.

## Related

[brain-inference](../modules/brain-inference.md), [system message
templates](../readings/system-message-templates.md), [ADR-0004](ADR-0004-model-lineup.md) (the
alternates), [ADR-0013](ADR-0013-untrusted-content.md) (the preamble and the fences),
[ADR-0038](ADR-0038-ranked-recall.md) (the recap), [ADR-0068](ADR-0068-port-contract-lists.md)
(the stream contract), [subagents on the CPU](../runbooks/subagents-cpu.md).
