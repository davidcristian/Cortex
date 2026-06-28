//! Live seam check in the Rust `integration` suite (AGENTS.md gate 3,
//! ADR-0002 decision 8's Rust counterpart): `#[ignore]`d so it never runs in
//! CI or counts toward coverage. Run it manually against a real brain
//! (e.g. `docker compose up brain`, Slice 2 runbook) with:
//!
//! ```text
//! cargo test -p body-rpc --test live -- --ignored
//! ```
//!
//! The target address comes from `CORTEX_BRAIN_ADDR`
//! (default `http://127.0.0.1:50051`).

use body_core::BrainTransport;
use body_rpc::BrainSeamClient;

#[tokio::test]
#[ignore = "live seam check: needs a real brain at CORTEX_BRAIN_ADDR (run with -- --ignored)"]
async fn brain_reports_ready_over_the_live_seam() {
    let addr = std::env::var("CORTEX_BRAIN_ADDR")
        .unwrap_or_else(|_| String::from("http://127.0.0.1:50051"));
    let client = match BrainSeamClient::connect(&addr).await {
        Ok(client) => client,
        Err(error) => panic!("cannot reach the brain at {addr}: {error}"),
    };
    let health = match client.health().await {
        Ok(health) => health,
        Err(error) => panic!("brain health call at {addr} failed: {error}"),
    };
    assert!(
        health.ready,
        "brain at {addr} is not ready: {}",
        health.detail
    );
}
