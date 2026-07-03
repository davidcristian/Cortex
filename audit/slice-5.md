# Audit of Slice 5 (Memory v1: retrieval that grows)

**Audited:** 2026-07-02 · **Verdict:** implemented, with undocumented documentation gaps

Method: a dedicated audit agent verified every checkable claim in the slice's
ROADMAP section (and its referenced ADRs, module docs, and runbooks) against the
actual tree; every discrepancy was then independently re-checked by an adversarial
verifier instructed to refute it. `just check` passed end to end on the audit date.

## Summary

Slice 5 is substantially delivered and matches its paper trail closely: the Embedder/MemoryStore ports, MemoryRecord/ScoredMemory values, MemoryRecaller use-case, and the InMemoryMemoryStore/HashEmbedder fakes all exist in cortex_core exactly as described; TurnEngine recalls top-5 into an ephemeral SYSTEM message (proven never-persisted by test) and records the exchange at turn end with memory off by default; LlamaCppEmbedder (MockTransport-tested, integration-marked live test) and PgVectorMemoryStore (canned-row fake Database, integration-marked live contract test) are in place; wiring is opt-in via CORTEX_MEMORY_BACKEND default none; the compose override, init.sql, runbook, ADR-0008, and the dated ADR-0004 addendum (nomic-embed-text-v1.5 Q8_0, 768-dim, 2026-06-29 host validation) are all present and mutually consistent. One promise is only partially met: the slice text and ADR-0004 addendum promise an *automated* dump/sync of the named volume into D:\Software\AI\Database, but only a manual pg_dump procedure exists in the runbook, and that automation gap is not recorded in the ROADMAP deferred ledger or ADR-0008. It is undocumented. The skipped bind-mount validation is a documented downgrade (ADR-0008 decision 7), and two minor stale-text drifts (TurnCapabilities bundle, taint-conditional recording) are superseded by later slices with the changes written down.

## Claims checked (22)

- **✅ verified.** Embedder port exists in the core (embed(text) -> Sequence[float], failures as EmbedderError)
  - Evidence: brain/packages/core/src/cortex_core/ports.py:82-89 (Embedder Protocol); errors referenced in docstring; exported via cortex_core __init__

- **✅ verified**. MemoryStore port exists in the core (add(record), search(embedding, k) -> top-k most-similar-first over one global space, failures as MemoryStoreError)
  - Evidence: brain/packages/core/src/cortex_core/ports.py:92-104

- **✅ verified**. MemoryRecord/ScoredMemory value types exist (pure, immutable, timezone-aware timestamp enforced)
  - Evidence: brain/packages/core/src/cortex_core/memory.py:7-33 (frozen dataclasses; __post_init__ rejects naive timestamps at lines 22-25); tests brain/packages/core/tests/test_memory.py:29-38

- **✅ verified**. MemoryRecaller remember/recall use-case in the pure core (record embeds+persists, recall embeds+searches)
  - Evidence: brain/packages/core/src/cortex_core/recall.py:20-48; tests brain/packages/core/tests/test_memory.py:90-116

- **✅ verified.** InMemoryMemoryStore fake: cosine-ranking twin of pgvector behind the same contract
  - Evidence: brain/packages/core/src/cortex_core/fakes.py:88-119 (_cosine + InMemoryMemoryStore, sorts by score desc, truncates to k); tests test_memory.py:56-87

- **✅ verified.** HashEmbedder fake: deterministic, distinct text -> distinct vector, never all-zero
  - Evidence: brain/packages/core/src/cortex_core/fakes.py:69-85 (sha256-based, byte-127.5 components); tests test_memory.py:41-53

- **✅ verified**. TurnEngine takes an optional MemoryRecaller; recalls top-k into an ephemeral Role.SYSTEM context message never persisted; records the exchange at turn end; memory=None keeps old behavior
  - Evidence: brain/packages/core/src/cortex_core/engine.py:32 (DEFAULT_RECALL_K=5), 51-61 (TurnCapabilities, memory: MemoryRecaller|None = None), 127-128 (record at turn end), 131-155 (_inference_messages builds ephemeral SYSTEM prefix handed only to the backend). Tests: brain/packages/core/tests/test_engine.py:250-277 (asserts session store holds only USER/ASSISTANT after recall), 280-297 (empty recall adds no context; exchange recorded as 'User: ...\nAssistant: ...'). Note: since Slice 6 the recaller is passed via the TurnCapabilities bundle rather than a direct constructor arg, and since Slice 6.5 recording is skipped for tainted turns (engine.py:127, test_engine.py:455-476). Both changes are documented (ROADMAP Slice 6 progress; ROADMAP deferred ledger 'Context-preserving tainted-memory recording', lines 511-513)

- **✅ verified**. cortex_embedding package: LlamaCppEmbedder over a llama-server OpenAI /v1/embeddings endpoint behind the Embedder port, failures wrapped as EmbedderError
  - Evidence: brain/packages/embedding/src/cortex_embedding/embedder.py:23-52 (POSTs {model, input} to {endpoint}/v1/embeddings, returns data[0].embedding coerced to float, wraps httpx.HTTPError and KeyError/IndexError/TypeError/ValueError as EmbedderError)

- **✅ verified**. cortex_embedding covered via httpx.MockTransport with an integration-marked live test
  - Evidence: brain/packages/embedding/tests/test_embedder.py:22 (httpx.MockTransport; success, int-coercion, status, transport, malformed-response cases at lines 26-76); tests/test_embedder_live.py:20-29 (@pytest.mark.integration, CORTEX_EMBEDDING_ENDPOINT/CORTEX_EMBEDDING_MODEL). The 100%-coverage figure itself is enforced by the just check gate (not re-run here)

- **✅ verified**. cortex_memory package: PgVectorMemoryStore behind the MemoryStore port (INSERT with ::vector literal, search ORDER BY embedding <=> $1::vector, score = 1 - distance, connect()/aclose() pool lifecycle, typed MemoryStoreError wrapping)
  - Evidence: brain/packages/memory/src/cortex_memory/store.py:26-31 (_INSERT/_SEARCH SQL), 40-47 (Database Protocol), 76-116 (adapter, error wrapping of asyncpg PostgresError/InterfaceError/OSError and malformed-row errors)

- **✅ verified**. PgVectorMemoryStore is CI-covered without a DB via a canned-row fake Database (the asyncpg analog of MockTransport)
  - Evidence: brain/packages/memory/tests/test_pgvector.py:19 (class FakeDatabase 'records calls and returns canned rows (or raises a canned error)'; add/search/close success + PostgresError/InterfaceError/malformed-row cases at lines 53-123)

- **✅ verified.** Integration-marked live test runs the MemoryStore behavioral contract (ALL_CHECKS) against real Postgres+pgvector
  - Evidence: brain/packages/memory/tests/test_pgvector_live.py (@pytest.mark.integration, CORTEX_MEMORY_DSN, iterates memory_contract.ALL_CHECKS, cleans up contract-% rows); brain/packages/memory/tests/memory_contract.py (empty search, cosine ranking, top-k, roundtrip checks)

- **✅ verified**. Memory wired into run_from_env opt-in via CORTEX_MEMORY_BACKEND, default none, alongside the embedder
  - Evidence: brain/packages/orchestrator/src/cortex_orchestrator/config.py:79-103 (MemoryConfig, backend: MemoryBackendName = "none", env_prefix CORTEX_MEMORY_, validator requiring CORTEX_MEMORY_DSN + CORTEX_MEMORY_EMBEDDER_ENDPOINT when pgvector); wiring.py:92-110 (build_memory returns MemoryRecaller over PgVectorMemoryStore + LlamaCppEmbedder, or None), 214 and 233 (run_from_env builds it and passes TurnCapabilities(memory=memory,...)), 239 (closer released on shutdown)

- **✅ verified**. docker/docker-compose.memory.yml adds Postgres+pgvector and a CPU embedding llama-server and flips the brain to CORTEX_MEMORY_BACKEND=pgvector
  - Evidence: docker/docker-compose.memory.yml:16-26 (brain env pgvector + DSN + embedder endpoint, depends_on healthy), 28-53 (pgvector/pgvector:pg16, cortex-pgdata named volume, init.sql bind, loopback-only 127.0.0.1:5432), 55-87 (llama-embed: ghcr.io/ggml-org/llama.cpp:server with --embeddings -ngl 0, nomic-embed-text-v1.5.Q8_0.gguf default, read-only models mount, loopback 127.0.0.1:8081)

- **✅ verified**. docker/postgres/init.sql creates the vector extension and the memories table (unbounded, unindexed vector column)
  - Evidence: docker/postgres/init.sql:8-15 (CREATE EXTENSION vector; memories(id text pk, text, embedding vector, created_at timestamptz))

- **✅ verified**. docs/runbooks/memory-pgvector.md exists and describes bring-up, both integration runs, the nomic pick, and the plug-and-play export
  - Evidence: docs/runbooks/memory-pgvector.md:1-83 (compose commands, CORTEX_MEMORY_DSN and CORTEX_EMBEDDING_ENDPOINT test invocations with --no-cov, nomic pick section dated 2026-06-29, pg_dump export section, teardown)

- **✅ verified.** ADR-0008 exists, resolves Letta vs. custom (custom + thin, behind the unchanged port), and records the named-volume-over-bind-mount decision
  - Evidence: docs/adr/ADR-0008-memory-v1.md:1-98 (Accepted, Slice 5, 2026-06-29; decision 1 custom-not-Letta; decision 7 named volume + dump/sync export, PGDATA bind mount downgraded to nice-to-have)

- **📄 verified-as-documented (host-only run; paper trail checked)**. ADR-0004 addendum records the embedder pick nomic-embed-text-v1.5 Q8_0, 768-dim, CPU placement, and the 2026-06-29 host validation (memory contract vs real Postgres+pgvector 0.8.4; embedder vs live CPU llama-server)
  - Evidence: docs/adr/ADR-0004-model-lineup.md:121-141 ('Addendum (2026-06-29): Slice 5 embedder pick + memory host validation'; table row nomic-embed-text-v1.5 Q8_0 768 0.146 GB CPU); corroborated by docs/runbooks/memory-pgvector.md:55-61 and commit ff87f1b 'docs: record Slice 5 host validation (pgvector + nomic embedder)'. Live GPU/DB runs cannot be re-executed here; the integration tests, runbook, and dated addendum form the paper trail

- **✅ verified**. Module contract docs exist for the two new packages (Doc-first DoD)
  - Evidence: docs/modules/brain-memory.md:1-47 and docs/modules/brain-embedding.md:1-41, both matching the code (SQL shapes, error contracts, env vars, test layout)

- **◐ partial.** Durable data placement: named volume as the live data dir (the default per ADR-0008) + automated sync into D:\Software\AI\Database (plug-and-play requirement)
  - Evidence: Named volume verified: docker/docker-compose.memory.yml:36-38,89-90 (cortex-pgdata). The sync exists only as a MANUAL procedure: docs/runbooks/memory-pgvector.md:63-74 documents a hand-run pg_dump then 'copy it out'. No automated job exists anywhere (searched scripts/, justfile, docker/*.yml, .github/, and the whole tree for pg_dump/sync/*.sh): only comments reference 'a dump/sync job' (docker-compose.memory.yml:13, ADR-0008 decision 7, ADR-0004 addendum line 61 'an automated dump/sync job')
  - Adversarial re-check: confirmed. The auditor is correct and cannot be refuted. The named-volume half of the claim is implemented (cortex-pgdata in docker-compose.memory.yml), but the "automated sync into D:\Software\AI\Database" exists only as intent: three docs (ROADMAP Slice 5, ADR-0008 decision 7, ADR-0004 addendum) and one compose comment describe a dump/sync job, while the sole concrete artifact is a manual pg_dump procedure

- **📄 verified-as-documented (host-only run; paper trail checked)**. Validate the Postgres-over-Windows-bind-mount caveat in this slice
  - Evidence: The validation was consciously downgraded, in writing: docs/adr/ADR-0008-memory-v1.md:70-75 ('validated on the host as a nice to have, not the default (the plug-and-play guarantee does not depend on it)') and docs/runbooks/memory-pgvector.md:73-74 ('optional'). The ROADMAP slice text itself acknowledges the fallback is now the default (docs/ROADMAP.md:90-91). No record that the bind-mount validation was ever performed. By the ADR's own terms it need not be

- **✅ verified**. ROADMAP deferred ledger records the Slice 5 deferrals (per-session scoping, tiered/self-editing memory + summarization, ANN index)
  - Evidence: docs/ROADMAP.md:522-528 ('Memory, Slice 5' block), each pointing back to ADR-0008 decisions 1/3 and ADR-0004

## Gaps (3)

### G1 · severity medium · **not documented as a deferral**

The 'automated sync' into D:\Software\AI\Database promised by the slice text (docs/ROADMAP.md:90-91) and the ADR-0004 addendum ('an automated dump/sync job', ADR-0004-model-lineup.md:61) is not implemented: no script, just recipe, compose service, or scheduled job exists. The delivered mechanism is a manual pg_dump + copy-out documented in docs/runbooks/memory-pgvector.md:63-74. The plug-and-play guarantee currently depends on the user remembering a manual step. This automation gap is not recorded in the ROADMAP 'Deferred refinements & later work' Memory block (docs/ROADMAP.md:522-528) nor as a deferral in ADR-0008 (decision 7 states 'a dump/sync job exports it' as if delivered).

**Adversarial re-check: confirmed.** The auditor is correct on both prongs. (1) Not implemented: an exhaustive repo-wide search (code, justfile, all six docker compose files, scripts/, CI workflows, git history) finds no script, recipe, compose service, or scheduled job performing the promised automated dump/sync into D:\Software\AI\Database. Every hit is documentation describing the job, and the only shipped mechanism is the manual pg_dump + copy-out in the runbook. (2) Not documented as a deferral: the ROADMAP "Deferred refinements & later work" Memory block records three other deferrals but not this one; ADR-0008 has no addendum and its decision 7 phrases the dump/sync job in the present tense as if delivered; ADR-0004's addenda state the requirement but never record the automation as consciously punted. The gap is real and unrecorded in both required places.

### G2 · severity low · documented (docs/adr/ADR-0008-memory-v1.md decision 7 ('validated on the host as a nice to have, not the default. The plug-and-play guarantee does not depend on it'); docs/runbooks/memory-pgvector.md:73-74 ('optional'))

The Postgres-over-Windows-bind-mount caveat validation named in the slice text was never performed; it was consciously downgraded to an optional nice-to-have.

### G3 · severity low · documented (docs/ROADMAP.md Slice 6 progress (TurnCapabilities bundle, line ~133) and the deferred ledger entry 'Context-preserving tainted-memory recording' (docs/ROADMAP.md:511-513, origin ADR-0013))

Stale text in the Slice 5 Progress paragraph: (a) 'TurnEngine takes an optional MemoryRecaller'. Since Slice 6 it is passed via the TurnCapabilities bundle (engine.py:51-61), though TurnCapabilities(memory=None) preserves the described semantics; (b) 'records the exchange at turn end' is now conditional. A turn that read untrusted content records nothing (engine.py:126-128, ADR-0013). Neither is misleading in practice and both supersessions are written down.
