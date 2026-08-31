//! The two effects the retry loop injects: [`Sleeper`] (the clock) and [`Randomness`] (the
//! jitter draw), plus the [`jittered`] arithmetic that spends them.
//!
//! Split out of `retry.rs` when the clock gained its second method (ADR-0024 deadline addendum)
//! and the file reached the line cap. The split is by responsibility rather than by size: this
//! module declares the ports, and `retry.rs` is the decorator that uses them. Every real
//! implementation lives in the ungated shell (the composition root) and every test
//! implementation is a fake, so this crate stays free of wall clocks and randomness while
//! remaining fully gated.

use std::future::Future;
use std::time::Duration;

/// A timer effect with two methods: [`Sleeper::sleep`] waits a given duration, which is the
/// backoff between attempts, and [`Sleeper::bounded`] gives up on a call after one, which is
/// the deadline on a single attempt. They are one port rather than two because both are the
/// same clock. The real `tokio` adapter lives in the ungated composition root and tests inject
/// a fake, so both the schedule and the deadline are asserted with no real time (ADR-0024).
pub trait Sleeper: Send + Sync {
    /// Resolves after `duration` has elapsed.
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send;

    /// Runs `call`, giving up on it after `deadline`: `Some(output)` when the call finished in
    /// time, `None` when the deadline expired first and the call was dropped.
    ///
    /// Dropping the abandoned call is what cancels it: for the gRPC adapter that resets the
    /// in-flight stream, so an attempt nobody is waiting for stops costing the brain. The core
    /// decides how long (the [`crate::retry::RetryPlan`]'s per-method deadline) and an adapter
    /// owns the clock that measures it. This is a port method rather than a race written here
    /// because `tokio::time::timeout` already implements it in the shell, and a fake that
    /// grants or expires a call outright makes the decorator's behaviour under a deadline
    /// deterministic.
    fn bounded<F>(
        &self,
        deadline: Duration,
        call: F,
    ) -> impl Future<Output = Option<F::Output>> + Send
    where
        F: Future + Send,
        F::Output: Send;
}

/// A randomness effect: one unit-interval draw per backoff, which is what jitter needs
/// (ADR-0024 addendum). It mirrors [`Sleeper`]: the real adapter lives in the ungated shell,
/// tests inject a scripted fake, and [`FullDelay`], the constant-1 source, disables jitter.
pub trait Randomness: Send + Sync {
    /// A value in `[0, 1]`. The retry loop sanitizes it, clamping an out-of-range value and
    /// treating a non-finite draw as the full delay, so a misbehaving source narrows the
    /// spread rather than panicking the `Duration` math.
    fn unit(&self) -> f64;
}

/// The constant-1 [`Randomness`]: equal jitter scales a delay by `0.5 + 0.5 * unit()`, so a
/// permanent 1 yields exactly the deterministic v1 schedule.
/// [`crate::retry::RetryingTransport::new`] composes it by default; a jittered composition opts
/// in via [`crate::retry::RetryingTransport::with_randomness`].
#[derive(Clone, Copy, Debug, Default)]
pub struct FullDelay;

impl Randomness for FullDelay {
    fn unit(&self) -> f64 {
        1.0
    }
}

/// `delay` scaled by equal jitter: half is kept as a floor (this wait exists to give a
/// restarting brain time to come back), the other half is scaled by the sanitized draw. A
/// non-finite draw (`clamp` would propagate a `NaN`, which `mul_f64` rejects) falls back to
/// the full delay, so a misbehaving source cannot panic the `Duration` math.
pub(crate) fn jittered(delay: Duration, randomness: &impl Randomness) -> Duration {
    let draw = randomness.unit();
    let scale = if draw.is_finite() {
        draw.clamp(0.0, 1.0)
    } else {
        1.0
    };
    delay.mul_f64(0.5 + 0.5 * scale)
}
