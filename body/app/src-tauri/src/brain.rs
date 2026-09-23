//! The shared brain connection the read IPC commands use: a transport that retries.
//!
//! It dials a lazy channel, so construction never fails on reachability and a brain that is
//! briefly away is retried with bounded backoff instead of failing the read at once.

use std::future::Future;
use std::hash::{BuildHasher, Hasher};
use std::time::Duration;

use body_core::{Randomness, RetryPlan, RetryPolicy, RetryingTransport, Sleeper, TurnGaps};
use body_rpc::BrainRpcClient;

/// The default brain address, the same one `body_rpc` uses; override with `CORTEX_BRAIN_ADDR`.
const DEFAULT_ADDR: &str = "http://127.0.0.1:50051";

/// The real [`Sleeper`]: `tokio::time`, for both questions the clock is asked.
pub struct TokioSleeper;

impl Sleeper for TokioSleeper {
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send {
        tokio::time::sleep(duration)
    }

    /// The per-attempt deadline.
    async fn bounded<F>(&self, deadline: Duration, call: F) -> Option<F::Output>
    where
        F: Future + Send,
        F::Output: Send,
    {
        tokio::time::timeout(deadline, call).await.ok()
    }
}

/// The real [`Randomness`]: unit draws from std's per-instance `RandomState`
/// seed, which is jitter-grade spread without a new dependency.
pub struct ShellRandomness {
    enabled: bool,
}

impl ShellRandomness {
    /// Reads `CORTEX_BRAIN_RETRY_JITTER`; anything but `off`/`0`/`false` leaves jitter on.
    pub fn from_env() -> Self {
        let value = std::env::var("CORTEX_BRAIN_RETRY_JITTER").unwrap_or_default();
        Self {
            enabled: !matches!(value.to_ascii_lowercase().as_str(), "off" | "0" | "false"),
        }
    }
}

impl Randomness for ShellRandomness {
    fn unit(&self) -> f64 {
        if !self.enabled {
            return 1.0;
        }
        // A fresh `RandomState` per draw: std seeds each instance randomly, and finishing an
        // empty hasher yields 64 of those bits.
        let bits = std::collections::hash_map::RandomState::new()
            .build_hasher()
            .finish();
        #[allow(clippy::cast_precision_loss)]
        {
            bits as f64 / (u64::MAX as f64 + 1.0)
        }
    }
}

/// The transport the read commands run over: a lazy [`BrainRpcClient`] wrapped in
/// [`RetryingTransport`] with the [`TokioSleeper`] and the [`ShellRandomness`] jitter.
pub type ResilientTransport = RetryingTransport<BrainRpcClient, TokioSleeper, ShellRandomness>;

/// Builds the read transport, reading the address, the optional token and the retry settings
/// from the environment. One `RetryPlan` is read once and handed to both the decorator that
/// enforces it and the client that announces it, so the two cannot disagree.
pub fn connect() -> Result<ResilientTransport, String> {
    let addr = std::env::var("CORTEX_BRAIN_ADDR").unwrap_or_else(|_| DEFAULT_ADDR.to_owned());
    let token = std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|token| !token.is_empty());
    let plan = plan_from_env();
    let client = BrainRpcClient::connect_lazy_with_token(&addr, token.as_deref())
        .map_err(|error| error.to_string())?
        .announcing(plan);
    Ok(RetryingTransport::with_randomness(
        client,
        TokioSleeper,
        ShellRandomness::from_env(),
        plan,
    ))
}

/// The per-method retry plan, from `CORTEX_BRAIN_RETRY_*`, `CORTEX_BRAIN_PROBE_*_MS` (1 s, 250 ms),
/// `CORTEX_BRAIN_CALL_DEADLINE_MS` (5 s) and the turn gaps `CORTEX_BRAIN_TURN_FIRST_GAP_MS` (10 min),
/// `CORTEX_BRAIN_TURN_IDLE_GAP_MS` (4 h) and `CORTEX_BRAIN_TURN_HEARTBEAT_GAP_MS` (2 min).
pub fn plan_from_env() -> RetryPlan {
    let default = RetryPlan::default();
    RetryPlan {
        reads: policy_from_env(),
        probe_budget: env_millis("CORTEX_BRAIN_PROBE_BUDGET_MS").unwrap_or(default.probe_budget),
        probe_deadline: env_millis("CORTEX_BRAIN_PROBE_DEADLINE_MS")
            .unwrap_or(default.probe_deadline),
        call_deadline: env_millis("CORTEX_BRAIN_CALL_DEADLINE_MS").unwrap_or(default.call_deadline),
        turn_gaps: TurnGaps {
            first: env_millis("CORTEX_BRAIN_TURN_FIRST_GAP_MS").unwrap_or(default.turn_gaps.first),
            idle: env_millis("CORTEX_BRAIN_TURN_IDLE_GAP_MS").unwrap_or(default.turn_gaps.idle),
            heartbeat: env_millis("CORTEX_BRAIN_TURN_HEARTBEAT_GAP_MS")
                .unwrap_or(default.turn_gaps.heartbeat),
            ..default.turn_gaps
        },
    }
}

/// The retry policy for the reads, each field overridable via `CORTEX_BRAIN_RETRY_*`, and
/// otherwise 3 attempts, 200 ms base, doubling, 2 s cap.
pub fn policy_from_env() -> RetryPolicy {
    let default = RetryPolicy::default();
    RetryPolicy {
        max_attempts: env_parse("CORTEX_BRAIN_RETRY_ATTEMPTS").unwrap_or(default.max_attempts),
        base_delay: env_millis("CORTEX_BRAIN_RETRY_BASE_MS").unwrap_or(default.base_delay),
        multiplier: env_parse("CORTEX_BRAIN_RETRY_MULTIPLIER").unwrap_or(default.multiplier),
        max_delay: env_millis("CORTEX_BRAIN_RETRY_MAX_MS").unwrap_or(default.max_delay),
    }
}

/// Parses an env var as `T`, or `None` if it is unset or does not parse.
fn env_parse<T: std::str::FromStr>(key: &str) -> Option<T> {
    std::env::var(key).ok().and_then(|value| value.parse().ok())
}

/// Parses an env var as a count of milliseconds.
fn env_millis(key: &str) -> Option<Duration> {
    env_parse(key).map(Duration::from_millis)
}
