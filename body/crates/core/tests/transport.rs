use std::cmp::Reverse;
use std::sync::{Mutex, MutexGuard, PoisonError};

use body_contract::transport::{Calls, Held, TransportSubject, run};
use body_core::{
    AttachedImage, BrainTransport, ConfirmDecision, DueReminder, RpcHealth, SessionMessage,
    SessionSummary, TransportError, TurnEvent,
};
use futures_core::Stream;
use tokio_stream::StreamExt;

/// A fake brain in memory: it answers from what it holds and applies each write to it, or fails
/// every call with `failure`.
struct FakeTransport {
    held: Mutex<Held>,
    failure: Option<TransportError>,
}

impl FakeTransport {
    fn holding(held: &Held) -> Self {
        Self {
            held: Mutex::new(held.clone()),
            failure: None,
        }
    }

    fn idle() -> Self {
        Self::holding(&Held {
            health: RpcHealth {
                ready: true,
                detail: String::new(),
                notes: Vec::new(),
            },
            chats: Vec::new(),
            reminders: Vec::new(),
            preferences: Vec::new(),
        })
    }

    fn failing(error: TransportError) -> Self {
        Self {
            failure: Some(error),
            ..Self::idle()
        }
    }

    /// The held state, or the failure every call answers with.
    fn held(&self) -> Result<MutexGuard<'_, Held>, TransportError> {
        match &self.failure {
            None => Ok(self.held.lock().unwrap_or_else(PoisonError::into_inner)),
            Some(TransportError::Connection(message)) => {
                Err(TransportError::Connection(message.clone()))
            }
            Some(TransportError::Rpc { code, message }) => Err(TransportError::Rpc {
                code: code.clone(),
                message: message.clone(),
            }),
            Some(TransportError::Protocol(message)) => {
                Err(TransportError::Protocol(message.clone()))
            }
            Some(TransportError::Timeout { after }) => {
                Err(TransportError::Timeout { after: *after })
            }
        }
    }
}

impl BrainTransport for FakeTransport {
    async fn health(&self) -> Result<RpcHealth, TransportError> {
        Ok(self.held()?.health.clone())
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
        _images: Vec<AttachedImage>,
        decisions: impl Stream<Item = ConfirmDecision> + Send + 'static,
    ) -> impl Stream<Item = Result<TurnEvent, TransportError>> + Send {
        drop(decisions);
        tokio_stream::iter(vec![
            Ok(TurnEvent::Delta(format!("turn:{text}"))),
            Ok(TurnEvent::Complete {
                turn_id: String::from(session_id),
            }),
        ])
    }

    async fn list_sessions(&self, limit: i32) -> Result<Vec<SessionSummary>, TransportError> {
        let held = self.held()?;
        let limit = usize::try_from(limit).unwrap_or(0);
        let rows = held.chats.iter().take(limit);
        Ok(rows.map(|chat| chat.summary.clone()).collect())
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        let held = self.held()?;
        let mut asked = held
            .chats
            .iter()
            .filter(|chat| chat.summary.session_id == session_id);
        Ok(asked
            .next()
            .map(|chat| chat.messages.clone())
            .unwrap_or_default())
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        Ok(self.held()?.reminders.clone())
    }

    async fn ack_reminder(
        &self,
        reminder_id: &str,
        fired_at_unix_ms: i64,
    ) -> Result<bool, TransportError> {
        let mut held = self.held()?;
        let before = held.reminders.len();
        held.reminders.retain(|due| {
            due.reminder_id != reminder_id || due.fired_at_unix_ms != fired_at_unix_ms
        });
        Ok(held.reminders.len() < before)
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        let mut held = self.held()?;
        for chat in &mut held.chats {
            if chat.summary.session_id == session_id {
                chat.summary.title = String::from(title);
            }
        }
        Ok(())
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        let mut held = self.held()?;
        held.chats
            .retain(|chat| chat.summary.session_id != session_id);
        Ok(())
    }

    async fn set_session_hoisted(
        &self,
        session_id: &str,
        hoisted: bool,
    ) -> Result<(), TransportError> {
        let mut held = self.held()?;
        for chat in &mut held.chats {
            if chat.summary.session_id == session_id {
                chat.summary.hoisted = hoisted;
            }
        }
        held.chats.sort_by_key(|chat| {
            (
                !chat.summary.hoisted,
                Reverse(chat.summary.last_activity_unix_ms),
            )
        });
        Ok(())
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        Ok(self.held()?.preferences.clone())
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        let mut held = self.held()?;
        held.preferences.retain(|(held_key, _)| held_key != key);
        if !value.is_empty() {
            held.preferences
                .push((String::from(key), String::from(value)));
            held.preferences.sort();
        }
        Ok(())
    }
}

struct Fake;

impl TransportSubject for Fake {
    fn serving(&self, held: &Held) -> Box<dyn Calls> {
        Box::new(FakeTransport::holding(held))
    }

    fn refusing(&self) -> Box<dyn Calls> {
        Box::new(FakeTransport::failing(TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }))
    }

    fn unreachable(&self) -> Box<dyn Calls> {
        Box::new(FakeTransport::failing(TransportError::Connection(
            String::from("connection refused"),
        )))
    }
}

#[tokio::test]
async fn the_fake_meets_every_transport_check() {
    run(&Fake).await;
}

/// Drains a `converse` turn through a generic bound, collecting every item.
async fn converse_probe<T: BrainTransport>(
    transport: &T,
    session_id: &str,
    text: &str,
) -> Vec<Result<TurnEvent, TransportError>> {
    let decisions = tokio_stream::iter(vec![ConfirmDecision {
        confirm_id: String::from("c-1"),
        approved: true,
    }]);
    let stream = transport.converse(session_id, text, Vec::new(), decisions);
    tokio::pin!(stream);
    let mut events = Vec::new();
    while let Some(event) = stream.next().await {
        events.push(event);
    }
    events
}

#[tokio::test]
async fn fake_transport_streams_a_converse_turn_through_the_generic_bound() {
    let fake = FakeTransport::idle();
    let events = converse_probe(&fake, "sess-1", "hello").await;
    let events: Vec<TurnEvent> = events.into_iter().map(Result::unwrap).collect();
    assert_eq!(
        events,
        vec![
            TurnEvent::Delta(String::from("turn:hello")),
            TurnEvent::Complete {
                turn_id: String::from("sess-1"),
            },
        ],
    );
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
