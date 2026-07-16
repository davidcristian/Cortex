//! Shared brain-seam connection for the read IPC commands: a resilient transport.

use std::future::Future;
use std::hash::{BuildHasher, Hasher};
use std::time::Duration;

use body_core::{Randomness, RetryPlan, RetryPolicy, RetryingTransport, Sleeper};
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

/// The real [`Randomness`] (ADR-0024 addendum): unit draws from std's per-instance `RandomState`
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
        // A fresh RandomState per draw: std seeds each instance randomly, and finishing an
        // empty hasher yields 64 of those bits. Scale to [0, 1] (both casts round to 2^64 at
        // the top, so the max bit pattern yields exactly 1.0, which the port permits).
        let bits = std::collections::hash_map::RandomState::new()
            .build_hasher()
            .finish();
        // Precision loss is fine: this feeds a jitter scale, not arithmetic that must be exact.
        #[allow(clippy::cast_precision_loss)]
        {
            bits as f64 / (u64::MAX as f64 + 1.0)
        }
    }
}

/// The transport the read commands run over: a lazy [`BrainSeamClient`] wrapped in
/// [`RetryingTransport`] with the [`TokioSleeper`] and the [`ShellRandomness`] jitter.
pub type ResilientTransport = RetryingTransport<BrainSeamClient, TokioSleeper, ShellRandomness>;

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
    Ok(RetryingTransport::with_randomness(
        client,
        TokioSleeper,
        ShellRandomness::from_env(),
        plan_from_env(),
    ))
}

/// The per-method retry plan: the read schedule from `CORTEX_BRAIN_RETRY_*`, plus the ceiling
/// on a `Health` probe's patience from `CORTEX_BRAIN_PROBE_BUDGET_MS` (default 1 s).
pub fn plan_from_env() -> RetryPlan {
    RetryPlan {
        reads: policy_from_env(),
        probe_budget: env_parse("CORTEX_BRAIN_PROBE_BUDGET_MS")
            .map(Duration::from_millis)
            .unwrap_or(RetryPlan::default().probe_budget),
    }
}

/// The retry policy for the reads, each field overridable via `CORTEX_BRAIN_RETRY_*`; the ADR-0024
/// defaults (3 attempts / 200 ms base / ×2 / 2 s cap) otherwise.
pub fn policy_from_env() -> RetryPolicy {
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
