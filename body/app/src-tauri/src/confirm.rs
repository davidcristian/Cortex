//! The `confirm_response` IPC command and the per-turn decision route: the overlay's
//! answer to a mid-turn confirm card is pushed into the running turn's decision channel, which
//! `converse` chains onto the open `Converse` request stream.

use std::sync::Mutex;

use body_core::ConfirmDecision;
use tauri::State;
use tokio::sync::mpsc::UnboundedSender;

/// The claimed slot: the running turn's decision sender plus the generation that claimed it, so a
/// stale turn's `clear` can be told apart from the live one's.
struct Claim {
    sender: UnboundedSender<ConfirmDecision>,
    generation: u64,
}

/// Managed state routing the user's confirm answers into the running turn.
#[derive(Default)]
pub struct ConfirmRoute {
    slot: Mutex<Option<Claim>>,
    next_generation: Mutex<u64>,
}

impl ConfirmRoute {
    /// Parks `sender` as the running turn's decision route (turn start) and returns this turn's
    /// generation.
    pub fn set(&self, sender: UnboundedSender<ConfirmDecision>) -> u64 {
        let generation = match self.next_generation.lock() {
            Ok(mut next) => {
                *next = next.wrapping_add(1);
                *next
            }
            // A poisoned lock cannot happen here, and 0 makes `clear` no-op rather than
            // clearing another turn's route.
            Err(_) => 0,
        };
        if let Ok(mut slot) = self.slot.lock() {
            *slot = Some(Claim { sender, generation });
        }
        generation
    }

    /// Drops the route iff it still holds `generation`'s sender (its own turn ended); a stale turn
    /// whose slot was already reclaimed by a newer turn no-ops, leaving the live turn answerable.
    pub fn clear(&self, generation: u64) {
        if let Ok(mut slot) = self.slot.lock()
            && slot
                .as_ref()
                .is_some_and(|claim| claim.generation == generation)
        {
            *slot = None;
        }
    }

    /// Sends one decision into the running turn, if any; send failures are ignored (closed route ==
    /// no turn to answer, so it is fail-closed brain-side).
    fn send(&self, decision: ConfirmDecision) {
        if let Ok(slot) = self.slot.lock()
            && let Some(claim) = slot.as_ref()
        {
            let _ = claim.sender.send(decision);
        }
    }
}

/// Answers a mid-turn `confirmRequest` event: forwards the user's decision to the open turn's
/// request stream.
#[tauri::command]
pub fn confirm_response(confirm_id: String, approved: bool, state: State<'_, ConfirmRoute>) {
    state.send(ConfirmDecision {
        confirm_id,
        approved,
    });
}
