# Ports without a shared contract suite

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Origin:** [ADR-0068](../../adr/ADR-0068-port-contract-lists.md)
**Trigger:** a Rust port gaining a shared check list, which answers the design question below for
Rust; or a Rust test passing over a fake while the adapter it stands in for fails the same
expectation, readable in CI for `BrainTransport`, `Sleeper` and `Randomness` and only on the
Windows host for the four OS ports.
**Verified:** 2026-09-24

A port with a fake and a real adapter should have one list of checks that both implementations
run, so the fake cannot promise something the adapter does not do. A review on 2026-08-10 that
followed the `MemoryStore` contract fix out to every port in both languages found the ports that
had no such list. The full inventory is in
[ADR-0068](../../adr/ADR-0068-port-contract-lists.md), which also names the ports whose two
implementations legitimately cannot share checks.

Every Python port and the overlay's `BrainBridge` now have a list, twenty-two in all: twenty-one in
Python (nineteen named `<port>_contract.py`, plus `session/tests/contract.py` and the own-text list
inside `tools/tests/test_own_text_contract.py`) and the overlay's `bridgeContract.ts`. What is left
is the Rust workspace, which has no shared check list for any port.

The Rust problem is worse than a repeated list; it is a repeated fake. `FakeAudio`, `FakeNotify`
and `FakeScreen` are each hand-written twice with independent expectations, once under
`body/crates/core/tests/` and again in `body/crates/rpc/tests/body_server.rs`, and `FakeBrain` is
written twice inside `body/crates/rpc/tests/`, in `converse.rs` and in `client.rs`. The generic
helpers that look like the missing driver (`register_via`, `get_via`, `show_via`, `capture_via`,
`probe`) contain no assertions at all; they only show that the trait is usable as a bound.
`BrainTransport` has eleven methods and three independent suites. The real OS adapters are
`cfg(windows)`, so CI neither compiles nor runs them, which is deliberate; it does mean a shared
list would be the only thing holding the Windows backends to the same description their fakes are
held to, and it would be ready the day the host runs it.

It is deferred rather than done because it has its own design questions: what a write-only port
owes, and whether a Rust list is a generic function or a table of function pointers. The inventory
in the ADR is the worklist, port by port.

## History

- 2026-08-10: Opened by the review that followed the `MemoryStore` contract fix out to every port
  in both languages. The review's own finding closed inside it: `SessionStore` had the same defect,
  its fourteen shared checks read only by the integration-marked live-Redis run while the CI driver
  repeated them by hand. It now runs over the shared tuple, shown able to fail by a poisoned
  fifteenth check that fails both implementations where the repeated driver had reported
  `66 passed`.
- 2026-08-11: The overlay's `BrainBridge` gained thirteen named checks run over `FakeBridge` and
  `DemoBridge`, the first shared list outside Python, and `demoBridge.ts` and its script came out
  of the overlay's coverage `exclude`, leaving `main.tsx` and the IPC-crossing `tauriBridge.ts`
  there with their reasons. The list paid on its first run, before either implementation was
  changed to suit it: `FakeBridge` ignored the `limit` given to `listSessions`, `FakeBridge`
  recorded a write the served record never contained, `DemoBridge` read a zero limit as "at most
  none" where the port documents it as the brain's default, and the demo bridge announced a capture
  activity inside the `converse` call, which the real bridge cannot do.
- 2026-08-11: `Embedder` was the first of the four Python ports, four checks over `HashEmbedder`
  and over `LlamaCppEmbedder` on a `MockTransport`. It found no behavioural disagreement, which is
  the right outcome for a port one method wide, but it found a fake that could not raise the one
  error the port names, so `HashEmbedder` gained a scripted `fail_with`.
- 2026-08-11: Writing that list also established that both implementations raise `EmbedderError`
  and nothing else, and that nothing in the brain caught it, so a stopped embedding server or an
  unreachable Postgres failed the turn instead of costing it its recalled notes.
- 2026-08-11: `ToolRegistry` was the second and the one that paid most, six checks over three
  implementations, since the translating and the reconnecting MCP registries are not the same
  implementation of every promise. The fake could express neither the port's central case nor the
  conditions it runs under, and one disagreement was decided against the port's own wording: it
  promised `ToolNotFoundError` for an unknown name, which only a registry holding its whole set can
  do.
- 2026-08-11: `BodyGateway` was the third, and its finding ran the dangerous way: the fake handed
  back a capture the adapter would have refused, so a core test could watch a turn accept a picture
  production would have thrown away. The bounds rule is domain logic rather than wire translation,
  so it moved into the core as `hold_to_the_bounds_asked_for` and both implementations call it.
- 2026-08-11: `Confirmer` was the fourth and last, five checks over `RecordingConfirmer` and
  `RpcConfirmer` with a scripted overlay wired into the adapter's `emit`. No behavioural
  disagreement came out of them. One deliberate break made nothing fail, because through the port
  only one request is ever outstanding, which is the division of labour rather than a hole.
- 2026-08-16: `InferenceBackend`'s streaming half closed, eight checks over the scripted twin and
  the llama.cpp adapter. The design question was answered inside the checks: a stream's obligations
  can be stated without counting an event, sizing one, or asking when it arrives. It paid twice
  against the port's own description, which promised tool calls interleaved with the text and a
  cadence event that closes the stream, when every implementation puts its calls after both closing
  events. The fake could not raise the port's one error and gained `fail_with`. The model-id half
  of that finding opened [R-280](280-twin-answers-for-any-model-id.md).
- 2026-09-11: Read against the tree. `Mailbox` gained a list on 2026-08-19 over `FakeMailbox` and
  `ImapMailbox`, and the own-text rule in `tools/tests/test_own_text_contract.py` followed on
  2026-09-02, so the count reached seventeen. Every Rust claim was checked again and one was
  repaired: both copies of `FakeBrain` have been in `rpc/tests/` since 2026-07-01, not one under
  `core/tests/`.
- 2026-09-17: Read against the tree with the ports enumerated by grep, and the entry was wrong
  about its own scope. `class <Name>(Protocol` across `brain/packages/*/src` gives 43 names where
  the origin's Python table named 25. Of the eighteen missing, `EmailSender` had a fake and a real
  adapter and no list; `Mailbox`, `PaceSink` and `MemoryScope` needed rows and have them;
  `RecallPolicy` gained a shared list the same day; and the other thirteen are protocols their own
  docs do not call ports. Neither half of the trigger has fired: no list has been added anywhere
  since 2026-09-02, and the one Rust port change since this opened, the capture target of
  2026-08-10, was mirrored into both `FakeScreen` copies without diverging.
- 2026-09-17: `EmailSender` closed, eight checks over `FakeSender` and `SmtpSender` on a stand-in
  `smtplib` that fakes only the socket, so no dependency was added. It paid three times: the port
  gained `SendError` for a send that reached nobody, the adapter now names recipients the server
  refused while accepting the others where it used to report them all sent, and the fake now
  applies the refusals it had skipped, from `cortex_email/drafts.py`, which both implementations
  call. Only the Rust rows are left.
- 2026-09-24: not fired. No Rust file holds a shared check list, `BrainTransport` still has eleven
  methods, and `FakeAudio` is still written in both `core/tests/os.rs` and
  `rpc/tests/body_server.rs`. The Python count was stale: `progress_contract.py` added a list on
  2026-09-22, so nineteen files are named `<port>_contract.py`. The new `ResidencyQueue` port has
  two implementations, `SwappingModelManager` and `ResidencyBoard`, both pure core, so it has no
  list by the origin's decision 6 and now sits in that row.
