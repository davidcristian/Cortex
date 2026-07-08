//! Shared brain-seam connection for the read IPC commands: a resilient transport.
//!
//! The session reads (`sessions.rs`) dial through a `RetryingTransport` over a **lazy**
//! channel (ADR-0024): construction never fails on reachability, and a briefly-unreachable
//! brain (restarting after a swap, a loopback blip) is retried with bounded backoff instead
//! of surfacing an immediate error to the switcher, since tonic reconnects transparently on a
//! retry. `converse.rs` keeps its own eager dial: a turn is non-idempotent, so a failed turn
//! stays terminal (ADR-0024 decision 2). Ungated shell glue. The retry *logic* is gated in
//! `body_core`; this only composes it with the real `tokio::time` sleeper and env config.

use std::future::Future;
use std::time::Duration;

use body_core::{RetryPolicy, RetryingTransport, Sleeper};
use body_rpc::BrainSeamClient;

/// Default brain seam address (matches `body_rpc`); override with `CORTEX_BRAIN_ADDR`.
const DEFAULT_ADDR: &str = "http://127.0.0.1:50051";

/// The real [`Sleeper`]: `tokio::time::sleep`. Kept here in the ungated shell so the timer
/// effect stays out of the gated crates (ADR-0024 decision 5); a zero-sized unit.
pub struct TokioSleeper;

impl Sleeper for TokioSleeper {
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send {
        tokio::time::sleep(duration)
    }
}

/// The transport the read commands run over: a lazy [`BrainSeamClient`] wrapped in
/// [`RetryingTransport`] with the [`TokioSleeper`].
pub type ResilientTransport = RetryingTransport<BrainSeamClient, TokioSleeper>;

/// Builds the resilient read transport, reading the address + optional seam token (ADR-0016)
/// and the retry knobs from env. Fails only on a bad URI / non-ASCII token. The lazy channel
/// never dials at construction, so an unreachable brain is a retry, not a connect error.
pub fn connect() -> Result<ResilientTransport, String> {
    let addr = std::env::var("CORTEX_BRAIN_ADDR").unwrap_or_else(|_| DEFAULT_ADDR.to_owned());
    let token = std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|token| !token.is_empty());
    let client = BrainSeamClient::connect_lazy_with_token(&addr, token.as_deref())
        .map_err(|error| error.to_string())?;
    Ok(RetryingTransport::new(client, TokioSleeper, policy_from_env()))
}

/// The retry policy, each field overridable via `CORTEX_BRAIN_RETRY_*`; the ADR-0024 defaults
/// (3 attempts / 200 ms base / ×2 / 2 s cap) otherwise.
fn policy_from_env() -> RetryPolicy {
    let default = RetryPolicy::default();
    RetryPolicy {
        max_attempts: env_parse("CORTEX_BRAIN_RETRY_ATTEMPTS").unwrap_or(default.max_attempts),
        base_delay: env_parse("CORTEX_BRAIN_RETRY_BASE_MS")
            .map(Duration::from_millis)
            .unwrap_or(default.base_delay),
        multiplier: env_parse("CORTEX_BRAIN_RETRY_MULTIPLIER").unwrap_or(default.multiplier),
        max_delay: env_parse("CORTEX_BRAIN_RETRY_MAX_MS")
            .map(Duration::from_millis)
            .unwrap_or(default.max_delay),
    }
}

/// Parses an env var as `T`, or `None` if it is unset or does not parse.
fn env_parse<T: std::str::FromStr>(key: &str) -> Option<T> {
    std::env::var(key).ok().and_then(|value| value.parse().ok())
}
