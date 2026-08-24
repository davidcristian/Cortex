//! Shared brain-seam connection for the read IPC commands: a resilient transport.
//!
//! The session reads (`sessions.rs`) dial through a `RetryingTransport` over a **lazy**
//! channel (ADR-0024): construction never fails on reachability, and a briefly-unreachable
//! brain (restarting after a swap, a loopback blip) is retried with bounded backoff instead
//! of surfacing an immediate error to the switcher, since tonic reconnects transparently on a
//! retry. `converse.rs` keeps its eager dial but composes `retry_with` around it (ADR-0024
//! addendum): a turn is non-idempotent once begun, so a *failed turn* stays terminal
//! (decision 2), while the dial before it may be patiently retried. Ungated shell glue. The
//! retry *logic* is gated in `body_core`; this only composes it with the real `tokio::time`
//! sleeper, the `RandomState`-seeded jitter source, and env config.
//!
//! Which calls may be retried at all is not configurable here, and deliberately so: that is
//! the `RetryPlan` gate in `body_core`, decided by what each seam method does. What env
//! supplies is the *schedule*, per method: the reads' backoff and the `Health` probe's
//! ceiling, which the connection indicator depends on staying short.

use std::future::Future;
use std::hash::{BuildHasher, Hasher};
use std::time::Duration;

use body_core::{Randomness, RetryPlan, RetryPolicy, RetryingTransport, Sleeper, TurnGaps};
use body_rpc::BrainSeamClient;

/// Default brain seam address (matches `body_rpc`); override with `CORTEX_BRAIN_ADDR`.
const DEFAULT_ADDR: &str = "http://127.0.0.1:50051";

/// The real [`Sleeper`]: `tokio::time`, for both questions the clock is asked. Kept here in the
/// ungated shell so the timer effect stays out of the gated crates (ADR-0024 decision 5); a
/// zero-sized unit.
pub struct TokioSleeper;

impl Sleeper for TokioSleeper {
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send {
        tokio::time::sleep(duration)
    }

    /// The per-attempt deadline (ADR-0024 deadline addendum). `tokio::time::timeout` already is
    /// exactly this primitive, correctly: it drops the call when the clock wins, which for a
    /// gRPC call resets the in-flight stream so an abandoned attempt stops costing the brain.
    /// The core keeps the policy (which call gets how long); this keeps the clock.
    async fn bounded<F>(&self, deadline: Duration, call: F) -> Option<F::Output>
    where
        F: Future + Send,
        F::Output: Send,
    {
        tokio::time::timeout(deadline, call).await.ok()
    }
}

/// The real [`Randomness`] (ADR-0024 addendum): unit draws from std's per-instance
/// `RandomState` seed, which is jitter-grade spread without a new dependency. `enabled:
/// false` (the `CORTEX_BRAIN_RETRY_JITTER=off` knob) pins the draw to 1, degenerating equal
/// jitter to the deterministic schedule, so one type serves both modes and the transport
/// alias stays a single type.
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
///
/// **One plan, read once, handed to both halves** (ADR-0024 courtesy-header addendum). The
/// decorator enforces the plan's per-attempt deadline and the client announces it to the brain as
/// `grpc-timeout`; the announcement is the longer of the two by the plan's own grace margin, so
/// the enforced bound wins the race the announcement inevitably starts. That ordering holds
/// because the same `RetryPlan` value reaches both, which is why it is a local here rather than
/// two calls to `plan_from_env()`: two reads of the same env could not drift today, but two
/// sources of one policy is the shape that eventually does.
pub fn connect() -> Result<ResilientTransport, String> {
    let addr = std::env::var("CORTEX_BRAIN_ADDR").unwrap_or_else(|_| DEFAULT_ADDR.to_owned());
    let token = std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|token| !token.is_empty());
    let plan = plan_from_env();
    let client = BrainSeamClient::connect_lazy_with_token(&addr, token.as_deref())
        .map_err(|error| error.to_string())?
        .announcing(plan);
    Ok(RetryingTransport::with_randomness(
        client,
        TokioSleeper,
        ShellRandomness::from_env(),
        plan,
    ))
}

/// The per-method retry plan: the read schedule from `CORTEX_BRAIN_RETRY_*`, the ceiling on a
/// `Health` probe's whole run from `CORTEX_BRAIN_PROBE_BUDGET_MS` (default 1 s), the two
/// per-attempt deadlines, `CORTEX_BRAIN_PROBE_DEADLINE_MS` (default 250 ms) and
/// `CORTEX_BRAIN_CALL_DEADLINE_MS` (default 5 s), and the two gaps a turn's stream may be silent
/// for, `CORTEX_BRAIN_TURN_FIRST_GAP_MS` (default 10 min) and `CORTEX_BRAIN_TURN_IDLE_GAP_MS`
/// (default 2 h).
///
/// The probe is separate because the connection indicator renders its answer: patience there
/// is time the dot spends claiming a state the seam has stopped proving. Turning the read
/// knobs up therefore buys a session read more patience without ever buying the indicator a
/// longer lie. The deadlines split for a different reason: a probe that waits a second has
/// already outlived its usefulness, while a store read may honestly take longer than that.
///
/// The gaps are a third kind and are the turn's alone. They bound how long the stream may say
/// NOTHING, never how long the turn may take, so a deployment that runs without the delegating
/// sidecars can turn the idle one down a long way: the shipped value is sized by a subagent batch
/// waiting for admission and then running, which a stack without them never produces
/// (ADR-0024 idle-gap addendum).
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
        },
    }
}

/// The retry policy for the reads, each field overridable via `CORTEX_BRAIN_RETRY_*`; the
/// ADR-0024 defaults (3 attempts / 200 ms base / ×2 / 2 s cap) otherwise. Also the schedule
/// the `converse` dial is retried on (`converse.rs`), which is not a seam method and so has no
/// entry in the plan: it is a dial, made before the non-idempotent turn begins.
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

/// Parses an env var as a count of milliseconds. Every duration knob on this seam is spelled
/// that way, so the conversion is written once.
fn env_millis(key: &str) -> Option<Duration> {
    env_parse(key).map(Duration::from_millis)
}
