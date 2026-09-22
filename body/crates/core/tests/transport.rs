use body_core::{
    BrainTransport, ConfirmDecision, DueReminder, SeamHealth, SessionMessage, SessionSummary,
    TransportError, TurnEvent,
};
use futures_core::Stream;
use tokio_stream::StreamExt;

/// A scripted in-crate fake: the simplest possible `BrainTransport`.
struct FakeTransport {
    script: Result<SeamHealth, TransportError>,
}

impl BrainTransport for FakeTransport {
    async fn health(&self) -> Result<SeamHealth, TransportError> {
        match &self.script {
            Ok(health) => Ok(health.clone()),
            Err(TransportError::Connection(message)) => {
                Err(TransportError::Connection(message.clone()))
            }
            Err(TransportError::Rpc { code, message }) => Err(TransportError::Rpc {
                code: code.clone(),
                message: message.clone(),
            }),
            Err(TransportError::Protocol(message)) => {
                Err(TransportError::Protocol(message.clone()))
            }
            Err(TransportError::Timeout { after }) => {
                Err(TransportError::Timeout { after: *after })
            }
        }
    }

    fn converse(
        &self,
        session_id: &str,
        text: &str,
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
        Ok(vec![SessionSummary {
            session_id: String::from("s1"),
            title: format!("limit {limit}"),
            preview: String::from("hi"),
            last_activity_unix_ms: 42,
            hoisted: false,
        }])
    }

    async fn session_messages(
        &self,
        session_id: &str,
    ) -> Result<Vec<SessionMessage>, TransportError> {
        Ok(vec![SessionMessage {
            role: String::from("user"),
            text: String::from(session_id),
            turn_id: String::from("t"),
            at_unix_ms: 7,
        }])
    }

    async fn list_due_reminders(&self) -> Result<Vec<DueReminder>, TransportError> {
        Ok(vec![DueReminder {
            reminder_id: String::from("r1"),
            text: String::from("stand up"),
            fired_at_unix_ms: 9,
            recurring: true,
            tainted: false,
            session_id: String::from("s1"),
        }])
    }

    async fn ack_reminder(
        &self,
        reminder_id: &str,
        fired_at_unix_ms: i64,
    ) -> Result<bool, TransportError> {
        Ok(reminder_id == "r1" && fired_at_unix_ms == 9)
    }

    async fn rename_session(&self, session_id: &str, title: &str) -> Result<(), TransportError> {
        if session_id.is_empty() {
            return Err(TransportError::Rpc {
                code: String::from("Unavailable"),
                message: String::from("store down"),
            });
        }
        let _ = title;
        Ok(())
    }

    async fn delete_session(&self, session_id: &str) -> Result<(), TransportError> {
        if session_id.is_empty() {
            return Err(TransportError::Rpc {
                code: String::from("Unavailable"),
                message: String::from("store down"),
            });
        }
        Ok(())
    }

    async fn set_session_hoisted(
        &self,
        session_id: &str,
        hoisted: bool,
    ) -> Result<(), TransportError> {
        if session_id.is_empty() {
            return Err(TransportError::Rpc {
                code: String::from("Unavailable"),
                message: String::from("store down"),
            });
        }
        let _ = hoisted;
        Ok(())
    }

    async fn get_preferences(&self) -> Result<Vec<(String, String)>, TransportError> {
        Ok(vec![
            (String::from("overlay.mark"), String::from("foam")),
            (String::from("overlay.theme"), String::from("midnight")),
        ])
    }

    async fn set_preference(&self, key: &str, value: &str) -> Result<(), TransportError> {
        if key.is_empty() {
            return Err(TransportError::Rpc {
                code: String::from("Unavailable"),
                message: String::from("store down"),
            });
        }
        let _ = value;
        Ok(())
    }
}

/// Uses the trait as a generic bound, the way application code will.
async fn probe<T: BrainTransport>(transport: &T) -> Result<SeamHealth, TransportError> {
    transport.health().await
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
    let stream = transport.converse(session_id, text, decisions);
    tokio::pin!(stream);
    let mut events = Vec::new();
    while let Some(event) = stream.next().await {
        events.push(event);
    }
    events
}

/// Compile-time check that a `BrainTransport::health` future is `Send`.
fn assert_send<F: Future + Send>(future: F) -> F {
    future
}

#[tokio::test]
async fn fake_transport_reports_health_through_the_generic_bound() {
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::from("fake brain ready"),
        }),
    };
    let health = assert_send(probe(&fake)).await.unwrap();
    assert!(health.ready);
    assert_eq!(health.detail, "fake brain ready");
}

#[tokio::test]
async fn fake_transport_propagates_connection_errors() {
    let fake = FakeTransport {
        script: Err(TransportError::Connection(String::from(
            "connection refused",
        ))),
    };
    let error = probe(&fake).await.unwrap_err();
    assert_eq!(
        error,
        TransportError::Connection(String::from("connection refused"))
    );
}

#[tokio::test]
async fn fake_transport_propagates_rpc_errors() {
    let fake = FakeTransport {
        script: Err(TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("scripted failure"),
        }),
    };
    let error = probe(&fake).await.unwrap_err();
    assert_eq!(
        error,
        TransportError::Rpc {
            code: String::from("Internal"),
            message: String::from("scripted failure"),
        }
    );
}

#[tokio::test]
async fn fake_transport_streams_a_converse_turn_through_the_generic_bound() {
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::from("unused"),
        }),
    };
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
fn seam_health_is_clone_eq_and_debug() {
    let ready = SeamHealth {
        ready: true,
        detail: String::from("cortex loaded"),
    };
    let cloned = ready.clone();
    assert_eq!(cloned, ready);
    let not_ready = SeamHealth {
        ready: false,
        detail: String::from("cortex loaded"),
    };
    let other_detail = SeamHealth {
        ready: true,
        detail: String::from("model loading"),
    };
    assert_ne!(ready, not_ready);
    assert_ne!(ready, other_detail);
    let debug = format!("{ready:?}");
    assert!(debug.contains("SeamHealth"), "{debug}");
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
            "malformed seam message: no event set",
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

#[tokio::test]
async fn fake_transport_lists_sessions_through_the_generic_bound() {
    async fn probe<T: BrainTransport>(t: &T, limit: i32) -> Vec<SessionSummary> {
        t.list_sessions(limit).await.unwrap()
    }
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::new(),
        }),
    };
    let sessions = assert_send(probe(&fake, 3)).await;
    assert_eq!(sessions.len(), 1);
    assert_eq!(sessions[0].title, "limit 3");
    assert_eq!(sessions[0].last_activity_unix_ms, 42);
}

#[tokio::test]
async fn fake_transport_reads_session_messages_through_the_generic_bound() {
    async fn probe<T: BrainTransport>(t: &T, session_id: &str) -> Vec<SessionMessage> {
        t.session_messages(session_id).await.unwrap()
    }
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::new(),
        }),
    };
    let messages = assert_send(probe(&fake, "chat-7")).await;
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].role, "user");
    assert_eq!(messages[0].text, "chat-7");
}

#[tokio::test]
async fn fake_transport_pulls_and_acks_reminders_through_the_generic_bound() {
    async fn pull<T: BrainTransport>(t: &T) -> Vec<DueReminder> {
        t.list_due_reminders().await.unwrap()
    }
    async fn ack<T: BrainTransport>(t: &T, reminder: &DueReminder) -> bool {
        t.ack_reminder(&reminder.reminder_id, reminder.fired_at_unix_ms)
            .await
            .unwrap()
    }
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::new(),
        }),
    };
    let due = assert_send(pull(&fake)).await;
    assert_eq!(due.len(), 1);
    assert_eq!(due[0].text, "stand up");
    assert!(due[0].recurring);
    assert!(assert_send(ack(&fake, &due[0])).await);
    let gone = DueReminder {
        reminder_id: String::from("gone"),
        ..due[0].clone()
    };
    assert!(!ack(&fake, &gone).await);
    let earlier = DueReminder {
        fired_at_unix_ms: 8,
        ..due[0].clone()
    };
    assert!(!ack(&fake, &earlier).await);
}

#[tokio::test]
async fn fake_transport_renames_a_session_through_the_generic_bound() {
    async fn rename<T: BrainTransport>(
        t: &T,
        session_id: &str,
        title: &str,
    ) -> Result<(), TransportError> {
        t.rename_session(session_id, title).await
    }
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::new(),
        }),
    };
    assert!(
        assert_send(rename(&fake, "s1", "Everything about cats"))
            .await
            .is_ok()
    );
    assert!(rename(&fake, "s1", "").await.is_ok());
    assert_eq!(
        rename(&fake, "", "x").await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
}

#[tokio::test]
async fn fake_transport_deletes_a_session_through_the_generic_bound() {
    async fn delete<T: BrainTransport>(t: &T, session_id: &str) -> Result<(), TransportError> {
        t.delete_session(session_id).await
    }
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::new(),
        }),
    };
    assert!(assert_send(delete(&fake, "s1")).await.is_ok());
    assert_eq!(
        delete(&fake, "").await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        }
    );
}

#[tokio::test]
async fn fake_transport_sets_the_hoist_through_the_generic_bound() {
    async fn set_hoisted<T: BrainTransport>(
        t: &T,
        session_id: &str,
        hoisted: bool,
    ) -> Result<(), TransportError> {
        t.set_session_hoisted(session_id, hoisted).await
    }
    let fake = FakeTransport {
        script: Ok(SeamHealth {
            ready: true,
            detail: String::new(),
        }),
    };
    assert!(assert_send(set_hoisted(&fake, "s1", true)).await.is_ok());
    assert!(set_hoisted(&fake, "s1", false).await.is_ok());
    assert_eq!(
        set_hoisted(&fake, "", true).await.unwrap_err(),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
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
