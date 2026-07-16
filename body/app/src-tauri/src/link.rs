//! The `check_link` IPC command (ADR-0011 addendum): one seam probe, reported as a state the
//! overlay's connection indicator can draw.
//!
//! Thin glue, as [`crate::sessions`] is. It dials the resilient read transport
//! (`seam::connect`, ADR-0024, so the probe *is* the reconnect attempt: `health` is retried
//! with backoff before the answer is `Down`) and hands the classification to the gated
//! `body_core::link`. The command is **infallible on purpose**: a failed probe is an answer
//! about the brain, not an error about the command, and returning it as one keeps the overlay
//! from having to invent a state for a rejected promise.

use body_core::{LinkState, LinkStatus, probe_link};
use serde::Serialize;

/// The overlay's `LinkStatus` (matches `bridge/types.ts`; the state names are
/// `body_core::LinkState::as_str`).
#[derive(Serialize)]
pub struct WireLink {
    state: &'static str,
    detail: String,
}

impl From<LinkStatus> for WireLink {
    fn from(status: LinkStatus) -> Self {
        Self {
            state: status.state.as_str(),
            detail: status.detail,
        }
    }
}

/// Probes the brain once and reports what the answer proved.
#[tauri::command]
pub async fn check_link() -> WireLink {
    match crate::seam::connect() {
        Ok(client) => probe_link(&client).await.into(),
        // A bad CORTEX_BRAIN_ADDR or a non-ASCII seam token means there is no brain this body
        // can reach at all, which is what the indicator should say, with the reason attached.
        Err(error) => WireLink {
            state: LinkState::Down.as_str(),
            detail: error,
        },
    }
}
