use std::time::Duration;

use body_contract::FakeTransport;
use body_contract::transport::{Calls, Held, TransportSubject, run};
use body_core::{
    ConfirmDecision, DueReminder, RetryPlan, RetryingTransport, RpcHealth, SessionMessage,
    SessionSummary, Sleeper, TransportError, TurnEvent,
};

/// A `Sleeper` that waits for nothing, so a retried call ends at once.
struct NoWait;

impl Sleeper for NoWait {
    fn sleep(&self, _duration: Duration) -> impl Future<Output = ()> + Send {
        std::future::ready(())
    }

    async fn bounded<F>(&self, _deadline: Duration, call: F) -> Option<F::Output>
    where
        F: Future + Send,
        F::Output: Send,
    {
        Some(call.await)
    }
}

/// The fake alone, or the fake inside a `RetryingTransport` when `retrying` is set.
struct Fake {
    retrying: bool,
}

impl Fake {
    fn wrap(&self, fake: FakeTransport) -> Box<dyn Calls> {
        if self.retrying {
            Box::new(RetryingTransport::new(fake, NoWait, RetryPlan::default()))
        } else {
            Box::new(fake)
        }
    }
}

impl TransportSubject for Fake {
    fn serving(&self, held: &Held) -> Box<dyn Calls> {
        self.wrap(FakeTransport::holding(held))
    }

    fn refusing(&self) -> Box<dyn Calls> {
        self.wrap(FakeTransport::failing(TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }))
    }

    fn unreachable(&self) -> Box<dyn Calls> {
        self.wrap(FakeTransport::failing(TransportError::Connection(
            String::from("connection refused"),
        )))
    }
}

#[tokio::test]
async fn the_fake_meets_every_transport_check() {
    run(&Fake { retrying: false }).await;
}

#[tokio::test]
async fn retrying_over_the_fake_meets_every_transport_check() {
    run(&Fake { retrying: true }).await;
}

#[test]
fn turn_event_is_clone_eq_and_debug() {
    let delta = TurnEvent::Delta(String::from("hi"));
    assert_eq!(delta.clone(), delta);
    assert_ne!(delta, TurnEvent::Delta(String::from("bye")));
    let tool = TurnEvent::ToolActivity {
        tool_name: String::from("read_email"),
        summary: String::from("reading"),
    };
    let outcome = TurnEvent::ToolOutcome {
        tool_name: String::from("read_email"),
        ok: true,
    };
    assert_ne!(
        outcome,
        TurnEvent::ToolOutcome {
            tool_name: String::from("read_email"),
            ok: false,
        }
    );
    let status = TurnEvent::Status {
        state: String::from("model_loading"),
        detail: String::from("swapping"),
    };
    let complete = TurnEvent::Complete {
        turn_id: String::from("t-1"),
    };
    let failed = TurnEvent::Failed {
        code: String::from("overloaded"),
        message: String::from("busy"),
    };
    let confirm = TurnEvent::ConfirmRequest {
        confirm_id: String::from("c-1"),
        tool_name: String::from("send_email"),
        arguments_json: String::from("{\"to\":\"a@b\"}"),
        reason: String::from("outbound"),
    };
    assert_ne!(tool, status);
    assert_ne!(complete, failed);
    assert_eq!(confirm.clone(), confirm);
    assert_ne!(confirm, complete);
    for (event, name) in [
        (&delta, "Delta"),
        (&tool, "ToolActivity"),
        (&outcome, "ToolOutcome"),
        (&status, "Status"),
        (&complete, "Complete"),
        (&failed, "Failed"),
        (&confirm, "ConfirmRequest"),
    ] {
        assert!(format!("{event:?}").contains(name), "{event:?}");
    }
}

#[test]
fn confirm_decision_is_clone_eq_and_debug() {
    let approve = ConfirmDecision {
        confirm_id: String::from("c-1"),
        approved: true,
    };
    assert_eq!(approve.clone(), approve);
    let deny = ConfirmDecision {
        confirm_id: String::from("c-1"),
        approved: false,
    };
    let other_id = ConfirmDecision {
        confirm_id: String::from("c-2"),
        approved: true,
    };
    assert_ne!(approve, deny);
    assert_ne!(approve, other_id);
    let debug = format!("{approve:?}");
    assert!(debug.contains("ConfirmDecision"), "{debug}");
    assert!(debug.contains("c-1"), "{debug}");
    assert!(debug.contains("approved: true"), "{debug}");
}

#[test]
fn rpc_health_is_clone_eq_and_debug() {
    let ready = RpcHealth {
        ready: true,
        detail: String::from("cortex loaded"),
        notes: Vec::new(),
    };
    let cloned = ready.clone();
    assert_eq!(cloned, ready);
    let not_ready = RpcHealth {
        ready: false,
        detail: String::from("cortex loaded"),
        notes: Vec::new(),
    };
    let other_detail = RpcHealth {
        ready: true,
        detail: String::from("model loading"),
        notes: Vec::new(),
    };
    assert_ne!(ready, not_ready);
    assert_ne!(ready, other_detail);
    let debug = format!("{ready:?}");
    assert!(debug.contains("RpcHealth"), "{debug}");
    assert!(debug.contains("ready: true"), "{debug}");
    assert!(debug.contains("cortex loaded"), "{debug}");
}

#[test]
fn error_messages_are_descriptive() {
    let cases = [
        (
            TransportError::Connection(String::from("connection refused")),
            "cannot reach the brain: connection refused",
        ),
        (
            TransportError::Rpc {
                code: String::from("Unimplemented"),
                message: String::from("converse lands in a later slice"),
            },
            "brain rpc failed (Unimplemented): converse lands in a later slice",
        ),
        (
            TransportError::Protocol(String::from("no event set")),
            "malformed message from the brain: no event set",
        ),
    ];
    for (error, message) in cases {
        assert_eq!(error.to_string(), message);
    }
}

#[test]
fn error_is_a_std_error_without_a_source() {
    let error: &dyn std::error::Error = &TransportError::Connection(String::from("boom"));
    assert!(error.source().is_none());
}

#[test]
fn error_debug_output_names_the_variant() {
    let connection = TransportError::Connection(String::from("boom"));
    let rpc = TransportError::Rpc {
        code: String::from("Internal"),
        message: String::from("boom"),
    };
    let protocol = TransportError::Protocol(String::from("boom"));
    assert!(format!("{connection:?}").contains("Connection"));
    assert!(format!("{rpc:?}").contains("Rpc"));
    assert!(format!("{protocol:?}").contains("Protocol"));
}

#[test]
fn error_equality_compares_variant_and_payload() {
    assert_eq!(
        TransportError::Connection(String::from("a")),
        TransportError::Connection(String::from("a"))
    );
    assert_eq!(
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        },
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        }
    );
    assert_ne!(
        TransportError::Connection(String::from("a")),
        TransportError::Connection(String::from("b"))
    );
    assert_ne!(
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        },
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("a"),
        }
    );
    assert_ne!(
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        },
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("b"),
        }
    );
    assert_ne!(
        TransportError::Connection(String::from("a")),
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("a"),
        }
    );
}

#[test]
fn due_reminder_is_clone_eq_and_debug() {
    let reminder = DueReminder {
        reminder_id: String::from("r1"),
        text: String::from("call the vet"),
        fired_at_unix_ms: 1000,
        recurring: false,
        tainted: true,
        session_id: String::from("s1"),
    };
    assert_eq!(reminder.clone(), reminder);
    assert_ne!(
        reminder,
        DueReminder {
            tainted: false,
            ..reminder.clone()
        }
    );
    assert_ne!(
        reminder,
        DueReminder {
            fired_at_unix_ms: 1001,
            ..reminder.clone()
        }
    );
    let debug = format!("{reminder:?}");
    assert!(debug.contains("DueReminder"), "{debug}");
    assert!(debug.contains("call the vet"), "{debug}");
    assert!(debug.contains("tainted: true"), "{debug}");
}

#[test]
fn session_summary_and_message_are_clone_eq_and_debug() {
    let summary = SessionSummary {
        session_id: String::from("s1"),
        title: String::from("about cats"),
        preview: String::from("cats are great"),
        last_activity_unix_ms: 1000,
        hoisted: true,
    };
    assert_eq!(summary.clone(), summary);
    assert_ne!(
        summary,
        SessionSummary {
            session_id: String::from("s2"),
            ..summary.clone()
        }
    );
    assert_ne!(
        summary,
        SessionSummary {
            hoisted: false,
            ..summary.clone()
        }
    );
    let summary_debug = format!("{summary:?}");
    assert!(summary_debug.contains("SessionSummary"), "{summary_debug}");
    assert!(summary_debug.contains("about cats"), "{summary_debug}");
    assert!(summary_debug.contains("hoisted: true"), "{summary_debug}");

    let message = SessionMessage {
        role: String::from("user"),
        text: String::from("hi"),
        turn_id: String::from("t-1"),
        at_unix_ms: 7,
    };
    assert_eq!(message.clone(), message);
    assert_ne!(
        message,
        SessionMessage {
            text: String::from("bye"),
            ..message.clone()
        }
    );
    let message_debug = format!("{message:?}");
    assert!(message_debug.contains("SessionMessage"), "{message_debug}");
    assert!(message_debug.contains("user"), "{message_debug}");
}
