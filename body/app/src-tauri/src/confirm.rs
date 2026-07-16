//! The `confirm_response` IPC command and the per-turn decision route
//! (ADR-0022): the overlay's answer to a mid-turn confirm card is pushed into
//! the running turn's decision channel, which `converse` chains onto the open
//! `Converse` request stream.
//!
//! Thin glue with one `Mutex<Option<Sender>>` slot plus a generation counter. The
//! `converse` command claims the slot at turn start (`set` returns the turn's
//! generation) and releases it only with `clear(generation)`: a *superseded*
//! turn whose event loop ends after a newer turn has claimed the slot must not
//! wipe the newer turn's route, so `clear` is a compare-and-clear that no-ops
//! unless the slot still holds that turn's own sender. An absent or closed route
//! is silently ok. The brain denies an unanswered confirm by timeout
//! (fail-closed), so a late answer is a harmless no-op, never a webview error.

use std::sync::Mutex;

use body_core::ConfirmDecision;
use tauri::State;
use tokio::sync::mpsc::UnboundedSender;

/// The claimed slot: the running turn's decision sender plus the generation that
/// claimed it, so a stale turn's `clear` can be told apart from the live one's.
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
    /// Parks `sender` as the running turn's decision route (turn start) and
    /// returns this turn's generation. Pass it to [`clear`](Self::clear) so a
    /// superseded turn cannot drop a newer turn's route.
    pub fn set(&self, sender: UnboundedSender<ConfirmDecision>) -> u64 {
        let generation = match self.next_generation.lock() {
            Ok(mut next) => {
                *next = next.wrapping_add(1);
                *next
            }
            // A poisoned lock cannot happen here (nothing panics while holding it); 0 is a
            // safe fallback (clear() would simply no-op rather than cross-clear).
            Err(_) => 0,
        };
        if let Ok(mut slot) = self.slot.lock() {
            *slot = Some(Claim { sender, generation });
        }
        generation
    }

    /// Drops the route iff it still holds `generation`'s sender (its own turn
    /// ended); a stale turn whose slot was already reclaimed by a newer turn
    /// no-ops, leaving the live turn answerable.
    pub fn clear(&self, generation: u64) {
        if let Ok(mut slot) = self.slot.lock()
            && slot
                .as_ref()
                .is_some_and(|claim| claim.generation == generation)
        {
            *slot = None;
        }
    }

    /// Sends one decision into the running turn, if any; send failures are
    /// ignored (closed route == no turn to answer, so it is fail-closed brain-side).
    fn send(&self, decision: ConfirmDecision) {
        if let Ok(slot) = self.slot.lock()
            && let Some(claim) = slot.as_ref()
        {
            let _ = claim.sender.send(decision);
        }
    }
}

/// Answers a mid-turn `confirmRequest` event: forwards the user's decision to
/// the open turn's request stream. Never errors toward the webview. With no
/// turn running (or the turn already gone) the brain's timeout denies.
#[tauri::command]
pub fn confirm_response(confirm_id: String, approved: bool, state: State<'_, ConfirmRoute>) {
    state.send(ConfirmDecision {
        confirm_id,
        approved,
    });
}
