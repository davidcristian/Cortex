//! `LinkStatus`: what the overlay's connection indicator is allowed to claim (ADR-0011).
//!
//! The overlay shows one dot for the health of the body->brain seam. A seam call can fail four
//! ways and each proves something different, so the classification lives in the pure core
//! rather than as a colour chosen in a component.
//!
//! - [`TransportError::Connection`] means the brain could not be reached at all (a refused dial,
//!   a bad address, a channel that died before any reply). Nothing answered: [`LinkState::Down`].
//! - [`TransportError::Rpc`] means the brain answered with a status, so it is running and
//!   reachable while something behind it is not serving (a store abort surfaces as `Unavailable`,
//!   a rejected seam token as `Unauthenticated`): [`LinkState::Degraded`].
//! - [`TransportError::Protocol`] means the brain answered something this side cannot read, so
//!   it is reachable and wrong: [`LinkState::Degraded`].
//! - [`TransportError::Timeout`] means the attempt was abandoned because nothing came back
//!   inside the probe's deadline (ADR-0024 deadline addendum), so [`LinkState::Down`].
//!   `Degraded` would claim the brain answered, which is exactly what the deadline could not
//!   establish. The detail names the deadline, so the tooltip still separates a brain that is
//!   wedged from one that is absent.
//! - A `Health` reply carries the brain's own verdict, so `ready = false` is the brain saying it
//!   is up and not serving turns: [`LinkState::Degraded`] with its detail shown verbatim.
//!
//! There is no "connecting" state here. Whether a probe is in flight is the caller's own fact
//! rather than the seam's, and the overlay composes it over the last known state (see
//! `docs/modules/body-app.md`). Waiting is composed the same way: probing through the
//! `RetryingTransport` decorator (ADR-0024) means a single probe already spans the reconnect
//! window before it reports `Down`.

use crate::transport::{BrainTransport, SeamHealth, TransportError};

/// What the last seam answer proved about the brain. The names are the wire names the
/// overlay's own `LinkState` union uses (`bridge/types.ts`), as `TurnEvent`'s tags are.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LinkState {
    /// The brain answered and reports itself ready to serve turns.
    Ready,
    /// The brain answered and is not serving: not ready, a non-OK status, or an unreadable
    /// reply. It is reachable either way, which is what separates this from [`LinkState::Down`].
    Degraded,
    /// The brain could not be reached at all.
    Down,
}

impl LinkState {
    /// The stable name the overlay knows this state by.
    #[must_use]
    pub fn as_str(self) -> &'static str {
        match self {
            LinkState::Ready => "ready",
            LinkState::Degraded => "degraded",
            LinkState::Down => "down",
        }
    }
}

/// One classified seam answer: the state plus the detail behind it, for the indicator's
/// tooltip. `detail` is display-only text (the brain's own health detail, or the failure's
/// message); it is never parsed, and a surface renders it inert.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LinkStatus {
    /// What the answer proved.
    pub state: LinkState,
    /// Why, in one line, for the indicator's tooltip. Empty when there is nothing to add.
    pub detail: String,
}

impl LinkStatus {
    /// Classifies a successful `Health` reply: the brain's own readiness verdict wins.
    #[must_use]
    pub fn from_health(health: &SeamHealth) -> Self {
        Self {
            state: if health.ready {
                LinkState::Ready
            } else {
                LinkState::Degraded
            },
            detail: health.detail.clone(),
        }
    }

    /// Classifies a failed seam call by what the failure proves (see the module docs).
    #[must_use]
    pub fn from_error(error: &TransportError) -> Self {
        match error {
            TransportError::Connection(message) => Self {
                state: LinkState::Down,
                detail: message.clone(),
            },
            TransportError::Rpc { code, message } => Self {
                state: LinkState::Degraded,
                detail: format!("{code}: {message}"),
            },
            TransportError::Protocol(message) => Self {
                state: LinkState::Degraded,
                detail: format!("unreadable reply: {message}"),
            },
            TransportError::Timeout { after } => Self {
                state: LinkState::Down,
                detail: format!("no reply within {after:?}"),
            },
        }
    }
}

/// Probes the seam once and reports what the answer proves. It never fails, because a failure
/// is itself an answer here, which is what lets the caller render a state instead of an error.
///
/// Composed over a [`crate::retry::RetryingTransport`] this is also the reconnect attempt, since
/// `health` is one of the retried idempotent calls (ADR-0024): the probe reports `Down` only
/// once the whole backoff budget has failed to reach the brain.
pub async fn probe_link(transport: &impl BrainTransport) -> LinkStatus {
    match transport.health().await {
        Ok(health) => LinkStatus::from_health(&health),
        Err(error) => LinkStatus::from_error(&error),
    }
}
