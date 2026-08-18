//! `LinkStatus`: what the overlay's connection indicator is allowed to claim (ADR-0011).

use crate::transport::{BrainTransport, SeamHealth, TransportError};

/// What the last seam answer proved about the brain. The names are the wire names the
/// overlay's own `LinkState` union uses (`bridge/types.ts`), as `TurnEvent`'s tags are.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LinkState {
    /// The brain answered and reports itself ready to serve turns.
    Ready,
    /// The brain answered, and is not serving: not ready, a non-OK status, or an unreadable
    /// reply. Reachable either way, which is what separates this from [`LinkState::Down`].
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

/// Probes the seam once and reports what the answer proves. Never fails: a failure *is* the
/// answer here, which is what lets the caller render a state instead of an error.
pub async fn probe_link(transport: &impl BrainTransport) -> LinkStatus {
    match transport.health().await {
        Ok(health) => LinkStatus::from_health(&health),
        Err(error) => LinkStatus::from_error(&error),
    }
}
