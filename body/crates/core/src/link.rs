//! `LinkStatus`: what the overlay's connection indicator is allowed to show.
//!
//! A timeout reports `Down` rather than `Degraded`, because `Degraded` would claim the brain
//! replied, which is what the expired deadline could not establish.

use crate::transport::{BrainTransport, RpcHealth, TransportError};

/// What the brain's last reply proved about it.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LinkState {
    /// The brain answered and reports itself ready to serve turns.
    Ready,
    /// The brain answered and is not serving: not ready, a non-OK status, or an unreadable reply.
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

/// One classified reply: the state plus the detail behind it, for the indicator's tooltip.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LinkStatus {
    /// What the answer proved.
    pub state: LinkState,
    /// Why, in one line, for the indicator's tooltip.
    pub detail: String,
}

impl LinkStatus {
    /// Classifies a successful `Health` reply: the brain's own readiness answer wins.
    #[must_use]
    pub fn from_health(health: &RpcHealth) -> Self {
        Self {
            state: if health.ready {
                LinkState::Ready
            } else {
                LinkState::Degraded
            },
            detail: health.detail.clone(),
        }
    }

    /// Classifies a failed call by what the failure proves.
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

/// Probes the brain once and reports what the answer proves. It never fails, because a failure
/// is itself an answer here.
pub async fn probe_link(transport: &impl BrainTransport) -> LinkStatus {
    match transport.health().await {
        Ok(health) => LinkStatus::from_health(&health),
        Err(error) => LinkStatus::from_error(&error),
    }
}
