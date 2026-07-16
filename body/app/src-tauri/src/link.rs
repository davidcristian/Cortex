//! The `check_link` IPC command: one probe of the brain, reported as a state the overlay's
//! connection indicator can draw. It never fails: a failed probe is an answer about the brain.

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
        Err(error) => WireLink {
            state: LinkState::Down.as_str(),
            detail: error,
        },
    }
}
