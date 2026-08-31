//! [`RetryPolicy`]: the backoff schedule, and the error half of the retry decision.

use std::time::Duration;

use crate::transport::TransportError;

/// Whether a failed call is worth retrying: a `Connection` failure and the gRPC `Unavailable`
/// status are; any other status, unreadable wire data, and an expired deadline are not.
#[must_use]
pub fn is_transient(error: &TransportError) -> bool {
    match error {
        TransportError::Connection(_) => true,
        TransportError::Rpc { code, .. } => code == "Unavailable",
        TransportError::Protocol(_) | TransportError::Timeout { .. } => false,
    }
}

/// A bounded exponential-backoff schedule (pure, `Copy`): the number of tries and the growing,
/// capped delay between them.
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
    /// The schedule that cannot retry: one attempt and no wait.
    pub const ONCE: Self = Self {
        max_attempts: 1,
        base_delay: Duration::ZERO,
        multiplier: 1,
        max_delay: Duration::ZERO,
    };

    /// The wait before retry `index` (0-based): `min(base · multiplierⁱⁿᵈᵉˣ, max_delay)`, grown by
    /// saturating multiply and clamped every step so no overflow escapes the cap.
    #[must_use]
    pub fn delay(&self, index: u32) -> Duration {
        let mut delay = self.base_delay.min(self.max_delay);
        for _ in 0..index {
            delay = delay.saturating_mul(self.multiplier).min(self.max_delay);
        }
        delay
    }

    /// The backoff to apply after `attempt` failures (0-based), or `None` to give up: it retries
    /// only while an attempt remains and the error is [`is_transient`].
    #[must_use]
    pub fn backoff(&self, attempt: u32, error: &TransportError) -> Option<Duration> {
        if attempt + 1 < self.max_attempts && is_transient(error) {
            Some(self.delay(attempt))
        } else {
            None
        }
    }

    /// The longest this schedule can spend waiting: the sum of every backoff it would use before
    /// giving up, unjittered (equal jitter only ever shortens a wait, never lengthens one).
    #[must_use]
    pub fn worst_case_backoff(&self) -> Duration {
        (0..self.max_attempts.saturating_sub(1)).fold(Duration::ZERO, |total, index| {
            total.saturating_add(self.delay(index))
        })
    }

    /// This schedule with its attempts trimmed until the whole run fits `budget`, counting each
    /// attempt as costing up to `attempt` and every backoff between them, and leaving the delays
    /// themselves untouched.
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
