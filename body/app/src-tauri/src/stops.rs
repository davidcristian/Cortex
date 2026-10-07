//! The `stop_turn` IPC command and the per-turn stop signals `converse` waits on beside its RPC.

use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use tauri::State;
use tokio::sync::Notify;

/// Managed state: one stop signal per running turn, keyed by the overlay's turn key.
#[derive(Default)]
pub struct TurnStops {
    signals: Mutex<HashMap<String, Arc<Notify>>>,
}

impl TurnStops {
    /// The signal for `turn`, created when absent, so a Stop that comes before its turn's command
    /// starts still ends it.
    pub fn signal(&self, turn: &str) -> Arc<Notify> {
        match self.signals.lock() {
            Ok(mut signals) => Arc::clone(signals.entry(turn.to_owned()).or_default()),
            Err(_) => Arc::new(Notify::new()),
        }
    }

    /// Drops `turn`'s signal once its command has returned.
    pub fn forget(&self, turn: &str) {
        if let Ok(mut signals) = self.signals.lock() {
            signals.remove(turn);
        }
    }
}

/// Ends the turn `turn` names: its `converse` command drops the RPC, and the brain cancels the
/// generation and stores no reply.
#[tauri::command]
pub fn stop_turn(turn: String, stops: State<'_, TurnStops>) {
    stops.signal(&turn).notify_one();
}
