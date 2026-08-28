# brain/packages/inference (`cortex_inference`)

**Purpose.** The llama.cpp adapter for the core's `InferenceBackend` port (ADR-0005,
ADR-0007). A thin HTTP translator: it takes a GPU lease from a `ModelManager`, opens a
streaming chat completion against the leased `llama-server` endpoint over the
OpenAI-compatible API, and yields the assistant reply deltas, a reasoning model's thinking
deltas (ADR-0020), any tool calls the model makes (native function-calling, ADR-0009), why the
completion ended when the server says (ADR-0005 finish-reason addendum), and the
completion's own decode rate when the server reports one (ADR-0030 spill-watch addendum).
No orchestration, no session state (the one hard rule). The core keeps talking only to
`InferenceBackend`.

**Three modules, split by the direction a value travels.** `request.py` maps core values onto
the wire, `decode.py` maps the wire back, and `backend.py` keeps what neither can own: the lease,
the HTTP call, and the order events leave in. The split happened when the cadence arm took
`backend.py` to the 300-line cap. The two halves are package-internal (nothing but
`LlamaCppBackend` is exported) but not underscored, a leading underscore being exactly the thing
that would forbid the adapter from importing them.

**Public contract** (everything importable from `cortex_inference`; `__all__` is the API):

- `LlamaCppBackend(model_manager: ModelManager, http_client: httpx.AsyncClient)` is an
  `InferenceBackend`. `stream(model, messages, *, tools=(), schema=None)`:
  1. `async with model_manager.acquire(model) as lease` queues for the GPU, gets the
     resident model's endpoint (or the manager raises for a non-resident model).
  2. POSTs `{model, messages, stream: true}` (plus `tools` when any are offered, plus a
     `response_format` of `{type: json_schema, json_schema: {name: reply, schema, strict: true}}`
     when `schema` is set, so the server constrains decoding to that shape, ADR-0028) to
     `{lease.endpoint}/v1/chat/completions`, mapping each `Message` to an OpenAI message:
     `USER`/`SYSTEM`/`ASSISTANT`→`{role, content}`, an assistant with `tool_calls`→the
     OpenAI `tool_calls` array, and a `TOOL` result→`{role: "tool", tool_call_id, content}`.
     A `TOOL` message carrying `images` (ADR-0029) emits `content` as an OpenAI
     **content-parts array** instead, and a tool message is the only one that can carry them
     (`Message` refuses images on every other role precisely because this mapping would drop
     them): one `{type: "text"}` part followed by one
     `{type: "image_url", image_url: {url: "data:<mime>;base64,…"}}` part per image. Measured
     against the real cortex: a `role: "tool"` message in that form is accepted inside a full
     tool-calling exchange and answered correctly, so the picture rides the message that
     *answers* the tool call and no user turn has to be forged. A message with no images emits
     the byte-identical plain string it always did, so a text-only deployment pays nothing.
     Native tool calling needs the server started with `--jinja` and a tool-capable chat
     template (gemma-4 ships one); vision additionally needs `--mmproj`, which the model host
     adds when `CORTEX_MMPROJ_FILE_CORTEX` names a projector.
  3. Parses the SSE `data:` lines: yields each `choices[0].delta.content` as a `TextChunk`,
     reassembles streamed `delta.tool_calls` fragments (id/name/arguments accumulated by
     index) and yields them as `ToolCall`s once the stream ends, and stops at
     `data: [DONE]`. Chunks with no text (the role-only opening chunk, an empty delta, an
     empty `choices`) are skipped.
  4. Yields one `DecodeStop(reason)` when a chunk's first choice carries a `finish_reason`
     (ADR-0005 finish-reason addendum), translating llama.cpp's word into the core's closed set:
     `stop`→`FINISHED`, `length`→`CAPPED`, `tool_calls`→`CALLED`, and anything else, a value that
     is not even a string included, →`UNKNOWN`. All three words were read off the shipped CPU tier
     on build `b9879-72874f559`. `null`, which every chunk but the last carries, and a chunk with
     no `choices` at all yield nothing, so a stream reports one stop and not one per chunk.
  5. Yields one `DecodeCadence(tokens_per_second, tokens)` when a chunk carries llama.cpp's own
     `timings` object, read from `predicted_per_second` and `predicted_n` (ADR-0030 spill-watch
     addendum). On build `b10298-15586e2d7` exactly one chunk of a stream carries it, the last,
     and it arrives unasked, so no request changed to get it. Timings are read **before** the
     chunk's `choices` are, so a build closing on `{"choices": []}` is still heard. The event is
     emitted after the text it describes, a rate being unknowable before the tokens are counted.
  - **The two closing events are independent.** They ride the same final chunk on this build but
    come off different parts of it, the stop off the first choice and the cadence off the chunk,
    so a build that offers one and not the other still reports what it has. Where both are
    present the order is the adapter's own: text, then the stop that explains where the text
    ended, then the cadence that closes the stream, then any tool calls, which are assembled only
    once the stream is over. `ChunkRead` is the record `decode.py` hands back per chunk, and the
    four independent facts on it are why it is a record rather than a tuple.
  - The injected `http_client` owns timeouts/transport (the adapter sets none itself because a
    generation may legitimately stream for a long time; the composition root gives it a short
    connect timeout and a generous **per-read stall ceiling**, ADR-0005 stall-ceiling addendum).
    That ceiling bounds the gap between SSE chunks and never the request, so a reply that keeps
    arriving is never cut off however long it runs, while one that stops arriving fails instead
    of parking the model lease forever. It is sized per tier by the root
    (`CORTEX_INFERENCE_STALL_TIMEOUT_S` 120 s for the resident and deep models,
    `CORTEX_SUBAGENTS_STALL_TIMEOUT_S` 600 s for the CPU pool), and it has to clear the worst
    legitimate **time to first token**, which is the longest silence a healthy server produces.

**A non-2xx quotes the server.** `raise_for_status` alone would report a bare status, because
the response is streamed and its body is never read, which makes the most likely
misconfiguration on this path (a vision request to a server started without its projector)
indistinguishable from any other failure. The adapter reads the body on a non-2xx only, quotes
at most 300 characters of it, and raises `InferenceError` with the status and that excerpt.
Reading it there is safe precisely because the request has already failed. That projector-less
case was measured on 2026-08-03: llama-server answers 500 with a 151-byte JSON body naming the
missing `mmproj`, so the bound quotes the whole of it, and
`test_a_projector_less_server_says_so_when_an_image_arrives` (integration-marked, needing a server
started without the `--mmproj` pair at `CORTEX_INFERENCE_ENDPOINT_NO_MMPROJ`) is the canary for a
llama.cpp wording change.

**Error contract.** Every failure crosses the `InferenceBackend` port as `InferenceError`
with the cause chained:

- a `ModelManager` failure (e.g. `ModelUnavailableError` for a non-resident model) is
  caught as `ModelManagerError` and re-raised, so the core sees only `InferenceError`;
- any transport or non-2xx status is caught as `httpx.HTTPError` and re-raised, with
  `_transport_failure` naming a **stall** apart from a dead server: an `httpx.ReadTimeout` means
  the client's ceiling fired on a server that took the request and then went quiet, which sends
  an operator somewhere else entirely than "nothing answered" does;
- a malformed streaming chunk (bad JSON, unexpected shape, non-string content) raises
  `InferenceError` directly, since a silently skipped chunk would drop reply text or a tool call,
  the same fail-loud stance the session store takes on corrupt records;
- a tool call whose accumulated arguments are not valid JSON raises the **narrower**
  `MalformedToolCallError` (ADR-0005 tool-call-cut addendum), because that fragment is the model's
  own tokens rather than the server's protocol: measured against a real server, a cap landing mid
  `arguments` leaves 71 to 899 characters of unterminated string under `finish_reason: "length"`,
  and the `DecodeStop` has already been yielded when this raises, so a caller holding a
  `StopLedger` can pair the two into "the run was cut" rather than "the backend died". It is a
  subclass, so every `except InferenceError` still catches it;
- **the decode cadence is the one exception, and it fails quiet.** A `timings` object that is
  missing, not an object, missing either field, holding a non-number, holding a bool (which is an
  `int` in Python and would otherwise arrive as 1.0 tok/s), or holding a negative yields no
  cadence and changes nothing else about the stream. It is a diagnostic that arrives after the
  answer, so killing a finished reply over it would trade what the user asked for against what the
  operator would have liked, and the core's `CadenceWatch` already reads "no cadence" as its own
  answer rather than as a healthy one.
- **the stop reason is the third stance, and it fails into a value.** A `finish_reason` outside
  the three words above, or one that is not a string at all, is neither raised nor dropped: it
  crosses as `StopReason.UNKNOWN`. Raising would cost the reply as above, and silence would file
  a reason this core could not read under the same heading as a reason nobody offered, which is
  the exact conflation the arm exists to remove.

**Invariants.**
- Stateless per call: nothing about a turn outlives `stream`; no KV or context is held
  here (the one hard rule). The adapter holds only its injected manager + client.
- Lease released on cancellation. The GPU lease is a non-reentrant lock held across the whole
  streaming block (`async with manager.acquire(model)` wrapping the HTTP stream), so a
  `CancelledError` raised mid-inference (a user Stop, a client `Cancel`, or an RPC teardown)
  propagates out through that `async with` and frees the lock before the next turn leases it.
  A Stop that freed the holder task but left the lock taken would wedge every later turn behind
  a lease no one can reclaim, so `test_cancelling_mid_stream_frees_the_model_lease` pins it (it
  cancels a turn suspended mid-stream and asserts a fresh acquire returns at once).
- Adapter-only: real network I/O lives here, never in the core (AGENTS.md gate 3).
- Fully typed, pyright strict clean; 100% line+branch via `httpx.MockTransport` + the
  pure `SingleResidentModelManager`, with no GPU and no network. Live streaming against a real
  `llama-server` is the `integration`-marked test in `tests/test_backend_live.py`
  (excluded from CI + coverage; run per `docs/runbooks/llamacpp-gpu.md`).
- Three shared port contracts are driven over this adapter and over a core twin, which is the
  ports-before-adapters gate: `tests/cadence_contract.py` for the decode rate,
  `tests/stop_contract.py` for the stop reason, and `tests/stream_contract.py` for the completion
  those two close, each run twice by its `test_*_contract.py`. All three feed the adapter leg a
  real llama-server body, so passing means the parser found the fact in bytes nobody shaped for
  it. The stop's live twin is `tests/test_finish_reason_live.py`
  (`integration`-marked), which caps a real request at eight tokens and follows the answer through
  the shipped `PlacedAttempt`. `tests/test_cut_tool_call_live.py` is the other half of that live
  pair: it caps a request while the model is writing a tool call's `arguments`, asserts the server
  reports the cap before the assembly fails, and follows the same shipped `PlacedAttempt` to a
  `TRUNCATED` outcome (ADR-0005 tool-call-cut addendum). It needs a server started the way a
  subagent tier is, deliberation off at the server, since the attempt sends no `thinking` of its
  own.
- **`tests/test_thinking_switch_live.py` is the probe for whether a deployment honours
  `thinking=False` at all** (`integration`-marked, ADR-0005 switch-is-advisory addendum). One
  prompt four ways against one endpoint, plain and carrying `REPLY_ENVELOPE`, each with the switch
  and without it, answering per request shape rather than per tier because that is how the answer
  came out: measured on the two shipped picks, both honour it plain and the E4B pick deliberates
  straight through it under a `response_format` on 4 draws in 5. It wants a server started with
  **neither** `--chat-template-kwargs` nor `--reasoning-budget`, both of those being the deployment
  answering for the model, and it **asserts its control**: the arms that send no switch must
  deliberate, or the prompt invited no thought and the run is thrown away rather than read. That
  assertion is the whole difference between it and the two earlier readings of the same question.
  Each cell is drawn `CORTEX_THINKING_REPEATS` times, 1 by default and 5 or more for anything
  quoted as a tier's behaviour, since the cell that carries the finding is a split and not a
  constant. Ahead of the cells it reads the **rendered prompt** for all four request shapes off the
  server's own `POST /apply-template`, prints whether the template read the switch, and asserts
  that the two shapes carrying one switch render the same prompt: that is what says a difference
  between their cells is the schema's doing and not a difference of prompt, and on the two picks it
  is also the mechanism, the cortex's template closing an empty thought where the E4B's writes
  nothing (ADR-0005 switch-is-advisory addendum).
- **What the streaming list holds is what a stream owes, said without saying when.** Ten checks
  over four worlds a fixture arranges (a reasoning model answering, a completion that asks for a
  tool, a completion with nothing to say, a backend that cannot answer): the reply is its deltas
  joined in arrival order; the thinking crosses as its own kind and is over before the reply
  starts; a deliberation that arrived despite a request asking for none crosses all the same, an
  implementation reporting what its deployment did rather than filtering it into the silence the
  caller asked for (ADR-0005 switch-is-advisory addendum); a tool call crosses whole; a tool call
  never precedes the words beside it; the two
  closing events arrive at most once each with the stop first and both after what they describe; a
  completion with nothing to say owes no event at all; an abandoned completion costs the backend
  nothing, the next one arriving whole; a backend that cannot answer fails its caller with
  `InferenceError`; and a backend answers only for a model it serves. Nothing in it counts events,
  sizes one, or asks when one arrives, because the two implementations produce them at different
  rates from different sources.
- **The served-model check is the one about the request rather than the stream**, and it needs no
  fifth world: both legs' builders already stand for a deployment serving `CONTRACT_MODEL` alone,
  this adapter because its fixture's `SingleResidentModelManager` holds that one resident and the
  twin because it is constructed `serves=[CONTRACT_MODEL]`, so asking either for `UNSERVED_MODEL`
  is the world the check wants. This adapter refuses before any request leaves the process, the
  manager's `ModelUnavailableError` crossing as `InferenceError`; the port asks only that no reply
  arrive for an id the implementation could not have served, so a backend fronting a router taking
  the refusal off the wire would pass the same check (ADR-0001 served-model addendum).

**Where this adapter legitimately differs from the core's twin, and so what the shared list does
not say.** Three, each decided when the streaming list was written rather than left implicit:

- **A delta carrying no text is permitted by the port and dropped by this adapter.** llama-server
  opens with a role-only chunk and closes with an empty delta, and neither is anything a consumer
  can show, so `_chunk_events` skips them; `ScriptedInferenceBackend` yields whatever it was
  handed, an empty chunk included, and the core is written for that (`turn_output` drops a delta
  the guardrail empties, and `ThinkingChannel` drops an empty status because a blank one would
  clear the overlay's chip). The list therefore never asks an implementation to filter, and the
  adapter's own suite holds this one: making `_chunk_events` emit a delta per chunk reddens 22
  cases there and exactly one shared check, for an ordering reason rather than an emptiness one.
- **Tool calls trail both closing events here**, because a call is only whole once the stream is
  over. The port asks only that a call never precede the words beside it, so a future backend
  whose engine hands over each call as it completes would still pass, which is why the check is
  written about order against the text rather than about position in the stream.
- **The twin's script advances per `stream` call while this adapter is stateless per call**, which
  is what makes a tool loop scriptable. So no check asks an implementation to answer twice the
  same way; a sampled model could not, and unlike `Embedder` this port never promised it.

**Dependencies.** cortex-core (the `InferenceBackend`/`ModelManager` ports and typed
errors), httpx (the async HTTP client). The composition root
(`cortex_orchestrator.wiring`) injects a concrete `ModelManager`
(`SingleResidentModelManager` in this slice) and an `httpx.AsyncClient`.
