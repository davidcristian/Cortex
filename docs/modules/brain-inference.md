# brain/packages/inference (`cortex_inference`)

**Purpose.** The llama.cpp adapter for the core's `InferenceBackend` port (ADR-0005, ADR-0007). It
is a thin HTTP translator: it takes a GPU lease from a `ModelManager`, opens a streaming chat
completion against the leased `llama-server` endpoint over the OpenAI-compatible API, and yields the
assistant reply deltas, a reasoning model's thinking deltas (ADR-0020), any tool calls the model
makes (ADR-0009), why the completion ended when the server says (ADR-0048), and the completion's own
decode rate when the server reports one (ADR-0055 decision 4). No orchestration and no session state
(the one hard rule); the core talks only to `InferenceBackend`.

**Five modules, split by the direction a value travels.** `request.py` maps core values onto the
wire, `decode.py` maps the wire back, `backend.py` keeps what neither can own (the lease, the HTTP
call, and the order events leave in), `trace_probe.py` asks a server one question before any
request is built, and `system_probe.py` asks the leased server one before a request that opens with
several system messages. The package-internal modules have no leading underscore, since that prefix
marks a module as private to its definer.

## Public contract

`__all__` is `LlamaCppBackend`, `reads_a_trace_budget` and `TRACE_BUDGET_PROBE_TIMEOUT_S`.

`LlamaCppBackend(model_manager: ModelManager, http_client: httpx.AsyncClient, *, send_trace_budget: bool = False)`
is an `InferenceBackend`. `stream(model, messages, *, tools=(), schema=None, bounds=None)` does
this:

1. `async with model_manager.acquire(model) as lease` queues for the GPU and gets the resident
   model's endpoint, or the manager raises for a model that is not resident.
2. When the messages open with two or more system messages, asks the leased server whether its
   template renders all of them, and joins them into one where it does not (the section below).
3. POSTs `{model, messages, stream: true}` to `{lease.endpoint}/v1/chat/completions`, plus `tools`
   when any are offered, plus a `response_format` of
   `{type: json_schema, json_schema: {name: reply, schema, strict: true}}` when `schema` is set, so
   the server constrains decoding to that shape (ADR-0028). Each `Message` maps to an OpenAI
   message: `USER`, `SYSTEM` and `ASSISTANT` to `{role, content}`, an assistant with `tool_calls` to
   the OpenAI `tool_calls` array, and a `TOOL` result to `{role: "tool", tool_call_id, content}`.
4. Parses the SSE `data:` lines: each `choices[0].delta.content` becomes a `TextChunk`, streamed
   `delta.tool_calls` fragments are reassembled by index and yielded as `ToolCall`s once the stream
   ends, and `data: [DONE]` stops it. Chunks with no text (the role-only opening chunk, an empty
   delta, an empty `choices`) are skipped.
5. Yields one `DecodeStop(reason)` when a chunk's first choice has a `finish_reason` (ADR-0048),
   translating llama.cpp's word into the core's closed set: `stop` to `FINISHED`, `length` to
   `CAPPED`, `tool_calls` to `CALLED`, and anything else, a non-string included, to `UNKNOWN`. All
   three words were read off the shipped CPU tier on build `b9879-72874f559`. A `null`, which every
   chunk but the last has, and a chunk with no `choices` yield nothing, so a stream reports one stop
   and not one per chunk.
6. Yields one `DecodeCadence(tokens_per_second, tokens)` when a chunk has llama.cpp's own `timings`
   object, read from `predicted_per_second` and `predicted_n` (ADR-0055 decision 4). Exactly one
   chunk of a stream has it, the last, and it arrives unasked: read on 2026-08-08 off the build that
   named itself `b10298-15586e2d7` in its own `system_fingerprint`, and again on 2026-09-08 off
   `b10680-d7bd3bfca`. Timings are read **before** the chunk's `choices` are, so a build closing on
   `{"choices": []}` is still read. The event is emitted after the text it describes, a rate being
   unknowable before the tokens are counted.
7. Logs `model now served by engine build` at `INFO` with `model`, `endpoint` and `build` the first
   time a model's chunk names a build in `system_fingerprint`, and again whenever it names another
   (ADR-0005 decision 9). Every chunk of a `b10680-d7bd3bfca` stream has it. No event crosses the
   port, since no core decision reads a build.

**Images.** A `TOOL` or `USER` message with `images` (ADR-0029, ADR-0070) emits `content` as an
OpenAI **content-parts array** instead of a string: one `{type: "text"}` part followed by one
`{type: "image_url", image_url: {url: "data:<mime>;base64,…"}}` part per image
(`message_content`). `Message` rejects images on the other two roles, which this mapping sends as
a plain string. Measured against the real cortex: a `role: "tool"` message in that
form is accepted inside a full tool-calling exchange and answered correctly, so no user turn has to
be forged. A message with no images emits the byte-identical plain string it always did. Native tool
calling needs the server started with `--jinja` and a tool-capable chat template (gemma-4 ships
one); vision additionally needs `--mmproj`.

**The two closing events are independent.** They arrive on the same final chunk on this build but
come off different parts of it, the stop off the first choice and the cadence off the chunk, so a
build that offers one and not the other still reports what it has. Where both are present the order
is the adapter's own: text, then the stop, then the cadence, then any tool calls, which are
assembled only once the stream is over. `ChunkRead` is the record `decode.py` hands back per chunk,
and the five independent facts on it are why it is a record rather than a tuple.

**Timeouts are the injected client's.** The adapter sets none on a generation, which may
legitimately stream for a long time, and sets one only on the system message probe below; the
composition root gives the client a short connect timeout and a generous **per-read stall
ceiling** (ADR-0005 decision 7). That ceiling bounds the gap between
SSE chunks and never the request, so a reply that keeps arriving is never cut off, while one that
stops arriving fails instead of holding the model lease forever. It is sized per tier by the root
(`CORTEX_INFERENCE_STALL_TIMEOUT_S` 120 s for the resident and deep models,
`CORTEX_SUBAGENTS_STALL_TIMEOUT_S` 600 s for the CPU pool), and it has to clear the worst legitimate
**time to first token**, which is the longest silence a healthy server produces.

## Leading system messages

A turn opens with the security preamble, the recalled memory and the recap, each a system message,
and a delegated task with tools opens with the preamble and its context. Qwen3.5's template raises
on a second system message and Qwen3.6's drops a third, while gemma renders each in a turn of its
own, so the adapter asks the template rather than choosing one layout for every model (ADR-0071).

`delivers_system_messages(endpoint, model, count, client)` in `system_probe.py` POSTs `count`
system messages, each holding a distinct marker, and a user `.` to `{endpoint}/apply-template`,
with no tools and a timeout of `SYSTEM_PROBE_TIMEOUT_S` (2.0 s) on that request. It returns `True`
when the rendered `prompt` holds every marker in order, and `False` when one is missing or out of
order or the server answers 500, which it does when a template raises. Any other answer raises
`SystemProbeError`. `stream` asks inside the lease whenever `leading_system_count(messages)` is two
or more, and sends `join_leading_system(messages)` on `False` or on a failure: each text stripped of
`" \t\n\v\f\r"`, the empty ones left out, the rest joined with `\n` into one message with the first
one's stamp. A lone system message, and one after any other role, are never touched. Nothing is
cached, since the model file behind an endpoint can change under a running brain. The backend logs
`system message probe answered` at `INFO` (`endpoint`, `system_messages`, `delivers`) and
`system message probe failed; joining the leading system messages` at `WARNING` (`endpoint`,
`system_messages`, `error`), each only when an endpoint's outcome for a count changes.

## The trace budget, and why it is a constructor argument

`GenerationBounds.trace_tokens` is sent as llama.cpp's
`reasoning_budget_tokens`, a sampler the engine reads from the request body, falling back to the
tier's `--reasoning-budget` where the request names nothing (ADR-0049). It is the half of the
thinking controls a request shape cannot overrule. A build that does not parse the key **ignores it
with no error**, so the adapter sends it only when `send_trace_budget` is true, which the root decides
once from `CORTEX_INFERENCE_TRACE_LEVER` (`auto`, `on` or `off`). Two rules are checked by tests:

- a bound naming no count sends no key, whatever `thinking` says, so the setting can never quietly
  budget a user's visible trace;
- a count of zero is sent as written rather than treated as nothing asked, zero being the setting
  three shipped bounds depend on.

With the option off, the first request whose count goes unsent logs one `WARNING`,
`trace budget not sent because its setting is off`, with `model` and `trace_budget`; later ones
on the same backend log nothing. A zero sent beside `thinking=False` is not reported, because
`drain_text` already warns when a trace arrives against that switch; a zero with the switch on is
reported. The flag is read and written with no await between, so concurrent streams print one line.

`reads_a_trace_budget(endpoint, model, client)` is the capability probe, exported beside the adapter
along with `TRACE_BUDGET_PROBE_TIMEOUT_S`, the timeout the composition root gives the client it hands
in. It sends one POST with an out-of-range budget: a build that parses the key rejects it by name
(HTTP 400), and one that does not answers the completion (HTTP 200). Measured 2026-08-29 against two
real builds one minute apart, `b10666-4e97ac86e` rejecting and `b9870-2d973636e` answering. Every
failure reads as absent: unreachable, another status, or a 400 that does not name the key all leave
the request with no budget, which is the request this repo sent before the key existed. The probe
runs **once**, at wiring, because the answer is a property of a binary, where the vision probe
beside it repeats because its answer is a property of an argv.

## Error contract

Every failure crosses the `InferenceBackend` port as `InferenceError` with the cause chained:

- a `ModelManager` failure (`ModelUnavailableError` for a model that is not resident, for instance)
  is caught as `ModelManagerError` and re-raised, so the core sees only `InferenceError`;
- any transport failure or non-2xx status is caught as `httpx.HTTPError` and re-raised, with
  `_transport_failure` naming a **stall** apart from a dead server: an `httpx.ReadTimeout` means the
  client's stall ceiling fired on a server that accepted the request and then stopped sending, which
  points an operator at a different problem than nothing answering;
- a malformed streaming chunk (bad JSON, unexpected shape, non-string content) raises
  `InferenceError` directly, since a skipped chunk would drop reply text or a tool call;
- a tool call whose accumulated arguments are not valid JSON raises the **narrower**
  `MalformedToolCallError` (ADR-0048), because that fragment is the model's own tokens rather than
  the server's protocol. Measured against a real server, a cap that ends a completion inside
  `arguments` leaves 71 to 899 characters of unterminated string under `finish_reason: "length"`,
  and the `DecodeStop` has already been yielded when this raises, so a caller holding a `StopLedger`
  can pair the two into "the run was cut" rather than "the backend died". It is a subclass, so every
  `except InferenceError` still catches it;
- **the decode cadence is an exception, and a malformed one is dropped with no error.** A
  `timings` object that is missing, not an object, missing either field, holding a non-number, a
  bool (which is an `int` in Python and would otherwise arrive as 1.0 tok/s) or a negative yields no
  cadence and changes nothing else about the stream. It is a diagnostic that arrives after the
  answer, so raising over it would discard a completed reply for the sake of a measurement, and the
  core's `CadenceWatch` already reads "no cadence" as its own answer. A build that is absent, empty
  or not a string is dropped the same way and logs nothing;
- **an unreadable stop reason becomes a value.** A `finish_reason` outside the three words above, or
  one that is not a string, is neither raised nor dropped: it crosses as `StopReason.UNKNOWN`.
  Raising would cost the reply, and dropping it would file a reason this core could not read under
  the same heading as a reason nobody offered.

**A non-2xx quotes the server.** `raise_for_status` alone would report a bare status, because the
response is streamed and its body is never read, which would make the most likely misconfiguration
here (a vision request to a server started without its projector) indistinguishable from any other
failure. The adapter reads the body on a non-2xx only, quotes at most 300 characters of it, and
raises `InferenceError` with the status and that excerpt. The projector-less case was measured on
2026-08-03: llama-server answers 500 with a 151-byte JSON body naming the missing `mmproj`, so the
bound quotes the whole of it, and `test_a_projector_less_server_says_so_when_an_image_arrives`
(`integration`-marked, needing a server at `CORTEX_INFERENCE_ENDPOINT_NO_MMPROJ` started without the
`--mmproj` pair) is the warning for a llama.cpp wording change.

## Invariants

- Stateless per call: nothing about a turn outlives `stream`, and no KV cache or context is held
  here (the one hard rule). Its only other state is three log records about servers, not turns.
- **The lease is released on cancellation.** The GPU lease is a non-reentrant lock held across the
  whole streaming block, so a `CancelledError` raised mid-inference (a user Stop, a client `Cancel`,
  or an RPC teardown) propagates out through that `async with` and frees the lock before the next
  turn takes it. A Stop that freed the holder task but left the lock taken would wedge every later
  turn, so `test_cancelling_mid_stream_frees_the_model_lease` asserts that a fresh acquire returns
  at once after a mid-stream cancel.
- Real network I/O lives here and never in the core.
- Fully typed, pyright strict clean, 100% line and branch covered through `httpx.MockTransport` and
  the pure `SingleResidentModelManager`, with no GPU and no network.

## Shared contracts

Three port contracts are driven over this adapter and over a core twin: `tests/cadence_contract.py`
for the decode rate, `tests/stop_contract.py` for the stop reason, and `tests/stream_contract.py`
for the completion those two close, each run twice by its `test_*_contract.py`. All three feed the
adapter a real llama-server body, so a pass means the parser found the fact in bytes not written for
the test.

**The streaming contract states what every stream owes, and never when it owes it.** Twelve checks
over five worlds a fixture arranges (a reasoning model answering, a completion that asks for a tool,
a completion with nothing to say, a backend that cannot answer, an engine whose template refuses a
second system message): the reply is its deltas joined in arrival order; the thinking crosses as its
own kind and is over before the reply starts; a deliberation that arrived despite a request asking
for none crosses all the same, so an implementation reports what its deployment did rather than
suppressing it to match the request; a trace that arrived despite a request budgeting it to zero
tokens crosses the same way, which is a separate obligation because a count reads as a limit where a
switch reads as a request (ADR-0049); a tool call crosses whole; a tool call never precedes the
words beside it; the two closing events arrive at most once each with the stop first and both after
what they describe; a completion with nothing to say owes no event at all; an abandoned completion
costs the backend nothing; a backend that cannot answer fails its caller with `InferenceError`; a
backend answers only for a model it serves; and a request that opens with several system messages is
answered, with every system text reaching the engine in order. Nothing in it counts events, sizes
one, or asks when one arrives, because the two implementations produce them at different rates from
different sources.

**Where this adapter legitimately differs from the core's twin**, and so what the shared list does
not say:

- **A delta with no text is permitted by the port and dropped here.** llama-server opens with a
  role-only chunk and closes with an empty delta, and neither is anything a consumer can show, so
  `_chunk_events` skips them; `ScriptedInferenceBackend` yields whatever it was handed and the core
  is written for that. Making `_chunk_events` emit a delta per chunk makes 22 cases in this package
  fail, along with exactly one shared check, and that one fails for an ordering reason rather than
  an emptiness one.
- **Tool calls follow both closing events here**, because a call is only whole once the stream is
  over. The port asks only that a call never precede the words beside it, so a future backend whose
  engine hands over each call as it completes would still pass.
- **The twin's script advances per `stream` call while this adapter is stateless per call**, which
  is what makes a tool loop scriptable. No check asks an implementation to answer twice the same
  way.

## Live tests

The `integration`-marked tests, and what each one measures, are in
[brain-inference-live](brain-inference-live.md).

**Dependencies.** cortex-core (the `InferenceBackend` and `ModelManager` ports and the typed errors)
and httpx. The composition root (`cortex_orchestrator.wiring`) injects a concrete `ModelManager` and
an `httpx.AsyncClient`.
