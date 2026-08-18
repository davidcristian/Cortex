//! [`RetryPolicy`]: the backoff schedule, and the error half of the retry decision.
//!
//! Split out of `retry.rs` when the per-method plan joined it (both files stay well under the
//! line cap). Two questions are answered here and nowhere else: *is this error worth another
//! attempt* ([`is_transient`]), and *how long is the wait before it* ([`RetryPolicy::delay`]).
//! The third question, *may this method be repeated at all*, is deliberately not here: it is a
//! property of the call, not of the failure, so it lives in [`crate::retry::plan`] and is asked
//! first. An error code never establishes that a repeat is safe.

use std::time::Duration;

use crate::transport::TransportError;

/// Whether a failed seam call is worth retrying: transient reachability/backend conditions
/// (`Connection`, and the gRPC-conventional `Rpc{Unavailable}`) are; a genuine application
/// answer (any other `Rpc` status), uninterpretable wire data (`Protocol`), or an expired
/// deadline (`Timeout`) is not. A repeat would return the same thing (ADR-0024 decision 3).
///
/// This is a *necessary* condition for a retry, never a sufficient one. `Unavailable` says the
/// brain could not serve the call; it does not say the brain did not already run it. Whether a
/// repeat is safe is [`crate::retry::SeamMethod::repeatable`]'s question, asked first.
///
/// **`Timeout` is terminal by decision, not by omission** (ADR-0024 deadline addendum), and it
/// is the one classification here that a plausible reading would get backwards. A retried
/// deadline is the classic load amplifier, and it amplifies precisely when the peer is least
/// able to take it. The argument that decides it, though, is narrower than that convention: a
/// timeout is not the brain's report about the call, it is **this side's decision to stop
/// waiting**. `Unavailable` is an answer that invites a repeat, because the brain is saying it
/// could not serve this one; an expired deadline says nothing whatever about the brain, and in
/// particular cannot say a second attempt would be faster. The cure for a call that needs
/// longer is a longer deadline, which is a knob, not a repeat.
#[must_use]
pub fn is_transient(error: &TransportError) -> bool {
    match error {
        TransportError::Connection(_) => true,
        TransportError::Rpc { code, .. } => code == "Unavailable",
        TransportError::Protocol(_) | TransportError::Timeout { .. } => false,
    }
}

/// A bounded exponential-backoff schedule (pure, `Copy`): the number of tries and the growing,
/// capped delay between them (ADR-0024 decision 4). Jitter is applied on top by the retry loop
/// (ADR-0024 addendum), so the schedule this describes is the unjittered worst case.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RetryPolicy {
    /// Total attempts including the first; `0` or `1` disables retry (one try only).
    pub max_attempts: u32,
    /// The wait before the first retry; each subsequent wait multiplies it.
    pub base_delay: Duration,
    /// The exponential growth factor applied per retry.
    pub multiplier: u32,
    /// The ceiling every computed delay is clamped to.
    pub max_delay: Duration,
}

impl Default for RetryPolicy {
    /// 3 attempts (2 retries), 200 ms base, ×2 growth, capped at 2 s. This is the shell default.
    fn default() -> Self {
        Self {
            max_attempts: 3,
            base_delay: Duration::from_millis(200),
            multiplier: 2,
            max_delay: Duration::from_secs(2),
        }
    }
}

impl RetryPolicy {
    /// The schedule that cannot retry: one attempt, no wait, nothing to compute. It is what a
    /// caller runs when [`crate::retry::RetryPlan::policy_for`] refuses a method, so a refusal
    /// is *executed* by the same loop as a permission rather than by a second code path no
    /// test can enter. A refused call therefore makes exactly one attempt and surfaces its
    /// result, whatever the failure looks like.
    pub const ONCE: Self = Self {
        max_attempts: 1,
        base_delay: Duration::ZERO,
        multiplier: 1,
        max_delay: Duration::ZERO,
    };

    /// The wait before retry `index` (0-based): `min(base · multiplierⁱⁿᵈᵉˣ, max_delay)`,
    /// grown by saturating multiply and clamped every step so no overflow escapes the cap.
    #[must_use]
    pub fn delay(&self, index: u32) -> Duration {
        let mut delay = self.base_delay.min(self.max_delay);
        for _ in 0..index {
            delay = delay.saturating_mul(self.multiplier).min(self.max_delay);
        }
        delay
    }

    /// The backoff to apply after `attempt` failures (0-based), or `None` to give up: retry
    /// only while an attempt remains *and* the error is [`is_transient`].
    #[must_use]
    pub fn backoff(&self, attempt: u32, error: &TransportError) -> Option<Duration> {
        if attempt + 1 < self.max_attempts && is_transient(error) {
            Some(self.delay(attempt))
        } else {
            None
        }
    }

    /// The longest this schedule can spend waiting: the sum of every backoff it would use
    /// before giving up, unjittered (equal jitter only ever shortens a wait, never lengthens
    /// one).
    ///
    /// This is the number a caller who must answer *within* some time cares about, which is
    /// why it exists: the connection indicator renders a probe's answer, so this is how long
    /// the dot may go on claiming a state the seam has stopped proving.
    #[must_use]
    pub fn worst_case_backoff(&self) -> Duration {
        (0..self.max_attempts.saturating_sub(1)).fold(Duration::ZERO, |total, index| {
            total.saturating_add(self.delay(index))
        })
    }

    /// This schedule with its attempts trimmed until the whole run fits `budget`, counting each
    /// attempt as costing up to `attempt` and every backoff between them, and leaving the
    /// delays themselves untouched.
    ///
    /// The per-attempt cost is why this takes two durations. Summing only the waits was right
    /// while an attempt could return at any time, and wrong the moment attempts became bounded:
    /// an attempt that spends its whole deadline and *then* fails transiently buys a wait on
    /// top, so a budget that counted the waits alone promised a bound it could not hold
    /// (ADR-0024 deadline addendum).
    ///
    /// One attempt always survives: a budget buys back patience, never the call itself, so a
    /// zero budget still makes exactly one try, and the guarantee is therefore
    /// `attempts × attempt + backoff ≤ max(budget, attempt)`. Trimming rather than rescaling
    /// keeps the early waits at the length that lets a restarting brain come back; what it
    /// drops is the long tail a caller with a budget could not spend anyway.
    #[must_use]
    pub fn within(self, budget: Duration, attempt: Duration) -> Self {
        let mut spent = attempt;
        let mut delay = self.base_delay.min(self.max_delay);
        let mut max_attempts = 1;
        while max_attempts < self.max_attempts {
            let extended = spent.saturating_add(delay).saturating_add(attempt);
            if extended > budget {
                break;
            }
            spent = extended;
            delay = delay.saturating_mul(self.multiplier).min(self.max_delay);
            max_attempts += 1;
        }
        Self {
            max_attempts,
            ..self
        }
    }
}
