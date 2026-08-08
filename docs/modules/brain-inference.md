# brain/packages/inference (`cortex_inference`)

**Purpose.** The llama.cpp adapter for the core's `InferenceBackend` port (ADR-0005,
ADR-0007). A thin HTTP translator: it takes a GPU lease from a `ModelManager`, opens a
streaming chat completion against the leased `llama-server` endpoint over the
OpenAI-compatible API, and yields the assistant reply deltas, a reasoning model's thinking
deltas (ADR-0020), any tool calls the model makes (native function-calling, ADR-0009), and the
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
  4. Yields one `DecodeCadence(tokens_per_second, tokens)` when a chunk carries llama.cpp's own
     `timings` object, read from `predicted_per_second` and `predicted_n` (ADR-0030 spill-watch
     addendum). On build `b10298-15586e2d7` exactly one chunk of a stream carries it, the last,
     and it arrives unasked, so no request changed to get it. Timings are read **before** the
     chunk's `choices` are, so a build closing on `{"choices": []}` is still heard. The event is
     emitted after the text it describes, a rate being unknowable before the tokens are counted.
  - The injected `http_client` owns timeouts/transport (the adapter sets none itself because a
    generation may legitimately stream for a long time; the composition root gives it a
    short connect timeout and no read deadline).

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
- any transport or non-2xx status is caught as `httpx.HTTPError` and re-raised;
- a malformed streaming chunk (bad JSON, unexpected shape, non-string content) or a
  tool call whose accumulated arguments are not valid JSON raises `InferenceError`
  directly, since a silently skipped chunk would drop reply text or a tool call, the same
  fail-loud stance the session store takes on corrupt records;
- **the decode cadence is the one exception, and it fails quiet.** A `timings` object that is
  missing, not an object, missing either field, holding a non-number, holding a bool (which is an
  `int` in Python and would otherwise arrive as 1.0 tok/s), or holding a negative yields no
  cadence and changes nothing else about the stream. It is a diagnostic that arrives after the
  answer, so killing a finished reply over it would trade what the user asked for against what the
  operator would have liked, and the core's `CadenceWatch` already reads "no cadence" as its own
  answer rather than as a healthy one.

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

**Dependencies.** cortex-core (the `InferenceBackend`/`ModelManager` ports and typed
errors), httpx (the async HTTP client). The composition root
(`cortex_orchestrator.wiring`) injects a concrete `ModelManager`
(`SingleResidentModelManager` in this slice) and an `httpx.AsyncClient`.
