//! Behavioral tests for `body_core::link`: what each seam answer proves about the brain, and
//! the `probe_link` call that turns an answer (or a failure) into a state the overlay can show.
//!
//! Network-free: a `ScriptedTransport` fake answers `health` from a script, and every other
//! port method is unreachable here on purpose (the probe calls exactly one method, which is
//! itself part of the contract: an indicator must not run a turn or a store read to draw a dot).

use std::sync::atomic::{AtomicUsize, Ordering};

use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, LinkState, LinkStatus, SeamHealth,
    SessionMessage, SessionSummary, TransportError, TurnEvent, probe_link,
};
use futures_core::Stream;

/// What the fake's `health` answers, rebuilt per call (`TransportError` is not `Clone`).
#[derive(Clone)]
enum Script {
    Ready(&'static str),
    NotReady(&'static str),
    Connection(&'static str),
    Rpc(&'static str, &'static str),
    Protocol(&'static str),
}

/// A `BrainTransport` whose `health` follows a script and counts its calls. The other methods
/// answer empty: the probe must never reach them, and a panic body would hide it if it did.
struct ScriptedTransport {
    script: Script,
    health_calls: AtomicUsize,
    other_calls: AtomicUsize,
}

impl ScriptedTransport {
    fn new(script: Script) -> Self {
        Self {
            script,
            health_calls: AtomicUsize::new(0),
            other_calls: AtomicUsize::new(0),
        }
    }

    fn touch_other(&self) {
        self.other_calls.fetch_add(1, Ordering::SeqCst);
    }
}

impl BrainTransport for ScriptedTransport {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        self.health_calls.fetch_add(1, Ordering::SeqCst);
        match self.script {
            Script::Ready(detail) => Ok(SeamHealth {
                ready: true,
                detail: String::from(detail),
            }),
            Script::NotReady(detail) => Ok(SeamHealth {
                ready: false,
                detail: String::from(detail),
            }),
            Script::Connection(message) => Err(TransportError::Connection(String::from(message))),
            Script::Rpc(code, message) => Err(TransportError::Rpc {
                code: String::from(code),
                message: String::from(message),
            }),
            Script::Protocol(message) => Err(TransportError::Protocol(String::from(message))),
        }
    }

    fn converse(
        &self,
        _session_id: &str,
        _text: &str,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        drop(decisions);
        self.touch_other();
        tokio_stream::iter(Vec::new())
    }

    async fn list_sessions(&self, _limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        self.touch_other();
        Ok(Vec::new())
    }

    async fn session_messages(
        &self,
        _session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        self.touch_other();
        Ok(Vec::new())
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        self.touch_other();
        Ok(Vec::new())
    }

    async fn ack_reminder(&self, _reminder_id: &str) -> Result<bool, TransportError> {
        self.touch_other();
        Ok(false)
    }

    async fn rename_session(&self, _session_id: &str, _title: &str) -> Result<(), TransportError> {
        self.touch_other();
        Ok(())
    }

    async fn delete_session(&self, _session_id: &str) -> Result<(), TransportError> {
        self.touch_other();
        Ok(())
    }

    async fn set_session_pinned(
        &self,
        _session_id: &str,
        _pinned: bool,
    ) -> Result<(), TransportError> {
        self.touch_other();
        Ok(())
    }
}

/// Probes once and reports the status plus how many methods the probe touched.
async fn probe(script: Script) -> (LinkStatus, usize, usize) {
    let transport = ScriptedTransport::new(script);
    let status = probe_link(&transport).await;
    (
        status,
        transport.health_calls.load(Ordering::SeqCst),
        transport.other_calls.load(Ordering::SeqCst),
    )
}

#[tokio::test]
async fn a_ready_brain_probes_ready_and_carries_its_own_detail() {
    let (status, health_calls, other_calls) =
        probe(Script::Ready("cortex-orchestrator 0.1.0")).await;
    assert_eq!(
        status,
        LinkStatus {
            state: LinkState::Ready,
            detail: String::from("cortex-orchestrator 0.1.0"),
        }
    );
    // Exactly one seam call, and never a turn or a store read: drawing the dot costs one probe.
    assert_eq!(health_calls, 1);
    assert_eq!(other_calls, 0);
}

#[tokio::test]
async fn a_brain_that_reports_itself_not_ready_is_degraded_not_down() {
    // The brain answered, so it is reachable; it says it cannot serve. Those are different
    // facts and the indicator shows different colours for them.
    let (status, ..) = probe(Script::NotReady("loading the brain-tier model")).await;
    assert_eq!(
        status,
        LinkStatus {
            state: LinkState::Degraded,
            detail: String::from("loading the brain-tier model"),
        }
    );
}

#[tokio::test]
async fn an_unreachable_brain_probes_down_with_the_dial_failure() {
    let (status, ..) = probe(Script::Connection("tcp connect error: refused")).await;
    assert_eq!(
        status,
        LinkStatus {
            state: LinkState::Down,
            detail: String::from("tcp connect error: refused"),
        }
    );
}

#[tokio::test]
async fn a_non_ok_status_is_degraded_because_the_brain_answered_it() {
    // A rejected seam token (ADR-0016) is the everyday case: reporting "cannot reach the brain"
    // would send the user looking at the wrong thing entirely.
    let (status, ..) = probe(Script::Rpc("Unauthenticated", "invalid seam token")).await;
    assert_eq!(
        status,
        LinkStatus {
            state: LinkState::Degraded,
            detail: String::from("Unauthenticated: invalid seam token"),
        }
    );
}

#[tokio::test]
async fn an_unreadable_reply_is_degraded_and_says_so() {
    let (status, ..) = probe(Script::Protocol("empty event")).await;
    assert_eq!(
        status,
        LinkStatus {
            state: LinkState::Degraded,
            detail: String::from("unreadable reply: empty event"),
        }
    );
}

#[test]
fn each_state_has_the_stable_name_the_overlay_knows_it_by() {
    // The overlay's LinkState union (bridge/types.ts) is these three strings; the shell's
    // wire mapping is a lookup, so a rename here must be a rename there.
    assert_eq!(LinkState::Ready.as_str(), "ready");
    assert_eq!(LinkState::Degraded.as_str(), "degraded");
    assert_eq!(LinkState::Down.as_str(), "down");
}

#[test]
fn a_status_is_clone_eq_and_debug() {
    let status = LinkStatus {
        state: LinkState::Degraded,
        detail: String::from("why"),
    };
    let copy = status.clone();
    assert_eq!(copy, status);
    assert_ne!(
        copy,
        LinkStatus {
            state: LinkState::Down,
            detail: String::from("why"),
        }
    );
    assert_eq!(
        format!("{status:?}"),
        "LinkStatus { state: Degraded, detail: \"why\" }"
    );
    assert_eq!(format!("{:?}", LinkState::Ready), "Ready");
}

#[test]
fn the_state_is_copy_so_a_caller_can_keep_one_while_matching_on_it() {
    let state = LinkState::Down;
    let copied = state;
    assert_eq!(state, copied);
}
