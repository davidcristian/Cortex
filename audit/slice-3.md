# Audit of Slice 3 (Cortex-only chat with fake inference)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Every functional claim in the Slice 3 ROADMAP text is implemented and directly verified in code: the SessionStore port (ports.py:21) with the InMemorySessionStore fake (fakes.py:26) and RedisSessionStore adapter (cortex_session/store.py:80) run behind one parametrized contract suite (session/tests/contract.py + test_store_contract.py:19), with the same checks re-run against live Redis in an integration-marked test; the InferenceBackend port (ports.py:36) has the deterministic EchoInferenceBackend scripted fake (fakes.py:45); TurnEngine, the 'handle a user turn' use-case, lives in the pure core wired only to ports (engine.py:64); Converse is wired end-to-end in the orchestrator over the proto RPC (converse.py, server.py:54, body.proto:18); and the slice acceptance (state surviving an orchestrator restart) is proven by test_converse_grpc.py:141, which restarts the server over the sole surviving fakeredis state and shows the reply counter continuing, with the live docker-compose-restart variant documented in the runbook and the implementing commit. The slice's one consciously deferred refinement (session-history windowing) is properly recorded in the ROADMAP ledger. The only finding is a low-severity stale docstring in converse.py promising bounded backpressure 'with real inference (Slice 4)': Slice 4 landed without it, the queue remains unbounded, and no deferral is written down anywhere. The undocumented (if trivial and arguably Slice-4-owned) lost decision mechanically drops the verdict from fully-implemented.

## Claims checked (14)

- **✅ verified**. ROADMAP marks Slice 3 'Cortex-only chat with fake inference' as done
  - Evidence: docs/ROADMAP.md:46-55 ('## Slice 3, Cortex-only chat with fake inference', 'Status: done.'); implementing commit 3c2004c 'feat: cortex chat with fake inference over redis-backed sessions' (git log)

- **✅ verified**. SessionStore port exists in the pure core
  - Evidence: brain/packages/core/src/cortex_core/ports.py:21-33. SessionStore Protocol with async append(session_id, message) and history(session_id), docstring cites the one hard rule; failures typed as SessionStoreError

- **✅ verified.** In-memory SessionStore fake exists
  - Evidence: brain/packages/core/src/cortex_core/fakes.py:26-42. InMemorySessionStore (dict-backed, explicitly documented as not surviving a restart, contract-test twin of the Redis adapter per fakes.py:4-5)

- **✅ verified**. Redis SessionStore adapter exists in cortex_session (store.py)
  - Evidence: brain/packages/session/src/cortex_session/store.py:80-115. RedisSessionStore over redis-py asyncio: RPUSH/LRANGE on key cortex:session:{id}:messages, versioned JSON records (v/kind, store.py:30-48), every RedisError wrapped as SessionStoreError with cause chained (store.py:100-115); pure translator, no business logic

- **✅ verified**. The in-memory fake and the Redis adapter sit behind the SAME contract test
  - Evidence: brain/packages/session/tests/contract.py:25-85. Shared behavior checks (empty history, append order, multi-session isolation, roundtrip fidelity incl. timezone offset); brain/packages/session/tests/test_store_contract.py:19-40. Pytest fixture parametrized over ['in-memory','redis'] (InMemorySessionStore vs RedisSessionStore over fakeredis) runs the identical checks against both; docstring at test_store_contract.py:1-5 names this the slice's ports-before-adapters gate; the same ALL_CHECKS also run against real Redis in the integration-marked live test (test_store_live.py:18-31, @pytest.mark.integration, excluded from CI/coverage per its docstring)

- **✅ verified.** InferenceBackend port + scripted fake exist
  - Evidence: brain/packages/core/src/cortex_core/ports.py:36-48. InferenceBackend Protocol (stateless streamed completion); brain/packages/core/src/cortex_core/fakes.py:45-66. EchoInferenceBackend: deterministic scripted reply 'reply {n}: {T}' streamed as three TextChunk deltas, where n is derived solely from the store-backed history so the count is observable across a restart; it is the default runtime backend in wiring.py:89 (Echo unless CORTEX_INFERENCE_BACKEND=llamacpp)

- **✅ verified**. Orchestrator use-case 'handle a user turn' lives in the pure core
  - Evidence: brain/packages/core/src/cortex_core/engine.py:64-155. TurnEngine wired only to ports (SessionStore, InferenceBackend, Clock; engine.py:20,73-91), no I/O imports; persists the user message before inference, streams TextDelta events, persists the assistant reply only on completion (engine.py:93-129); TurnCapabilities() default preserves the bare Slice 3 behavior after later slices added memory/tools (engine.py:51-62, docs/modules/brain-core.md:184)

- **✅ verified.** A turn arrives over Converse and is answered by the fake
  - Evidence: proto/body.proto:18. rpc Converse(stream ClientEvent) returns (stream ServerEvent); brain/packages/orchestrator/src/cortex_orchestrator/server.py:54-72. BrainService.Converse servicer delegates to converse(); brain/packages/orchestrator/src/cortex_orchestrator/converse.py:56-192. Full stream contract (queued turns, Cancel semantics, typed SeamError codes at converse.py:42-44); end-to-end proven over a real loopback grpc.aio server in brain/packages/orchestrator/tests/test_converse_grpc.py:118-128 (deltas join to 'reply 1: hello', >=3 deltas, TurnComplete with real turn_id)

- **✅ verified** (CI-safe test). Session state survives an orchestrator process restart (state is external)
  - Evidence: brain/packages/orchestrator/tests/test_converse_grpc.py:141-172. test_conversation_survives_a_server_and_deps_restart: only a fakeredis FakeServer survives; instance A (server+store+engine) is stopped, the store is verified AND seeded out-of-band via a bare RedisSessionStore handle (so hidden in-process state would still count 1, lines 154-164), then a fresh instance B over the same redis state answers 'reply 3: again'. The count continues across the restart. Header comment at test_converse_grpc.py:3-4 names it THE Slice 3 acceptance test

- **📄 verified-as-documented (host-only run; paper trail checked)**. The restart acceptance was also proven live against a real brain container restart
  - Evidence: docs/runbooks/local-dev-wsl.md:63-68. 'State survives a brain restart, the Slice 3 acceptance': run a turn, docker compose restart brain, run another turn, the reply counter keeps counting; commit 3c2004c body records 'Acceptance proven live twice: the reply counter continues across a brain container restart because state exists only in redis'; the body-side live test converse_round_trips_one_turn_over_the_live_seam exists at body/crates/rpc/tests/live.rs:58-60 with #[ignore = "live seam check..."] and is documented in docs/modules/body-rpc.md:63

- **✅ verified.** Gate proven: ports-before-adapters with contract tests; repository pattern
  - Evidence: test_store_contract.py:1-5 states and implements observable interchangeability of both SessionStore implementations behind the port; RedisSessionStore is the repository over Redis (store.py:80-115); composition root injects it via CORTEX_REDIS_URL at the edge only (wiring.py:195-241, run_from_env with store_factory=RedisSessionStore.from_url; docker/docker-compose.yml:22 sets CORTEX_REDIS_URL=redis://redis:6379/0)

- **✅ verified**. Redis runs in the Compose stack as the surviving state store
  - Evidence: docker/docker-compose.yml:1 ('Slice 3: cortex-only chat; state in redis'), :20-31 (brain env CORTEX_REDIS_URL, depends_on redis healthy), :49-64 (redis:8-alpine, appendonly yes so sessions survive a redis restart too, loopback-only publish, redis-data named volume, redis-cli ping healthcheck)

- **✅ verified**. Module docs cover the slice's modules per the doc-first Definition of Done
  - Evidence: docs/modules/brain-session.md:1-60. Purpose, full public contract, storage layout, record evolution policy, error contract for RedisSessionStore; docs/modules/brain-core.md:20-33. 'Conversation domain (Slice 3)' (Role, Message, TurnEvent, TextChunk) and TurnEngine contract (brain-core.md:170-190); docs/modules/brain-orchestrator.md:95-109. The restart invariant naming the Slice 3 acceptance and pointing at the runbook

- **✅ verified**. The slice's consciously deferred refinement is recorded in the ROADMAP ledger
  - Evidence: docs/ROADMAP.md:463-469. 'Cortex chat / session, Slice 3: Session-history windowing / truncation / summarization' deferral, matching the code (engine.py:100,155 sends the full store-backed history every turn; CORTEX_CTX_SIZE referenced there exists at docker/docker-compose.gpu.yml:44 and docs/runbooks/llamacpp-gpu.md:26)

## Gaps (1)

### G1 · severity low · **not documented as a deferral**

Stale in-code promise: the Converse output queue docstring (brain/packages/orchestrator/src/cortex_orchestrator/converse.py:60-63) justifies the deliberately unbounded asyncio.Queue by the echo backend's short finite replies and states 'bounded backpressure arrives with real inference (Slice 4)'. Slice 4 has since landed real llama.cpp inference (opt-in via CORTEX_INFERENCE_BACKEND, wiring.py:85-89) but the queue is still unbounded (converse.py:78) and no backpressure was added. The deferral is not recorded in the ROADMAP 'Deferred refinements & later work' ledger (no entry under the Slice 3 or Slice 4 groups; grep for 'backpressure' hits only the code comment) nor in ADR-0007. Practical impact is small (single-user system, unread output bounded by one turn's reply), but the comment's justification no longer covers the enabled-GPU path and the punted refinement is a lost decision per AGENTS.md gate 4. Strictly this staleness was created by Slice 4, not Slice 3. Every claim in the Slice 3 ROADMAP text itself is implemented.

**Adversarial re-check: confirmed.** Could not refute the auditor. I verified every factual leg of the claim directly: the converse output queue is still unbounded (converse.py:78) while its docstring (converse.py:61-63) promises bounded backpressure 'with real inference (Slice 4)', and Slice 4's real llama.cpp backend has landed (wiring.py:83-86, ADR-0007 marked host-validated 2026-06-29). I then searched adversarially for any written record of the deferral: the full ROADMAP 'Deferred refinements & later work' section (both the Slice 3 'Cortex chat / session' group and the Slice 4 'Inference / Model Manager' group), all of ADR-0007 including its addenda, docs/modules/brain-orchestrator.md, ADR-0003, and a repo-wide plus git-history grep for backpressure/bounded/queue/flow-control variants. The only occurrence of 'backpressure' anywhere in the repository is the stale code comment itself. The queue mentions elsewhere (ModelManager lease queue, subagent scheduler queue, Redis task queue) are unrelated subsystems. The gap is real and undocumented; the auditor's caveat also holds. The staleness was created by Slice 4 landing, not by any unimplemented Slice 3 promise.
