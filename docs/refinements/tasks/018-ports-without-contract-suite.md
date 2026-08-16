# Ports without a shared contract suite

**Status:** open, fix when it bites
**Area:** repo-gates
**Origin:** [ADR-0001](../../adr/ADR-0001-architecture.md)
**Trigger:** The next port to gain a shared check list, or the first drift caught in the wild.

Opened 2026-08-10 by the sweep that followed the `MemoryStore` contract
fix out to every port in both languages, recorded with its full inventory in the
[ADR-0001](../../adr/ADR-0001-architecture.md) addendum on decision 2's contract-test half.
The sweep's own finding closed inside it: `SessionStore` had the same defect the memory port
had just been fixed for, its shared tuple read only by the integration-marked live-Redis run
while the CI driver restated all fourteen checks by hand, and it now parametrizes over the
tuple like the other four stores in that directory. What stays open is the larger half the
sweep could only measure.

**Four Python ports have a fake and a real adapter and no shared check list**, `Embedder`,
`ToolRegistry`, `BodyGateway` and `Confirmer`, with `InferenceBackend` a fifth in part: its
decode-cadence arm is contract-tested over both implementations and the rest of the
streaming contract is restated between the core's suite for `ScriptedInferenceBackend` and
the adapter's own. None of the five is blocked on hardware. Each already has a CI-runnable
real adapter, over `MockTransport` for the embedder and the backend, a fake MCP session for
the registry, a real loopback `BodyService` for the gateway, and the seam's fake for the
confirmer, so what is missing is the shared file and its two drivers rather than any way to
run one.

**The Rust workspace has no shared check list for any port**, and the shape there is worse
than a restated list, being a restated fake: `FakeAudio`, `FakeNotify`, `FakeScreen` and
`FakeBrain` are each hand-written twice with independent expectations, once under
`body/crates/core/tests/` and again under `body/crates/rpc/tests/`. The generic helpers that
look like the missing driver (`register_via`, `get_via`, `show_via`, `capture_via`, `probe`)
hold no assertions at all; they prove the trait is usable as a bound. The real OS adapters
are `cfg(windows)` and so are neither compiled nor run by CI, which is gate 3 and not a
defect, but it does mean a shared list would be the only artifact holding the Windows
backends to the same description their fakes are held to, and it would be ready the day the
host runs it.

**The overlay's `BrainBridge` is the sharpest single case**, having three implementations of
which one is tested, while `body/app/vite.config.ts` names `tauriBridge.ts` and
`demoBridge.ts` in its coverage `exclude` list. The 100% threshold is therefore met with two
thirds of that port unmeasured, which is the same class of thing this sweep was looking for:
a gate that reads green over code it was never pointed at.

**That case closed on 2026-08-11, which is this entry's trigger firing once rather than the
entry closing.** The next port to gain a shared check list was the overlay's, and it adopted the
arrangement the nine Python ones share rather than inventing a tenth:
`body/app/src/bridge/bridgeContract.ts` holds thirteen named checks and the case a check runs
against, and `bridgeContract.test.ts` builds a fresh case per check and runs the list over
`FakeBridge` and `DemoBridge`, `describe.each` and `it.each` standing where the Python driver's
fixture parameters and `pytest.mark.parametrize` stand. `demoBridge.ts` and `demoScript.ts` came
out of the coverage `exclude` with it, which is where the paragraph above was one file short of
the tree: three files were named there, not two, the demo's script having been split out of the
bridge when the line cap started measuring the overlay. What is left in that list is `main.tsx`
and `tauriBridge.ts`, each with its reason written beside it. `TauriBridge` stays out on the
argument the sweep's own design question was reaching for: every method of it is an `invoke`
call, so a shared driver over it would fake `invoke` and measure the fake.

The list paid on its first run, before either implementation was changed to suit it, with three
disagreements decided against the port's own description in `types.ts`. `FakeBridge` ignored the
`limit` its `listSessions` was given, so a test could pass against a listing production would
have cut. `FakeBridge.setPreference` recorded a write the served record never carried, alone
among its writes in that, the three catalog writes beside it having always reflected theirs.
And `DemoBridge` read a zero limit as "at most none" where the port documents it as the brain's
own default, so browser dev answered an empty switcher to a caller asking for the default
listing. A fourth came from the turn-handle check rather than from the two arms disagreeing, the
demo bridge having announced a capture activity inside the `converse` call, which is a delivery
the real bridge cannot make: its events cross a Tauri channel and arrive after the call has
handed back the cancellation its caller stores. It was then proven able to fail three times over,
on a delete put back to the no-op it once was, on a cancellation that leaves its turn's timers
running, and on a completion moved ahead of the reply it settles. The first two redden one arm of
the shared list apiece and the third reddens the demo's own suite while all thirteen shared
checks stay green, which is the division of labour showing itself: the list holds the port and
the suite holds the script. Each break was restored. The whole account, including the four places
the two implementations legitimately disagree and so what the list holds instead, is the
[ADR-0001](../../adr/ADR-0001-architecture.md) addendum of the same day, with the divergences
themselves in [docs/modules/body-app.md](../../modules/body-app.md).

**The rest of the inventory stays open, unchanged**: the four Python ports with no shared list,
`InferenceBackend`'s unshared streaming half, and every Rust row, where the fakes themselves are
still hand-written twice in two crates. The trigger below is live for those, with one correction
it earns from being fired: the arrangement to adopt is now shared by ten lists rather than nine,
the overlay's being the first outside Python and the evidence that the shape carries across the
language boundary.

**The Python half is being taken one port per commit from 2026-08-11, and `Embedder` is the
first of the four.** `brain/packages/embedding/tests/embedder_contract.py` holds four checks and
`test_embedder_contract.py` runs them over `HashEmbedder` and over `LlamaCppEmbedder` on a
`MockTransport` whose stand-in server answers the digest bytes of the text it was given, as JSON
integers, which is a shape a real server is free to send and is what makes the check on float
elements a statement about the adapter's coercion. The four are that an embedding is a non-empty
sequence of real floats, that every text embeds at one width, that one text always embeds to one
vector with an unrelated embedding in between changing nothing, and that a backend which cannot
answer raises `EmbedderError`.

It found no behavioural disagreement, which is the honest outcome for a port one method wide and
is recorded rather than left as a silence. What it did find is that the fake could not fail at
all: `HashEmbedder` had no way to raise the one error the port names, so nothing in the core
could exercise a remember or a recall against a dead embedding server, and on the only path where
the two implementations have anything to disagree about the fake could not stand in for the
adapter. It gained `fail_with`, the scripted failure `InMemoryBodyGateway` has carried since it
was written. Two divergences are legitimate and so are written into
[docs/modules/brain-embedding.md](../../modules/brain-embedding.md) instead of into a check: the
fake answers a `tuple` and the adapter a `list`, and their widths differ, which is why the width
check compares an implementation's own answers with each other rather than with a number.

**Proven able to fail, once per arm and once per side of the new knob.** Dropping the adapter's
`float(value)` coercion reddens `text_embeds_to_a_vector_of_real_numbers[llamacpp]` alone, 1
failed against 7 passed; making the fake's width depend on the text's parity reddens
`every_text_embeds_at_one_width[hash]` alone; letting the adapter's `httpx.HTTPError` escape
reddens `a_backend_that_cannot_answer_raises_embedder_error[llamacpp]`; and making `fail_with` a
no-op reddens that same check on the `hash` arm, which is what proves the knob load-bearing. Each
break was restored. The account port by port is the
[ADR-0001](../../adr/ADR-0001-architecture.md) addendum of the same day. **Three of the four Python
ports stay open**, `ToolRegistry`, `BodyGateway` and `Confirmer`, alongside
`InferenceBackend`'s streaming half and every Rust row.

**`ToolRegistry` is the second, and it is the one that paid.**
`brain/packages/tools/tests/registry_contract.py` holds six checks and
`test_registry_contract.py` runs them over three implementations, the core's
`InMemoryToolRegistry` and both MCP ones, since the translating `McpToolRegistry` and the
`ReconnectingMcpToolRegistry` production wires are not the same implementation of every promise.
The six are that every served tool is advertised with its name, purpose and schema in order;
that the listing is read again on every walk; that a call comes back stamped with its own id and
the tool's text; that a tool which ran and failed is an `is_error` result rather than an
exception; that a name the registry does not serve never comes back as a success; and that an
unreachable backend raises `ToolError` from both verbs.

The fake could express neither the port's central case nor its world. `InMemoryToolRegistry`
handlers answered result text, so the fake could never produce a result with `is_error` set,
which is the case the port draws its whole `is_error`-against-raise distinction around, and every
core test of a failing tool went through the other branch, a handler raising, which the
dispatcher labels differently (its own sentence is trusted, a relayed one is not). It copied its
tool set at construction, so no test could move the world the port promises to re-read. And it
had no way to be unreachable, so nothing held it to the `ToolError` that
`SkipUnavailableToolRegistry` is built on. It gained a widened handler answer, `serve`, and the
same `fail_with` the embedder's fake took.

**One divergence was decided against the port rather than against an implementation.** The port
promised `ToolNotFoundError` for an unknown name, which only a registry that knows its whole set
can keep: an MCP server answers an unknown tool with an error result, so the adapter has never
raised there and cannot without sniffing an error string or paying a listing round trip per call.
The description was the thing that was wrong, and it now states the safety half both owe, that a
name an implementation does not serve never comes back as a success, with the divergence and its
downstream consequence written into
[docs/modules/brain-tools.md](../../modules/brain-tools.md).

**Proven able to fail four times, each on the arms that can carry the defect.** An adapter
reading `isError` as always false reddens the failed-tool check and the unknown-name check on
both MCP arms while the fake stays green (4 failed, 15 passed); an adapter dropping the call's
arguments reddens the id-and-text check and the failed-tool check on the same two; a fake
answering an empty listing instead of raising when unreachable reddens the backend check on the
`in-memory` arm alone; and a listing cache in `McpToolRegistry` reddens the re-read check on the
`mcp` arm only, since the reconnecting wrapper builds a fresh inner registry per call and is
structurally immune to it, which is the evidence that both MCP arms earn their place. Each break
was restored. **Two of the four Python ports stay open**, `BodyGateway` and `Confirmer`,
alongside `InferenceBackend`'s streaming half and every Rust row.

**`BodyGateway` is the third, and its finding runs the dangerous way.**
`brain/packages/body_client/tests/gateway_contract.py` holds ten checks and
`test_gateway_contract.py` runs them over `InMemoryBodyGateway` and over `GrpcBodyGateway`
talking to a `BodyService` served on loopback, so nothing on the adapter's side is stubbed. The
ten are the volume read, the write that touches only the field it was given, the write that
reports the state after it, the clamp, the notification that reaches the body with its taint
bit, the decline that answers `False` rather than raising, the capture that reports what the
body pointed at rather than what was asked, the capture refused for breaking the bound it asked
for, the capture attempted exactly once, and the single `BodyGatewayError` every verb fails
with.

The fake handed back a capture the adapter would have refused. A non-zero `max_edge` or
`max_bytes` is a bound on the reply, since a proto3 field an older body ignores is a constraint
the brain only believes it set, and the gRPC adapter has verified it on receipt since the
capture slice; the fake answered its scripted capture verbatim whatever was asked. So a core
test could watch a turn accept a picture production would have thrown away, which is a fake more
permissive than the adapter it stands in for, the direction that hides defects rather than
inventing them. The rule is domain logic rather than wire translation, so it moved into the core
as `hold_to_the_bounds_asked_for` and both implementations call it, which also leaves one fewer
place for the two to drift. The fake gained `fail_with` and `show_notifications` besides, a body
going away mid-run and a host switching toasts off being conditions a construction argument
cannot supply. Two divergences are legitimate and are written into
[docs/modules/brain-body-client.md](../../modules/brain-body-client.md): the level is 32 bits on
the wire and a Python float in the fake, so every level the checks use is exact in both, and the
clamp happens in different places, which is why the check asks only that a legal state comes
back.

**Proven able to fail four times, once per side.** The bounds rule taken back out of the fake
reddens the refusal check on the `in-memory` arm alone (1 failed, 19 passed), which is the
finding measured rather than asserted; the adapter sending a zero for an absent level instead of
leaving the field unset reddens the presence check on the `grpc` arm alone, which is the mute
that would silence the host; the adapter stamping the asked target onto the answer reddens the
target check the same way; and the fake recording a notification without its taint bit reddens
the notification check on `in-memory`. Each break was restored. **One of the four Python ports
stays open**, `Confirmer`, alongside `InferenceBackend`'s streaming half and every Rust row.

**`Confirmer` is the fourth and last of them.**
`brain/packages/orchestrator/tests/confirmer_contract.py` holds five checks and
`test_confirmer_contract.py` runs them over `RecordingConfirmer` and over `SeamConfirmer`. The
list sits beside the real adapter rather than beside the seam's fake, which is where the other
lists sit and where the fixture's work is: it wires a scripted overlay into the adapter's
`emit`, reads the card off the control path, decodes it back into a `ConfirmationRequest`, and
answers through `resolve` exactly as the Converse stream does, so nothing about the adapter is
stubbed and only the person is. The five are that an explicit approval is the only `True`, that
a refusal blocks, that a person who never answers denies, that the person is shown the call that
would run, and that each ask is answered on its own.

The fake's answer was fixed at construction, and a person is not a constant, so it could not be
asked about two calls in one run; it gained `answer_with`. No behavioural disagreement came out
of the five, which for a port whose whole contract is that only an explicit yes is `True` is the
answer worth having. One legitimate divergence went into
[docs/modules/brain-orchestrator.md](../../modules/brain-orchestrator.md): the fake records the
request object while the real card crosses as JSON built with `default=str`, so a value JSON
cannot represent would reach the person rendered rather than verbatim, and the checks use the
JSON-native arguments a model always sends.

**Proven able to fail three times, and once deliberately not.** A timeout that approves reddens
the silence check on the `seam` arm alone; a card emitted without its reason reddens the two
checks that read what the person was shown, on `seam`; a fake that stops recording reddens the
same two on `recording`. The fourth attempt is the informative one: `resolve` rewritten to
answer whichever ask is pending rather than the one whose id it was given leaves all ten green,
because through the port only one ask is ever outstanding. That is the division of labour rather
than a hole, the shared list holding the port while `test_confirm.py` holds the stream, where a
stale or forged `confirm_id` resolving nothing is checked directly.

**The four Python ports named at the top of this entry are done, and the entry is still open.**
What is left is `InferenceBackend`, whose decode cadence is shared and whose streaming contract
is not, and every Rust row. The inference one is deliberately not folded into the four: two
implementations producing events at different rates from different sources need a list that says
what a stream owes without saying when, which is a design question rather than a transcription.

**`InferenceBackend`'s streaming half closed on 2026-08-16, which leaves only Rust.**
`brain/packages/inference/tests/stream_contract.py` holds eight checks and
`test_stream_contract.py` runs them over `ScriptedInferenceBackend` and over `LlamaCppBackend`
reading real llama-server bodies through a `MockTransport`, the third file of this port's list
beside the two that hold one closing event each. The design question the entry recorded got an
answer written into the checks themselves: a stream owes that the reply is its deltas joined in
arrival order, that thinking crosses apart and is over before the reply starts, that a tool call
crosses whole and never precedes the words beside it, that the two closing events arrive at most
once each with the stop first and both after what they describe, that a completion with nothing
to say owes no event at all, that an abandoned completion costs the backend nothing, and that a
backend which cannot answer fails with `InferenceError`. Nothing in it counts events, sizes one,
or asks when one arrives, which is what "without saying when" turned out to mean.

It paid twice against the port's own description and once against the fake. The port promised
`ToolCall`s "interleaved" with the text, which no implementation has ever done, and called the
cadence the event that "closes the stream", which the trailing tool calls disprove in the other
direction; both sentences were the thing that was wrong, and the list holds the half both
implementations already keep. The fake could not fail at all: `ScriptedInferenceBackend` had no
way to raise the port's one error, which is why ten test files hand-roll a backend of their own to
make one, and it gained `fail_with` like the three fakes before it. Three legitimate divergences
went into [docs/modules/brain-inference.md](../../modules/brain-inference.md) instead of into
checks: an empty delta is permitted by the port and dropped by the adapter, tool calls trail both
closing events there because a call is whole only once the stream ends, and the twin's script
advances per call, which is why nothing asks an implementation to answer twice the same way. The
shipped `EchoInferenceBackend` is deliberately not a third leg, since three of the four worlds
cannot be put to it and teaching it any of them would turn shipped wiring into a test stub. What
that left open is narrower and is filed as its own entry
([R-280](280-twin-answers-for-any-model-id.md)): the twin answers for a model id no deployment
serves, where the adapter refuses one its manager cannot lease. The whole account, including the
seven breaks that proved the list able to fail and the eighth that deliberately did not, is the
[ADR-0001](../../adr/ADR-0001-architecture.md) addendum of the same day.

**The trigger below counts nine and the tree now holds sixteen**, which is the entry's own text
aging rather than a defect in it: fifteen in Python, fourteen named `*_contract.py` plus
`session/tests/contract.py`, and the overlay's `bridgeContract.ts`. The trigger keeps its
wording because the arrangement it points at is unchanged and the number was true when it was
written; the count that matters to the next reader is here and in the ADR tables.

**What is left is every Rust row**, and nothing else: the four OS ports whose fakes are
hand-written twice in two crates, `BrainTransport` with three independent suites over one
eleven-method trait, and the two small ones beside them. The Python half and the overlay are
done, so this entry is now one language wide.

**Why deferred rather than done.** The ports named above come to five in Python counting the
partial one, seven in Rust and one in the overlay, and writing contract suites for them is a
slice with its own design questions (what a write-only port owes, whether a Rust list is a
generic function or a table of function pointers, whether the overlay's fake and its Tauri
bridge can share a driver at all when one answers from a record and the other crosses an IPC
boundary), while the sweep that found them was scoped to one pass and one commit. The ADR
addendum's tables are the worklist, port by port, with the ports that legitimately cannot
share checks already argued out of it so the next reader does not re-derive them.

**Trigger:** the next port to gain a shared check list, which should adopt the arrangement
the nine existing ones share rather than invent a tenth; or the first drift caught in the
wild, meaning a check that passes against a fake and fails against its adapter in a way a
shared list would have named.

## Trail

- 2026-08-10: Opened by the sweep that carried the `MemoryStore` contract fix out to every port in
  both languages, taking the area from four entries to five by arrival rather than exchange. The
  sweep's own finding closed inside it, `SessionStore` having had the identical defect, its
  fourteen shared checks read only by the integration-marked live-Redis run while the CI driver
  restated them by hand; it now parametrizes over the tuple and was proven able to fail on a
  poisoned fifteenth check, which reddens both implementations where the restated driver had
  answered `66 passed` over it. What opened is the half the sweep could only measure. The full port
  inventory went into the ADR-0001 addendum on decision 2 rather than into this entry, so that the
  next sweep re-reads it rather than re-deriving it, and it names the ports whose fake and adapter
  legitimately cannot share checks: the write-only sinks, `Clock`, `Sleeper` and `ZoneResolver`,
  whose two implementations are deliberately not interchangeable.
- 2026-08-11: The trigger fired once without the entry closing. The overlay's `BrainBridge` gained
  thirteen named checks driven over `FakeBridge` and `DemoBridge`, the first shared list outside
  Python, and `demoBridge.ts` and its script came out of the overlay's coverage `exclude` behind it,
  leaving `main.tsx` and the IPC-crossing `tauriBridge.ts` there with their reasons beside them. The
  list paid on its first run, before either implementation was changed to suit it, on three
  disagreements decided against the port's own description plus a fourth from the turn-handle check.
  Every line of the demo's script is reached by the turns those suites drive, so the 0% the overlay
  entry had measured for it was about a script nothing imported in CI rather than about the file.
- 2026-08-11: `Embedder` was the first of the four Python ports, four checks over `HashEmbedder`
  and over `LlamaCppEmbedder` on a `MockTransport`. It found no behavioural disagreement, which is
  the honest outcome for a port one method wide, and it found a fake that could not raise the one
  error the port names, so `HashEmbedder` gained a scripted `fail_with`.
- 2026-08-11: Writing that list also established that both implementations raise `EmbedderError`
  and nothing else, and then that nothing in the brain caught it, nor the store's error either, so
  a stopped embedding server or an unreachable Postgres failed the turn instead of costing it its
  recalled notes. The index filed that arrival to the memory area rather than here.
- 2026-08-11: `ToolRegistry` was the second and the one that paid, six checks over three
  implementations, since the translating and the reconnecting MCP registries are not the same
  implementation of every promise. The fake could express neither the port's central case nor its
  world, and one divergence was decided against the port's own wording rather than against either
  implementation.
- 2026-08-11: `BodyGateway` was the third and its finding ran the dangerous way, the fake handing
  back a capture the adapter would have refused, which is a fake more permissive than the adapter
  it stands in for. The bounds rule turned out to be domain logic rather than wire translation and
  moved into the core, where both implementations call it.
- 2026-08-11: `Confirmer` was the fourth and last, five checks over `RecordingConfirmer` and
  `SeamConfirmer` with a scripted overlay wired into the adapter's `emit`. No behavioural
  disagreement came out of them, and one break deliberately did not redden, which is the division
  of labour rather than a hole. That finished the four Python ports the sweep named, leaving
  `InferenceBackend`'s streaming half, which is a design question rather than a transcription, and
  every Rust row.
- 2026-08-16: `InferenceBackend`'s streaming half closed, eight checks over the scripted twin and
  the llama.cpp adapter, and the design question was answered by writing only obligations and
  orders: what a stream owes turned out to be sayable without counting an event, sizing one, or
  asking when it arrives. It paid twice against the port's own description, which promised
  interleaved tool calls and a cadence that closes the stream where every implementation trails its
  calls behind both closing events, and once against the fake, which could not raise the port's one
  error and gained `fail_with`. The model-id half of that finding was too narrow to fold in and
  opened [R-280](280-twin-answers-for-any-model-id.md). The Python half of this entry and the
  overlay are now done, so what remains is every Rust row, where the fakes themselves are still
  hand-written twice in two crates.
