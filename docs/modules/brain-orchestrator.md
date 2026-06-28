# brain/packages/orchestrator (`cortex_orchestrator`)

**Purpose.** The thin grpc.aio service hosting `BrainService` (the brain's end of the
seam. A shell only: orchestration logic belongs in `cortex_core` (this slice has none),
and no conversation/task state may live in this process (AGENTS.md hard rule).

**Public contract** (everything importable from `cortex_orchestrator`; `__all__` is the API):

- `SeamServerConfig` is a pydantic-settings model, env prefix `CORTEX_SEAM_`:
  `host: str = "127.0.0.1"` (`CORTEX_SEAM_HOST`), `port: int = 50051`
  (`CORTEX_SEAM_PORT`); `bind_address` property yields `"host:port"`. Explicit
  constructor arguments beat the environment. The body's live check dials the same
  endpoint via `CORTEX_BRAIN_ADDR` (default `http://127.0.0.1:50051`), so keep the two
  in sync when overriding.
- `BrainService` is the `BrainServiceServicer` implementation:
  - `Health` → `HealthReply(ready=True, detail="cortex-orchestrator <version>")`.
  - `Converse` → aborts `UNIMPLEMENTED` with a message pointing at Slice 3, where the
    conversation loop lands.
- `create_server(config: SeamServerConfig) -> tuple[grpc.aio.Server, int]` builds the
  aio server, registers `BrainService`, binds `config.bind_address`; returns the
  not-yet-started server plus the actually-bound port (the OS pick when `port=0`;
  gRPC reports 0 if the bind failed).
- `serve(config: SeamServerConfig) -> None` (async) starts the server and blocks
  until SIGTERM/SIGINT or task cancellation; handlers for both signals are installed on
  the running loop for the server's lifetime (removed on exit) and trigger the same
  graceful stop as cancellation: in-flight RPCs drain for up to the 5 s grace before the
  listener closes. SIGTERM is what `docker compose down` delivers.
- `ORCHESTRATOR_VERSION` is the static version string `Health` reports.
- Entrypoint: `python -m cortex_orchestrator` runs `serve(SeamServerConfig())`;
  configuration is env-only, per AGENTS.md.

**Invariants.**
- Loopback by default (ROADMAP assumption 5); listening wider is an explicit env choice.
- Stateless across RPCs: nothing outlives a single call, so a process restart or model
  swap loses nothing (the one hard rule).
- Seam names are imported only via the `cortex_seam` facade, never from `_generated`.
- Fully typed, pyright strict clean; 100% line+branch coverage. The `__main__` guard is
  the only coverage pragma. Tests are loopback-only (ephemeral ports), CI-safe.

**Dependencies.** cortex-seam (workspace), grpcio (`grpc.aio`), pydantic-settings.
