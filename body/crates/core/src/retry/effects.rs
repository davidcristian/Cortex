//! The two effects the retry loop injects: [`Sleeper`] (the clock) and [`Randomness`] (the jitter
//! draw), plus the [`jittered`] arithmetic that spends them.

use std::future::Future;
use std::time::Duration;

/// A timer effect with two methods: [`Sleeper::sleep`] waits a given duration, which is the backoff
/// between attempts, and [`Sleeper::bounded`] gives up on a call after one, which is the deadline
/// on a single attempt.
pub trait Sleeper: Send + Sync {
    /// Resolves after `duration` has elapsed.
    fn sleep(&self, duration: Duration) -> impl Future<Output = ()> + Send;

    /// Runs `call`, giving up on it after `deadline`: `Some(output)` when the call finished in
    /// time, `None` when the deadline expired first and the call was dropped.
    fn bounded<F>(
        &self,
        deadline: Duration,
        call: F,
    ) -> impl Future<Output = Option<F::Output>> + Send
    where
        F: Future + Send,
        F::Output: Send;
}

/// A randomness effect: one draw in `[0, 1]` per backoff, which is what jitter needs.
pub trait Randomness: Send + Sync {
    /// A value in `[0, 1]`.
    fn unit(&self) -> f64;
}

/// The constant-1 [`Randomness`]: equal jitter scales a delay by `0.5 + 0.5 * unit()`, so a
/// permanent 1 yields exactly the deterministic v1 schedule.
#[derive(Clone, Copy, Debug, Default)]
pub struct FullDelay;

impl Randomness for FullDelay {
    fn unit(&self) -> f64 {
        1.0
    }
}

/// `delay` scaled by equal jitter: half is kept as a floor (this wait exists to give a restarting
/// brain time to come back), the other half is scaled by the sanitized draw.
pub(crate) fn jittered(delay: Duration, randomness: &impl Randomness) -> Duration {
    let draw = randomness.unit();
    let scale = if draw.is_finite() {
        draw.clamp(0.0, 1.0)
    } else {
        1.0
    };
    delay.mul_f64(0.5 + 0.5 * scale)
}
